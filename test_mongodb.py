"""
File test kết nối MongoDB
Sử dụng cấu hình từ src/config.py
"""
import sys

# Helper function để print an toàn với encoding UTF-8
def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        message = ' '.join(str(arg) for arg in args)
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

from pymongo import MongoClient
from src.config import MONGODB_URI, MONGODB_DB_NAME

def test_connection():
    """Test kết nối MongoDB"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        safe_print(f"URI: {MONGODB_URI.split('@')[0]}@***")
        
        client = MongoClient(MONGODB_URI)
        
        # Test connection
        client.admin.command('ping')
        safe_print("✅ Kết nối MongoDB thành công!")
        
        # Test database và collection
        db = client[MONGODB_DB_NAME]
        collection = db["test_collection"]
        
        # Test insert
        test_doc = {
            "message": "Hello MongoDB!",
            "type": "test",
            "description": "Đây là test kết nối MongoDB"
        }
        result = collection.insert_one(test_doc)
        safe_print(f"✅ Test insert thành công! ID: {result.inserted_id}")
        
        # Test find - hiển thị tất cả documents
        safe_print("\n📄 Tất cả documents trong collection:")
        for doc in collection.find():
            safe_print(f"   {doc}")
        
        # Xóa test document
        collection.delete_one({"_id": result.inserted_id})
        safe_print("\n✅ Đã xóa test document")
        
        # Hiển thị thông tin database
        safe_print(f"\n📊 Database: {MONGODB_DB_NAME}")
        safe_print(f"📊 Collection: test_collection")
        safe_print(f"📊 Số documents hiện tại: {collection.count_documents({})}")
        
        client.close()
        safe_print("\n🎉 Tất cả test đều thành công!")
        return True
        
    except Exception as e:
        safe_print(f"❌ Lỗi kết nối MongoDB: {e}")
        safe_print("\n💡 Hướng dẫn:")
        safe_print("1. Kiểm tra lại cấu hình trong src/config.py")
        safe_print("2. Đảm bảo cluster URL, username, password đúng")
        safe_print("3. Kiểm tra network connection và MongoDB Atlas whitelist IP")
        return False

if __name__ == "__main__":
    test_connection()

