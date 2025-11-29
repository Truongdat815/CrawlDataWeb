"""
Script để xem dữ liệu đã lưu trong MongoDB
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
from src.config import MONGODB_URI, MONGODB_DB_NAME, MONGODB_COLLECTION_FICTIONS
import json

def view_data():
    """Xem dữ liệu trong MongoDB"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection = db[MONGODB_COLLECTION_FICTIONS]
        
        # Đếm số lượng documents
        count = collection.count_documents({})
        safe_print(f"\n📊 Tổng số truyện đã lưu: {count}")
        
        if count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong MongoDB")
            safe_print("💡 Chạy 'python main.py' để cào và lưu dữ liệu")
            return
        
        # Hiển thị danh sách truyện
        safe_print("\n📚 Danh sách truyện:")
        safe_print("=" * 80)
        
        for i, doc in enumerate(collection.find().sort("id", 1), 1):
            safe_print(f"\n{i}. ID: {doc.get('id', 'N/A')}")
            safe_print(f"   Title: {doc.get('title', 'N/A')}")
            safe_print(f"   Author: {doc.get('author', 'N/A')}")
            safe_print(f"   Chapters: {len(doc.get('chapters', []))}")
            safe_print(f"   Status: {doc.get('status', 'N/A')}")
        
        # Hỏi xem có muốn xem chi tiết không
        safe_print("\n" + "=" * 80)
        safe_print("\n💡 Để xem chi tiết một truyện, sử dụng:")
        safe_print("   python view_mongodb.py <fiction_id>")
        safe_print("\n   Ví dụ: python view_mongodb.py 21220")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")

def view_detail(fiction_id):
    """Xem chi tiết một truyện"""
    try:
        safe_print(f"🔍 Đang tìm truyện với ID: {fiction_id}...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection = db[MONGODB_COLLECTION_FICTIONS]
        
        doc = collection.find_one({"id": fiction_id})
        
        if not doc:
            safe_print(f"❌ Không tìm thấy truyện với ID: {fiction_id}")
            return
        
        # Hiển thị chi tiết
        safe_print("\n" + "=" * 80)
        safe_print("📖 CHI TIẾT TRUYỆN")
        safe_print("=" * 80)
        safe_print(json.dumps(doc, ensure_ascii=False, indent=2))
        safe_print("=" * 80)
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Xem chi tiết một truyện
        fiction_id = sys.argv[1]
        view_detail(fiction_id)
    else:
        # Xem danh sách tất cả truyện
        view_data()

