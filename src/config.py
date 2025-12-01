import os

# --- CẤU HÌNH HỆ THỐNG ---
BASE_URL = "https://www.wattpad.com"

# Thư mục lưu trữ
DATA_DIR = "data"
JSON_DIR = os.path.join(DATA_DIR, "json")
IMAGES_DIR = os.path.join(DATA_DIR, "images")

# Tạo thư mục nếu chưa có
os.makedirs(JSON_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# Cấu hình Bot
TIMEOUT = 60000  # 60 giây
HEADLESS = True # True = Chạy ngầm, False = Hiện trình duyệt

# ========== CẤU HÌNH TỐC ĐỘ ==========
# ⚠️ Lưu ý: Giảm delays có thể tăng tốc nhưng cũng tăng rủi ro bị ban IP
# ✅ Khuyến nghị: Bắt đầu với giá trị mặc định, test và giảm dần nếu không bị ban

# Delays - Giảm để tăng tốc (cẩn thận với rate limiting)
DELAY_BETWEEN_CHAPTERS = 2 # Giây - Delay giữa các chương (có thể giảm xuống 0.5-1)
DELAY_BETWEEN_REQUESTS = 5 # Giây - Delay giữa các request để tránh ban IP (có thể giảm xuống 1-2)
DELAY_THREAD_START = 0.5 # Giây - Delay để stagger các thread khi bắt đầu (có thể giảm xuống 0.1)

# Parallel Processing - Tăng để crawl nhanh hơn (tốn nhiều RAM/CPU hơn)
MAX_WORKERS = 3  # Số thread để cào chapters song song (có thể tăng lên 6-10 nếu CPU/RAM cho phép)
MAX_FICTION_WORKERS = 2  # Số fiction crawl song song cùng lúc (có thể tăng lên 3-5)

# ========== CẤU HÌNH TỐI ƯU (Uncomment để dùng) ==========
# DELAY_BETWEEN_CHAPTERS = 0.5  # Tăng tốc 4x
# DELAY_BETWEEN_REQUESTS = 1   # Tăng tốc 5x
# MAX_WORKERS = 8              # Tăng tốc 2.6x
# ⚠️ Cảnh báo: Có thể bị ban IP nếu tăng tốc quá nhiều

# --- CẤU HÌNH MONGODB ---
MONGODB_ENABLED = True
MONGODB_USERNAME = "xuannguyentruong15"
MONGODB_PASSWORD = "grXsKiSEOf3APbRD"
CLUSTER_URL = "crawl.ujyutza.mongodb.net"

MONGODB_DB_NAME = "WattpadData"
MONGODB_COLLECTION_STORIES = "stories"

# Connection string đầy đủ với các options chuẩn
# Dùng password trực tiếp, KHÔNG encode
# MONGODB_URI = (
#     f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}"
#     f"@{CLUSTER_URL}/?appName=Crawl"
# )
MONGODB_URI = (
   "mongodb+srv://xuannguyentruong15:grXsKiSEOf3APbRD@crawl.ujyutza.mongodb.net/?appName=Crawl"
)

# Cho phép override bằng environment variable (ưu tiên)
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")