"""
Script migration: Thêm các fields còn thiếu vào collection stories
Các fields sẽ được thêm với giá trị trống (empty)
"""
import sys
from pymongo import MongoClient
from src.config import MONGODB_URI, MONGODB_DB_NAME, MONGODB_COLLECTION_STORIES

def safe_print(*args, **kwargs):
    """Safe print với encoding UTF-8"""
    try:
        message = ' '.join(str(arg) for arg in args)
        print(message, **kwargs)
    except:
        print(*args, **kwargs)

def migrate_stories_fields():
    """Thêm các fields còn thiếu vào tất cả documents trong collection stories"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection = db[MONGODB_COLLECTION_STORIES]
        
        # Đếm số lượng documents
        total_count = collection.count_documents({})
        safe_print(f"\n📊 Tổng số truyện trong collection: {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong MongoDB")
            client.close()
            return
        
        # Các fields cần thêm (nếu chưa có)
        fields_to_add = {
            "genres": [],  # genres - mảng rỗng
            "user_id": "",  # user_id - string rỗng
        }
        
        # Đếm số documents cần update
        update_count = 0
        
        safe_print("\n🔄 Đang cập nhật các documents...")
        
        # Lấy tất cả documents và update từng cái
        for doc in collection.find():
            update_data = {}
            
            # Kiểm tra và thêm genres nếu chưa có
            if "genres" not in doc:
                update_data["genres"] = []
            
            # Kiểm tra và thêm user_id nếu chưa có
            # Nếu có author_id thì dùng author_id, nếu không thì để rỗng
            if "user_id" not in doc:
                if "author_id" in doc and doc["author_id"]:
                    update_data["user_id"] = doc["author_id"]
                else:
                    update_data["user_id"] = ""
            
            # Đảm bảo total_chapters luôn có (nếu chưa có)
            if "total_chapters" not in doc:
                update_data["total_chapters"] = ""
            
            # Nếu có fields cần update
            if update_data:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": update_data}
                )
                update_count += 1
                safe_print(f"  ✅ Đã cập nhật story: {doc.get('web_story_id', doc.get('id', 'N/A'))}")
        
        safe_print(f"\n✅ Hoàn thành! Đã cập nhật {update_count}/{total_count} documents")
        safe_print("\n📋 Các fields đã được thêm:")
        safe_print("   - genres: [] (mảng rỗng)")
        safe_print("   - user_id: '' (string rỗng hoặc giá trị từ author_id)")
        safe_print("   - total_chapters: '' (nếu chưa có)")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_stories_fields()

