import json
import os
from pymongo import MongoClient

# ==========================================
# CONFIGURATION
# ==========================================
MONGO_URI = "mongodb://localhost:27017/my_database"
DB_NAME = "my_database"
INPUT_DIR = 'data/json_final'

# Danh sách collection cần import (Đúng thứ tự ưu tiên)
COLLECTIONS = [
    'stories', 'storyInfo', 'chapters', 'chapterContents', 
    'websites', 'rankings', 'comments', 'users', 'reviews', 'scores'
]

def import_file(db, filepath):
    print(f"📂 Đang đọc file: {os.path.basename(filepath)}")
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Duyệt qua từng loại collection trong file JSON
    for col_name in COLLECTIONS:
        items = data.get(col_name, [])
        if items:
            # DEBUG: Kiểm tra soi dữ liệu trước khi nạp
            if col_name == 'comments':
                valid_sample = next((c for c in items if c.get('commentText') and c.get('chapterId')), None)
                if valid_sample:
                    print(f"   👀 [DEBUG Comments] Mẫu sắp nạp: {valid_sample.get('commentText')[:30]}... | ChapID: {valid_sample.get('chapterId')}")
                else:
                    print(f"   ⚠️ [DEBUG Comments] Không tìm thấy comment nào có text trong lô này??")

            try:
                # Dùng insert_many: Nhanh và giữ nguyên vẹn dữ liệu
                db[col_name].insert_many(items)
                print(f"   ✅ Đã nạp {len(items)} dòng vào bảng '{col_name}'")
            except Exception as e:
                print(f"   ❌ Lỗi nạp bảng '{col_name}': {e}")

    # In tên truyện để biết file nào
    story_name = "Unknown"
    if data.get('stories') and len(data['stories']) > 0:
        story_name = data['stories'][0].get('storyName', 'Unknown')
    print(f"🎉 Hoàn tất truyện: {story_name}\n")

def main():
    print(f"🔌 Connecting to: {MONGO_URI}")
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        print(f"🔗 Connected DB: {DB_NAME}")
        
        # --- 1. XÓA SẠCH DATABASE CŨ ---
        print("\n🧹 [BƯỚC 1] ĐANG XÓA SẠCH DỮ LIỆU CŨ...")
        for col in COLLECTIONS:
            db[col].drop()
        print("✨ Database đã trắng tinh! Sẵn sàng nạp mới.\n")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return

    if not os.path.exists(INPUT_DIR):
        print(f"❌ Folder '{INPUT_DIR}' not found!")
        return

    files = [f for f in os.listdir(INPUT_DIR) if f.startswith('final_') and f.endswith('.json')]
    
    if not files:
        print("⚠️ No final JSON files found. Run transform_data.py first.")
        return

    print(f"🚀 [BƯỚC 2] BẮT ĐẦU IMPORT ({len(files)} files)...")
    
    for f_name in files:
        try:
            import_file(db, os.path.join(INPUT_DIR, f_name))
        except Exception as e:
            print(f"❌ Critical Error importing {f_name}: {e}")

    print("\n🏁 TẤT CẢ ĐÃ XONG! HÃY KIỂM TRA MONGODB.")

if __name__ == "__main__":
    main()