import json
import os

# Đường dẫn folder chứa file raw json
INPUT_DIR = 'data/json'

def analyze_keys():
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Không tìm thấy thư mục {INPUT_DIR}")
        return

    # Lấy file json đầu tiên tìm thấy
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
    if not files:
        print("❌ Không có file JSON nào để kiểm tra.")
        return
    
    # Chọn file đầu tiên để soi
    target_file = os.path.join(INPUT_DIR, files[0])
    print(f"🔍 Đang kiểm tra file: {files[0]}\n")

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. KIỂM TRA CHAPTER COMMENTS (Comment trong chương)
        print("1️⃣  KIỂM TRA CHAPTER COMMENTS:")
        chapters = data.get('chapters', [])
        if chapters and len(chapters) > 0:
            first_chap = chapters[0]
            comments = first_chap.get('comments', [])
            if comments and len(comments) > 0:
                print(f"   ✅ Tìm thấy {len(comments)} comment trong chương đầu.")
                print(f"   🔑 Các Key có trong 1 comment mẫu: {list(comments[0].keys())}")
                print(f"   📄 Mẫu dữ liệu: {json.dumps(comments[0], indent=2, ensure_ascii=False)[:300]}...")
            else:
                print("   ⚠️  Chương đầu tiên không có comment nào.")
        else:
            print("   ⚠️  Không tìm thấy chapters.")

        print("\n" + "-"*50 + "\n")

        # 2. KIỂM TRA REVIEW REPLIES (Trả lời đánh giá)
        print("2️⃣  KIỂM TRA REVIEW REPLIES (Book Comments):")
        reviews = data.get('comments', []) # Trong scraper gọi là comments, schema gọi là reviews
        if reviews and len(reviews) > 0:
            first_review = reviews[0]
            replies = first_review.get('replies', [])
            if replies and len(replies) > 0:
                print(f"   ✅ Tìm thấy {len(replies)} reply trong review đầu.")
                print(f"   🔑 Các Key có trong 1 reply mẫu: {list(replies[0].keys())}")
                print(f"   📄 Mẫu dữ liệu: {json.dumps(replies[0], indent=2, ensure_ascii=False)[:300]}...")
            else:
                print("   ⚠️  Review đầu tiên không có reply nào.")
        else:
            print("   ⚠️  Không tìm thấy book comments (reviews).")

    except Exception as e:
        print(f"❌ Lỗi khi đọc file: {e}")

if __name__ == "__main__":
    analyze_keys()