# 🔒 Giải pháp Cloudflare Challenge - Cải thiện mạnh

## ⚠️ Vấn đề

Cloudflare vẫn đang chặn bot với message:
> "Please unblock challenges.cloudflare.com to proceed."

## ✅ Giải pháp đã cải thiện

### 1. Anti-Detection Mạnh Hơn

**File: `src/handlers/base_handler.py`**

#### Browser Args (Tăng từ 3 → 20+ args):
- `--disable-blink-features=AutomationControlled`
- `--disable-dev-shm-usage`
- `--no-sandbox`
- `--disable-setuid-sandbox`
- `--disable-web-security`
- Và nhiều args khác để ẩn automation

#### JavaScript Stealth Scripts (Tăng từ 5 → 15+ scripts):
- Ẩn `navigator.webdriver`
- Giả lập `window.chrome`
- Giả lập `navigator.plugins` (với PDF plugins thật)
- Giả lập `navigator.languages`
- Override `WebGLRenderingContext.getParameter`
- Ẩn `navigator.permissions`
- Override `navigator.userAgent`
- Và nhiều scripts khác

### 2. Cloudflare Challenge Detection Cải thiện

**Cải thiện:**
- Tăng thời gian đợi từ 30s → 60s
- Kiểm tra nhiều indicators hơn:
  - "challenges.cloudflare.com"
  - "please unblock"
  - "checking your browser"
  - "just a moment"
  - "cf-browser-verification"
  - "cf-challenge"
- Kiểm tra nhiều selectors hơn
- Tự động scroll để giúp pass challenge
- In log chi tiết hơn

### 3. Configuration

**File: `src/config.py`**

```python
# QUAN TRỌNG: HEADLESS = False
HEADLESS = False  # Browser hiển thị → Cloudflare pass dễ hơn

# Cloudflare delays (TĂNG LÊN)
CLOUDFLARE_MAX_WAIT = 60  # Tăng từ 30 → 60 giây
CLOUDFLARE_CHECK_DELAY = 5  # Tăng từ 3 → 5 giây
CLOUDFLARE_CHALLENGE_DELAY = 15  # Tăng từ 10 → 15 giây
```

### 4. Page Navigation Cải thiện

- Dùng `wait_until="domcontentloaded"` thay vì `networkidle` (nhanh hơn)
- Tự động reload nếu vẫn bị chặn
- Delay sau mỗi goto để đợi Cloudflare

## 🚀 Cách sử dụng

### Bước 1: Đảm bảo HEADLESS = False

Trong `src/config.py`:
```python
HEADLESS = False  # QUAN TRỌNG!
```

### Bước 2: Chạy test

```bash
python test_scribblehub.py
```

Browser sẽ mở và bạn sẽ thấy:
- Cloudflare challenge đang chạy (nếu có)
- Browser tự động đợi challenge hoàn thành
- Sau khi pass, sẽ scrape được data

### Bước 3: Nếu vẫn bị chặn

**Option 1: Tăng thời gian đợi**
```python
# Trong src/config.py
CLOUDFLARE_MAX_WAIT = 90  # Tăng lên 90 giây
CLOUDFLARE_CHALLENGE_DELAY = 20  # Tăng lên 20 giây
```

**Option 2: Chạy với browser hiển thị và đợi thủ công**
- Browser sẽ mở
- Bạn có thể thấy Cloudflare challenge
- Đợi challenge hoàn thành (thường 5-10 giây)
- Code sẽ tự động tiếp tục

**Option 3: Dùng User Data Directory (giữ cookies)**
- Có thể cấu hình Playwright để dùng Chrome profile có sẵn
- Cookies đã pass challenge sẽ được giữ lại

## 🔍 Debugging

### Kiểm tra xem có bị chặn không:

1. **Chạy với browser hiển thị:**
   ```python
   HEADLESS = False
   ```

2. **Xem logs:**
   - "🔒 Phát hiện Cloudflare challenge" → Đang đợi
   - "✅ Đã pass Cloudflare challenge!" → Thành công
   - "❌ Vẫn bị Cloudflare chặn" → Cần điều chỉnh

3. **Kiểm tra browser:**
   - Nếu thấy "Just a moment..." → Cloudflare đang chạy
   - Đợi cho đến khi page load xong
   - Code sẽ tự động tiếp tục

## 💡 Tips

1. **Lần đầu tiên:**
   - Chạy với `HEADLESS = False`
   - Xem browser để đảm bảo Cloudflare pass
   - Sau khi pass, có thể thử `HEADLESS = True`

2. **Nếu IP bị đánh dấu:**
   - Đợi một thời gian (30 phút - 1 giờ)
   - Hoặc dùng VPN/proxy

3. **Rate Limiting:**
   - Giữ delays cao (8 giây giữa requests)
   - Không scrape quá nhanh

## 📊 So sánh

| Tính năng | Trước | Sau |
|-----------|-------|-----|
| Browser Args | 3 | 20+ |
| Stealth Scripts | 5 | 15+ |
| Cloudflare Wait | 30s | 60s |
| Detection Indicators | 4 | 6+ |
| Selectors Checked | 4 | 6+ |

## ⚠️ Lưu ý quan trọng

1. **HEADLESS = False là QUAN TRỌNG:**
   - Cloudflare thường chặn headless browser
   - Browser hiển thị → pass dễ hơn nhiều

2. **Thời gian đợi:**
   - Cloudflare challenge thường mất 5-15 giây
   - Code đã set đợi tối đa 60 giây
   - Nếu vẫn không đủ, tăng `CLOUDFLARE_MAX_WAIT`

3. **Lần đầu tiên:**
   - Có thể mất nhiều thời gian hơn
   - Sau khi pass lần đầu, cookies sẽ được giữ
   - Lần sau sẽ nhanh hơn

## 🎯 Kết quả mong đợi

Sau khi cải thiện:
- ✅ Anti-detection mạnh hơn nhiều
- ✅ Phát hiện Cloudflare tốt hơn
- ✅ Đợi challenge đủ lâu (60 giây)
- ✅ Browser hiển thị → pass dễ hơn
- ✅ Tự động reload nếu cần

