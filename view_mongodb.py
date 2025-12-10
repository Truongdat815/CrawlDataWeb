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
from src.config import MONGODB_URI, MONGODB_DB_NAME, MONGODB_COLLECTION_STORIES
import json

def view_data():
    """Xem dữ liệu trong MongoDB"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        collection = db[MONGODB_COLLECTION_STORIES]
        
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
        collection = db[MONGODB_COLLECTION_STORIES]
        
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

def view_chapters(web_story_id=None):
    """Xem danh sách chapters trong MongoDB collection 'chapters'"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        chapters_collection = db["chapters"]
        
        # Đếm số lượng documents
        total_count = chapters_collection.count_documents({})
        safe_print(f"\n📊 Tổng số chapters trong collection 'chapters': {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có chapters nào trong MongoDB collection 'chapters'")
            safe_print("💡 Chạy 'python main.py' để cào và lưu dữ liệu")
            client.close()
            return
        
        # Nếu có web_story_id, filter theo story
        query = {}
        if web_story_id:
            # Tìm story_id từ web_story_id
            stories_collection = db[MONGODB_COLLECTION_STORIES]
            story = stories_collection.find_one({"web_story_id": str(web_story_id)})
            if story:
                story_id = story.get("story_id")
                query = {"story_id": story_id}
                safe_print(f"\n🔍 Tìm chapters của story: {web_story_id} (story_id: {story_id})")
            else:
                safe_print(f"\n⚠️ Không tìm thấy story với web_story_id: {web_story_id}")
                client.close()
                return
        
        # Đếm số chapters theo query
        count = chapters_collection.count_documents(query)
        safe_print(f"📚 Số chapters tìm thấy: {count}")
        
        if count == 0:
            safe_print("📭 Không có chapters nào")
            client.close()
            return
        
        # Hiển thị danh sách chapters
        safe_print("\n📖 Danh sách chapters:")
        safe_print("=" * 100)
        
        for i, doc in enumerate(chapters_collection.find(query).sort("order", 1).limit(50), 1):
            order = doc.get("order", "N/A")
            chapter_name = doc.get("chapter_name", "N/A")[:60]  # Lấy 60 ký tự đầu
            web_chapter_id = doc.get("web_chapter_id", "N/A")
            published_time = doc.get("published_time", "N/A")
            story_id = doc.get("story_id", "N/A")
            
            safe_print(f"\n{i}. Order: {order} | web_chapter_id: {web_chapter_id}")
            safe_print(f"   Name: {chapter_name}")
            safe_print(f"   Published: {published_time}")
            safe_print(f"   story_id: {story_id}")
        
        if count > 50:
            safe_print(f"\n... và {count - 50} chapters khác")
        
        safe_print("\n" + "=" * 100)
        safe_print(f"\n💡 Collection: 'chapters' trong MongoDB database '{MONGODB_DB_NAME}'")
        safe_print(f"💡 Để xem chapters của một story cụ thể:")
        safe_print(f"   python view_mongodb.py chapters <web_story_id>")
        safe_print(f"   Ví dụ: python view_mongodb.py chapters 1420052")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())

def view_chapter_contents(web_story_id=None):
    """Xem danh sách chapter contents trong MongoDB collection 'chapter_contents'"""
    try:
        safe_print("🔌 Đang kết nối MongoDB...")
        client = MongoClient(MONGODB_URI)
        
        db = client[MONGODB_DB_NAME]
        chapter_contents_collection = db["chapter_contents"]
        chapters_collection = db["chapters"]
        
        # Đếm số lượng documents
        total_count = chapter_contents_collection.count_documents({})
        safe_print(f"\n📊 Tổng số chapter contents trong collection 'chapter_contents': {total_count}")
        
        if total_count == 0:
            safe_print("📭 Chưa có chapter contents nào trong MongoDB collection 'chapter_contents'")
            safe_print("💡 Chạy 'python main.py' để cào và lưu dữ liệu")
            client.close()
            return
        
        # Nếu có web_story_id, filter theo story
        query = {}
        chapter_ids = []
        if web_story_id:
            # Tìm story_id từ web_story_id
            stories_collection = db[MONGODB_COLLECTION_STORIES]
            story = stories_collection.find_one({"web_story_id": str(web_story_id)})
            if story:
                story_id = story.get("story_id")
                # Tìm tất cả chapters của story này
                chapters = list(chapters_collection.find({"story_id": story_id}))
                chapter_ids = [ch.get("chapter_id") for ch in chapters if ch.get("chapter_id")]
                query = {"chapter_id": {"$in": chapter_ids}}
                safe_print(f"\n🔍 Tìm chapter contents của story: {web_story_id} (story_id: {story_id}, {len(chapter_ids)} chapters)")
            else:
                safe_print(f"\n⚠️ Không tìm thấy story với web_story_id: {web_story_id}")
                client.close()
                return
        
        # Đếm số chapter contents theo query
        count = chapter_contents_collection.count_documents(query)
        safe_print(f"📚 Số chapter contents tìm thấy: {count}")
        
        if count == 0:
            safe_print("📭 Không có chapter contents nào")
            client.close()
            return
        
        # Hiển thị thống kê
        safe_print("\n📊 Thống kê:")
        safe_print("=" * 100)
        
        total_content_length = 0
        chapters_with_content = []
        
        for doc in chapter_contents_collection.find(query).limit(50):
            chapter_id = doc.get("chapter_id", "N/A")
            content = doc.get("content", "")
            content_length = len(content) if content else 0
            total_content_length += content_length
            
            # Tìm chapter name
            chapter_name = "N/A"
            if chapter_id != "N/A":
                chapter = chapters_collection.find_one({"chapter_id": chapter_id})
                if chapter:
                    chapter_name = chapter.get("chapter_name", "N/A")[:50]
                    chapters_with_content.append({
                        "chapter_id": chapter_id,
                        "chapter_name": chapter_name,
                        "content_length": content_length
                    })
            
            safe_print(f"\n📄 Chapter: {chapter_name}")
            safe_print(f"   chapter_id: {chapter_id}")
            safe_print(f"   Content length: {content_length:,} ký tự")
            if content_length > 0:
                preview = content[:100].replace("\n", " ") if content else ""
                safe_print(f"   Preview: {preview}...")
        
        if count > 50:
            safe_print(f"\n... và {count - 50} chapter contents khác")
        
        # Tính trung bình
        avg_length = total_content_length / count if count > 0 else 0
        safe_print("\n" + "=" * 100)
        safe_print(f"\n📈 Tổng kết:")
        safe_print(f"   Tổng số chapter contents: {count}")
        safe_print(f"   Tổng độ dài nội dung: {total_content_length:,} ký tự")
        safe_print(f"   Độ dài trung bình: {avg_length:,.0f} ký tự/chapter")
        safe_print(f"\n💡 Collection: 'chapter_contents' trong MongoDB database '{MONGODB_DB_NAME}'")
        safe_print(f"💡 Để xem chapter contents của một story cụ thể:")
        safe_print(f"   python view_mongodb.py contents <web_story_id>")
        safe_print(f"   Ví dụ: python view_mongodb.py contents 1420052")
        
        client.close()
        
    except Exception as e:
        safe_print(f"❌ Lỗi: {e}")
        import traceback
        safe_print(traceback.format_exc())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "chapters":
            # Xem chapters
            web_story_id = sys.argv[2] if len(sys.argv) > 2 else None
            view_chapters(web_story_id)
        elif sys.argv[1] == "contents":
            # Xem chapter contents
            web_story_id = sys.argv[2] if len(sys.argv) > 2 else None
            view_chapter_contents(web_story_id)
        else:
            # Xem chi tiết một truyện
            fiction_id = sys.argv[1]
            view_detail(fiction_id)
    else:
        # Xem danh sách tất cả truyện
        view_data()

