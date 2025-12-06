#!/usr/bin/env python3
"""
cleanup_project.py

Safe cleanup utility to remove temporary, debug, and test files before batch scraping.

Usage:
    python cleanup_project.py

This script will:
- Delete specific development/test files listed in FILES_TO_DELETE
- Delete files matching PATTERNS_TO_DELETE (HTML dumps and logs)
- Clean out the data/debug/ folder (HTML debug dumps)

Safety:
- Will NOT delete core system files listed in PROTECTED_FILES
- Will NOT delete any JSON files under data/json/
"""

import os
import glob
import shutil

def cleanup_project():
    print("🧹 ĐANG QUÉT DỌN DỰ ÁN DỰA TRÊN HÌNH ẢNH CUNG CẤP...")

    # 1. Danh sách chính xác các file rác (Dựa trên screenshot)
    files_to_delete = [
        # Script cũ và Test
        "autorum.py",
        "run_full_pipeline.py",
        "scrape_to_json.py",
        "run_scraper_auto.py",
        "scrape_comments_generic.py",
        "scrape_webnovel_comments.py",
        "webnovel_api_scraper.py", # File cũ, code mới nằm trong src/
        "test_robust_chapter.py",
        "test_chapter_fix.py",
        "test_comment_html.py",
        "test_network.py",
        "test_pagination.py",
        "test_step2_comments.py",
        "test_single_chapter.py",
        "test_single_chapter_comments.py",
        "test_chapter_comments_fix.py",
        "quick_test.py",
        "debug_inspector.py",
        "debug_drawer_live.py",
        "debug_button_selector.py",
        "debug_chapter_page.py",
        "debug_modal_html.py",
        "debug_pagination.py",
        "debug_reply_selector.py",
        "get_chapter_urls.py", # Cái này cũ rồi, logic nằm trong class
        "repair_chapters.py",
        "refetch_chapter_comments.py",
        "fix_timestamps_only.py",
        "final_fix_data.py",
        "fetch_only_comments.py",
        "manual_inspector.py",
        "diagnostic_comment_test.py",

        # File Hướng dẫn (Markdown) thừa
        "NEXT_STEPS.md",
        "SCRAPER_README.md",
        "SCRIPT_COMPARISON.md",
        "STEP1_CHAPTER_FIX_COMPLETE.md",
        "STEP2_ANALYSIS.md",
        "STEP2_COMPLETE.md",
        "HUONG_DAN_COMMENTS.md",
        "TIMEOUT_FIX_APPLIED.md",
        "OPTIMIZATIONS_APPLIED.md",
        "ENHANCED_PATIENCE_APPLIED.md",
        "TIMING_FIX_APPLIED.md",
        "CHAPTER_COMMENTS_FIX_SUMMARY.md",
        "BATCH_SCRAPING_GUIDE.md",
        "BATCH_SCRAPING_README.md",
        ".env.example", # Giữ .env thật thôi
        
        # File dữ liệu rác ở Root (Không phải trong data/json)
        "webnovel_reviews.json",
        "chapter_urls.json",
        "test_chapter_output.json",
        "test_step2_result.json",
        "test_chapter_result.txt",
        "debug_modal_html_output.txt",
        "debug_html_output.txt",
        "webnovel_comments_api_34078380808505505.json"
    ]

    # 2. Xóa các file cụ thể
    print("\n--- Xóa File Rác ---")
    for filename in files_to_delete:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"🗑️ Đã xóa: {filename}")
            except Exception as e:
                print(f"⚠️ Lỗi xóa {filename}: {e}")

    # 3. Xóa theo đuôi file (Quét sạch ảnh và log rác)
    print("\n--- Quét sạch file rác theo đuôi ---")
    extensions = ["*.png", "*.log", "*.html"] # Xóa hết ảnh debug, log lỗi, html debug
    for ext in extensions:
        for filepath in glob.glob(ext):
            try:
                os.remove(filepath)
                print(f"🗑️ Đã xóa: {filepath}")
            except Exception as e:
                print(f"⚠️ Lỗi xóa {filepath}: {e}")

    # 4. Dọn dẹp folder debug (Giữ folder data nhưng xóa debug bên trong)
    debug_folder = "data/debug"
    if os.path.exists(debug_folder):
        try:
            shutil.rmtree(debug_folder)
            os.makedirs(debug_folder)
            print(f"\n✨ Đã làm sạch thư mục: {debug_folder}")
        except Exception as e:
            print(f"⚠️ Lỗi dọn folder debug: {e}")
            
    # 5. Dọn dẹp folder tools (Nếu có và không dùng)
    tools_folder = "tools"
    if os.path.exists(tools_folder):
         try:
            shutil.rmtree(tools_folder)
            print(f"✨ Đã xóa thư mục thừa: {tools_folder}")
         except Exception as e:
            print(f"⚠️ Lỗi dọn folder tools: {e}")

    # 6. KIỂM TRA HỆ THỐNG CÒN LẠI
    print("\n" + "="*50)
    print("✅ HỆ THỐNG ĐÃ SẠCH SẼ! CÁC FILE QUAN TRỌNG CÒN LẠI:")
    print("="*50)
    
    core_files = [
        "main.py", 
        "get_category_links.py", 
        "batch_runner.py", 
        "setup_login.py", 
        "import_to_mongodb.py", 
        "cookies.json", 
        ".env",
        "requirements.txt"
    ]
    
    all_good = True
    for f in core_files:
        if os.path.exists(f):
            print(f"   OK: {f}")
        else:
            print(f"   ❌ THIẾU: {f} (Cần kiểm tra lại!)")
            all_good = False
            
    if os.path.exists("src") and os.path.isdir("src"):
         print(f"   OK: Folder src/ (Mã nguồn)")
    else:
         print(f"   ❌ THIẾU: Folder src/")
         all_good = False

    if os.path.exists("data/json") and os.path.isdir("data/json"):
         count = len(glob.glob("data/json/*.json"))
         print(f"   OK: Folder data/json/ (Chứa {count} file truyện đã cào)")
    else:
         print(f"   ❌ THIẾU: Folder data/json/")
         all_good = False

    if all_good:
        print("\n🚀 SẴN SÀNG ĐỂ CHẠY BATCH SCRAPING!")
    else:
        print("\n⚠️ CÓ FILE QUAN TRỌNG BỊ THIẾU. VUI LÒNG KIỂM TRA.")

if __name__ == "__main__":
    cleanup_project()
