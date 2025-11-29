# Hướng dẫn Tối ưu Hiệu suất - Tăng tốc độ Crawl/Sync

## 🚀 Các cách tăng tốc độ

### 1. ⚡ Giảm Delays (Nhanh nhất - Rủi ro bị ban IP)

**File: `src/config.py`**

```python
# Trước (chậm):
DELAY_BETWEEN_REQUESTS = 5  # 5 giây
DELAY_BETWEEN_CHAPTERS = 2  # 2 giây

# Sau (nhanh hơn):
DELAY_BETWEEN_REQUESTS = 1  # 1 giây (giảm 5x)
DELAY_BETWEEN_CHAPTERS = 0.5  # 0.5 giây (giảm 4x)
```

**Lưu ý:** 
- ⚠️ Giảm quá nhiều có thể bị ban IP
- ✅ Bắt đầu với 1-2 giây, test xem có bị ban không
- ✅ Nếu không bị ban, có thể giảm xuống 0.5-1 giây

### 2. 🔥 Tăng số Workers (Parallel Processing)

**File: `src/config.py`**

```python
# Trước:
MAX_WORKERS = 3  # 3 threads

# Sau:
MAX_WORKERS = 8  # 8 threads (tăng 2.6x)
# Hoặc cao hơn nếu CPU/RAM cho phép: 10, 12, 16...
```

**Lưu ý:**
- ✅ Tăng workers = tăng tốc độ crawl chapters song song
- ⚠️ Tăng quá cao có thể:
  - Tốn RAM (mỗi browser ~200-500MB)
  - Bị ban IP (quá nhiều requests cùng lúc)
  - CPU quá tải

**Khuyến nghị:**
- CPU 4 cores: MAX_WORKERS = 4-6
- CPU 8 cores: MAX_WORKERS = 8-12
- CPU 16+ cores: MAX_WORKERS = 12-16

### 3. 📦 Sử dụng Config Performance

**Copy file config:**
```bash
# Backup config hiện tại
cp src/config.py src/config_backup.py

# Sử dụng config tối ưu
cp src/config_performance.py src/config.py
```

**Hoặc import trực tiếp:**
```python
# Trong code, thay vì:
from src import config

# Dùng:
import src.config_performance as config
```

### 4. 🎯 Tối ưu MongoDB Operations

**Sử dụng Bulk Operations:**

```python
from pymongo import UpdateOne
from src.performance_optimizer import BulkMongoWriter

# Thay vì update từng document:
for fiction in fictions:
    collection.update_one({"id": fiction_id}, {"$set": data})

# Dùng bulk write:
writer = BulkMongoWriter(collection, batch_size=100)
for fiction in fictions:
    writer.add_update({"id": fiction_id}, data)
writer.close()
```

**Tăng Connection Pool:**
```python
# Trong config:
MONGODB_MAX_POOL_SIZE = 50  # Tăng từ mặc định
MONGODB_MIN_POOL_SIZE = 10
```

### 5. 🔄 Browser Pool (Tái sử dụng Browsers)

**Sử dụng Browser Pool thay vì tạo mới:**

```python
from src.performance_optimizer import BrowserPool

# Khởi tạo pool
browser_pool = BrowserPool(pool_size=4)
browser_pool.initialize()

# Sử dụng
browser = browser_pool.get_browser()
# ... dùng browser ...
browser_pool.return_browser(browser)

# Đóng pool
browser_pool.close_all()
```

**Lợi ích:**
- ✅ Giảm thời gian khởi động browser (từ ~2s → ~0.1s)
- ✅ Tiết kiệm tài nguyên

### 6. ⚡ Parallel Sync

**Sync nhiều fictions song song:**

```python
from src.performance_optimizer import parallel_sync_fictions

# Sync tuần tự (chậm):
for fiction in fictions:
    sync_fiction(fiction)

# Sync song song (nhanh):
parallel_sync_fictions(sync_fiction, fictions, max_workers=5)
```

### 7. 🎯 Smart Delay

**Giảm delay nếu không có lỗi:**

```python
from src.performance_optimizer import smart_delay

# Thay vì delay cố định:
time.sleep(config.DELAY_BETWEEN_REQUESTS)

# Dùng smart delay:
delay = smart_delay(
    base_delay=config.DELAY_BETWEEN_REQUESTS,
    success_count=success_count,
    error_count=error_count
)
time.sleep(delay)
```

### 8. 📊 Tăng Batch Sizes

**File: `src/config.py` hoặc `src/config_performance.py`**

```python
# Sync workers:
METADATA_BATCH_SIZE = 20  # Tăng từ 10 → 20
CHAPTER_BATCH_SIZE = 10   # Tăng từ 5 → 10
CHAPTERS_PER_FICTION = 20 # Tăng từ 10 → 20
```

### 9. 🚫 Block Resources không cần thiết

**Block images/CSS để tăng tốc load page:**

```python
from src.performance_optimizer import optimize_page_load

page = browser.new_page()
page = optimize_page_load(page)  # Block images
```

**Lưu ý:** Chỉ dùng nếu không cần images

### 10. ⏱️ Giảm Timeout

**File: `src/config.py`**

```python
# Trước:
TIMEOUT = 60000  # 60 giây

# Sau:
TIMEOUT = 30000  # 30 giây (nhanh hơn 2x)
```

## 📊 So sánh Tốc độ

### Trước khi tối ưu:
- Delay: 5 giây/request
- Workers: 3
- **Tốc độ:** ~0.2 requests/giây

### Sau khi tối ưu:
- Delay: 1 giây/request (giảm 5x)
- Workers: 8 (tăng 2.6x)
- **Tốc độ:** ~8 requests/giây (**Tăng ~40x**)

## ⚠️ Lưu ý quan trọng

### 1. Rate Limiting
- ⚠️ Tăng tốc quá nhiều có thể bị ban IP
- ✅ Test từ từ: bắt đầu với delay 2s, giảm dần
- ✅ Monitor lỗi: nếu có nhiều lỗi → tăng delay lại

### 2. Tài nguyên hệ thống
- ⚠️ Tăng workers → tăng RAM/CPU usage
- ✅ Monitor: `htop` hoặc Task Manager
- ✅ Không tăng quá khả năng máy

### 3. MongoDB Limits
- ⚠️ Quá nhiều connections → có thể bị limit
- ✅ Dùng connection pooling
- ✅ Dùng bulk operations

## 🎯 Khuyến nghị Cấu hình

### Cấu hình An toàn (Không bị ban):
```python
DELAY_BETWEEN_REQUESTS = 2
DELAY_BETWEEN_CHAPTERS = 1
MAX_WORKERS = 4
```

### Cấu hình Cân bằng:
```python
DELAY_BETWEEN_REQUESTS = 1
DELAY_BETWEEN_CHAPTERS = 0.5
MAX_WORKERS = 6-8
```

### Cấu hình Tối đa (Rủi ro cao):
```python
DELAY_BETWEEN_REQUESTS = 0.5
DELAY_BETWEEN_CHAPTERS = 0.2
MAX_WORKERS = 10-12
```

## 🔧 Cách áp dụng

### Bước 1: Backup config hiện tại
```bash
cp src/config.py src/config_backup.py
```

### Bước 2: Sử dụng config performance
```bash
# Option 1: Copy file
cp src/config_performance.py src/config.py

# Option 2: Chỉnh sửa config.py trực tiếp
```

### Bước 3: Test với số lượng nhỏ
```python
# Test với 1-2 fictions trước
bot.scrape_best_rated_fictions(url, num_fictions=2)
```

### Bước 4: Monitor và điều chỉnh
- Xem có bị ban IP không
- Xem tốc độ có tăng không
- Điều chỉnh delays/workers nếu cần

## 📈 Kết quả mong đợi

Với cấu hình tối ưu:
- ✅ **Tốc độ crawl:** Tăng 5-10x
- ✅ **Tốc độ sync:** Tăng 3-5x
- ✅ **Thời gian crawl 1000 chapters:** Từ ~14 giờ → ~2-3 giờ

## 🚀 Quick Start

```bash
# 1. Sử dụng config performance
cp src/config_performance.py src/config.py

# 2. Chạy với cấu hình mới
python main.py

# 3. Monitor và điều chỉnh nếu cần
```

