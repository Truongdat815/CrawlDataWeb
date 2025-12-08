"""
Script migration: Đổi tên collection rankings và các fields
Collection: rankings (giữ nguyên tên hoặc đổi từ tên khác)
Fields mapping:
- rank_id -> rankId
- rank_name -> rankName
- rank_number -> rankNumber
- website_id -> websiteId
- story_id -> storyId
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

def migrate_rankings_collection():
    """Đổi tên collection và các fields trong rankings"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        
        # Thử tìm collection với các tên có thể có
        possible_collection_names = ["rankings", "ranking", "ranks"]
        collection_old = None
        collection_name_old = None
        
        for name in possible_collection_names:
            if name in db.list_collection_names():
                collection_old = db[name]
                collection_name_old = name
                safe_print(f"📋 Tìm thấy collection: {name}")
                break
        
        if not collection_old:
            safe_print("📭 Không tìm thấy collection rankings trong database")
            # Tạo collection mới (rỗng) để đảm bảo collection tồn tại
            collection_new = db["rankings"]
            collection_new.insert_one({})
            collection_new.delete_one({})
            safe_print("✅ Đã tạo collection rankings (rỗng)")
            client.close()
            return
        
        collection_new = db["rankings"]
        
        # Đếm số lượng documents
        total_count = collection_old.count_documents({})
        safe_print(f"\n📊 Tổng số documents trong collection {collection_name_old}: {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong collection")
            # Vẫn tạo collection mới (rỗng) để đảm bảo collection tồn tại
            collection_new.insert_one({})
            collection_new.delete_one({})
            safe_print("✅ Đã tạo collection rankings (rỗng)")
            if collection_name_old != "rankings":
                safe_print(f"⚠️  Collection cũ '{collection_name_old}' vẫn còn trong database.")
                safe_print("   Bạn có thể xóa collection cũ sau khi đã xác nhận migration thành công.")
            client.close()
            return
        
        # Mapping các fields cũ -> mới
        field_mappings = {
            "rank_id": "rankId",
            "rank_name": "rankName",
            "rank_number": "rankNumber",
            "website_id": "websiteId",
            "story_id": "storyId"
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
                    # Giữ nguyên field không có trong mapping
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
                rank_id = doc.get("rankId") or doc.get("rank_id", "N/A")
                safe_print(f"  🔄 Đã cập nhật document: {rank_id}")
            else:
                # Insert mới
                collection_new.insert_one(new_doc)
                migrate_count += 1
                rank_id = doc.get("rankId") or doc.get("rank_id", "N/A")
                safe_print(f"  ✅ Đã migrate document: {rank_id}")
        
        safe_print(f"\n✅ Hoàn thành! Đã migrate {migrate_count} documents, cập nhật {skip_count} documents")
        safe_print(f"📋 Collection mới: rankings có {collection_new.count_documents({})} documents")
        safe_print("\n📋 Các fields đã được đổi tên:")
        for old_field, new_field in field_mappings.items():
            safe_print(f"   - {old_field} -> {new_field}")
        
        if collection_name_old != "rankings":
            safe_print(f"\n⚠️  LƯU Ý: Collection cũ '{collection_name_old}' vẫn còn trong database.")
            safe_print("   Bạn có thể xóa collection cũ sau khi đã xác nhận migration thành công.")
            safe_print(f"   Để xóa: db.{collection_name_old}.drop()")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_rankings_collection()

