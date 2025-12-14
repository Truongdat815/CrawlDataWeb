"""
Script migrate toàn bộ field names từ snake_case sang camelCase
Chạy 1 lần để update toàn bộ code
"""
import os
import re

# Mapping snake_case → camelCase
FIELD_MAPPING = {
    # Story fields
    "story_id": "storyId",
    "web_story_id": "webStoryId",
    "story_name": "storyName",
    "story_url": "storyUrl",
    "cover_image": "coverImage",
    "user_id": "userId",
    "total_chapters": "totalChapters",
    "story_hash": "storyHash",
    
    # Chapter fields
    "chapter_id": "chapterId",
    "web_chapter_id": "webChapterId",
    "chapter_name": "chapterName",
    "chapter_url": "chapterUrl",
    "published_time": "publishedTime",
    "total_comments": "totalComments",
    
    # Chapter content fields
    "content_id": "contentId",
    
    # Comment fields
    "comment_id": "commentId",
    "web_comment_id": "webCommentId",
    "comment_text": "commentText",
    "reply_to_user_id": "replyToUserId",
    "parent_id": "parentId",
    "is_root": "isRoot",
    "website_id": "websiteId",
    "is_deleted": "isDeleted",
    
    # Review fields
    "review_id": "reviewId",
    "web_review_id": "webReviewId",
    "score_id": "scoreId",
    "is_review_swap": "isReviewSwap",
    
    # Score fields
    "overall_score": "overallScore",
    "style_score": "styleScore",
    "story_score": "storyScore",
    "grammar_score": "grammarScore",
    "character_score": "characterScore",
    
    # User fields
    "web_user_id": "webUserId",
    "user_url": "userUrl",
    "created_date": "createdDate",
    "number_of_stories": "numberOfStories",
    "total_words": "totalWords",
    "total_reviews_received": "totalReviewsReceived",
    "total_ratings_received": "totalRatingsReceived",
    "total_favorites_received": "totalFavoritesReceived",
    
    # Story Info fields
    "info_id": "infoId",
    "total_views": "totalViews",
    "average_views": "averageViews",
    "page_views": "pageViews",
    "free_chapter": "freeChapter",
    "time_to_finish": "timeToFinish",
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
    "user_dropped": "userDropped",
    
    # Website fields
    "website_name": "websiteName",
    
    # Other
    "web_story_ids": "webStoryIds",
    "chapter_1_hash": "chapter1Hash",
}

def migrate_file(file_path):
    """Migrate một file Python"""
    if not os.path.exists(file_path):
        print(f"⏭️  Bỏ qua {file_path} (không tồn tại)")
        return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes = []
    
    # Thay thế từng field
    for snake, camel in FIELD_MAPPING.items():
        # Pattern để match field names (trong dict keys, queries, etc.)
        patterns = [
            # Dict keys: "snake_case"
            (f'"{snake}"', f'"{camel}"'),
            # Dict keys: 'snake_case'
            (f"'{snake}'", f"'{camel}'"),
            # .get("snake_case")
            (f'.get("{snake}"', f'.get("{camel}"'),
            (f".get('{snake}'", f".get('{camel}'"),
            # ["snake_case"]
            (f'["{snake}"]', f'["{camel}"]'),
            (f"['{snake}']", f"['{camel}']"),
        ]
        
        for old, new in patterns:
            if old in content:
                count = content.count(old)
                content = content.replace(old, new)
                if count > 0:
                    changes.append(f"  {snake} → {camel}: {count} lần")
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Đã migrate {file_path}")
        for change in changes[:10]:  # Hiển thị 10 thay đổi đầu
            print(change)
        if len(changes) > 10:
            print(f"  ... và {len(changes) - 10} thay đổi khác")
    else:
        print(f"⏭️  Không có thay đổi trong {file_path}")

def main():
    """Migrate toàn bộ project"""
    print("🚀 Bắt đầu migrate snake_case → camelCase")
    print("=" * 80)
    
    # Lấy thư mục gốc của project
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Danh sách files cần migrate
    files = [
        os.path.join(base_dir, "src", "handlers", "mongo_handler.py"),
        os.path.join(base_dir, "src", "handlers", "story_handler.py"),
        os.path.join(base_dir, "src", "handlers", "chapter_handler.py"),
        os.path.join(base_dir, "src", "handlers", "comment_handler.py"),
        os.path.join(base_dir, "src", "handlers", "review_handler.py"),
        os.path.join(base_dir, "src", "handlers", "user_handler.py"),
        os.path.join(base_dir, "src", "handlers", "glossary_handler.py"),
    ]
    
    for file_path in files:
        migrate_file(file_path)
        print()
    
    print("=" * 80)
    print("✅ Hoàn tất migration!")

if __name__ == "__main__":
    main()
