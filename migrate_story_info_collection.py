"""
Script migration: Đổi tên collection story_info thành storyInfo và đổi tên các fields
Collection: story_info -> storyInfo
Fields mapping:
- info_id -> infoId
- story_id -> storyId
- website_id -> websiteId
- total_views -> totalViews
- average_views -> averageViews
- page_views -> pageViews
- overall_score -> overallScore
- style_score -> styleScore
- story_score -> storyScore
- grammar_score -> grammarScore
- character_score -> characterScore
- time -> timeToFinish
- release_rate -> releaseRate
- number_of_reader -> numberOfReader
- rating_total -> ratingTotal
- total_views_chapters -> totalViewsChapters
- total_word -> totalWord
- average_words -> averageWords
- last_updated -> lastUpdated
- total_reviews -> totalReviews
- user_reading -> userReading
- user_plan_to_read -> userPlanToRead
- user_completed -> userCompleted
- user_paused -> userPaused
- user_dropped -> userDropped
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

def migrate_story_info_collection():
    """Đổi tên collection và các fields trong storyInfo"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection_old = db["story_info"]
        collection_new = db["storyInfo"]
        
        # Đếm số lượng documents
        total_count = collection_old.count_documents({})
        safe_print(f"\n📊 Tổng số documents trong collection story_info: {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong collection story_info")
            # Vẫn tạo collection mới (rỗng) để đảm bảo collection tồn tại
            collection_new.insert_one({})
            collection_new.delete_one({})
            safe_print("✅ Đã tạo collection storyInfo (rỗng)")
            client.close()
            return
        
        # Mapping các fields cũ -> mới
        field_mappings = {
            "info_id": "infoId",
            "story_id": "storyId",
            "website_id": "websiteId",
            "total_views": "totalViews",
            "average_views": "averageViews",
            "page_views": "pageViews",
            "overall_score": "overallScore",
            "style_score": "styleScore",
            "story_score": "storyScore",
            "grammar_score": "grammarScore",
            "character_score": "characterScore",
            "time": "timeToFinish",
            "release_rate": "releaseRate",
            "number_of_reader": "numberOfReader",
            "rating_total": "ratingTotal",
            "total_views_chapters": "totalViewsChapters",
            "total_word": "totalWord",
            "average_words": "averageWords",
            "last_updated": "lastUpdated",
            "total_reviews": "totalReviews",
            "user_reading": "userReading",
            "user_plan_to_read": "userPlanToRead",
            "user_completed": "userCompleted",
            "user_paused": "userPaused",
            "user_dropped": "userDropped"
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
                    # Giữ nguyên field không có trong mapping (như freeChapter, voted, followers, favorites)
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
                safe_print(f"  🔄 Đã cập nhật document: {doc.get('story_id', doc.get('_id', 'N/A'))}")
            else:
                # Insert mới
                collection_new.insert_one(new_doc)
                migrate_count += 1
                story_id = doc.get("story_id") or doc.get("storyId", "N/A")
                safe_print(f"  ✅ Đã migrate document: {story_id}")
        
        safe_print(f"\n✅ Hoàn thành! Đã migrate {migrate_count} documents, cập nhật {skip_count} documents")
        safe_print(f"📋 Collection mới: storyInfo có {collection_new.count_documents({})} documents")
        safe_print("\n📋 Các fields đã được đổi tên:")
        for old_field, new_field in field_mappings.items():
            safe_print(f"   - {old_field} -> {new_field}")
        
        safe_print("\n⚠️  LƯU Ý: Collection cũ 'story_info' vẫn còn trong database.")
        safe_print("   Bạn có thể xóa collection cũ sau khi đã xác nhận migration thành công.")
        safe_print("   Để xóa: db.story_info.drop()")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_story_info_collection()

