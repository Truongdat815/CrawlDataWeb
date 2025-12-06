import os

# --- CẤU HÌNH HỆ THỐNG ---
BASE_URL = "https://www.webnovel.com"

# Thư mục lưu trữ dữ liệu
DATA_DIR = "data"
JSON_DIR = os.path.join(DATA_DIR, "json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
BATCH_OUTPUT_DIR = os.path.join(DATA_DIR, "batch_output")  # Thêm folder cho Batch Scraping

# Tạo các thư mục cần thiết nếu chưa có
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(BATCH_OUTPUT_DIR, exist_ok=True)

# --- CẤU HÌNH BOT SCRAPER ---
TIMEOUT = 60000       # 60s là đủ cho domcontentloaded
HEADLESS = True       # Mặc định chạy ẩn để tối ưu hiệu suất khi cào nhiều
FAST_MODE = True      # Chặn ảnh/font để tăng tốc độ tải trang
DELAY_BETWEEN_CHAPTERS = 2
DELAY_BETWEEN_BOOKS = 10

# --- CẤU HÌNH MONGODB (TEAM SERVER - FINAL SCHEMA) ---
MONGODB_ENABLED = True

# Team VPS MongoDB Connection
MONGODB_URI = "mongodb://user:56915001@103.90.224.232:27017/my_database"
DB_NAME = "my_database"

# Final Schema Collections
COL_STORIES = "stories"
COL_CHAPTERS = "chapters"
COL_CHAPTER_CONTENTS = "chapter_contents"
COL_COMMENTS = "comments"
COL_USERS = "users"
COL_REVIEWS = "reviews"
COL_WEBSITES = "websites"
COL_RANKINGS = "rankings"
COL_SCORES = "scores"

# Backward compatibility
MONGODB_DB_NAME = DB_NAME
MONGODB_COLLECTION_STORIES = COL_STORIES

# Allow environment variable override
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")
if os.getenv("DB_NAME"):
    DB_NAME = os.getenv("DB_NAME")

# --- CẤU HÌNH FALLBACK & DEBUG (Thêm vào cuối file - SÁT LỀ TRÁI) ---
USE_PLAYWRIGHT_FALLBACK = True
PLAYWRIGHT_TIMEOUT_MS = 60000
DEBUG_OUTPUT_DIR = os.path.join(DATA_DIR, "debug")
os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)

# --- CẤU HÌNH COOKIE PATH ---
PLAYWRIGHT_STORAGE_STATE = os.path.join(DATA_DIR, "cookies.json")