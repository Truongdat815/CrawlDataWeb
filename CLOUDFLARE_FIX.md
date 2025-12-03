# 🔒 Xử lý Cloudflare Challenge - ScribbleHub

## ✅ Đã thực hiện

### 1. Cloudflare Challenge Detection
- ✅ Tự động phát hiện Cloudflare challenge
- ✅ Đợi challenge hoàn thành (tối đa 30 giây)
- ✅ Kiểm tra xem đã pass challenge chưa

### 2. Cải thiện Page Navigation
- ✅ Tất cả `page.goto()` đều dùng `wait_until="networkidle"`
- ✅ Delay sau mỗi lần goto để đợi Cloudflare
- ✅ Kiểm tra nội dung page để phát hiện challenge

### 3. Helper Function
- ✅ `wait_for_cloudflare_challenge()` trong BaseHandler
- ✅ `goto_with_cloudflare()` helper function (có thể dùng sau)

## 🔧 Cách hoạt động

### Khi gặp Cloudflare challenge:

1. **Phát hiện challenge:**
   - Kiểm tra nội dung page có chứa "challenges.cloudflare.com"
   - Kiểm tra các selector Cloudflare (#challenge-form, .cf-browser-verification, etc.)

2. **Đợi challenge:**
   - Đợi tối đa 30 giây (có thể điều chỉnh trong config)
   - Kiểm tra mỗi 2 giây xem đã pass chưa

3. **Xác nhận pass:**
   - Kiểm tra xem page đã load content chưa
   - Tìm các element thông thường của ScribbleHub (.fic_title, ol.toc_ol, etc.)

## ⚙️ Cấu hình

Trong `src/config.py`:

```python
# Thời gian đợi Cloudflare challenge (giây)
CLOUDFLARE_MAX_WAIT = 30  # Thời gian tối đa đợi Cloudflare challenge
CLOUDFLARE_CHECK_DELAY = 3  # Delay sau khi goto để kiểm tra Cloudflare
CLOUDFLARE_CHALLENGE_DELAY = 10  # Delay thêm nếu phát hiện challenge
```

### Điều chỉnh nếu cần:

- **Nếu vẫn bị chặn:** Tăng `CLOUDFLARE_MAX_WAIT` lên 60 giây
- **Nếu quá chậm:** Giảm `CLOUDFLARE_CHALLENGE_DELAY` xuống 5 giây

## 📝 Các file đã cập nhật

1. **`src/handlers/base_handler.py`**
   - Thêm `wait_for_cloudflare_challenge()`
   - Thêm `goto_with_cloudflare()` helper

2. **`src/scraper_engine.py`**
   - Cập nhật `scrape_story()` để xử lý Cloudflare

3. **`src/handlers/story_handler.py`**
   - Cập nhật tất cả `page.goto()` để dùng `wait_until="networkidle"`
   - Thêm kiểm tra Cloudflare challenge

4. **`src/handlers/chapter_handler.py`**
   - Cập nhật `scrape_single_chapter_worker()` để xử lý Cloudflare

5. **`src/handlers/review_handler.py`**
   - Cập nhật để xử lý Cloudflare

6. **`src/handlers/comment_handler.py`**
   - Cập nhật tất cả `page.goto()` để xử lý Cloudflare

## 🚀 Cách test

### Test với URL cụ thể:

```bash
python test_scribblehub.py
```

### Debug Cloudflare:

Nếu vẫn bị chặn, chạy với `HEADLESS = False` để xem browser:

```python
# Trong src/config.py
HEADLESS = False
```

Sau đó chạy:
```bash
python test_scribblehub.py
```

Bạn sẽ thấy browser mở và có thể xem Cloudflare challenge đang chạy.

## ⚠️ Lưu ý

1. **Cloudflare có thể thay đổi:**
   - Nếu Cloudflare thay đổi cách hoạt động, có thể cần cập nhật code
   - Monitor logs để phát hiện sớm

2. **Rate Limiting:**
   - Cloudflare vẫn có thể chặn nếu request quá nhiều
   - Giữ delays hợp lý (8 giây giữa requests)

3. **IP Reputation:**
   - Nếu IP bị đánh dấu là bot, có thể cần đợi lâu hơn
   - Có thể cần dùng proxy nếu vẫn bị chặn

## 🎯 Kết quả mong đợi

Sau khi cập nhật:
- ✅ Tự động phát hiện và đợi Cloudflare challenge
- ✅ Pass challenge thành công
- ✅ Lấy được danh sách chapters
- ✅ Scrape được content

## 📊 Debugging

Nếu vẫn gặp vấn đề, kiểm tra:

1. **Logs:** Xem có message "Phát hiện Cloudflare challenge" không
2. **Browser:** Chạy với `HEADLESS = False` để xem trực tiếp
3. **Timing:** Tăng `CLOUDFLARE_MAX_WAIT` nếu challenge mất nhiều thời gian
4. **Network:** Kiểm tra network tab trong browser để xem requests

## 🔍 Troubleshooting

### Vấn đề: Vẫn bị chặn sau khi đợi

**Giải pháp:**
- Tăng `CLOUDFLARE_MAX_WAIT` lên 60 giây
- Tăng `CLOUDFLARE_CHALLENGE_DELAY` lên 15 giây
- Chạy với `HEADLESS = False` để xem challenge

### Vấn đề: Quá chậm

**Giải pháp:**
- Giảm `CLOUDFLARE_CHECK_DELAY` xuống 2 giây
- Giảm `CLOUDFLARE_CHALLENGE_DELAY` xuống 5 giây
- Chỉ tăng khi thực sự cần

### Vấn đề: Không phát hiện challenge

**Giải pháp:**
- Kiểm tra xem page content có chứa "challenges.cloudflare.com" không
- Cập nhật selector trong `wait_for_cloudflare_challenge()` nếu Cloudflare thay đổi

