import os

# --- CẤU HÌNH HỆ THỐNG ---
BASE_URL = "https://www.scribblehub.com"

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
DELAY_BETWEEN_CHAPTERS = 2 # Giây - Delay giữa các chương
DELAY_BETWEEN_REQUESTS = 5 # Giây - Delay giữa các request để tránh ban IP
DELAY_THREAD_START = 0.5 # Giây - Delay để stagger các thread khi bắt đầu
MAX_WORKERS = 3  # Số thread để cào chapters song song

# --- CẤU HÌNH MONGODB ---
MONGODB_ENABLED = True
# Sử dụng environment variables để bảo mật (ưu tiên)
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "ngohoangtruongdat2_db_user")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "DatMongo2025!")
CLUSTER_URL = os.getenv("MONGODB_CLUSTER_URL", "project.uoeyhrh.mongodb.net")

MONGODB_DB_NAME = "scribblehub_db"
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
MONGODB_URI = (
    f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}"
    f"@{CLUSTER_URL}/?retryWrites=true&w=majority&appName=Project"
)

# Cho phép override bằng environment variable (ưu tiên)
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")