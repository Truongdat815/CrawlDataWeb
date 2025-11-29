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
TIMEOUT = 60000  # 60 giây
HEADLESS = True # True = Chạy ngầm, False = Hiện trình duyệt
DELAY_BETWEEN_CHAPTERS = 2 # Giây - Delay giữa các chương
DELAY_BETWEEN_REQUESTS = 5 # Giây - Delay giữa các request để tránh ban IP
DELAY_THREAD_START = 0.5 # Giây - Delay để stagger các thread khi bắt đầu
MAX_WORKERS = 3  # Số thread để cào chapters song song