"""
Script để xóa collection rankings khỏi MongoDB
"""
from src import config
from pymongo import MongoClient

def delete_rankings_collection():
    """Xóa collection rankings khỏi MongoDB"""
    try:
        client = MongoClient(config.MONGODB_URI)
        db = client[config.MONGODB_DB_NAME]
        
        # Kiểm tra xem collection có tồn tại không
        collections = db.list_collection_names()
        if "rankings" in collections:
            # Xóa collection
            db.drop_collection("rankings")
            print(f"✅ Đã xóa collection 'rankings' khỏi database '{config.MONGODB_DB_NAME}'")
        else:
            print(f"ℹ️ Collection 'rankings' không tồn tại trong database '{config.MONGODB_DB_NAME}'")
        
        client.close()
    except Exception as e:
        print(f"❌ Lỗi khi xóa collection rankings: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    delete_rankings_collection()

