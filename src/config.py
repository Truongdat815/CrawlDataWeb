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
TIMEOUT = 60  # 60 giây
HEADLESS = False # True = Chạy ngầm, False = Hiện trình duyệt

# ========== RATE LIMITING & ERROR HANDLING ==========
# Rate limiting để tránh ban IP từ Wattpad
REQUEST_DELAY = 1.0  # Giây - Delay giữa các request (default: 1 giây)
MAX_RETRIES = 3  # Số lần retry nếu request thất bại
RETRY_BACKOFF = 2  # Multiplier cho exponential backoff (1s, 2s, 4s, 8s...)
MAX_REQUESTS_PER_MINUTE = 60  # Rate limit: max 60 requests/phút
REQUEST_TIMEOUT = 30  # Timeout cho mỗi request (giây)

# ========== HTTP & PROXY CONFIGURATION ==========
# Connection pooling headers và proxy để tránh bị block
# User-Agent và headers mặc định cho mọi HTTP requests
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Playwright settings
# Directory to store persistent profile (cookies, localStorage)
PLAYWRIGHT_PROFILE_DIR = os.path.join(DATA_DIR, "playwright_profile")
# Playwright user agent override (defaults to DEFAULT_USER_AGENT)
PLAYWRIGHT_USER_AGENT = DEFAULT_USER_AGENT
# Use stealth-sync integration if available
PLAYWRIGHT_USE_STEALTH = True

# Optional list of proxy servers to rotate through (strings like 'http://user:pass@host:port')
# If empty, will fallback to HTTP_PROXY / HTTPS_PROXY
PROXIES = []

# Optional proxy configuration (None để không dùng proxy)
# Ví dụ: "http://user:pass@proxy.example.com:3128"
HTTP_PROXY = None
HTTPS_PROXY = None

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

# Multi-Threading Parallel Crawling (NEW)
MAX_STORY_WORKERS = 3  # Số stories cào song song (3-5 recommended)
MAX_CHAPTER_WORKERS = 2  # Số chapters cào song song mỗi story (2-3 recommended)
USE_PARALLEL_CRAWLING = True  # Enable/disable parallel crawling
PARALLEL_RANDOM_DELAY_MIN = 1.0  # Min delay giữa requests (seconds)
PARALLEL_RANDOM_DELAY_MAX = 3.0  # Max delay giữa requests (seconds)

# Retry & Recovery Configuration
MAX_STORY_RETRIES = 2  # Số lần retry cho failed stories (0 = no retry)
RETRY_DELAY = 5.0  # Delay trước khi retry (seconds)

# Progress Checkpoint Configuration
ENABLE_CHECKPOINTS = True  # Enable progress checkpoints
CHECKPOINT_INTERVAL = 10  # Save checkpoint mỗi N stories
CHECKPOINT_FILE = os.path.join(DATA_DIR, "crawl_checkpoint.json")  # Checkpoint file path

# ========== CẤU HÌNH TỐI ƯU (Uncomment để dùng) ==========
# DELAY_BETWEEN_CHAPTERS = 0.5  # Tăng tốc 4x
# DELAY_BETWEEN_REQUESTS = 1   # Tăng tốc 5x
# MAX_WORKERS = 8              # Tăng tốc 2.6x
# ⚠️ Cảnh báo: Có thể bị ban IP nếu tăng tốc quá nhiều

# ========== SCRAPING LIMITS ==========
# Giới hạn số lượng chapters và comments khi cào
MAX_CHAPTERS_PER_STORY = 10  # None = Lấy tất cả, số = Tối đa N chapters
MAX_COMMENTS_PER_CHAPTER = 10  # None = Lấy tất cả, số = Tối đa N comments
MAX_STORIES_PER_BATCH = 5  # Tối đa 100 stories khi scrape batch

# ========== WATTPAD LOGIN CREDENTIALS ==========
# Thêm credentials để tự động đăng nhập
# Để trống nếu muốn dùng cookies từ file
WATTPAD_USERNAME = "buonnguqua"
WATTPAD_PASSWORD = "Abcdefgh123@"

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