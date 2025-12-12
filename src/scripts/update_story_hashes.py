"""
Script để update hash cho các stories đã có trong DB
"""
from src.handlers.mongo_handler import MongoHandler
from src.utils.hash_utils import create_chapter_hash
from src.utils import safe_print

def update_all_story_hashes():
    """Update hash cho tất cả stories chưa có hash"""
    mongo = MongoHandler()
    
    if not mongo.mongo_collection_stories:
        safe_print("⚠️ Không kết nối được MongoDB")
        return
    
    try:
        # Lấy tất cả stories chưa có hash
        stories = mongo.mongo_collection_stories.find({
            "$or": [
                {"chapter_1_hash": {"$exists": False}},
                {"chapter_1_hash": None}
            ]
        })
        
        updated_count = 0
        total_stories = mongo.mongo_collection_stories.count_documents({
            "$or": [
                {"chapter_1_hash": {"$exists": False}},
                {"chapter_1_hash": None}
            ]
        })
        
        safe_print(f"📚 Tìm thấy {total_stories} stories chưa có hash")
        
        for story in stories:
            story_id = story.get("story_id")
            story_name = story.get("story_name", "Unknown")
            web_story_id = story.get("web_story_id", "")
            
            safe_print(f"\n  🔍 Đang xử lý: {story_name} (web_story_id: {web_story_id})")
            
            # Lấy chapter 1 content
            chapter_1_content = mongo.get_chapter_1_content(story_id)
            
            if chapter_1_content:
                # Tạo hash
                chapter_1_hash = create_chapter_hash(chapter_1_content)
                
                if chapter_1_hash:
                    # Update story
                    mongo.mongo_collection_stories.update_one(
                        {"story_id": story_id},
                        {"$set": {"chapter_1_hash": chapter_1_hash}}
                    )
                    updated_count += 1
                    safe_print(f"        ✅ Updated hash cho: {story_name}")
                else:
                    safe_print(f"        ⚠️ Không thể tạo hash cho: {story_name}")
            else:
                safe_print(f"        ⚠️ Không tìm thấy chapter 1 content cho: {story_name}")
        
        safe_print(f"\n✅ Hoàn thành! Đã update hash cho {updated_count}/{total_stories} stories")
        
    except Exception as e:
        safe_print(f"⚠️ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())
    finally:
        mongo.close()

if __name__ == "__main__":
    update_all_story_hashes()

