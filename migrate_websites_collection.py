"""
Script migration: Đổi tên các fields trong collection websites
Fields mapping:
- website_id -> websiteId
- website_name -> websiteName
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

def migrate_websites_collection():
    """Đổi tên các fields trong collection websites"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection = db["websites"]
        
        # Đếm số lượng documents
        total_count = collection.count_documents({})
        safe_print(f"\n📊 Tổng số documents trong collection websites: {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong collection websites")
            client.close()
            return
        
        # Mapping các fields cũ -> mới
        field_mappings = {
            "website_id": "websiteId",
            "website_name": "websiteName"
        }
        
        # Đếm số documents cần update
        update_count = 0
        skip_count = 0
        
        safe_print("\n🔄 Đang đổi tên các fields...")
        
        # Lấy tất cả documents và update từng cái
        for doc in collection.find():
            update_data = {}
            unset_data = {}
            
            # Kiểm tra từng field mapping
            for old_field, new_field in field_mappings.items():
                # Nếu có field cũ và chưa có field mới
                if old_field in doc and new_field not in doc:
                    update_data[new_field] = doc[old_field]
                    unset_data[old_field] = ""
                # Nếu có cả field cũ và mới, giữ lại field mới và xóa field cũ
                elif old_field in doc and new_field in doc:
                    unset_data[old_field] = ""
            
            # Nếu có fields cần update
            if update_data or unset_data:
                update_operation = {}
                if update_data:
                    update_operation["$set"] = update_data
                if unset_data:
                    update_operation["$unset"] = unset_data
                
                collection.update_one(
                    {"_id": doc["_id"]},
                    update_operation
                )
                update_count += 1
                website_name = doc.get("websiteName") or doc.get("website_name", "N/A")
                safe_print(f"  ✅ Đã cập nhật website: {website_name}")
            else:
                skip_count += 1
        
        safe_print(f"\n✅ Hoàn thành! Đã cập nhật {update_count}/{total_count} documents")
        if skip_count > 0:
            safe_print(f"   ⏭️  Bỏ qua {skip_count} documents (đã có field names mới)")
        safe_print("\n📋 Các fields đã được đổi tên:")
        for old_field, new_field in field_mappings.items():
            safe_print(f"   - {old_field} -> {new_field}")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_websites_collection()

