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
# ⚠️ QUAN TRỌNG: HEADLESS = False để pass Cloudflare dễ hơn
# Cloudflare thường chặn headless browser, nên để False để browser hiển thị
HEADLESS = False # True = Chạy ngầm (dễ bị Cloudflare chặn), False = Hiện trình duyệt (pass Cloudflare tốt hơn)
DELAY_BETWEEN_CHAPTERS = 2 # Giây - Delay giữa các chương
DELAY_BETWEEN_REQUESTS = 5 # Giây - Delay giữa các request để tránh ban IP
DELAY_THREAD_START = 0.5 # Giây - Delay để stagger các thread khi bắt đầu
MAX_WORKERS = 3  # Số thread để cào chapters song song

# ========== CẤU HÌNH RIÊNG CHO SCRIBBLEHUB ==========
# Delays riêng cho ScribbleHub (cẩn thận hơn để tránh bị chặn)
SCRIBBLEHUB_DELAY_BETWEEN_REQUESTS = 8  # Tăng từ 5 → 8 giây
SCRIBBLEHUB_DELAY_BETWEEN_CHAPTERS = 3  # Tăng từ 2 → 3 giây
SCRIBBLEHUB_MAX_WORKERS = 1  # Giảm xuống 1 worker để tránh quá nhiều requests (tránh bị flag bot)

# Cấu hình anti-detection
ENABLE_ANTI_DETECTION = True  # Bật anti-detection
ENABLE_HUMAN_BEHAVIOR = True  # Bật giả lập hành vi người dùng

# ========== CẤU HÌNH CLOUDFLARE ==========
# Thời gian đợi Cloudflare challenge (giây) - TĂNG LÊN để pass challenge tốt hơn
CLOUDFLARE_MAX_WAIT = 180  # Thời gian tối đa đợi Cloudflare challenge (tăng lên 180 giây = 3 phút)
CLOUDFLARE_CHECK_DELAY = 5  # Delay sau khi goto để kiểm tra Cloudflare
CLOUDFLARE_CHALLENGE_DELAY = 15  # Delay thêm nếu phát hiện challenge
CLOUDFLARE_POST_PASS_DELAY = 15  # Delay sau khi detect challenge pass
CLOUDFLARE_VERIFY_WAIT = 30  # Thời gian đợi sau khi verify (TĂNG lên 30 giây để đảm bảo)

# ========== CẤU HÌNH COOKIES & SESSION ==========
# Lưu cookies sau khi verify để không phải verify lại
ENABLE_COOKIE_PERSISTENCE = True  # Bật lưu cookies

# ========== REAL BROWSER MODE (Khuyên dùng) ==========
# Dùng launch_persistent_context với user_data_dir để dùng real Chrome profile
# → navigator.webdriver = undefined (real browser)
# → Cookies được giữ tự động
# → Verify 1 lần duy nhất, scrape suốt không loop
USE_PERSISTENT_CONTEXT = True  # Bật persistent context (real browser mode)
USER_DATA_DIR = "user-data"  # Thư mục lưu Chrome profile (tự động tạo)
# Hoặc dùng Chrome profile có sẵn: "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"

# ========== CẤU HÌNH SCRAPING METHOD ==========
# ✅ CÁCH 5: Dùng requests cho chapter scraping (không dùng Playwright)
USE_REQUESTS_FOR_CHAPTERS = True  # Dùng requests cho chapters → không bị detect như bot
SCRAPE_CHAPTERS_SEQUENTIAL = True  # Scrape tuần tự (không parallel) → tránh bị flag bot

# ========== CẤU HÌNH MANUAL VERIFY ==========
# Nếu bật, code sẽ đợi user verify thủ công và bấm Enter để tiếp tục
ENABLE_MANUAL_VERIFY = True  # Bật chế độ đợi verify thủ công

# --- CẤU HÌNH MONGODB ---
MONGODB_ENABLED = True
MONGODB_USERNAME = "ngohoangtruongdat2_db_user"
MONGODB_PASSWORD = "DatMongo2025!"
CLUSTER_URL = "project.uoeyhrh.mongodb.net"

MONGODB_DB_NAME = "RoyalRoadData"
MONGODB_COLLECTION_STORIES = "stories"
MONGODB_COLLECTION_STORY_INFO = "story_info"

# Connection string đầy đủ với các options chuẩn
# Dùng password trực tiếp, KHÔNG encode
MONGODB_URI = (
    f"mongodb+srv://{MONGODB_USERNAME}:{MONGODB_PASSWORD}"
    f"@{CLUSTER_URL}/?retryWrites=true&w=majority&appName=Project"
)

# Cho phép override bằng environment variable (ưu tiên)
if os.getenv("MONGODB_URI"):
    MONGODB_URI = os.getenv("MONGODB_URI")

# ========== HELPER FUNCTIONS ==========
def get_delay_between_requests():
    """Lấy delay giữa các requests (ưu tiên ScribbleHub nếu đang scrape ScribbleHub)"""
    # Có thể kiểm tra BASE_URL hoặc flag để quyết định
    if BASE_URL == "https://www.scribblehub.com":
        return SCRIBBLEHUB_DELAY_BETWEEN_REQUESTS
    return DELAY_BETWEEN_REQUESTS

def get_delay_between_chapters():
    """Lấy delay giữa các chapters (ưu tiên ScribbleHub nếu đang scrape ScribbleHub)"""
    if BASE_URL == "https://www.scribblehub.com":
        return SCRIBBLEHUB_DELAY_BETWEEN_CHAPTERS
    return DELAY_BETWEEN_CHAPTERS

def get_max_workers():
    """Lấy số workers (ưu tiên ScribbleHub nếu đang scrape ScribbleHub)"""
    if BASE_URL == "https://www.scribblehub.com":
        return SCRIBBLEHUB_MAX_WORKERS
    return MAX_WORKERS