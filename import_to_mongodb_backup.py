"""
MongoDB Import Script - Final Schema with UUID BSON Conversion
Imports scraped JSON data to team MongoDB with proper UUID v7 Binary format

Features:
- Converts UUID strings to BSON Binary for optimal database performance
- Upserts based on platform_id to avoid duplicates
- Separates collections: novels, chapters, comments
- Comprehensive error handling and progress tracking
"""
import os
import sys
import json
from pathlib import Path
from uuid import UUID
from bson.binary import Binary, UuidRepresentation
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'my_database')
COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'novels')

JSON_DIR = Path('data/json')


def uuid_to_binary(uuid_str):
    """Convert UUID string to BSON Binary format"""
    try:
        if not uuid_str:
            return None
        # Handle UUID v7 strings
        return Binary.from_uuid(UUID(uuid_str))
    except Exception as e:
        print(f"⚠️  UUID conversion failed for '{uuid_str}': {e}")
        return None


def convert_document_uuids(doc, is_book=True):
    """Recursively convert all UUID fields to BSON Binary"""
    if isinstance(doc, dict):
        converted = {}
        for key, value in doc.items():
            # Convert ID fields
            if key in ['id', 'book_id', 'story_id', 'chapter_id', 'comment_id', 'user_id']:
                if isinstance(value, str) and len(value) == 36:  # UUID format
                    converted[key] = uuid_to_binary(value)
                else:
                    converted[key] = value
            elif isinstance(value, dict):
                converted[key] = convert_document_uuids(value, is_book=False)
            elif isinstance(value, list):
                converted[key] = [convert_document_uuids(item, is_book=False) for item in value]
            else:
                converted[key] = value
        return converted
    else:
        return doc


def import_book(collection, book_data, filename):
    """Import single book with UUID conversion"""
    try:
        # Convert all UUID strings to BSON Binary
        book_doc = convert_document_uuids(book_data, is_book=True)
        
        # Ensure _id field for MongoDB
        if 'id' in book_doc:
            book_doc['_id'] = book_doc['id']
        
        # Upsert based on platform_id to avoid duplicates
        platform_id = book_doc.get('platform_id')
        if not platform_id:
            print(f"   ⚠️  No platform_id found in {filename}, using _id for upsert")
            platform_id = book_doc.get('_id')
        
        result = collection.update_one(
            {'platform_id': platform_id},
            {'$set': book_doc},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"   ✅ Inserted new: {book_data.get('name', 'Unknown')} ({platform_id})")
            return 'inserted'
        elif result.modified_count > 0:
            print(f"   🔄 Updated existing: {book_data.get('name', 'Unknown')} ({platform_id})")
            return 'updated'
        else:
            print(f"   ℹ️  No changes: {book_data.get('name', 'Unknown')} ({platform_id})")
            return 'unchanged'
            
    except PyMongoError as e:
        print(f"   ❌ MongoDB error for {filename}: {e}")
        return 'error'
    except Exception as e:
        print(f"   ❌ Unexpected error for {filename}: {e}")
        return 'error'


def main():
    print("="*70)
    print("📦 MONGODB IMPORT - FINAL SCHEMA WITH UUID v7 BSON")
    print("="*70)
    print()
    
    # Validate environment
    if not MONGO_URI:
        print("❌ Error: MONGO_URI not found in environment")
        print("   Please create .env file with:")
        print("   MONGO_URI=mongodb://user:56915001@103.90.224.232:27017/my_database")
        return 1
    
    print(f"⚙️  Configuration:")
    print(f"   MongoDB URI: {MONGO_URI[:50]}...")
    print(f"   Database: {DB_NAME}")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   JSON Directory: {JSON_DIR}")
    print()
    
    # Check JSON directory
    if not JSON_DIR.exists():
        print(f"❌ Error: JSON directory not found: {JSON_DIR}")
        return 1
    
    # Find all JSON files
    json_files = list(JSON_DIR.glob('*.json'))
    if not json_files:
        print(f"❌ Error: No JSON files found in {JSON_DIR}")
        return 1
    
    print(f"📋 Found {len(json_files)} JSON files to import")
    print()
    
    # Connect to MongoDB
    print("🔌 Connecting to MongoDB...")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        client.server_info()
        print("✅ Connected successfully!")
        print()
    except PyMongoError as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return 1
    
    # Get database and collection
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    # Import statistics
    stats = {
        'inserted': 0,
        'updated': 0,
        'unchanged': 0,
        'error': 0
    }
    
    # Process each JSON file
    for i, json_file in enumerate(json_files, 1):
        print(f"📚 [{i}/{len(json_files)}] Processing: {json_file.name}")
        
        try:
            # Read JSON file
            with open(json_file, 'r', encoding='utf-8') as f:
                book_data = json.load(f)
            
            # Import to MongoDB
            result = import_book(collection, book_data, json_file.name)
            stats[result] += 1
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON in {json_file.name}: {e}")
            stats['error'] += 1
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            stats['error'] += 1
        
        print()
    
    # Final summary
    print("="*70)
    print("🎉 IMPORT COMPLETE")
    print("="*70)
    print(f"📊 Final Statistics:")
    print(f"   ✅ Inserted: {stats['inserted']}")
    print(f"   🔄 Updated: {stats['updated']}")
    print(f"   ℹ️  Unchanged: {stats['unchanged']}")
    print(f"   ❌ Errors: {stats['error']}")
    print(f"   📚 Total processed: {sum(stats.values())}/{len(json_files)}")
    print("="*70)
    print()
    
    # Verify data in database
    print("🔍 Verifying data in MongoDB...")
    try:
        total_docs = collection.count_documents({})
        print(f"   Total documents in collection: {total_docs}")
        
        # Show sample document structure
        sample = collection.find_one()
        if sample:
            print(f"\n📄 Sample document structure:")
            print(f"   _id type: {type(sample.get('_id'))}")
            print(f"   id type: {type(sample.get('id'))}")
            print(f"   platform_id: {sample.get('platform_id')}")
            print(f"   name: {sample.get('name', 'N/A')[:50]}...")
            print(f"   chapters count: {len(sample.get('chapters', []))}")
            print(f"   comments count: {len(sample.get('comments', []))}")
    except Exception as e:
        print(f"   ⚠️  Verification error: {e}")
    
    print()
    print("✅ All done! Check MongoDB Compass to verify UUID Binary format.")
    
    # Close connection
    client.close()
    
    return 0 if stats['error'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
