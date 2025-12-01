# Scrapers Module - Modular Architecture

## Cấu trúc thư mục

```
src/
├── scraper_engine.py      (Main orchestrator - quản lý browser, calls scrapers)
└── scrapers/              (Modular scrapers for each collection)
    ├── __init__.py        (Package exports)
    ├── base.py            (BaseScraper class - shared functionality)
    ├── story.py           (StoryScraper - story metadata)
    ├── chapter.py         (ChapterScraper - chapter content)
    ├── review.py          (ReviewScraper - story reviews)
    ├── comment.py         (CommentScraper - comments)
    ├── user.py            (UserScraper - user/author data)
    └── score.py           (ScoreScraper - rating scores)
```

## Mô tả từng module

### `base.py` - BaseScraper
- Base class cho tất cả scrapers
- Chứa common utilities:
  - `safe_print()` - UTF-8 safe printing
  - `BaseScraper` - class cơ sở với page/mongo_db/config references
  - Collection management helpers

**Ưu điểm:**
- Tránh code duplication
- Unified error handling
- Consistent interface

### `story.py` - StoryScraper
**Responsibilities:**
- Cào metadata của bộ truyện (title, description, stats, etc)
- Trích xuất scores (overall, style, story, grammar, character)
- Trích xuất stats (views, followers, ratings, etc)
- Lưu story vào MongoDB collection `stories`

**Methods:**
- `scrape_story_metadata(story_url)` - main method
- `_extract_description()` - parse description HTML
- `_extract_scores()` - lấy điểm đánh giá
- `_extract_stats()` - lấy thống kê
- `save_story_to_mongo(story_data)` - lưu DB

### `chapter.py` - ChapterScraper
**Responsibilities:**
- Cào nội dung từng chapter
- Lấy comments cho chapter
- Lưu chapter vào MongoDB collection `chapters`

**Methods:**
- `scrape_chapter(chapter_url, story_id)` - main method
- `_extract_chapter_id()` - parse chapter ID từ URL
- `_extract_chapter_title()` - lấy title
- `_extract_chapter_content()` - lấy nội dung HTML
- `_scrape_chapter_comments()` - cào comments
- `save_chapter_to_mongo()` - lưu DB

### `review.py` - ReviewScraper
**Responsibilities:**
- Cào reviews của bộ truyện
- Parse từng review element
- Lưu review vào MongoDB collection `reviews`
- Trigger user save cho reviewer

**Methods:**
- `scrape_reviews(story_url, story_id)` - main method
- `_parse_review(review_elem, story_id)` - parse single review
- `_extract_review_*()` - extract individual fields
- `save_review_to_mongo()` - lưu DB

### `comment.py` - CommentScraper
**Responsibilities:**
- Lưu comments vào MongoDB collection `comments`
- Simple wrapper for comment storage

**Methods:**
- `save_comment_to_mongo(comment_data)` - lưu comment

### `user.py` - UserScraper
**Responsibilities:**
- Lưu user/author info vào MongoDB collection `users`
- Update user nếu username thay đổi

**Methods:**
- `save_user_to_mongo(user_id, username)` - lưu user

### `score.py` - ScoreScraper
**Responsibilities:**
- Lưu rating scores vào MongoDB collection `scores`

**Methods:**
- `save_score_to_mongo(score_id, ...)` - lưu scores

## Cách sử dụng

### Từ `scraper_engine.py`:
```python
class RoyalRoadScraper:
    def start(self):
        # Initialize scrapers
        self.story_scraper = StoryScraper(self.page, self.mongo_db)
        self.chapter_scraper = ChapterScraper(self.page, self.mongo_db)
        self.review_scraper = ReviewScraper(self.page, self.mongo_db)
        # ... etc
    
    def scrape_story(self, story_url):
        # Use scrapers
        story_data = self.story_scraper.scrape_story_metadata(story_url)
        reviews = self.review_scraper.scrape_reviews(story_url, story_id)
```

### Độc lập (ví dụ):
```python
from src.scrapers import StoryScraper
from pymongo import MongoClient

mongo_db = MongoClient(uri)[db_name]
scraper = StoryScraper(page, mongo_db)
story_data = scraper.scrape_story_metadata(url)
```

## Lợi ích của kiến trúc này

✅ **Modular** - Mỗi collection có module riêng, dễ maintain  
✅ **Reusable** - Các scraper có thể dùng độc lập  
✅ **Testable** - Mỗi module có thể unit test riêng  
✅ **Scalable** - Thêm collection mới = thêm file mới  
✅ **Clear separation** - Business logic tách biệt rõ ràng  
✅ **Backward compatible** - `scraper_engine.py` vẫn hoạt động như cũ  

## Tiếp theo có thể làm

1. **Unit tests** - Thêm tests cho từng scraper
2. **Async support** - Chuyển sang async/await nếu cần
3. **Caching** - Cache results trước khi lưu DB
4. **Error recovery** - Retry logic cho failed requests
5. **Progress tracking** - Lưu progress trước khi crash
