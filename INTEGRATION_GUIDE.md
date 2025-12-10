# Integration Guide: MongoDB Intelligent Synchronization Pipeline

## 🎯 Purpose

This guide shows how to integrate the new intelligent synchronization system into your existing Web Novel scraping pipeline.

## 📋 Pre-Integration Checklist

- [ ] MongoDB installed and running
- [ ] `pymongo>=4.6.0` installed (`pip install pymongo`)
- [ ] Existing scraper outputs data in dictionary format
- [ ] You have a MongoDB connection string

## 🔄 Integration Steps

### Step 1: Review Your Current Data Flow

**Current System (Simple Approach):**
```
Scrape → JSON File → Manual Import to MongoDB
```

**New System (Intelligent Sync):**
```
Scrape → Intelligent Sync Pipeline → MongoDB (auto-deduplicated)
```

### Step 2: Add MongoDB Connection to Your Config

Update `src/config.py`:

```python
# Add these MongoDB settings
MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DATABASE = "webnovel_database"

# Optional: MongoDB settings
MONGODB_POOL_SIZE = 10
MONGODB_TIMEOUT = 5000
```

### Step 3: Integration Points

You have several options for integration:

#### Option A: Modify `etl_webnovel.py` (Recommended)

Add direct MongoDB sync at the end of the ETL process:

```python
# In etl_webnovel.py
from pymongo import MongoClient
from mongo_pipeline import MongoSyncPipeline
import src.config as config

class ETLWebNovel:
    def __init__(self):
        # ... existing init code ...
        
        # Add MongoDB connection
        self.mongo_client = MongoClient(config.MONGODB_URI)
        self.db = self.mongo_client[config.MONGODB_DATABASE]
        self.sync_pipeline = MongoSyncPipeline(self.db)
    
    def process_story(self, story_url):
        """Modified to include MongoDB sync."""
        try:
            # Existing scraping logic
            raw_data = self.scrape_story(story_url)
            transformed_data = self.transform_data(raw_data)
            
            # NEW: Sync to MongoDB
            result = self.sync_pipeline.sync_story_complete(
                scraped_data=transformed_data,
                website_id='wn_webnovel'  # or config.WEBSITE_ID
            )
            
            logger.info(f"✓ Story synced: {result['story_id']}")
            logger.info(f"  Chapters: {result['chapters']['inserted']} new")
            
            # Optional: Still save JSON for backup
            if config.SAVE_JSON_BACKUP:
                self.save_json(transformed_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing {story_url}: {e}")
            raise
```

#### Option B: Add Post-Processing Step

Keep your existing pipeline, add sync as a post-process:

```python
# In your existing workflow
def scrape_and_save(story_url):
    # Your existing scraping
    data = scrape_story(story_url)
    save_to_json(data)
    
    # NEW: Sync to MongoDB
    sync_to_mongodb(data)

def sync_to_mongodb(scraped_data):
    """New function to sync after scraping."""
    from pymongo import MongoClient
    from mongo_pipeline import MongoSyncPipeline
    
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    return pipeline.sync_story_complete(
        scraped_data,
        'wn_webnovel'
    )
```

#### Option C: Batch Process Existing JSON Files

Process your existing JSON files in `data/json/`:

```python
# Create: process_existing_json.py
import json
import os
from glob import glob
from pymongo import MongoClient
from mongo_pipeline import MongoSyncPipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_json_directory(json_dir, website_id):
    """Process all JSON files in a directory."""
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    json_files = glob(os.path.join(json_dir, '*.json'))
    logger.info(f"Found {len(json_files)} JSON files to process")
    
    results = []
    for json_file in json_files:
        try:
            logger.info(f"Processing: {os.path.basename(json_file)}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = pipeline.sync_story_complete(data, website_id)
            
            logger.info(f"  ✓ Story ID: {result['story_id']}")
            logger.info(f"  Chapters: {result['chapters']['inserted']} new, "
                       f"{result['chapters']['skipped']} existing")
            
            results.append({
                'file': json_file,
                'story_id': str(result['story_id']),
                'success': True
            })
            
        except Exception as e:
            logger.error(f"  ✗ Error: {e}")
            results.append({
                'file': json_file,
                'error': str(e),
                'success': False
            })
    
    # Summary
    successful = sum(1 for r in results if r['success'])
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing complete: {successful}/{len(results)} successful")
    
    return results

if __name__ == '__main__':
    # Process existing WebNovel JSON files
    process_json_directory('data/json/', 'wn_webnovel')
    
    # Process files ready for MongoDB
    process_json_directory('data/json/Read to push MongoDB/', 'wn_webnovel')
```

### Step 4: Data Format Verification

Ensure your scraped data matches the expected format:

```python
# Your existing scraper should output:
{
    'webStoryId': 'wn_12345...',        # ✓ You have this
    'storyName': 'Story Title',          # ✓ You have this
    'author': {                          # ✓ Verify structure
        'webUserId': 'user_id',
        'username': 'Author Name',
        'avatar': 'url'
    },
    'chapters': [                        # ✓ Verify structure
        {
            'webChapterId': 'ch_id',
            'chapterName': 'Chapter 1',
            'content': 'Full content...',
            'order': 1,
            'wordCount': 1000
        }
    ],
    'comments': [...],                   # Optional
    'reviews': [...]                     # Optional
}
```

### Step 5: Update Your Batch Scripts

Modify `batch_runner.py` or `single_book_runner.py`:

```python
# In batch_runner.py
from mongo_pipeline import MongoSyncPipeline
from pymongo import MongoClient

class BatchRunner:
    def __init__(self):
        # ... existing code ...
        
        # Add MongoDB pipeline
        self.mongo_client = MongoClient('mongodb://localhost:27017/')
        self.db = self.mongo_client['webnovel_database']
        self.sync_pipeline = MongoSyncPipeline(self.db)
    
    def process_book(self, book_url):
        """Process a single book with MongoDB sync."""
        try:
            # Your existing scraping
            data = self.scrape_book(book_url)
            
            # Save JSON (optional backup)
            self.save_json(data)
            
            # NEW: Sync to MongoDB
            result = self.sync_pipeline.sync_story_complete(
                data,
                'wn_webnovel'
            )
            
            logger.info(f"✓ Synced to MongoDB: {result['story_id']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error: {e}")
            # Continue with next book
```

## 🔧 Configuration Examples

### Minimal Configuration

```python
# src/config.py additions
MONGODB_URI = "mongodb://localhost:27017/"
MONGODB_DATABASE = "webnovel_database"
WEBSITE_ID = "wn_webnovel"  # Used for multi-source isolation
```

### Advanced Configuration

```python
# src/config.py additions
class MongoDBConfig:
    URI = "mongodb://localhost:27017/"
    DATABASE = "webnovel_database"
    
    # Connection pooling
    MAX_POOL_SIZE = 10
    MIN_POOL_SIZE = 1
    
    # Timeouts
    CONNECT_TIMEOUT_MS = 5000
    SERVER_SELECTION_TIMEOUT_MS = 5000
    
    # Website identifiers for different sources
    WEBSITE_IDS = {
        'webnovel': 'wn_webnovel',
        'royalroad': 'rr_royalroad',
        'wattpad': 'wp_wattpad',
        'scribblehub': 'sh_scribblehub'
    }
    
    # Sync options
    SAVE_JSON_BACKUP = True  # Keep JSON files as backup
    SYNC_BATCH_SIZE = 10     # Process N stories at a time
```

## 🧪 Testing Integration

### Test with One Story

```python
# test_integration.py
from pymongo import MongoClient
from mongo_pipeline import MongoSyncPipeline
import json

def test_single_story():
    """Test sync with one existing JSON file."""
    # Load existing JSON
    with open('data/json/wn_33921120008813005_019af837-d328-7e01-8650-128a66e51f8e_Samsara_Tower_Only_I_Know_the_Plot!.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Connect to MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['webnovel_test']  # Use test database
    pipeline = MongoSyncPipeline(db)
    
    # Sync
    result = pipeline.sync_story_complete(data, 'wn_webnovel')
    
    print(f"✓ Test successful!")
    print(f"  Story ID: {result['story_id']}")
    print(f"  Chapters: {result['chapters']['inserted']}")
    print(f"  Comments: {result['comments']['inserted']}")
    
    # Cleanup test database
    client.drop_database('webnovel_test')

if __name__ == '__main__':
    test_single_story()
```

Run: `python test_integration.py`

## 📊 Migration Strategy

### Phase 1: Parallel Operation (Recommended)
1. Keep existing JSON saving
2. Add MongoDB sync in parallel
3. Compare results
4. Build confidence

### Phase 2: Primary System
1. Make MongoDB primary storage
2. Keep JSON as backup
3. Monitor for issues

### Phase 3: Full Migration
1. Remove JSON saving (optional)
2. Use MongoDB exclusively
3. Archive old JSON files

## 🔍 Monitoring & Verification

### Check Sync Status

```python
def verify_sync_status(db):
    """Check what's been synced to MongoDB."""
    stats = {
        'stories': db.stories.count_documents({}),
        'chapters': db.chapters.count_documents({}),
        'comments': db.comments.count_documents({}),
        'reviews': db.reviews.count_documents({}),
        'users': db.users.count_documents({})
    }
    
    print("MongoDB Status:")
    for collection, count in stats.items():
        print(f"  {collection}: {count:,}")
    
    return stats
```

### Compare JSON vs MongoDB

```python
def compare_sources(json_file, story_id, db):
    """Compare JSON file with MongoDB data."""
    # Load JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    # Get MongoDB data
    story = db.stories.find_one({'_id': story_id})
    chapters = list(db.chapters.find({'storyId': story_id}))
    
    # Compare
    print(f"JSON chapters: {len(json_data.get('chapters', []))}")
    print(f"MongoDB chapters: {len(chapters)}")
    
    if len(json_data['chapters']) == len(chapters):
        print("✓ Chapter count matches!")
    else:
        print("⚠ Chapter count mismatch - investigate")
```

## ⚠️ Common Issues & Solutions

### Issue 1: "storyName is required"
**Solution:** Verify your scraper sets `storyName` field

### Issue 2: Duplicate stories appearing
**Solution:** Check that `author.username` is consistent

### Issue 3: Chapters not inserting
**Solution:** Ensure `webChapterId` and `order` are present

### Issue 4: Connection errors
**Solution:** Verify MongoDB is running: `mongosh` or check service

## 📈 Performance Optimization

### For Large Batches

```python
def batch_sync_optimized(json_files, batch_size=10):
    """Process files in batches with connection pooling."""
    from pymongo import MongoClient
    from mongo_pipeline import MongoSyncPipeline
    
    # Single connection for all
    client = MongoClient(
        'mongodb://localhost:27017/',
        maxPoolSize=50
    )
    db = client['webnovel_database']
    pipeline = MongoSyncPipeline(db)
    
    for i in range(0, len(json_files), batch_size):
        batch = json_files[i:i+batch_size]
        
        for json_file in batch:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                pipeline.sync_story_complete(data, 'wn_webnovel')
                
            except Exception as e:
                logger.error(f"Error in {json_file}: {e}")
                continue
        
        logger.info(f"Completed batch {i//batch_size + 1}")
    
    client.close()
```

## 🎓 Next Steps

1. **Test with sample data**: Use `test_integration.py`
2. **Process existing JSON**: Use `process_existing_json.py`
3. **Integrate with main scraper**: Modify `etl_webnovel.py`
4. **Monitor results**: Use verification scripts
5. **Scale up**: Process all stories in batches

## 📚 Additional Resources

- `MONGO_PIPELINE_USAGE.md` - Detailed API documentation
- `example_mongo_pipeline.py` - Usage examples
- `test_mongo_pipeline.py` - Test suite
- `MONGO_PIPELINE_README.md` - Quick reference

---

**Need help?** Check the troubleshooting section in `MONGO_PIPELINE_USAGE.md`
