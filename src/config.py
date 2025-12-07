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

# ========== BROWSER & BOT CONFIGURATION ==========
TIMEOUT = 60  # 60 giây
HEADLESS = True  # True = Chạy ngầm (tiết kiệm tài nguyên), False = Hiện trình duyệt
# ⚠️ Lưu ý: Code đã tích hợp stealth plugins để tránh bị phát hiện bot

# ========== HTTP & PROXY CONFIGURATION ==========
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Playwright settings
PLAYWRIGHT_PROFILE_DIR = os.path.join(DATA_DIR, "playwright_profile")
PLAYWRIGHT_USER_AGENT = DEFAULT_USER_AGENT
PLAYWRIGHT_USE_STEALTH = True

# Optional proxy configuration (None để không dùng proxy)
PROXIES = []
HTTP_PROXY = None
HTTPS_PROXY = None

# ========== RATE LIMITING & ERROR HANDLING ==========
MAX_RETRIES = 3  # Số lần retry nếu request thất bại
RETRY_BACKOFF = 2  # Multiplier cho exponential backoff (1s, 2s, 4s, 8s...)
MAX_REQUESTS_PER_MINUTE = 60  # Rate limit: 60 requests/phút (dùng cho shared rate limiter)
REQUEST_TIMEOUT = 30  # Timeout cho mỗi HTTP request (giây)

# ========== PARALLEL CRAWLING CONFIGURATION ==========
# 🚀 Tốc độ crawl (dùng multi-threading)
MAX_STORY_WORKERS = 3  # Số stories cào song song (recommended: 3-5)
MAX_CHAPTER_WORKERS = 2  # Số chapters cào song song mỗi story (recommended: 2-3)

# 🎲 Random delays giữa các requests (anti-bot detection)
PARALLEL_RANDOM_DELAY_MIN = 1.0  # Min delay (seconds)
PARALLEL_RANDOM_DELAY_MAX = 3.0  # Max delay (seconds)

# 🔄 Retry & Recovery
MAX_STORY_RETRIES = 2  # Số lần retry cho failed stories (0 = no retry) - DEPRECATED, use per-chapter retry instead
MAX_CHAPTER_RETRIES = 3  # Số lần retry cho failed chapters (per API step)
RETRY_DELAY = 5.0  # Delay trước khi retry (seconds)

# ✅ Per-Chapter Retry Settings
RETRY_BACKOFF_INITIAL = 1.0  # Initial backoff time (seconds)
RETRY_BACKOFF_MAX = 60.0  # Maximum backoff time
RETRY_BACKOFF_MULTIPLIER = 2.0  # Exponential backoff multiplier

# 📊 Progress tracking
ENABLE_CHECKPOINTS = True  # Lưu tiến độ để resume sau
CHECKPOINT_INTERVAL = 10  # Save checkpoint mỗi N stories
CHECKPOINT_FILE = os.path.join(DATA_DIR, "crawl_checkpoint.json")
CHECKPOINT_DIR = os.path.join(DATA_DIR, "checkpoints")  # Per-chapter checkpoints directory

# ========== SCRAPING LIMITS ==========
MAX_CHAPTERS_PER_STORY = 3  # None = Tất cả, số = Tối đa N chapters
MAX_COMMENTS_PER_CHAPTER = 10  # None = Tất cả, số = Tối đa N comments
MAX_STORIES_PER_BATCH = 2

# ========== WATTPAD LOGIN CREDENTIALS ==========
WATTPAD_USERNAME = "buonnguqua"
WATTPAD_PASSWORD = "Abcdefgh123@"

# ========== COOKIE & SESSION MANAGEMENT ==========
# 🍪 Cookie reuse để tránh login multiple times
COOKIE_FILE = os.path.join(DATA_DIR, "wattpad_cookies.json")  # Lưu cookie từ login duy nhất
COOKIE_REFRESH_INTERVAL = 30 * 60  # Refresh cookie mỗi 30 phút (seconds)
# ⚠️ QUAN TRỌNG: Login 1 lần → tất cả threads reuse cookie từ file
#              Không login trong mỗi thread (tránh account lock / IP ban)
SKIP_LOGIN_IF_COOKIE_EXISTS = True  # Nếu cookie file tồn tại, bỏ qua login

# ========== MONGODB CONFIGURATION ==========
MONGODB_ENABLED = True
"""
# ========== MONGODB SELF-HOSTED (CURRENT) ==========
MONGODB_USERNAME = "user"
MONGODB_PASSWORD = "56915001"
MONGODB_HOST = "103.90.224.232"
MONGODB_PORT = "27017"
MONGODB_DB_NAME = "my_database"
MONGODB_COLLECTION_STORIES = "stories"
MONGODB_COLLECTION_CHAPTERS = "chapters"
MONGODB_COLLECTION_COMMENTS = "comments"

MONGODB_URI = f"mongodb://{MONGODB_USERNAME}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DB_NAME}"

# Allow override via environment variable
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")

    
"""


# ========== MONGODB ATLAS (OLD - COMMENTED FOR REFERENCE) ==========
MONGODB_USERNAME = "xuannguyentruong15"
MONGODB_PASSWORD = "grXsKiSEOf3APbRD"
MONGODB_CLUSTER_URL = "crawl.ujyutza.mongodb.net"
MONGODB_DB_NAME = "WattpadData"
MONGODB_URI = "mongodb+srv://xuannguyentruong15:grXsKiSEOf3APbRD@crawl.ujyutza.mongodb.net/?appName=Crawl"
MONGODB_COLLECTION_STORIES = "stories"
MONGODB_COLLECTION_CHAPTERS = "chapters"
MONGODB_COLLECTION_COMMENTS = "comments"