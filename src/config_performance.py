"""
Cấu hình tối ưu hiệu suất - Tăng tốc độ crawl/sync
Sử dụng file này thay cho config.py để có tốc độ cao hơn
"""
import os

# --- CẤU HÌNH HỆ THỐNG ---
BASE_URL = "https://www.royalroad.com"

# Thư mục lưu trữ
DATA_DIR = "data"
JSON_DIR = os.path.join(DATA_DIR, "json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")

# Tạo thư mục nếu chưa có
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# ========== CẤU HÌNH TỐI ƯU HIỆU SUẤT ==========

# Cấu hình Bot - TỐI ƯU TỐC ĐỘ
TIMEOUT = 30000  # 30 giây (giảm từ 60s)
HEADLESS = True  # Luôn chạy ngầm để nhanh hơn

# Delays - GIẢM ĐỂ TĂNG TỐC (cẩn thận với rate limiting)
DELAY_BETWEEN_CHAPTERS = 0.5  # Giảm từ 2s → 0.5s
DELAY_BETWEEN_REQUESTS = 1  # Giảm từ 5s → 1s (có thể giảm thêm nếu không bị ban)
DELAY_THREAD_START = 0.1  # Giảm từ 0.5s → 0.1s

# Parallel Processing - TĂNG SỐ WORKERS
MAX_WORKERS = 8  # Tăng từ 3 → 8 (hoặc cao hơn nếu CPU/RAM cho phép)
MAX_FICTION_WORKERS = 3  # Số fiction crawl song song cùng lúc (có thể tăng lên 4-5)
# Lưu ý: Tăng quá cao có thể bị ban IP hoặc tốn tài nguyên

# Browser Pool - Tái sử dụng browsers
BROWSER_POOL_SIZE = 4  # Số browser instances trong pool
REUSE_BROWSERS = True  # Tái sử dụng browsers thay vì tạo mới

# MongoDB - Tối ưu connection
MONGODB_MAX_POOL_SIZE = 50  # Tăng connection pool
MONGODB_MIN_POOL_SIZE = 10
MONGODB_BULK_WRITE = True  # Dùng bulk operations

# Batch Sizes - Tăng batch để xử lý nhiều hơn
METADATA_BATCH_SIZE = 20  # Tăng từ 10 → 20
CHAPTER_BATCH_SIZE = 10  # Tăng từ 5 → 10
CHAPTERS_PER_FICTION = 20  # Tăng từ 10 → 20

# Sync Intervals - Giảm để sync thường xuyên hơn
METADATA_SYNC_INTERVAL = 300  # 5 phút (giảm từ 10 phút)
CHAPTER_SYNC_INTERVAL = 900  # 15 phút (giảm từ 30 phút)

# Smart Sync - Chỉ sync những gì cần
SKIP_UNCHANGED = True  # Bỏ qua chapters không thay đổi
PARALLEL_SYNC = True  # Sync nhiều fiction song song

# --- CẤU HÌNH MONGODB ---
MONGODB_ENABLED = True
MONGODB_USERNAME = "ngohoangtruongdat2_db_user"
MONGODB_PASSWORD = "DatMongo2025!"
CLUSTER_URL = "project.uoeyhrh.mongodb.net"

MONGODB_DB_NAME = "royalroad_db"
MONGODB_COLLECTION_FICTIONS = "fictions"

# Connection string với pool settings
MONGODB_URI = (
    f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}"
    f"@{CLUSTER_URL}/?retryWrites=true&w=majority&appName=Project"
    f"&maxPoolSize={MONGODB_MAX_POOL_SIZE}&minPoolSize={MONGODB_MIN_POOL_SIZE}"
)

# Cho phép override bằng environment variable (ưu tiên)
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")

