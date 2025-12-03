# 🚀 Cải thiện ScribbleHub Scraper

## ✅ Đã thực hiện

### 1. Anti-Detection System
- ✅ Thêm User-Agent giống browser thật
- ✅ Thêm headers đầy đủ (Accept, Accept-Language, etc.)
- ✅ Ẩn webdriver property
- ✅ Ẩn các dấu hiệu automation khác (chrome.runtime, plugins, languages)
- ✅ Thêm args `--disable-blink-features=AutomationControlled`

**File:** `src/handlers/base_handler.py`

### 2. Human Behavior Simulation
- ✅ Giả lập scroll ngẫu nhiên
- ✅ Di chuyển chuột ngẫu nhiên
- ✅ Delay ngẫu nhiên giữa các hành động

**File:** `src/handlers/base_handler.py` - Method `simulate_human_behavior()`

### 3. ScribbleHub-Specific Delays
- ✅ Delays riêng cho ScribbleHub (cẩn thận hơn):
  - `SCRIBBLEHUB_DELAY_BETWEEN_REQUESTS = 8` giây (tăng từ 5)
  - `SCRIBBLEHUB_DELAY_BETWEEN_CHAPTERS = 3` giây (tăng từ 2)
  - `SCRIBBLEHUB_MAX_WORKERS = 2` (giảm từ 3)

**File:** `src/config.py`

### 4. Helper Functions
- ✅ `get_delay_between_requests()` - Tự động chọn delay phù hợp
- ✅ `get_delay_between_chapters()` - Tự động chọn delay phù hợp
- ✅ `get_max_workers()` - Tự động chọn số workers phù hợp

**File:** `src/config.py`

### 5. Test Script
- ✅ File `test_scribblehub.py` để test với URL cụ thể

## 📝 Cách sử dụng

### Test với URL cụ thể:

```bash
python test_scribblehub.py
```

File này sẽ scrape story:
`https://www.scribblehub.com/series/1266790/dao-of-money-xianxia-business/`

### Chạy scraper bình thường:

```bash
python main.py
```

## ⚙️ Cấu hình

### Bật/tắt Anti-Detection:

Trong `src/config.py`:
```python
ENABLE_ANTI_DETECTION = True  # Bật anti-detection
ENABLE_HUMAN_BEHAVIOR = True  # Bật giả lập hành vi người dùng
```

### Điều chỉnh Delays:

```python
# Delays riêng cho ScribbleHub
SCRIBBLEHUB_DELAY_BETWEEN_REQUESTS = 8  # Có thể tăng/giảm
SCRIBBLEHUB_DELAY_BETWEEN_CHAPTERS = 3  # Có thể tăng/giảm
SCRIBBLEHUB_MAX_WORKERS = 2  # Có thể tăng/giảm
```

## 🔍 Các tính năng Anti-Detection

1. **User-Agent**: Giống Chrome thật
2. **Headers**: Đầy đủ như browser thật
3. **Webdriver Property**: Đã ẩn
4. **Chrome Runtime**: Giả lập
5. **Plugins**: Giả lập
6. **Languages**: Giả lập
7. **Human Behavior**: Scroll và mouse movement ngẫu nhiên

## ⚠️ Lưu ý

- Delays cao hơn = An toàn hơn nhưng chậm hơn
- Nếu vẫn bị chặn, tăng delays lên
- Nếu không bị chặn, có thể giảm delays xuống
- Luôn test với 1-2 stories trước khi chạy hàng loạt

## 🎯 Kết quả mong đợi

Với các cải thiện này:
- ✅ Giảm khả năng bị phát hiện là bot
- ✅ Giảm khả năng bị chặn IP
- ✅ Tăng tỷ lệ thành công khi scrape
- ✅ Giữ được tốc độ hợp lý

## 📊 So sánh

| Tính năng | Trước | Sau |
|-----------|-------|-----|
| Anti-Detection | ❌ Không có | ✅ Đầy đủ |
| Human Behavior | ❌ Không có | ✅ Có |
| Delays | 5s/2s | 8s/3s (ScribbleHub) |
| Workers | 3 | 2 (ScribbleHub) |


