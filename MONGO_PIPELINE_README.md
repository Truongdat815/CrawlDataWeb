# MongoDB Intelligent Synchronization Pipeline

## 🎯 Overview

A production-ready Python module for intelligent MongoDB synchronization in web scraping pipelines. Replaces simple "wipe and replace" with sophisticated deduplication and incremental updates.

## ✨ Key Features

- **Smart Story Deduplication**: Prevents duplicates using metadata + SimHash
- **Incremental Chapter Updates**: Only adds new chapters, preserves existing data
- **Soft Delete for Social Data**: Comments/reviews marked as deleted, not removed
- **Multi-Source Safe**: Website-scoped operations prevent cross-source conflicts
- **Production Ready**: Comprehensive error handling, logging, and indexing

## 📦 Files Created

```
mongo_pipeline.py              # Main synchronization module (500+ lines)
utils.py                       # Helper functions (SimHash, normalization, etc.)
example_mongo_pipeline.py      # Usage examples and integration patterns
test_mongo_pipeline.py         # Comprehensive test suite (pytest)
MONGO_PIPELINE_USAGE.md        # Detailed documentation
```

## 🚀 Quick Start

### Installation

```bash
pip install pymongo
```

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
    'storyName': 'My Novel',
    'author': {'webUserId': 'user_1', 'username': 'Author'},
    'chapters': [
        {'webChapterId': 'ch_1', 'chapterName': 'Chapter 1', 
         'content': 'Content...', 'order': 1}
    ],
    'comments': [
        {'webCommentId': 'comment_1', 'content': 'Great!', 'username': 'Reader'}
    ],
    'reviews': [
        {'webReviewId': 'review_1', 'content': 'Excellent', 
         'username': 'Reviewer', 'rating': 5.0}
    ]
}

# Synchronize everything
result = pipeline.sync_story_complete(
    scraped_data=scraped_data,
    website_id='wn_webnovel'  # Your website identifier
)

print(f"Story ID: {result['story_id']}")
print(f"New story: {result['is_new_story']}")
print(f"Chapters inserted: {result['chapters']['inserted']}")
```

## 🔍 How It Works

### Story Deduplication

```
1. Metadata Check
   ├─ Query: storyName (case-insensitive) + userId (author)
   └─ If found → Return existing story

2. SimHash Fallback
   ├─ Calculate hash of first 500 chars of Chapter 1
   ├─ Query: storyHash
   └─ If found → Return existing story

3. Create New
   └─ Insert new story + author
```

### Chapter Synchronization

- Checks both `webChapterId` and `order` fields
- Only inserts chapters not already in database
- Perfect for incremental updates

### Social Data Sync (Comments/Reviews)

```
For each scraped item:
├─ If webId exists in DB
│  └─ Update content, set isDeleted=false
└─ If webId is new
   └─ Insert with isDeleted=false

For DB items not in scraped data:
└─ Set isDeleted=true (soft delete)
```

## 📊 MongoDB Schema

```javascript
// Stories
{
  _id: ObjectId,
  webStoryId: String,
  storyName: String,
  userId: ObjectId,           // Reference to users collection
  storyHash: String,          // SimHash for deduplication
  description: String,
  status: String,
  createdAt: Date,
  updatedAt: Date
}

// Chapters
{
  _id: ObjectId,
  storyId: ObjectId,          // Reference to stories collection
  webChapterId: String,
  chapterName: String,
  content: String,
  order: Number,
  createdAt: Date
}

// Comments & Reviews
{
  _id: ObjectId,
  webCommentId: String,       // or webReviewId
  storyId: ObjectId,
  websiteId: String,          // Multi-source isolation
  content: String,
  username: String,
  isDeleted: Boolean,         // Soft delete flag
  createdAt: Date,
  updatedAt: Date
}
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest test_mongo_pipeline.py -v

# Run specific test class
python -m pytest test_mongo_pipeline.py::TestStoryDeduplication -v

# Run with coverage
pip install pytest-cov
python -m pytest test_mongo_pipeline.py --cov=mongo_pipeline --cov-report=html
```

## 📚 Documentation

See `MONGO_PIPELINE_USAGE.md` for:
- Detailed API documentation
- Advanced usage patterns
- Multi-source synchronization
- Performance optimization
- Troubleshooting guide

## 🎓 Examples

Run the examples:

```bash
python example_mongo_pipeline.py
```

Available examples:
1. Basic WebNovel synchronization
2. Incremental chapter updates
3. Multi-source deduplication
4. Soft delete demonstration
5. Integration with existing scrapers

## 🔧 API Reference

### Main Class: `MongoSyncPipeline`

#### Methods

**`find_or_create_story(scraped_data) -> Tuple[ObjectId, bool]`**
- Finds existing story or creates new one
- Returns: `(story_id, is_new)`

**`sync_chapters(story_id, scraped_chapters) -> Dict[str, int]`**
- Synchronizes chapters incrementally
- Returns: `{'inserted': int, 'skipped': int, 'total': int}`

**`sync_social_data(collection_name, story_id, website_id, scraped_items) -> Dict[str, int]`**
- Synchronizes comments or reviews with soft delete
- Returns: `{'inserted': int, 'updated': int, 'soft_deleted': int, 'total_scraped': int}`

**`sync_story_complete(scraped_data, website_id) -> Dict[str, Any]`**
- Complete synchronization workflow
- Returns full sync results

### Standalone Functions

```python
# For backward compatibility, these are also available:
from mongo_pipeline import (
    find_or_create_story,
    sync_chapters,
    sync_social_data,
    sync_story_complete
)

# Usage (requires passing db parameter)
story_id, is_new = find_or_create_story(scraped_data, db)
```

## 🛠️ Integration with Existing Code

```python
# In your existing scraper
from mongo_pipeline import MongoSyncPipeline

def your_existing_scraper(url):
    # ... your scraping logic ...
    return scraped_data

def scrape_and_sync(url):
    # Scrape
    data = your_existing_scraper(url)
    
    # Sync to MongoDB
    pipeline = MongoSyncPipeline(db)
    result = pipeline.sync_story_complete(data, 'wn_webnovel')
    
    return result
```

## ⚠️ Important Notes

1. **Always provide `websiteId`**: Essential for multi-source safety
2. **First chapter content required**: For SimHash deduplication
3. **Consistent web IDs**: Don't change ID formats between runs
4. **Handle errors**: One failure shouldn't stop entire batch

## 🐛 Troubleshooting

### Duplicate stories still appearing
- Check story name extraction
- Verify author username consistency
- Enable DEBUG logging to see deduplication decisions

### Chapters not inserting
- Verify `webChapterId` and `order` are unique
- Check logs for duplicate detection

### Comments not updating
- Ensure `websiteId` matches exactly (case-sensitive)
- Verify `webCommentId` format consistency

## 📈 Performance Tips

- Indexes are created automatically
- Use batch operations for multiple stories
- Monitor MongoDB slow query log
- Consider connection pooling for high volume

## 🔒 Production Considerations

- ✅ Comprehensive error handling
- ✅ Detailed logging
- ✅ Automatic index management
- ✅ Transaction-safe operations
- ✅ Input sanitization (null bytes, etc.)
- ✅ Type hints for IDE support

## 📄 License

Part of Web Novel Scraping Pipeline project.

## 🤝 Contributing

This is a standalone module that can be integrated into your scraping pipeline. Modify as needed for your specific use case.

## 📞 Support

For detailed documentation, see `MONGO_PIPELINE_USAGE.md`.
For examples, see `example_mongo_pipeline.py`.
For tests, see `test_mongo_pipeline.py`.

---

**Built with ❤️ for intelligent web scraping pipelines**
