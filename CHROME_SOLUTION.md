# 🚀 Giải pháp: Dùng Chrome thật (System Chrome)

## ✅ Đã cập nhật

Code đã được cập nhật để dùng **Google Chrome thật** trên máy tính thay vì Chromium tích hợp của Playwright.

## 🔍 Vì sao cần dùng Chrome thật?

1. **TLS Fingerprint**: Chromium tích hợp có TLS fingerprint khác với Chrome thật → Cloudflare phát hiện
2. **Automation Flag**: Chromium tích hợp có các flag automation → Cloudflare chặn
3. **User-Agent mismatch**: User-Agent cứng không khớp với version thật → Cloudflare phát hiện

## ✅ Giải pháp đã implement

### 1. Dùng System Chrome

**File: `src/handlers/base_handler.py`**

```python
# Dùng Chrome thật trên máy
self.context = self.playwright.chromium.launch_persistent_context(
    user_data_dir=user_data_dir,
    channel="chrome",  # ⚠️ QUAN TRỌNG: Dùng Chrome thật
    headless=config.HEADLESS,
    args=browser_args,
    # KHÔNG set user_agent - để Chrome tự lấy đúng version
)
```

### 2. Xóa User-Agent cứng

- **Trước**: User-Agent cứng `Chrome/120.0.0.0` (có thể lệch với version thật)
- **Sau**: Chrome tự lấy User-Agent đúng version → Không bị phát hiện

### 3. Thêm Browser Args quan trọng

```python
browser_args = [
    "--disable-blink-features=AutomationControlled",
    "--exclude-switches=enable-automation",  # ⚠️ QUAN TRỌNG
    "--no-first-run",
    "--no-service-autorun",
    # ...
]
```

### 4. Fallback Chain

1. Thử `channel="chrome"` (Google Chrome)
2. Nếu không có → Thử `channel="msedge"` (Microsoft Edge)
3. Nếu không có → Dùng Chromium tích hợp (có thể bị chặn)

## 🚀 Cách sử dụng

### Bước 1: Đảm bảo đã cài Chrome

- Windows: Chrome tự động cài khi dùng Playwright
- Nếu chưa có: Tải từ https://www.google.com/chrome/

### Bước 2: Chạy code

```bash
python main.py
```

### Bước 3: Verify Cloudflare (lần đầu)

1. Browser sẽ mở (vì `HEADLESS = False`)
2. Nếu thấy Cloudflare challenge:
   - Tick checkbox để verify
   - Đợi challenge hoàn thành (5-15 giây)
3. Code sẽ tự động lưu cookies
4. **Lần sau không cần verify lại!**

## ⚙️ Cấu hình

**File: `src/config.py`**

```python
HEADLESS = False  # ⚠️ QUAN TRỌNG: Phải False
USE_PERSISTENT_CONTEXT = True  # Bật persistent context
ENABLE_COOKIE_PERSISTENCE = True  # Bật lưu cookies
```

## 💡 Lưu ý

1. **Lần đầu chạy**: Cần verify Cloudflare thủ công
2. **Lần sau**: Cookies đã được lưu → Không cần verify lại
3. **Nếu vẫn bị chặn**: 
   - Xóa thư mục `user-data/` và verify lại
   - Đảm bảo Chrome đã được cài đặt

## 🎯 Kết quả mong đợi

- ✅ Dùng Chrome thật → TLS Fingerprint đúng
- ✅ User-Agent tự động → Không bị phát hiện
- ✅ Verify 1 lần duy nhất → Cookies được lưu
- ✅ Lần sau không cần verify lại

## 📋 Checklist

- [ ] Chrome đã được cài đặt trên máy
- [ ] `HEADLESS = False` trong `config.py`
- [ ] `USE_PERSISTENT_CONTEXT = True`
- [ ] `ENABLE_COOKIE_PERSISTENCE = True`
- [ ] Chạy code và verify Cloudflare lần đầu
- [ ] Cookies được lưu vào `cookies_scribblehub.json`

