"""
Batch processor for syncing JSON to MongoDB (Strict Schema Adapter).
"""
import json
import os
import sys
import logging
from glob import glob
from pymongo import MongoClient
# Import class mới
from mongo_pipeline import StorySyncPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # SETUP MẶC ĐỊNH
    DEFAULT_DIR = 'data/json_final'
    DEFAULT_WEBSITE_ID = 'wn_019b3870-1234-7567-89ab-cdef01234567'
    
    # Auto-detect arguments
    target_dir = DEFAULT_DIR
    website_id = DEFAULT_WEBSITE_ID
    
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
        
    if not os.path.exists(target_dir):
        print(f"❌ Folder not found: {target_dir}")
        return

    # INIT PIPELINE
    mongo_uri = "mongodb://localhost:27017/"
    try:
        pipeline = StorySyncPipeline(mongo_uri, "webnovel_database")
        print(f"✅ Connected to MongoDB. Pipeline ready.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    # PROCESS FILES
    json_files = glob(os.path.join(target_dir, "*.json"))
    print(f"📦 Found {len(json_files)} files to sync...")

    for f_path in json_files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # --- ADAPTER: Convert List-based JSON to Object-based ---
            # File transform_data.py tạo ra json dạng {'stories': [...], 'chapters': [...]}
            # Pipeline cần input dạng phẳng {'storyName': ..., 'chapters': ...}
            
            flat_data = {}
            
            # 1. Extract Story Metadata
            if raw_data.get('stories'):
                story = raw_data['stories'][0]
                flat_data.update(story) # Lấy storyName, webStoryId...
            
            # 2. Extract Author
            if raw_data.get('users'):
                # Tìm user là tác giả (userId khớp với story.userId)
                author_id = flat_data.get('userId')
                for u in raw_data['users']:
                    if u['userId'] == author_id:
                        flat_data['author'] = u
                        break
            
            # 3. Extract Lists
            flat_data['chapters'] = raw_data.get('chapters', [])
            # Map content vào chapters
            if raw_data.get('chapterContents'):
                content_map = {c['chapterId']: c['content'] for c in raw_data['chapterContents']}
                for ch in flat_data['chapters']:
                    ch['content'] = content_map.get(ch['chapterId'], "")

            flat_data['comments'] = raw_data.get('comments', [])
            flat_data['reviews'] = raw_data.get('reviews', [])
            
            # 4. Info & Stats
            if raw_data.get('storyInfo'):
                flat_data['info'] = raw_data['storyInfo'][0]
                flat_data['ratings'] = raw_data['storyInfo'][0] # Reuse stats

            # 5. Website Context
            flat_data['websiteId'] = website_id
            
            # --- EXECUTE SYNC ---
            story_id = pipeline.process_story(flat_data)
            print(f"   🚀 Synced Story ID: {story_id}")

        except Exception as e:
            print(f"   ❌ Error processing {os.path.basename(f_path)}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()