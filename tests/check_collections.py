"""
Quick test to verify MongoDB collections are created
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pymongo import MongoClient
from src import config

print("🔍 Checking MongoDB collections...")
print("=" * 60)

try:
    client = MongoClient(config.MONGODB_URI)
    db = client[config.MONGODB_DB_NAME]
    
    # List all collections
    collections = db.list_collection_names()
    print(f"\n📊 Total collections: {len(collections)}")
    print("\n📁 Collections:")
    for coll in sorted(collections):
        count = db[coll].count_documents({})
        print(f"   ✓ {coll}: {count} documents")
    
    # Check for new collections
    required = ["stories", "story_info", "chapters", "chapter_contents", "comments", "users", "websites"]
    print(f"\n🔍 Required collections:")
    for req in required:
        exists = req in collections
        status = "✅" if exists else "❌"
        count = db[req].count_documents({}) if exists else 0
        print(f"   {status} {req}: {count} docs")
    
    # Sample documents from each collection
    print(f"\n📄 Sample documents schema:")
    for coll_name in ["stories", "story_info", "chapters", "comments"]:
        doc = db[coll_name].find_one()
        if doc:
            fields = [f for f in doc.keys() if f != '_id']
            print(f"\n   {coll_name}:")
            print(f"      Fields: {', '.join(fields[:5])}")
            if len(fields) > 5:
                print(f"      ... and {len(fields) - 5} more")
        else:
            print(f"\n   {coll_name}: (empty)")
    
    client.close()
    print("\n✅ Check completed")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
