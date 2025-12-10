import json
import os
import shutil
import uuid6
import requests
from datetime import datetime
from utils import calculate_story_hash  # Import hàm tính hash

# ... (Giữ nguyên phần Cấu hình và các hàm safe_get, safe_str...) ...
# ==============================================================================
# CẤU HÌNH HỆ THỐNG
# ==============================================================================
INPUT_DIR = 'data/json'
OUTPUT_DIR = 'data/json_final'
WEBNOVEL_WEBSITE_ID = "wn_019b3870-1234-7567-89ab-cdef01234567"
API_UPLOAD_URL = "https://api-image.techleaf.pro/api/upload"
API_DOMAIN = "https://api-image.techleaf.pro"
API_KEY = "k8JdR4xP9uA2mQ7wF1zT0bVgN5yHcS3LrE8qWfU6pXjK2dM9sB4hY0vG7tC1n"
uploaded_cache = {}

def generate_id(): return f"wn_{uuid6.uuid7()}"

def safe_get(data, key, default=None):
    if isinstance(data, dict): return data.get(key, default)
    return default

def safe_str(value):
    if value is None: return None
    s = str(value).strip()
    if not s or s.lower() == "null": return None
    return s

def safe_int(value):
    if value is None or value == "null" or value == "": return None
    if isinstance(value, (int, float)): return int(value)
    s = str(value).upper().replace(',', '').strip()
    try:
        if 'M' in s: return int(float(s.replace('M', '')) * 1000000)
        if 'K' in s: return int(float(s.replace('K', '')) * 1000)
        return int(float(s))
    except: return None

def safe_float(value):
    if value is None or value == "null" or value == "": return None
    try: return float(value)
    except: return None

def parse_date(time_str):
    if not time_str or str(time_str).lower() == "null": return None
    return str(time_str)

# ... (Hàm process_cover_image giữ nguyên như cũ) ...
def process_cover_image(image_path_or_url):
    if not image_path_or_url or image_path_or_url == "null": return None
    if image_path_or_url in uploaded_cache: return uploaded_cache[image_path_or_url]
    try:
        files = None
        temp_file_name = None
        if os.path.exists(image_path_or_url):
            print(f"   📤 Đang upload ảnh từ local: {image_path_or_url}...")
            files = {'image': open(image_path_or_url, 'rb')}
        elif image_path_or_url.startswith('http'):
            # print(f"   ⬇️  Đang tải ảnh từ URL: {image_path_or_url}...")
            try:
                img_resp = requests.get(image_path_or_url, timeout=10)
                if img_resp.status_code == 200:
                    temp_file_name = f"temp_cover_{uuid6.uuid7()}.jpg"
                    with open(temp_file_name, 'wb') as f: f.write(img_resp.content)
                    files = {'image': open(temp_file_name, 'rb')}
                else: return None
            except: return None
        else: return None

        if files:
            headers = {'x-api-key': API_KEY}
            try:
                response = requests.post(API_UPLOAD_URL, headers=headers, files=files)
                files['image'].close()
                if temp_file_name and os.path.exists(temp_file_name): os.remove(temp_file_name)
                if response.status_code == 200:
                    resp_json = response.json()
                    path = None
                    if isinstance(resp_json, dict):
                        if 'local_path' in resp_json: path = resp_json['local_path']
                        elif 'data' in resp_json and isinstance(resp_json['data'], dict):
                            path = resp_json['data'].get('local_path')
                    if path:
                        full_url = f"{API_DOMAIN}{path}"
                        uploaded_cache[image_path_or_url] = full_url
                        return full_url
            except Exception:
                if files: files['image'].close()
                if temp_file_name and os.path.exists(temp_file_name): os.remove(temp_file_name)
    except Exception: return None
    return None

def transform_json(raw_data, filename):
    story_oid = generate_id()
    website_oid = WEBNOVEL_WEBSITE_ID
    info_oid = generate_id()

    raw_chapters = raw_data.get('chapters', []) or []
    raw_comments = raw_data.get('comments', []) or []
    raw_ratings = raw_data.get('ratings', {}) or {}
    
    users_map = {} 

    def get_user_id(name, web_id=None):
        name_val = safe_str(name)
        if name_val is None: name_val = "Anonymous"
        if name_val not in users_map:
            users_map[name_val] = {
                "userId": generate_id(), "webUserId": safe_str(web_id), "username": name_val,
                "userUrl": None, "createdDate": None, "gender": None, "location": None,
                "followers": None, "following": None, "comments": None, "bio": None,
                "favorites": None, "ratings": None, "reviews": None, "numberOfStories": None,
                "totalWords": None, "totalReviewsReceived": None, "totalRatingsReceived": None,
                "totalFavoritesReceived": None
            }
        return users_map[name_val]["userId"]

    author_name = safe_get(raw_data, 'author', 'Unknown')
    author_oid = get_user_id(author_name)
    
    # --- LOGIC TÍNH SIMHASH ---
    # 1. Tìm Chapter 1 (Order = 1)
    chapter_1_content = ""
    # Sắp xếp chapters theo order để tìm chap 1 chính xác
    sorted_raw_chapters = sorted(raw_chapters, key=lambda x: safe_int(x.get('order')) or 9999)
    if sorted_raw_chapters:
        # Giả định chapter đầu tiên sau khi sort là chapter 1
        chapter_1_content = safe_str(sorted_raw_chapters[0].get('content')) or ""
    
    # 2. Tạo Hash từ 500 ký tự đầu
    final_story_hash = calculate_story_hash(chapter_1_content)
    # --------------------------

    final_cover_url = process_cover_image(safe_get(raw_data, 'cover_image'))

    story_doc = {
        "storyId": story_oid, "webStoryId": safe_str(safe_get(raw_data, 'platform_id')),
        "storyName": safe_str(safe_get(raw_data, 'name')), "storyUrl": safe_str(safe_get(raw_data, 'url')),
        "coverImage": final_cover_url,
        "category": safe_str(safe_get(raw_data, 'category')),
        "status": safe_str(safe_get(raw_data, 'status')), "genres": safe_get(raw_data, 'tags', []) or [],
        "tags": safe_get(raw_data, 'tags', []) or [], "description": safe_str(safe_get(raw_data, 'description')),
        "userId": author_oid, "totalChapters": safe_int(safe_get(raw_data, 'total_chapters')),
        "language": "English", # Mặc định hoặc lấy từ raw
        "storyHash": final_story_hash # <--- FIELD QUAN TRỌNG
    }

    story_info_doc = {
        "infoId": info_oid, "storyId": story_oid, "websiteId": website_oid,
        "totalViews": safe_int(safe_get(raw_data, 'total_views')),
        "overallScore": safe_float(safe_get(raw_ratings, 'overall_score')),
        "ratingTotal": safe_int(safe_get(raw_ratings, 'total_ratings')),
        "totalReviews": len(raw_comments) if raw_comments else 0,
        "lastUpdated": parse_date(datetime.utcnow().isoformat()),
        # Các field điểm số chi tiết nếu có
        "styleScore": safe_float(safe_get(raw_ratings, 'world_background')),
        "storyScore": safe_float(safe_get(raw_ratings, 'story_development')),
        "grammarScore": safe_float(safe_get(raw_ratings, 'writing_quality')),
        "characterScore": safe_float(safe_get(raw_ratings, 'character_design')),
        # Các field khác set null
        "averageViews": None, "followers": None, "favorites": None, "pageViews": None,
        "voted": None, "freeChapter": None, "timeToFinish": None, "releaseRate": None,
        "numberOfReader": None, "totalViewsChapters": None, "totalWord": None, "averageWords": None,
        "userReading": None, "userPlanToRead": None, "userCompleted": None, "userPaused": None, "userDropped": None
    }

    chapters_list = []
    content_list = []
    comments_list = []
    reviews_list = []
    scores_list = []
    rankings_list = []

    # REVIEWS processing ... (Giữ nguyên logic cũ)
    for rv in raw_comments:
        if not isinstance(rv, dict): continue
        u_name = safe_get(rv, 'user_name')
        u_oid = get_user_id(u_name)
        
        rv_oid = generate_id()
        score_oid = generate_id()
        
        raw_score = safe_get(rv, 'score', {})
        overall_score = safe_float(raw_score.get('overall')) if isinstance(raw_score, dict) else safe_float(raw_score)

        reviews_list.append({
            "reviewId": rv_oid, "webReviewId": safe_str(safe_get(rv, 'comment_id') or safe_get(rv, 'webReviewId')),
            "title": None, "time": parse_date(safe_get(rv, 'time')), 
            "content": safe_str(safe_get(rv, 'content')),
            "userId": u_oid, "chapterId": None, "storyId": story_oid, "scoreId": score_oid,
            "isReviewSwap": False, "websiteId": website_oid, "isDeleted": False
        })
        scores_list.append({
            "scoreId": score_oid, "overallScore": overall_score, "styleScore": None, "storyScore": None,
            "grammarScore": None, "characterScore": None, "reviewId": rv_oid
        })

        # Replies
        for rep in safe_get(rv, 'replies', []):
            r_name = safe_get(rep, 'user_name')
            r_u_oid = get_user_id(r_name)
            comments_list.append({
                "commentId": generate_id(), 
                "webCommentId": safe_str(safe_get(rep, 'reply_id') or safe_get(rep, 'comment_id')), 
                "commentText": safe_str(safe_get(rep, 'content')),
                "time": parse_date(safe_get(rep, 'time')), 
                "chapterId": None, "userId": r_u_oid, "replyToUserId": u_oid, "parentId": rv_oid, 
                "isRoot": False, "react": None, "websiteId": website_oid, "isDeleted": False
            })

    # CHAPTERS processing ...
    for ch in raw_chapters:
        ch_oid = generate_id()
        chapters_list.append({
            "chapterId": ch_oid, "webChapterId": safe_str(safe_get(ch, 'id')), "storyId": story_oid,
            "order": safe_int(safe_get(ch, 'order')), "chapterName": safe_str(safe_get(ch, 'name')),
            "chapterUrl": safe_str(safe_get(ch, 'url')), "publishedTime": parse_date(safe_get(ch, 'published_time')),
            "voted": None, "views": None, "totalComments": len(safe_get(ch, 'comments', []))
        })
        
        # Chapter Content (Separated)
        content_text = safe_str(safe_get(ch, 'content'))
        if content_text:
            content_list.append({"contentId": generate_id(), "chapterId": ch_oid, "content": content_text})

        # Chapter Comments
        for cmt in safe_get(ch, 'comments', []):
            c_name = safe_get(cmt, 'user_name')
            c_oid = get_user_id(c_name)
            cmt_oid = generate_id()
            comments_list.append({
                "commentId": cmt_oid, "webCommentId": safe_str(safe_get(cmt, 'comment_id')), 
                "commentText": safe_str(safe_get(cmt, 'content')),
                "time": parse_date(safe_get(cmt, 'time')), 
                "chapterId": ch_oid, "userId": c_oid, "replyToUserId": None, "parentId": None, 
                "isRoot": True, "react": safe_int(safe_get(cmt, 'likes')), "websiteId": website_oid, "isDeleted": False
            })
            
            # Chapter Comment Replies
            for rep in safe_get(cmt, 'replies', []):
                r_name = safe_get(rep, 'user_name')
                r_u_oid = get_user_id(r_name)
                comments_list.append({
                    "commentId": generate_id(), "webCommentId": safe_str(safe_get(rep, 'reply_id')), 
                    "commentText": safe_str(safe_get(rep, 'content')),
                    "time": parse_date(safe_get(rep, 'time')), 
                    "chapterId": ch_oid, "userId": r_u_oid, "replyToUserId": c_oid, "parentId": cmt_oid, 
                    "isRoot": False, "react": None, "websiteId": website_oid, "isDeleted": False
                })

    if safe_get(raw_data, 'power_ranking_position'):
        rankings_list.append({
            "rankId": generate_id(), "rankName": safe_str(safe_get(raw_data, 'power_ranking_title')),
            "rankNumber": safe_int(safe_get(raw_data, 'power_ranking_position')), 
            "websiteId": website_oid, "storyId": story_oid
        })

    return {
        "stories": [story_doc], "storyInfo": [story_info_doc], "chapters": chapters_list,
        "chapterContents": content_list, "websites": [{"websiteId": website_oid, "websiteName": "Webnovel"}], 
        "rankings": rankings_list, "comments": comments_list, "users": list(users_map.values()), 
        "reviews": reviews_list, "scores": scores_list
    }

def main():
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
    print(f"🚀 Bắt đầu chuyển đổi ({len(files)} files) - Calculating SimHash (500 chars)...")
    for f_name in files:
        try:
            with open(os.path.join(INPUT_DIR, f_name), 'r', encoding='utf-8') as f:
                raw = json.load(f)
            final_data = transform_json(raw, f_name)
            out_name = f"final_{f_name}"
            with open(os.path.join(OUTPUT_DIR, out_name), 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Đã xong: {out_name}")
        except Exception as e:
            print(f"❌ Lỗi file {f_name}: {e}")

if __name__ == "__main__":
    main()