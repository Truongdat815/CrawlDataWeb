"""
Unit tests for MongoDB Intelligent Synchronization Pipeline.
Run with: python -m pytest test_mongo_pipeline.py -v
"""

import pytest
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from mongo_pipeline import MongoSyncPipeline
from utils import (
    normalize_text,
    calculate_simhash,
    calculate_story_hash,
    hamming_distance,
    is_similar_hash,
    sanitize_for_db,
    extract_first_chapter_content
)


# Test fixtures
@pytest.fixture
def mongodb_client():
    """Create MongoDB test client."""
    client = MongoClient('mongodb://localhost:27017/')
    yield client
    client.close()


@pytest.fixture
def test_db(mongodb_client):
    """Create test database."""
    db = mongodb_client['test_webnovel_pipeline']
    yield db
    # Cleanup after tests
    mongodb_client.drop_database('test_webnovel_pipeline')


@pytest.fixture
def pipeline(test_db):
    """Create pipeline instance."""
    return MongoSyncPipeline(test_db)


@pytest.fixture
def sample_story_data():
    """Sample scraped story data."""
    return {
        'webStoryId': 'test_story_001',
        'storyName': 'Test Novel',
        'description': 'A test novel for unit testing',
        'author': {
            'webUserId': 'test_user_001',
            'username': 'TestAuthor',
            'avatar': 'https://example.com/avatar.jpg'
        },
        'chapters': [
            {
                'webChapterId': 'test_ch_001',
                'chapterName': 'Chapter 1: The Beginning',
                'content': 'This is the first chapter content for testing deduplication. ' * 20,
                'order': 1,
                'wordCount': 100
            },
            {
                'webChapterId': 'test_ch_002',
                'chapterName': 'Chapter 2: The Journey',
                'content': 'This is the second chapter content.',
                'order': 2,
                'wordCount': 50
            }
        ],
        'comments': [
            {
                'webCommentId': 'test_comment_001',
                'content': 'Great story!',
                'username': 'Reader1',
                'likes': 10
            },
            {
                'webCommentId': 'test_comment_002',
                'content': 'Love it!',
                'username': 'Reader2',
                'likes': 5
            }
        ],
        'reviews': [
            {
                'webReviewId': 'test_review_001',
                'content': 'Excellent novel',
                'username': 'Reviewer1',
                'rating': 4.5,
                'likes': 20
            }
        ]
    }


# ============================================================================
# Utils Tests
# ============================================================================

class TestUtils:
    """Test utility functions."""
    
    def test_normalize_text(self):
        """Test text normalization."""
        assert normalize_text('Hello World!') == 'hello world'
        assert normalize_text('Test-Novel: Part 1') == 'testnovel part 1'
        assert normalize_text('  Multiple   Spaces  ') == 'multiple spaces'
        assert normalize_text('') == ''
        assert normalize_text(None) == ''
    
    def test_calculate_simhash(self):
        """Test SimHash calculation."""
        text1 = 'This is a test text for SimHash'
        text2 = 'This is a test text for SimHash'
        text3 = 'Completely different content here'
        
        hash1 = calculate_simhash(text1)
        hash2 = calculate_simhash(text2)
        hash3 = calculate_simhash(text3)
        
        # Same text should produce same hash
        assert hash1 == hash2
        
        # Different text should produce different hash
        assert hash1 != hash3
        
        # Hash should be hexadecimal string
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_hamming_distance(self):
        """Test Hamming distance calculation."""
        assert hamming_distance('1010', '1010') == 0
        assert hamming_distance('1010', '1011') == 1
        assert hamming_distance('0000', '1111') == 4
        
        with pytest.raises(ValueError):
            hamming_distance('10', '1010')
    
    def test_is_similar_hash(self):
        """Test hash similarity check."""
        assert is_similar_hash('1010', '1010', threshold=0) is True
        assert is_similar_hash('1010', '1011', threshold=1) is True
        assert is_similar_hash('1010', '1111', threshold=1) is False
    
    def test_sanitize_for_db(self):
        """Test database text sanitization."""
        assert sanitize_for_db('normal text') == 'normal text'
        assert sanitize_for_db('text\x00with\x00nulls') == 'textwithnulls'
        assert sanitize_for_db('long text', max_length=5) == 'long '
        assert sanitize_for_db(None) == ''
    
    def test_extract_first_chapter_content(self):
        """Test first chapter extraction."""
        data = {
            'chapters': [
                {'order': 2, 'content': 'Second chapter'},
                {'order': 1, 'content': 'First chapter'},
                {'order': 3, 'content': 'Third chapter'}
            ]
        }
        
        content = extract_first_chapter_content(data)
        assert content == 'First chapter'
        
        # Test with empty chapters
        assert extract_first_chapter_content({'chapters': []}) == ''
        assert extract_first_chapter_content({}) == ''


# ============================================================================
# Pipeline Tests
# ============================================================================

class TestStoryDeduplication:
    """Test story deduplication logic."""
    
    def test_create_new_story(self, pipeline, sample_story_data):
        """Test creating a new story."""
        story_id, is_new = pipeline.find_or_create_story(sample_story_data)
        
        assert is_new is True
        assert isinstance(story_id, ObjectId)
        
        # Verify story in database
        story = pipeline.stories_col.find_one({'_id': story_id})
        assert story is not None
        assert story['storyName'] == 'Test Novel'
        assert 'storyHash' in story
    
    def test_deduplicate_by_metadata(self, pipeline, sample_story_data):
        """Test deduplication by story name and author."""
        # Create first time
        story_id_1, is_new_1 = pipeline.find_or_create_story(sample_story_data)
        assert is_new_1 is True
        
        # Try to create again (should find existing)
        story_id_2, is_new_2 = pipeline.find_or_create_story(sample_story_data)
        assert is_new_2 is False
        assert story_id_1 == story_id_2
    
    def test_deduplicate_by_simhash(self, pipeline, sample_story_data):
        """Test deduplication by SimHash."""
        # Create first story
        story_id_1, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Create different story with same content (different metadata)
        different_metadata = sample_story_data.copy()
        different_metadata['storyName'] = 'Different Title'
        different_metadata['webStoryId'] = 'different_id'
        different_metadata['author'] = {
            'webUserId': 'different_user',
            'username': 'DifferentAuthor'
        }
        # Keep same chapter content for SimHash matching
        
        story_id_2, is_new_2 = pipeline.find_or_create_story(different_metadata)
        
        # Should recognize as same story by SimHash
        assert is_new_2 is False
        assert story_id_1 == story_id_2
    
    def test_create_different_story(self, pipeline, sample_story_data):
        """Test creating genuinely different story."""
        # Create first story
        story_id_1, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Create completely different story
        different_story = {
            'webStoryId': 'different_story',
            'storyName': 'Completely Different Novel',
            'author': {
                'webUserId': 'another_user',
                'username': 'AnotherAuthor'
            },
            'chapters': [
                {
                    'webChapterId': 'diff_ch_001',
                    'chapterName': 'Different Chapter',
                    'content': 'Completely different content that should not match.',
                    'order': 1
                }
            ]
        }
        
        story_id_2, is_new_2 = pipeline.find_or_create_story(different_story)
        
        assert is_new_2 is True
        assert story_id_1 != story_id_2


class TestChapterSync:
    """Test chapter synchronization."""
    
    def test_insert_new_chapters(self, pipeline, sample_story_data):
        """Test inserting new chapters."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        result = pipeline.sync_chapters(story_id, sample_story_data['chapters'])
        
        assert result['inserted'] == 2
        assert result['skipped'] == 0
        assert result['total'] == 2
        
        # Verify in database
        chapters = list(pipeline.chapters_col.find({'storyId': story_id}))
        assert len(chapters) == 2
    
    def test_skip_existing_chapters(self, pipeline, sample_story_data):
        """Test skipping existing chapters."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Insert first time
        pipeline.sync_chapters(story_id, sample_story_data['chapters'])
        
        # Insert again (should skip)
        result = pipeline.sync_chapters(story_id, sample_story_data['chapters'])
        
        assert result['inserted'] == 0
        assert result['skipped'] == 2
        
        # Should still have only 2 chapters
        chapters = list(pipeline.chapters_col.find({'storyId': story_id}))
        assert len(chapters) == 2
    
    def test_incremental_chapter_update(self, pipeline, sample_story_data):
        """Test adding new chapters to existing story."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Insert first 2 chapters
        pipeline.sync_chapters(story_id, sample_story_data['chapters'])
        
        # Add a new chapter
        new_chapters = sample_story_data['chapters'] + [
            {
                'webChapterId': 'test_ch_003',
                'chapterName': 'Chapter 3: New Addition',
                'content': 'This is a new chapter.',
                'order': 3,
                'wordCount': 75
            }
        ]
        
        result = pipeline.sync_chapters(story_id, new_chapters)
        
        assert result['inserted'] == 1
        assert result['skipped'] == 2
        
        # Should now have 3 chapters
        chapters = list(pipeline.chapters_col.find({'storyId': story_id}))
        assert len(chapters) == 3


class TestSocialDataSync:
    """Test social data synchronization."""
    
    def test_insert_new_comments(self, pipeline, sample_story_data):
        """Test inserting new comments."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        result = pipeline.sync_social_data(
            'comments',
            story_id,
            'test_website',
            sample_story_data['comments']
        )
        
        assert result['inserted'] == 2
        assert result['updated'] == 0
        assert result['soft_deleted'] == 0
    
    def test_update_existing_comments(self, pipeline, sample_story_data):
        """Test updating existing comments."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Insert first time
        pipeline.sync_social_data(
            'comments',
            story_id,
            'test_website',
            sample_story_data['comments']
        )
        
        # Update comment content
        updated_comments = [
            {
                'webCommentId': 'test_comment_001',
                'content': 'Updated comment content!',
                'username': 'Reader1',
                'likes': 15  # Increased likes
            },
            {
                'webCommentId': 'test_comment_002',
                'content': 'Love it!',
                'username': 'Reader2',
                'likes': 5
            }
        ]
        
        result = pipeline.sync_social_data(
            'comments',
            story_id,
            'test_website',
            updated_comments
        )
        
        assert result['inserted'] == 0
        assert result['updated'] == 2
        assert result['soft_deleted'] == 0
        
        # Verify update
        comment = pipeline.comments_col.find_one({'webCommentId': 'test_comment_001'})
        assert comment['content'] == 'Updated comment content!'
        assert comment['likes'] == 15
    
    def test_soft_delete_comments(self, pipeline, sample_story_data):
        """Test soft deleting removed comments."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Insert 2 comments
        pipeline.sync_social_data(
            'comments',
            story_id,
            'test_website',
            sample_story_data['comments']
        )
        
        # Sync with only 1 comment (second one removed)
        reduced_comments = [sample_story_data['comments'][0]]
        
        result = pipeline.sync_social_data(
            'comments',
            story_id,
            'test_website',
            reduced_comments
        )
        
        assert result['soft_deleted'] == 1
        
        # Verify soft delete
        deleted_comment = pipeline.comments_col.find_one(
            {'webCommentId': 'test_comment_002'}
        )
        assert deleted_comment['isDeleted'] is True
        
        # First comment should not be deleted
        active_comment = pipeline.comments_col.find_one(
            {'webCommentId': 'test_comment_001'}
        )
        assert active_comment['isDeleted'] is False
    
    def test_website_id_isolation(self, pipeline, sample_story_data):
        """Test that websiteId properly isolates data."""
        story_id, _ = pipeline.find_or_create_story(sample_story_data)
        
        # Insert comments for website A
        pipeline.sync_social_data(
            'comments',
            story_id,
            'website_a',
            sample_story_data['comments']
        )
        
        # Insert different comments for website B
        website_b_comments = [
            {
                'webCommentId': 'website_b_comment_001',
                'content': 'Comment from website B',
                'username': 'ReaderB'
            }
        ]
        
        pipeline.sync_social_data(
            'comments',
            story_id,
            'website_b',
            website_b_comments
        )
        
        # Should have 3 total comments (2 from A, 1 from B)
        total_comments = pipeline.comments_col.count_documents({'storyId': story_id})
        assert total_comments == 3
        
        # Verify isolation: updating website A shouldn't affect website B
        pipeline.sync_social_data('comments', story_id, 'website_a', [])
        
        # Website A comments should be soft deleted
        a_comments = list(pipeline.comments_col.find({
            'storyId': story_id,
            'websiteId': 'website_a'
        }))
        assert all(c['isDeleted'] for c in a_comments)
        
        # Website B comment should still be active
        b_comment = pipeline.comments_col.find_one({
            'storyId': story_id,
            'websiteId': 'website_b'
        })
        assert b_comment['isDeleted'] is False


class TestCompleteSync:
    """Test complete synchronization workflow."""
    
    def test_sync_story_complete(self, pipeline, sample_story_data):
        """Test complete story synchronization."""
        result = pipeline.sync_story_complete(
            sample_story_data,
            'test_website'
        )
        
        assert 'story_id' in result
        assert result['is_new_story'] is True
        assert result['chapters']['inserted'] == 2
        assert result['comments']['inserted'] == 2
        assert result['reviews']['inserted'] == 1
        
        # Verify all data in database
        story_id = result['story_id']
        
        story = pipeline.stories_col.find_one({'_id': story_id})
        assert story is not None
        
        chapters = list(pipeline.chapters_col.find({'storyId': story_id}))
        assert len(chapters) == 2
        
        comments = list(pipeline.comments_col.find({'storyId': story_id}))
        assert len(comments) == 2
        
        reviews = list(pipeline.reviews_col.find({'storyId': story_id}))
        assert len(reviews) == 1
    
    def test_multiple_sync_runs(self, pipeline, sample_story_data):
        """Test multiple synchronization runs."""
        # First sync
        result1 = pipeline.sync_story_complete(sample_story_data, 'test_website')
        story_id_1 = result1['story_id']
        
        # Second sync (should deduplicate)
        result2 = pipeline.sync_story_complete(sample_story_data, 'test_website')
        story_id_2 = result2['story_id']
        
        assert story_id_1 == story_id_2
        assert result2['is_new_story'] is False
        assert result2['chapters']['inserted'] == 0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
