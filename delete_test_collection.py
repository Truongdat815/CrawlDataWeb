"""
Script để xóa test_collection từ MongoDB
"""
from pymongo import MongoClient
from src.config import MONGODB_URI, MONGODB_DB_NAME
from src.utils import safe_print

def delete_test_collection():
    """Xóa test_collection từ MongoDB"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        # Test connection
        client.admin.command('ping')
        safe_print("✅ Kết nối MongoDB thành công!")
        
        # Lấy database
        db = client[MONGODB_DB_NAME]
        
        # Kiểm tra collection có tồn tại không
        collections = db.list_collection_names()
        if "test_collection" in collections:
            # Xóa collection
            db.drop_collection("test_collection")
            safe_print("✅ Đã xóa collection 'test_collection'")
        else:
            safe_print("ℹ️ Collection 'test_collection' không tồn tại")
        
        # Hiển thị danh sách collections còn lại
        safe_print(f"\n📊 Collections còn lại trong database '{MONGODB_DB_NAME}':")
        remaining_collections = db.list_collection_names()
        for col in sorted(remaining_collections):
            count = db[col].count_documents({})
            safe_print(f"   - {col}: {count} documents")
        
        client.close()
        safe_print("\n🎉 Hoàn thành!")
        return True
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())
        return False

if __name__ == "__main__":
    delete_test_collection()

