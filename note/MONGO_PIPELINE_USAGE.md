# MongoDB Intelligent Synchronization Pipeline

## Overview

This intelligent synchronization system replaces the simple "wipe and replace" approach with sophisticated deduplication and incremental updates. It's designed for multi-source web scraping pipelines that need to prevent duplicate stories and efficiently manage updates.

## Features

### ✨ Core Capabilities

1. **Intelligent Story Deduplication**
   - Primary: Metadata matching (story name + author)
   - Fallback: SimHash-based content fingerprinting
   - Prevents duplicate stories from multiple sources

2. **Incremental Chapter Updates**
   - Only inserts new chapters
   - Preserves existing chapter data
   - Efficient for ongoing story updates

3. **Social Data Soft Delete**
   - Scoped by websiteId (multi-source safe)
   - Updates existing comments/reviews
   - Soft deletes missing items (isDeleted flag)

4. **Production-Ready**
   - Comprehensive error handling
   - Detailed logging
   - Automatic index management
   - Transaction-safe operations

## Installation

```bash
pip install pymongo
```

## Quick Start

### Basic Usage

```python
from pymongo import MongoClient
from mongo_pipeline import MongoSyncPipeline

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['your_database']

# Initialize pipeline
pipeline = MongoSyncPipeline(db)

# Your scraped data
scraped_data = {
    'webStoryId': 'wn_12345',
    'storyName': 'Example Novel',
    'author': {
        'webUserId': 'user_123',
        'username': 'AuthorName',
        'avatar': 'https://...'
    },
    'description': 'Story description...',
    'chapters': [
        {
            'webChapterId': 'ch_1',
            'chapterName': 'Chapter 1',
            'content': 'Chapter content...',
            'order': 1
        },
        # ... more chapters
    ],
    'comments': [
        {
            'webCommentId': 'comment_1',
            'content': 'Great story!',
            'username': 'Reader1',
            'likes': 10
        },
        # ... more comments
    ],
    'reviews': [
        {
            'webReviewId': 'review_1',
            'content': 'Excellent plot',
            'username': 'Reviewer1',
            'rating': 4.5
        },
        # ... more reviews
    ]
}

# Perform complete synchronization
result = pipeline.sync_story_complete(
    scraped_data=scraped_data,
    website_id='wn_webnovel'  # Your website identifier
)

print(f"Story ID: {result['story_id']}")
print(f"New story: {result['is_new_story']}")
print(f"Chapters inserted: {result['chapters']['inserted']}")
print(f"Comments updated: {result['comments']['updated']}")
```

### Individual Operations

#### 1. Story Deduplication Only

```python
# Find or create story (returns story_id and whether it's new)
story_id, is_new = pipeline.find_or_create_story(scraped_data)

if is_new:
    print(f"Created new story: {story_id}")
else:
    print(f"Found existing story: {story_id}")
```

#### 2. Chapter Synchronization Only

```python
from bson import ObjectId

story_id = ObjectId('...')  # Your existing story ID

chapters_result = pipeline.sync_chapters(
    story_id=story_id,
    scraped_chapters=scraped_data['chapters']
)

print(f"Inserted: {chapters_result['inserted']}")
print(f"Skipped (existing): {chapters_result['skipped']}")
```

#### 3. Social Data Sync Only

```python
# Sync comments
comments_result = pipeline.sync_social_data(
    collection_name='comments',
    story_id=story_id,
    website_id='wn_webnovel',
    scraped_items=scraped_data['comments']
)

# Sync reviews
reviews_result = pipeline.sync_social_data(
    collection_name='reviews',
    story_id=story_id,
    website_id='wn_webnovel',
    scraped_items=scraped_data['reviews']
)

print(f"Comments - Inserted: {comments_result['inserted']}, "
      f"Updated: {comments_result['updated']}, "
      f"Soft deleted: {comments_result['soft_deleted']}")
```

## Data Structure Requirements

### Scraped Data Format

```python
scraped_data = {
    # Story fields (required)
    'webStoryId': 'unique_story_id',
    'storyName': 'Story Title',
    
    # Author info (required)
    'author': {
        'webUserId': 'unique_user_id',
        'username': 'Author Name',
        'avatar': 'https://avatar-url.com/image.jpg'
    },
    
    # Story metadata (optional but recommended)
    'description': 'Story description',
    'coverImage': 'https://cover-url.com/image.jpg',
    'status': 'ongoing',  # or 'completed'
    'categories': ['Fantasy', 'Adventure'],
    'tags': ['magic', 'hero'],
    'views': 1000,
    'likes': 500,
    'rating': 4.5,
    
    # Chapters (optional)
    'chapters': [
        {
            'webChapterId': 'unique_chapter_id',
            'chapterName': 'Chapter Title',
            'content': 'Chapter content text...',
            'order': 1,  # Chapter sequence number
            'wordCount': 2000,
            'publishDate': datetime(...),
            'unlockPrice': 0  # For premium chapters
        }
    ],
    
    # Comments (optional)
    'comments': [
        {
            'webCommentId': 'unique_comment_id',
            'content': 'Comment text',
            'username': 'Commenter Name',
            'avatar': 'https://...',
            'likes': 10,
            'publishDate': datetime(...),
            'chapterId': ObjectId('...')  # Optional: specific chapter
        }
    ],
    
    # Reviews (optional)
    'reviews': [
        {
            'webReviewId': 'unique_review_id',
            'content': 'Review text',
            'username': 'Reviewer Name',
            'avatar': 'https://...',
            'rating': 4.5,
            'likes': 20,
            'publishDate': datetime(...)
        }
    ]
}
```

## How Deduplication Works

### 1. Story Deduplication Strategy

```
Step 1: Metadata Check
├─ Query: storyName (case-insensitive) + userId (author)
└─ If found → Return existing story

Step 2: SimHash Fallback
├─ Extract first 500 chars of Chapter 1
├─ Calculate SimHash
├─ Query: storyHash
└─ If found → Return existing story

Step 3: Create New
└─ Insert new story + author
```

### 2. Chapter Deduplication

- Checks both `webChapterId` and `order` fields
- Skips chapters that already exist
- Only inserts genuinely new chapters

### 3. Social Data Handling

```
For each scraped item:
├─ If webId exists in DB
│  └─ Update content, set isDeleted=false
└─ If webId is new
   └─ Insert with isDeleted=false

For DB items not in scraped data:
└─ Set isDeleted=true (soft delete)
```

## Multi-Source Safety

The pipeline is designed for scraping from multiple sources:

```python
# WebNovel scraper
pipeline.sync_story_complete(webnovel_data, website_id='wn_webnovel')

# RoyalRoad scraper
pipeline.sync_story_complete(royalroad_data, website_id='rr_royalroad')

# Comments/reviews are scoped by websiteId
# No interference between sources!
```

## Performance Optimization

### Automatic Indexes

The pipeline automatically creates indexes on:
- `stories`: `storyHash`, `storyName + userId`, `webStoryId`
- `chapters`: `storyId + order`, `webChapterId`
- `users`: `webUserId`, `username`
- `comments`: `webCommentId + websiteId`, `storyId + websiteId`
- `reviews`: `webReviewId + websiteId`, `storyId + websiteId`

### Batch Operations

For bulk operations, use the pipeline in a loop:

```python
# Process multiple stories
for story_data in scraped_stories:
    result = pipeline.sync_story_complete(story_data, website_id)
    print(f"Processed: {result['story_id']}")
```

## Error Handling

The pipeline includes comprehensive error handling:

```python
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

try:
    result = pipeline.sync_story_complete(scraped_data, website_id)
except ValueError as e:
    print(f"Data validation error: {e}")
except Exception as e:
    print(f"Sync error: {e}")
    # Continue with next story...
```

## Utility Functions

### SimHash Calculation

```python
from utils import calculate_simhash, hamming_distance, is_similar_hash

# Calculate hash
hash1 = calculate_simhash("Some text content")
hash2 = calculate_simhash("Similar text content")

# Check similarity
distance = hamming_distance(hash1, hash2)
similar = is_similar_hash(hash1, hash2, threshold=3)
```

### Text Normalization

```python
from utils import normalize_text

# Normalize for comparison
normalized = normalize_text("Story Title: Part 1!")
# Result: "story title part 1"
```

## Migration from Old System

If you have existing data with the "wipe and replace" approach:

```python
# Option 1: Keep existing system, just use for new data
# Old stories remain as-is, new stories use smart deduplication

# Option 2: Migrate existing data
# 1. Calculate storyHash for existing stories
from utils import calculate_story_hash

for story in db.stories.find({'storyHash': {'$exists': False}}):
    first_chapter = db.chapters.find_one(
        {'storyId': story['_id']},
        sort=[('order', 1)]
    )
    if first_chapter:
        story_hash = calculate_story_hash(first_chapter['content'])
        db.stories.update_one(
            {'_id': story['_id']},
            {'$set': {'storyHash': story_hash}}
        )
```

## Testing

```python
# Test with sample data
test_data = {
    'webStoryId': 'test_001',
    'storyName': 'Test Novel',
    'author': {'webUserId': 'test_user', 'username': 'TestAuthor'},
    'chapters': [
        {'webChapterId': 'ch_1', 'chapterName': 'Ch 1', 'content': 'Content', 'order': 1}
    ]
}

# First run - should create new story
result1 = pipeline.sync_story_complete(test_data, 'test_website')
assert result1['is_new_story'] == True

# Second run - should find existing story
result2 = pipeline.sync_story_complete(test_data, 'test_website')
assert result2['is_new_story'] == False
assert result2['story_id'] == result1['story_id']
```

## Troubleshooting

### Issue: Duplicate stories still appearing

**Solution**: Check that story names and author usernames are being extracted correctly. Use logging to debug:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Issue: Chapters not being inserted

**Solution**: Verify that `webChapterId` and `order` are unique. Check logs for duplicate detection.

### Issue: Comments/reviews not updating

**Solution**: Ensure `websiteId` matches exactly between scraping runs. It's case-sensitive.

## Best Practices

1. **Always provide websiteId**: This ensures multi-source safety
2. **Use consistent webIds**: Don't change ID formats between scraping runs
3. **Include first chapter content**: Required for SimHash deduplication
4. **Handle errors gracefully**: One failed story shouldn't stop the batch
5. **Monitor logs**: Use logging to track deduplication decisions

## License

This code is provided as part of the Web Novel Scraping Pipeline project.
