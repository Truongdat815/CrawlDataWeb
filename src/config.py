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

# Cấu hình Bot
TIMEOUT = 120000  # 120 seconds (increased to allow heavy pages to finish)
HEADLESS = False # True = Chạy ngầm, False = Hiện trình duyệt (để debug comments)
DELAY_BETWEEN_CHAPTERS = 2 # Giây - Delay giữa các chương
DELAY_BETWEEN_REQUESTS = 5 # Giây - Delay giữa các request để tránh ban IP
DELAY_THREAD_START = 0.5 # Giây - Delay để stagger các thread khi bắt đầu
MAX_WORKERS = 3  # Số thread để cào chapters song song

# Playwright fallback configuration
USE_PLAYWRIGHT_FALLBACK = True
PLAYWRIGHT_STORAGE_STATE = os.path.join('data', 'cookies', 'webnovel_storage_state.json')
PLAYWRIGHT_TIMEOUT_MS = 120000
DEBUG_OUTPUT_DIR = os.path.join('data', 'debug')

# --- CẤU HÌNH MONGODB ---
MONGODB_ENABLED = True  # Tạm tắt để test (credentials cần update)
MONGODB_USERNAME = "ahkhoinguyen169_db_user"
MONGODB_PASSWORD = "Y8mA9QwH0G4ROF70!"
CLUSTER_URL = "cluster0.fbu9egx.mongodb.net"

MONGODB_DB_NAME = "webnovel_db"
# Collection names - tách riêng như bạn của bạn
MONGODB_COLLECTION_STORIES = "stories"
MONGODB_COLLECTION_CHAPTERS = "chapters"
MONGODB_COLLECTION_COMMENTS = "comments"
MONGODB_COLLECTION_REVIEWS = "reviews"
MONGODB_COLLECTION_SCORES = "scores"
MONGODB_COLLECTION_USERS = "users"
# Giữ lại collection cũ để tương thích (có thể xóa sau)
MONGODB_COLLECTION_FICTIONS = "fictions"

# Connection string đầy đủ với các options chuẩn
# Dùng password trực tiếp, KHÔNG encode
# MONGODB_URI = (
#     f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}"
#     f"@{CLUSTER_URL}/?retryWrites=true&w=majority&appName=Project"
# )

MONGODB_URI = ("mongodb://user:56915001@103.90.224.232:27017/my_database")

# Cho phép override bằng environment variable (ưu tiên)
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")