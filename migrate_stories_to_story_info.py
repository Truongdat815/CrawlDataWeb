"""
Script migration: Tách các fields thống kê/metrics từ collection stories sang collection story_info
"""
import sys
from pymongo import MongoClient
from src.config import MONGODB_URI, MONGODB_DB_NAME, MONGODB_COLLECTION_STORIES
from src.utils import generate_id

def safe_print(*args, **kwargs):
    """Safe print với encoding UTF-8"""
    try:
        message = ' '.join(str(arg) for arg in args)
        print(message, **kwargs)
    except:
        print(*args, **kwargs)

def init_or_get_website(db, website_name):
    """Khởi tạo hoặc lấy website_id của website"""
    collection_websites = db["websites"]
    
    try:
        # Tìm website theo tên
        existing = collection_websites.find_one({"website_name": website_name})
        
        if existing:
            website_id = existing.get("website_id")
            safe_print(f"✅ Đã tìm thấy website '{website_name}' với ID: {website_id}")
            return website_id
        else:
            # Tạo website mới
            website_id = generate_id()
            website_data = {
                "website_id": website_id,
                "website_name": website_name
            }
            collection_websites.insert_one(website_data)
            safe_print(f"✅ Đã tạo website mới '{website_name}' với ID: {website_id}")
            return website_id
    except Exception as e:
        safe_print(f"⚠️ Lỗi khi init/get website: {e}")
        return None

def migrate_stories_to_story_info():
    """Di chuyển các fields thống kê/metrics từ stories sang story_info"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection_stories = db[MONGODB_COLLECTION_STORIES]
        collection_story_info = db["story_info"]
        
        # Khởi tạo hoặc lấy website "Royal Road"
        safe_print("\n🌐 Đang khởi tạo website 'Royal Road'...")
        royal_road_website_id = init_or_get_website(db, "Royal Road")
        
        if not royal_road_website_id:
            safe_print("⚠️ Không thể lấy website_id, tiếp tục với website_id rỗng")
        
        # Đếm số lượng documents
        total_count = collection_stories.count_documents({})
        safe_print(f"\n📊 Tổng số truyện trong collection stories: {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có dữ liệu nào trong MongoDB")
            client.close()
            return
        
        # Các fields cần di chuyển từ stories sang story_info
        stats_fields = [
            "total_views", "average_views", "followers", "favorites", 
            "ratings", "page_views", "overall_score", "style_score", 
            "story_score", "grammar_score", "character_score"
        ]
        
        # Các fields cơ bản cần giữ lại trong stories
        basic_fields = [
            "id", "web_story_id", "name", "url", "cover_image", 
            "category", "status", "genres", "tags", "description", 
            "user_id", "author_id", "total_chapters"
        ]
        
        update_count = 0
        story_info_count = 0
        
        safe_print("\n🔄 Đang di chuyển các fields thống kê/metrics...")
        
        # Lấy tất cả documents và xử lý từng cái
        for doc in collection_stories.find():
            story_id = doc.get("id")
            web_story_id = doc.get("web_story_id")
            
            if not story_id or not web_story_id:
                safe_print(f"  ⚠️ Bỏ qua document không có id hoặc web_story_id: {doc.get('_id')}")
                continue
            
            # Kiểm tra xem đã có story_info chưa
            existing_info = collection_story_info.find_one({"story_id": story_id})
            
            # Tạo story_info_data
            story_info_data = {
                "info_id": existing_info.get("info_id") if existing_info else generate_id(),
                "story_id": story_id,  # FK to stories
                "website_id": royal_road_website_id if royal_road_website_id else "",  # FK to websites
            }
            
            # Di chuyển các fields thống kê/metrics
            has_stats = False
            for field in stats_fields:
                if field in doc:
                    story_info_data[field] = doc[field]
                    has_stats = True
            
            # Thêm các fields mới (để trống)
            new_fields = {
                "stability_of_updates": "",
                "voted": "",
                "freeChapter": "",
                "time": "",
                "release_rate": "",
                "number_of_reader": "",
                "rating_total": doc.get("ratings", ""),  # Map từ ratings
                "total_views_chapters": "",
                "total_word": "",
                "average_words": "",
                "last_updated": "",
                "total_reviews": "",
                "user_reading": "",
                "user_plan_to_read": "",
                "user_completed": "",
                "user_paused": "",
                "user_dropped": "",
            }
            
            # Chỉ thêm các fields mới nếu chưa có trong existing_info
            if existing_info:
                for key, value in new_fields.items():
                    if key not in existing_info:
                        story_info_data[key] = value
            else:
                story_info_data.update(new_fields)
            
            # Lưu hoặc update story_info
            if existing_info:
                collection_story_info.update_one(
                    {"story_id": story_id},
                    {"$set": story_info_data}
                )
            else:
                collection_story_info.insert_one(story_info_data)
                story_info_count += 1
            
            # Xóa các fields thống kê/metrics khỏi stories (chỉ giữ lại các fields cơ bản)
            fields_to_remove = {}
            for field in stats_fields:
                if field in doc:
                    fields_to_remove[field] = ""  # $unset chỉ cần key, value không quan trọng
            
            if fields_to_remove:
                # Sử dụng $unset để xóa các fields
                collection_stories.update_one(
                    {"_id": doc["_id"]},
                    {"$unset": fields_to_remove}
                )
                update_count += 1
                safe_print(f"  ✅ Đã di chuyển fields từ story: {web_story_id}")
        
        safe_print(f"\n✅ Hoàn thành!")
        safe_print(f"   - Đã cập nhật {update_count} stories (xóa fields thống kê/metrics)")
        safe_print(f"   - Đã tạo/cập nhật {story_info_count} story_info documents")
        safe_print(f"\n📋 Các fields đã được di chuyển:")
        safe_print(f"   - Từ stories → story_info: {', '.join(stats_fields)}")
        safe_print(f"   - Giữ lại trong stories: {', '.join(basic_fields)}")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_stories_to_story_info()

