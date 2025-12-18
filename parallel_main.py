# -*- coding: utf-8 -*-
"""
Parallel Main - Entry point cho parallel crawling system
Sử dụng multi-threading để cào nhiều stories đồng thời
"""

import sys
import os
import traceback
from pathlib import Path
from src import config
from src.parallel_crawler import ParallelCrawler
from src.scrapers import safe_print
# JSON file saving has been disabled: stories are persisted directly to DB


def main():
    """Main entry point for parallel crawling"""
    
    # ========== ĐỌC STORY URLs TỪ FILE ==========
    # Có thể dùng story_urls.txt hoặc test_category_urls.txt
    BASE_DIR = Path(__file__).resolve().parent
    url_file = BASE_DIR / 'story_urls.txt'
    
    # Uncomment để test category crawling
    # url_file = 'test_category_urls.txt'
    
    try:
        with url_file.open('r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        safe_print(f"❌ Lỗi: Không tìm thấy file {url_file}")
        safe_print(f"   Tạo file {url_file} và dán URLs vào")
        return
    
    # Filter và clean URLs (bỏ comment và blank lines)
    story_urls = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            story_urls.append(line)
    
    if not story_urls:
        safe_print("❌ Lỗi: Không có URL nào trong story_urls.txt")
        safe_print("   Vui lòng dán URLs story vào file")
        return
    
    safe_print(f"\n{'='*60}")
    safe_print(f"📋 Total Input URLs: {len(story_urls)}")
    safe_print(f"{'='*60}")
    
    # ========== CẤU HÌNH PARALLEL CRAWLING ========="
    safe_print(f"\n{'='*60}")
    safe_print("⚙️  Cấu hình Parallel Crawling:")
    safe_print(f"   Story workers: {config.MAX_STORY_WORKERS}")
    safe_print(f"   Chapter workers per story: {config.MAX_CHAPTER_WORKERS}")
    safe_print(f"   Max chapters/story: {config.MAX_CHAPTERS_PER_STORY or 'Unlimited'}")
    safe_print(f"   Max comments/chapter: {config.MAX_COMMENTS_PER_CHAPTER or 'Unlimited'}")
    safe_print(f"   Rate limit: {config.MAX_REQUESTS_PER_MINUTE} requests/minute")
    safe_print(f"   Random delay: {config.PARALLEL_RANDOM_DELAY_MIN}-{config.PARALLEL_RANDOM_DELAY_MAX}s")
    safe_print(f"{'='*60}\n")
    
    # ========== KHỞI TạO PARALLEL CRAWLER ==========
    crawler = ParallelCrawler(
        max_story_workers=config.MAX_STORY_WORKERS,
        max_chapter_workers=config.MAX_CHAPTER_WORKERS
    )
    
    try:
        # ========== CRAWL PARALLEL ==========
        # crawl_stories_from_urls() tự động xử lý:
        # - Story IDs
        # - Story URLs
        # - Category/Browse pages
        results = crawler.crawl_stories_from_urls(story_urls)
        
        # ========== LƯU KẾT QUẢ ==========
        # JSON export disabled — stories are persisted directly to the database
        if results:
            saved_count = len(results)
            safe_print(f"\n💾 Đã lưu {saved_count} stories trực tiếp vào DB (không xuất JSON).\n")
        else:
            safe_print("\n⚠️ Không có data để lưu")
            saved_count = 0
        
        # ========== SUMMARY ==========
        safe_print(f"\n{'='*60}")
        safe_print("📊 FINAL SUMMARY")
        safe_print(f"   Total URLs input: {len(story_urls)}")
        safe_print(f"   Successfully crawled: {len(results)}")
        safe_print(f"   Files saved: {saved_count}")
        safe_print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        safe_print("\n⚠️ Crawl interrupted by user (Ctrl+C)")
    except Exception as e:
        safe_print(f"\n❌ Lỗi chương trình: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    # ========== TÙY CHỈNH CẤU HÌNH (Optional) ==========
    # Uncomment để override config mặc định:
    
    # Story-level parallelism (số stories cào đồng thời)
    # config.MAX_STORY_WORKERS = 5  # 3-5 recommended
    
    # Chapter-level parallelism (số chapters cào đồng thời mỗi story)
    # config.MAX_CHAPTER_WORKERS = 3  # 2-3 recommended
    
    # Limits (để test nhanh)
    # config.MAX_CHAPTERS_PER_STORY = 5  # Lấy 5 chapters đầu mỗi story
    # config.MAX_COMMENTS_PER_CHAPTER = 10  # Lấy 10 comments đầu mỗi chapter
    
    # Rate limiting (cẩn thận với anti-ban)
    # config.MAX_REQUESTS_PER_MINUTE = 30  # Giảm nếu bị ban
    # config.PARALLEL_RANDOM_DELAY_MIN = 2.0  # Tăng delay nếu bị detect
    # config.PARALLEL_RANDOM_DELAY_MAX = 4.0
    
    main()
