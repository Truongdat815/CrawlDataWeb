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
from src.config import (
    MONGODB_URI, MONGODB_DB_NAME, 
    MONGODB_COLLECTION_STORIES, MONGODB_COLLECTION_CHAPTERS,
    MONGODB_COLLECTION_COMMENTS, MONGODB_COLLECTION_REVIEWS,
    MONGODB_COLLECTION_SCORES, MONGODB_COLLECTION_USERS,
    MONGODB_COLLECTION_FICTIONS
)
import json

def view_data():
    """Xem dữ liệu trong MongoDB - hiển thị từ các collections mới"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        
        # Lấy các collections
        stories_col = db[MONGODB_COLLECTION_STORIES]
        chapters_col = db[MONGODB_COLLECTION_CHAPTERS]
        comments_col = db[MONGODB_COLLECTION_COMMENTS]
        reviews_col = db[MONGODB_COLLECTION_REVIEWS]
        scores_col = db[MONGODB_COLLECTION_SCORES]
        users_col = db[MONGODB_COLLECTION_USERS]
        
        # Đếm số lượng documents trong mỗi collection
        stories_count = stories_col.count_documents({})
        chapters_count = chapters_col.count_documents({})
        comments_count = comments_col.count_documents({})
        reviews_count = reviews_col.count_documents({})
        scores_count = scores_col.count_documents({})
        users_count = users_col.count_documents({})
        
        safe_print("\n" + "=" * 80)
        safe_print("📊 THỐNG KÊ DỮ LIỆU TRONG MONGODB")
        safe_print("=" * 80)
        safe_print(f"📚 Stories: {stories_count}")
        safe_print(f"📖 Chapters: {chapters_count}")
        safe_print(f"💬 Comments: {comments_count}")
        safe_print(f"⭐ Reviews: {reviews_count}")
        safe_print(f"📊 Scores: {scores_count}")
        safe_print(f"👤 Users: {users_count}")
        safe_print("=" * 80)
        
        if stories_count == 0:
            safe_print("\n📭 Chưa có dữ liệu nào trong MongoDB")
            safe_print("💡 Chạy 'python main.py' để cào và lưu dữ liệu")
            return
        
        # Hiển thị danh sách truyện từ collection "stories"
        safe_print("\n📚 Danh sách truyện:")
        safe_print("=" * 80)
        
        for i, doc in enumerate(stories_col.find().sort("id", 1), 1):
            story_id = doc.get('id', 'N/A')
            # Đếm số chapters, comments, reviews cho truyện này
            chapter_count = chapters_col.count_documents({"story_id": story_id})
            comment_count = comments_col.count_documents({"story_id": story_id})
            review_count = reviews_col.count_documents({"story_id": story_id})
            
            safe_print(f"\n{i}. ID: {story_id}")
            safe_print(f"   Name: {doc.get('name', 'N/A')}")
            safe_print(f"   Author: {doc.get('author', 'N/A')}")
            safe_print(f"   Chapters: {chapter_count}")
            safe_print(f"   Comments: {comment_count}")
            safe_print(f"   Reviews: {review_count}")
            safe_print(f"   Status: {doc.get('status', 'N/A')}")
        
        # Hỏi xem có muốn xem chi tiết không
        safe_print("\n" + "=" * 80)
        safe_print("\n💡 Để xem chi tiết một truyện, sử dụng:")
        safe_print("   python view_mongodb.py <story_id>")
        safe_print("\n   Ví dụ: python view_mongodb.py 21220")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())

def view_detail(fiction_id):
    """Xem chi tiết một truyện từ các collections mới"""
    try:
        safe_print(f"🔍 Đang tìm truyện với ID: {fiction_id}...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        
        # Lấy từ collection "stories"
        stories_col = db[MONGODB_COLLECTION_STORIES]
        story_doc = stories_col.find_one({"id": fiction_id})
        
        if not story_doc:
            # Thử tìm trong collection cũ
            old_col = db[MONGODB_COLLECTION_FICTIONS]
            old_doc = old_col.find_one({"id": fiction_id})
            if old_doc:
                safe_print(f"⚠️ Tìm thấy trong collection cũ 'fictions', vui lòng chạy lại scraper để migrate sang collections mới")
                safe_print(json.dumps(old_doc, ensure_ascii=False, indent=2))
                client.close()
                return
            else:
                safe_print(f"❌ Không tìm thấy truyện với ID: {fiction_id}")
                client.close()
                return
        
        # Lấy dữ liệu từ các collections khác
        chapters_col = db[MONGODB_COLLECTION_CHAPTERS]
        comments_col = db[MONGODB_COLLECTION_COMMENTS]
        reviews_col = db[MONGODB_COLLECTION_REVIEWS]
        scores_col = db[MONGODB_COLLECTION_SCORES]
        
        chapters = list(chapters_col.find({"story_id": fiction_id}).sort("id", 1))
        comments = list(comments_col.find({"story_id": fiction_id}))
        reviews = list(reviews_col.find({"story_id": fiction_id}))
        score = scores_col.find_one({"story_id": fiction_id})
        
        # Tạo cấu trúc dữ liệu đầy đủ
        full_data = {
            "story": story_doc,
            "chapters": chapters,
            "comments": comments,
            "reviews": reviews,
            "score": score
        }
        
        # Hiển thị chi tiết
        safe_print("\n" + "=" * 80)
        safe_print("📖 CHI TIẾT TRUYỆN")
        safe_print("=" * 80)
        safe_print(f"\n📚 STORY:")
        safe_print(json.dumps(story_doc, ensure_ascii=False, indent=2))
        
        if score:
            safe_print(f"\n📊 SCORE:")
            safe_print(json.dumps(score, ensure_ascii=False, indent=2))
        
        safe_print(f"\n📖 CHAPTERS ({len(chapters)}):")
        for i, chapter in enumerate(chapters[:5], 1):  # Chỉ hiển thị 5 chương đầu
            safe_print(f"   {i}. {chapter.get('name', 'N/A')} (ID: {chapter.get('id', 'N/A')})")
        if len(chapters) > 5:
            safe_print(f"   ... và {len(chapters) - 5} chương khác")
        
        safe_print(f"\n💬 COMMENTS ({len(comments)}):")
        safe_print(f"   Tổng số comments: {len(comments)}")
        
        safe_print(f"\n⭐ REVIEWS ({len(reviews)}):")
        for i, review in enumerate(reviews[:3], 1):  # Chỉ hiển thị 3 reviews đầu
            safe_print(f"   {i}. {review.get('title', 'N/A')} - {review.get('username', 'N/A')}")
        if len(reviews) > 3:
            safe_print(f"   ... và {len(reviews) - 3} reviews khác")
        
        safe_print("\n" + "=" * 80)
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Xem chi tiết một truyện
        fiction_id = sys.argv[1]
        view_detail(fiction_id)
    else:
        # Xem danh sách tất cả truyện
        view_data()

