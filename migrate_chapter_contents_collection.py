"""
Script migration: Đổi tên collection chapter_contents thành chapterContents và đổi tên các fields
Collection: chapter_contents -> chapterContents
Fields mapping:
- content_id -> contentId
- chapter_id -> chapterId
"""
import sys
from pymongo import MongoClient
from src.config import MONGODB_URI, MONGODB_DB_NAME

def safe_print(*args, **kwargs):
    """Safe print với encoding UTF-8"""
    try:
        message = ' '.join(str(arg) for arg in args)
        print(message, **kwargs)
    except:
        print(*args, **kwargs)

def migrate_chapter_contents_collection():
    """Đổi tên collection và các fields trong chapterContents"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection_old = db["chapter_contents"]
        collection_new = db["chapterContents"]
        
        # Đếm số lượng documents
        total_count = collection_old.count_documents({})
        safe_print(f"\n📊 Tổng số documents trong collection chapter_contents: {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong collection chapter_contents")
            # Vẫn tạo collection mới (rỗng) để đảm bảo collection tồn tại
            collection_new.insert_one({})
            collection_new.delete_one({})
            safe_print("✅ Đã tạo collection chapterContents (rỗng)")
            client.close()
            return
        
        # Mapping các fields cũ -> mới
        field_mappings = {
            "content_id": "contentId",
            "chapter_id": "chapterId"
        }
        
        # Đếm số documents đã migrate
        migrate_count = 0
        skip_count = 0
        
        safe_print("\n🔄 Đang migrate collection và đổi tên các fields...")
        
        # Lấy tất cả documents từ collection cũ và migrate sang collection mới
        for doc in collection_old.find():
            new_doc = {}
            
            # Copy tất cả fields không cần đổi tên
            for key, value in doc.items():
                if key == "_id":
                    # Giữ nguyên _id
                    new_doc[key] = value
                elif key in field_mappings:
                    # Đổi tên field
                    new_doc[field_mappings[key]] = value
                else:
                    # Giữ nguyên field không có trong mapping (như content)
                    new_doc[key] = value
            
            # Kiểm tra xem document đã có trong collection mới chưa
            existing = collection_new.find_one({"_id": doc["_id"]})
            if existing:
                # Update nếu đã có
                collection_new.update_one(
                    {"_id": doc["_id"]},
                    {"$set": new_doc}
                )
                skip_count += 1
                chapter_id = doc.get("chapterId") or doc.get("chapter_id", "N/A")
                safe_print(f"  🔄 Đã cập nhật document: {chapter_id}")
            else:
                # Insert mới
                collection_new.insert_one(new_doc)
                migrate_count += 1
                chapter_id = doc.get("chapterId") or doc.get("chapter_id", "N/A")
                safe_print(f"  ✅ Đã migrate document: {chapter_id}")
        
        safe_print(f"\n✅ Hoàn thành! Đã migrate {migrate_count} documents, cập nhật {skip_count} documents")
        safe_print(f"📋 Collection mới: chapterContents có {collection_new.count_documents({})} documents")
        safe_print("\n📋 Các fields đã được đổi tên:")
        for old_field, new_field in field_mappings.items():
            safe_print(f"   - {old_field} -> {new_field}")
        
        safe_print("\n⚠️  LƯU Ý: Collection cũ 'chapter_contents' vẫn còn trong database.")
        safe_print("   Bạn có thể xóa collection cũ sau khi đã xác nhận migration thành công.")
        safe_print("   Để xóa: db.chapter_contents.drop()")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_chapter_contents_collection()

