"""
Example usage of the MongoDB Intelligent Synchronization Pipeline.
This script demonstrates how to integrate the pipeline with your scraping workflow.
"""

from pymongo import MongoClient
from datetime import datetime
from mongo_pipeline import MongoSyncPipeline
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_webnovel_sync():
    """
    Example: Synchronize data scraped from WebNovel.
    """
    # Connect to MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    
    # Initialize pipeline
    pipeline = MongoSyncPipeline(db)
    
    # Example scraped data from WebNovel
    scraped_data = {
        'webStoryId': 'wn_12345678901234567',
        'storyName': 'My Awesome Novel',
        'description': 'An epic tale of adventure and magic...',
        'coverImage': 'https://example.com/cover.jpg',
        'status': 'ongoing',
        'categories': ['Fantasy', 'Adventure', 'Magic'],
        'tags': ['wizard', 'hero', 'dragon'],
        'views': 150000,
        'likes': 5000,
        'rating': 4.7,
        
        # Author information
        'author': {
            'webUserId': 'user_999',
            'username': 'EpicAuthor',
            'avatar': 'https://example.com/avatar.jpg'
        },
        
        # Chapters
        'chapters': [
            {
                'webChapterId': 'ch_001',
                'chapterName': 'The Beginning',
                'content': 'Once upon a time in a land far away... [full chapter content here]',
                'order': 1,
                'wordCount': 2500,
                'publishDate': datetime(2024, 1, 1),
                'unlockPrice': 0
            },
            {
                'webChapterId': 'ch_002',
                'chapterName': 'The Journey Begins',
                'content': 'The hero set out on his quest... [full chapter content here]',
                'order': 2,
                'wordCount': 2800,
                'publishDate': datetime(2024, 1, 2),
                'unlockPrice': 0
            },
            {
                'webChapterId': 'ch_003',
                'chapterName': 'First Battle',
                'content': 'Enemies appeared from the shadows... [full chapter content here]',
                'order': 3,
                'wordCount': 3200,
                'publishDate': datetime(2024, 1, 3),
                'unlockPrice': 5
            }
        ],
        
        # Comments
        'comments': [
            {
                'webCommentId': 'comment_001',
                'content': 'Great story! Can\'t wait for the next chapter!',
                'username': 'Reader123',
                'avatar': 'https://example.com/reader1.jpg',
                'likes': 45,
                'publishDate': datetime(2024, 1, 2, 10, 30)
            },
            {
                'webCommentId': 'comment_002',
                'content': 'The world-building is amazing!',
                'username': 'FantasyFan',
                'avatar': 'https://example.com/reader2.jpg',
                'likes': 32,
                'publishDate': datetime(2024, 1, 2, 15, 20)
            }
        ],
        
        # Reviews
        'reviews': [
            {
                'webReviewId': 'review_001',
                'content': 'One of the best fantasy novels I\'ve read. The magic system is well thought out.',
                'username': 'CriticPro',
                'avatar': 'https://example.com/critic.jpg',
                'rating': 5.0,
                'likes': 120,
                'publishDate': datetime(2024, 1, 5)
            }
        ]
    }
    
    # Perform complete synchronization
    logger.info("Starting synchronization for WebNovel story...")
    
    result = pipeline.sync_story_complete(
        scraped_data=scraped_data,
        website_id='wn_webnovel'
    )
    
    # Log results
    logger.info(f"Story ID: {result['story_id']}")
    logger.info(f"New story: {result['is_new_story']}")
    logger.info(f"Chapters - Inserted: {result['chapters']['inserted']}, "
                f"Skipped: {result['chapters']['skipped']}")
    logger.info(f"Comments - Inserted: {result['comments']['inserted']}, "
                f"Updated: {result['comments']['updated']}, "
                f"Soft deleted: {result['comments']['soft_deleted']}")
    logger.info(f"Reviews - Inserted: {result['reviews']['inserted']}, "
                f"Updated: {result['reviews']['updated']}, "
                f"Soft deleted: {result['reviews']['soft_deleted']}")
    
    return result


def example_incremental_update():
    """
    Example: Incremental update - adding new chapters to existing story.
    """
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    # Second scraping run - story already exists, but has new chapters
    updated_data = {
        'webStoryId': 'wn_12345678901234567',
        'storyName': 'My Awesome Novel',  # Same story
        'author': {
            'webUserId': 'user_999',
            'username': 'EpicAuthor'
        },
        'chapters': [
            # Old chapters (will be skipped)
            {'webChapterId': 'ch_001', 'chapterName': 'The Beginning', 
             'content': 'Once upon a time...', 'order': 1},
            {'webChapterId': 'ch_002', 'chapterName': 'The Journey Begins', 
             'content': 'The hero set out...', 'order': 2},
            
            # New chapter (will be inserted)
            {'webChapterId': 'ch_004', 'chapterName': 'The Plot Thickens', 
             'content': 'New developments emerged...', 'order': 4, 'wordCount': 3500}
        ]
    }
    
    logger.info("Running incremental update...")
    result = pipeline.sync_story_complete(updated_data, 'wn_webnovel')
    
    logger.info(f"Incremental update - New chapters: {result['chapters']['inserted']}")
    logger.info(f"Existing chapters skipped: {result['chapters']['skipped']}")


def example_multi_source():
    """
    Example: Syncing the same story from multiple sources.
    """
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    # Story from WebNovel
    webnovel_data = {
        'webStoryId': 'wn_12345',
        'storyName': 'Cross-Platform Novel',
        'author': {'webUserId': 'wn_author_1', 'username': 'AuthorName'},
        'chapters': [
            {'webChapterId': 'wn_ch_1', 'chapterName': 'Chapter 1', 
             'content': 'Content...', 'order': 1}
        ],
        'comments': [
            {'webCommentId': 'wn_comment_1', 'content': 'WebNovel comment', 
             'username': 'WNReader'}
        ]
    }
    
    # Same story from RoyalRoad
    royalroad_data = {
        'webStoryId': 'rr_54321',
        'storyName': 'Cross-Platform Novel',  # Same story name
        'author': {'webUserId': 'rr_author_1', 'username': 'AuthorName'},  # Same author
        'chapters': [
            {'webChapterId': 'rr_ch_1', 'chapterName': 'Chapter 1', 
             'content': 'Content...', 'order': 1}  # Same chapter
        ],
        'comments': [
            {'webCommentId': 'rr_comment_1', 'content': 'RoyalRoad comment', 
             'username': 'RRReader'}
        ]
    }
    
    # Sync from WebNovel
    logger.info("Syncing from WebNovel...")
    result_wn = pipeline.sync_story_complete(webnovel_data, 'wn_webnovel')
    
    # Sync from RoyalRoad - will recognize as same story
    logger.info("Syncing from RoyalRoad...")
    result_rr = pipeline.sync_story_complete(royalroad_data, 'rr_royalroad')
    
    # Both should have same story_id (deduplication worked!)
    logger.info(f"WebNovel story ID: {result_wn['story_id']}")
    logger.info(f"RoyalRoad story ID: {result_rr['story_id']}")
    logger.info(f"Same story detected: {result_wn['story_id'] == result_rr['story_id']}")
    
    # Comments are separate (scoped by websiteId)
    logger.info(f"WebNovel comments: {result_wn['comments']['inserted']}")
    logger.info(f"RoyalRoad comments: {result_rr['comments']['inserted']}")


def example_soft_delete():
    """
    Example: Demonstrating soft delete for removed comments/reviews.
    """
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    # First scraping - 3 comments
    initial_data = {
        'webStoryId': 'wn_softdelete_test',
        'storyName': 'Soft Delete Test Novel',
        'author': {'webUserId': 'user_test', 'username': 'TestAuthor'},
        'chapters': [
            {'webChapterId': 'ch_1', 'chapterName': 'Ch 1', 
             'content': 'Content...', 'order': 1}
        ],
        'comments': [
            {'webCommentId': 'comment_1', 'content': 'First comment', 'username': 'User1'},
            {'webCommentId': 'comment_2', 'content': 'Second comment', 'username': 'User2'},
            {'webCommentId': 'comment_3', 'content': 'Third comment', 'username': 'User3'}
        ]
    }
    
    logger.info("Initial sync with 3 comments...")
    result1 = pipeline.sync_story_complete(initial_data, 'wn_test')
    logger.info(f"Inserted: {result1['comments']['inserted']} comments")
    
    # Second scraping - comment_2 was deleted on the website
    updated_data = {
        'webStoryId': 'wn_softdelete_test',
        'storyName': 'Soft Delete Test Novel',
        'author': {'webUserId': 'user_test', 'username': 'TestAuthor'},
        'chapters': [
            {'webChapterId': 'ch_1', 'chapterName': 'Ch 1', 
             'content': 'Content...', 'order': 1}
        ],
        'comments': [
            {'webCommentId': 'comment_1', 'content': 'First comment (updated)', 'username': 'User1'},
            # comment_2 is missing (deleted on website)
            {'webCommentId': 'comment_3', 'content': 'Third comment', 'username': 'User3'}
        ]
    }
    
    logger.info("Second sync - comment_2 removed...")
    result2 = pipeline.sync_story_complete(updated_data, 'wn_test')
    logger.info(f"Updated: {result2['comments']['updated']} comments")
    logger.info(f"Soft deleted: {result2['comments']['soft_deleted']} comments")
    
    # Verify soft delete
    story_id = result1['story_id']
    deleted_comment = db.comments.find_one({'webCommentId': 'comment_2'})
    logger.info(f"Comment 2 isDeleted: {deleted_comment.get('isDeleted', False)}")


def example_integration_with_existing_scraper():
    """
    Example: How to integrate with your existing scraper code.
    """
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    # Simulate your existing scraper output
    # (This would come from your scraper_engine.py or similar)
    def scrape_story(story_url):
        """Your existing scraper function."""
        # ... scraping logic ...
        return {
            'webStoryId': 'scraped_id',
            'storyName': 'Scraped Story',
            'author': {'webUserId': 'author_id', 'username': 'Author'},
            'chapters': [
                # ... scraped chapters
            ],
            'comments': [
                # ... scraped comments
            ]
        }
    
    # Integration point: After scraping, sync to MongoDB
    def scrape_and_sync(story_url, website_id):
        """Scrape a story and sync to MongoDB."""
        try:
            # Step 1: Scrape
            logger.info(f"Scraping {story_url}...")
            scraped_data = scrape_story(story_url)
            
            # Step 2: Sync to MongoDB
            logger.info("Syncing to MongoDB...")
            result = pipeline.sync_story_complete(scraped_data, website_id)
            
            # Step 3: Report
            logger.info(f"✓ Sync complete - Story ID: {result['story_id']}")
            logger.info(f"  Chapters: {result['chapters']['inserted']} new, "
                       f"{result['chapters']['skipped']} existing")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing {story_url}: {e}")
            raise
    
    # Use in batch processing
    story_urls = [
        'https://webnovel.com/story1',
        'https://webnovel.com/story2',
        'https://webnovel.com/story3'
    ]
    
    for url in story_urls:
        try:
            scrape_and_sync(url, 'wn_webnovel')
        except Exception as e:
            logger.error(f"Failed to process {url}, continuing...")
            continue


if __name__ == '__main__':
    print("MongoDB Intelligent Synchronization Pipeline - Examples\n")
    print("=" * 60)
    
    # Uncomment the example you want to run:
    
    # Example 1: Basic synchronization
    # example_webnovel_sync()
    
    # Example 2: Incremental updates
    # example_incremental_update()
    
    # Example 3: Multi-source deduplication
    # example_multi_source()
    
    # Example 4: Soft delete demonstration
    # example_soft_delete()
    
    # Example 5: Integration pattern
    # example_integration_with_existing_scraper()
    
    print("\n" + "=" * 60)
    print("Examples complete! Check the logs for details.")
    print("\nTo run an example, uncomment the function call in __main__")
