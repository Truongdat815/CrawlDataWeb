# 🍪 Giải pháp Cookie Persistence - Tránh verify Cloudflare nhiều lần

## ✅ Đã implement 2 cách

### CÁCH 1: Cookie Persistence (Đã implement) ✅

**Cách hoạt động:**
1. Lần đầu tiên: Verify Cloudflare thủ công
2. Sau khi verify: Code tự động lưu cookies vào file `cookies_scribblehub.json`
3. Lần sau: Code tự động load cookies từ file → Không cần verify lại!

**File:** `src/utils/cookie_manager.py`

**Cấu hình:**
```python
# Trong src/config.py
ENABLE_COOKIE_PERSISTENCE = True  # Bật lưu cookies
```

**Cách sử dụng:**
1. Chạy lần đầu, verify Cloudflare thủ công
2. Cookies sẽ được lưu tự động
3. Lần sau chạy, cookies sẽ được load tự động → Không cần verify lại!

### CÁCH 2: User Data Directory (Đã implement) ✅

**Cách hoạt động:**
- Dùng Chrome profile có sẵn (giữ cookies, history, settings)
- Cookies được lưu trong Chrome profile → Giữ giữa các lần chạy

**Cấu hình:**
```python
# Trong src/config.py
USER_DATA_DIR = "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"
# Hoặc None để không dùng
```

**Lưu ý:**
- Chỉ dùng khi không có Chrome đang chạy
- Có thể dùng profile riêng để tránh conflict

## 🚀 Cách sử dụng

### Option 1: Dùng Cookie Persistence (Khuyên dùng)

1. **Bật trong config:**
   ```python
   # src/config.py
   ENABLE_COOKIE_PERSISTENCE = True
   ```

2. **Chạy lần đầu:**
   ```bash
   python test_scribblehub.py
   ```
   - Verify Cloudflare thủ công
   - Cookies sẽ được lưu tự động

3. **Lần sau:**
   ```bash
   python test_scribblehub.py
   ```
   - Cookies sẽ được load tự động
   - Không cần verify lại!

### Option 2: Dùng User Data Directory

1. **Tìm Chrome User Data Directory:**
   - Windows: `C:/Users/YourName/AppData/Local/Google/Chrome/User Data`
   - Mac: `~/Library/Application Support/Google/Chrome`
   - Linux: `~/.config/google-chrome`

2. **Cấu hình:**
   ```python
   # src/config.py
   USER_DATA_DIR = "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"
   ```

3. **Chạy:**
   ```bash
   python test_scribblehub.py
   ```
   - Lần đầu verify, lần sau không cần

## 📝 Files

- `src/utils/cookie_manager.py` - Quản lý cookies (save/load)
- `src/config.py` - Cấu hình
- `cookies_scribblehub.json` - File lưu cookies (tự động tạo)

## ⚠️ Lưu ý

1. **Cookie Persistence:**
   - Cookies có thể expire (thường 1-7 ngày)
   - Nếu cookies expire, cần verify lại
   - File `cookies_scribblehub.json` có thể xóa để verify lại

2. **User Data Directory:**
   - Chỉ dùng khi Chrome không chạy
   - Có thể dùng profile riêng: `USER_DATA_DIR = "path/to/profile"`

3. **Xóa cookies:**
   ```python
   from src.utils.cookie_manager import clear_cookies
   clear_cookies()  # Xóa file cookies
   ```

## 🎯 Kết quả

Sau khi implement:
- ✅ Lần đầu: Verify 1 lần
- ✅ Lần sau: Không cần verify (dùng cookies)
- ✅ Tiết kiệm thời gian
- ✅ Không bị reload challenge

## 💡 Tips

1. **Nếu cookies không work:**
   - Xóa file `cookies_scribblehub.json`
   - Verify lại và lưu cookies mới

2. **Nếu vẫn bị challenge:**
   - Cookies có thể đã expire
   - Verify lại và lưu cookies mới

3. **Kết hợp cả 2 cách:**
   - Dùng Cookie Persistence (đơn giản hơn)
   - Hoặc dùng User Data Directory (giữ nhiều thứ hơn)

