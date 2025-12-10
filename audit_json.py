import json
import os

INPUT_DIR = 'data/json_final'

def audit():
    print("🕵️‍♂️ ĐANG KIỂM TRA CHẤT LƯỢNG FILE JSON FINAL...\n")
    
    files = [f for f in os.listdir(INPUT_DIR) if f.startswith('final_') and f.endswith('.json')]
    if not files:
        print("❌ Không tìm thấy file final json.")
        return

    total_good = 0
    total_bad = 0

    for f_name in files:
        path = os.path.join(INPUT_DIR, f_name)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        comments = data.get('comments', [])
        file_good = 0
        file_bad = 0
        
        # Kiểm tra từng comment
        for i, c in enumerate(comments):
            # Tiêu chuẩn: Phải có Text và (WebID hoặc ChapterID)
            has_text = c.get('commentText') is not None and c.get('commentText') != "null"
            has_id = c.get('webCommentId') is not None and c.get('webCommentId') != "null"
            
            if has_text and has_id:
                file_good += 1
            else:
                file_bad += 1
                # In thử 3 lỗi đầu tiên để soi
                if file_bad <= 3:
                    print(f"⚠️ [LỖI] Dòng {i} trong file {f_name} bị thiếu dữ liệu:")
                    print(f"   - Text: {c.get('commentText')}")
                    print(f"   - WebID: {c.get('webCommentId')}")
                    print(f"   - ChapID: {c.get('chapterId')}")
                    print("-" * 30)

        print(f"📂 File: {f_name}")
        print(f"   ✅ Dữ liệu TỐT: {file_good}")
        print(f"   ❌ Dữ liệu RÁC (Null): {file_bad}")
        print("="*50)
        
        total_good += file_good
        total_bad += file_bad

    print(f"\n📊 TỔNG KẾT TOÀN BỘ:")
    print(f"   ✅ Tổng dòng XỊN: {total_good}")
    print(f"   ❌ Tổng dòng RÁC: {total_bad}")

    if total_bad > 0:
        print("\n👉 KẾT LUẬN: Code Transform vẫn đang để lọt dữ liệu rác vào file JSON.")
        print("   Hãy gửi kết quả này cho tôi để tôi chặn lỗ hổng đó lại.")
    else:
        print("\n👉 KẾT LUẬN: File JSON hoàn hảo 100%. Nếu DB vẫn null thì lỗi do MongoDB Compass hiển thị sai.")

if __name__ == "__main__":
    audit()