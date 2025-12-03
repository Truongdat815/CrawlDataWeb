# 🚀 Real Browser Mode - Giải pháp chuyên nghiệp cho Cloudflare

## ✅ Đã implement Real Browser Mode

### Vấn đề trước đây:
1. ❌ `navigator.webdriver = true` → Cloudflare detect automation
2. ❌ Cookies không được giữ → Phải verify lại nhiều lần
3. ❌ Cloudflare reload challenge sau khi verify → Loop vô hạn
4. ❌ Quá nhiều requests → Bị flag bot

### Giải pháp: Real Browser Mode với `launch_persistent_context`

**Cách hoạt động:**
- Dùng `launch_persistent_context` với `user_data_dir`
- → `navigator.webdriver = undefined` (real browser)
- → Cookies được giữ tự động trong `user_data_dir`
- → Verify 1 lần duy nhất, scrape suốt không loop

## 🎯 Cấu hình

**File: `src/config.py`**

```python
# ========== REAL BROWSER MODE (Khuyên dùng) ==========
USE_PERSISTENT_CONTEXT = True  # Bật persistent context (real browser mode)
USER_DATA_DIR = "user-data"  # Thư mục lưu Chrome profile (tự động tạo)
```

## 🚀 Cách sử dụng

### Bước 1: Cấu hình

Đảm bảo trong `src/config.py`:
```python
USE_PERSISTENT_CONTEXT = True
USER_DATA_DIR = "user-data"  # Hoặc path khác
HEADLESS = False  # Browser hiển thị
```

### Bước 2: Chạy lần đầu

```bash
python test_scribblehub.py
```

**Lần đầu:**
- Browser sẽ mở với real Chrome profile
- Verify Cloudflare thủ công 1 lần
- Cookies sẽ được lưu tự động trong `user-data/`

### Bước 3: Lần sau

```bash
python test_scribblehub.py
```

**Lần sau:**
- Browser sẽ dùng lại profile cũ
- Cookies đã được giữ → Không cần verify lại!
- Scrape suốt không loop

## 📁 User Data Directory

**Thư mục `user-data/`:**
- Tự động tạo khi chạy lần đầu
- Chứa Chrome profile (cookies, history, settings)
- Giữ giữa các lần chạy

**Xóa để reset:**
```bash
# Xóa thư mục user-data để reset
rm -rf user-data  # Linux/Mac
rmdir /s user-data  # Windows
```

## 🔍 So sánh

| Tính năng | launch() (cũ) | launch_persistent_context (mới) |
|-----------|---------------|----------------------------------|
| navigator.webdriver | true | undefined (real browser) |
| Cookies | Phải lưu thủ công | Tự động giữ |
| Verify | Nhiều lần | 1 lần duy nhất |
| Cloudflare loop | Có thể xảy ra | Không |
| Detection | Dễ bị detect | Khó detect hơn |

## ⚙️ Cải thiện khác

### 1. Giảm số workers
```python
SCRIBBLEHUB_MAX_WORKERS = 1  # Giảm từ 2 → 1 để tránh quá nhiều requests
```

### 2. Detect JS redirects
- Detect Cloudflare JS redirects (pushState, replaceState)
- Detect trong request/response handlers
- Kiểm tra trong JavaScript context

### 3. Cải thiện timing
- Đợi 15 giây sau khi detect pass
- Kiểm tra 3 lần liên tiếp
- Đợi networkidle

## ⚠️ Lưu ý

1. **User Data Directory:**
   - Chỉ dùng 1 instance tại một thời điểm
   - Nếu dùng nhiều instance, dùng `user-data-1`, `user-data-2`, etc.

2. **Cookies:**
   - Cookies có thể expire (thường 1-7 ngày)
   - Nếu expire, verify lại 1 lần

3. **Performance:**
   - Persistent context hơi chậm hơn launch() một chút
   - Nhưng ổn định hơn nhiều

## 🎯 Kết quả

Sau khi implement:
- ✅ `navigator.webdriver = undefined` (real browser)
- ✅ Cookies được giữ tự động
- ✅ Verify 1 lần duy nhất
- ✅ Không bị Cloudflare loop
- ✅ Scrape ổn định hơn

## 💡 Tips

1. **Nếu vẫn bị challenge:**
   - Xóa thư mục `user-data` và verify lại
   - Đảm bảo `USE_PERSISTENT_CONTEXT = True`

2. **Nếu muốn dùng Chrome profile có sẵn:**
   ```python
   USER_DATA_DIR = "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"
   ```
   ⚠️ Chỉ dùng khi Chrome không chạy

3. **Nếu muốn reset:**
   - Xóa thư mục `user-data`
   - Chạy lại để tạo profile mới

