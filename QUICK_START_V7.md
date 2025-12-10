# Quick Start - V7 Human-Assist Mode

## 🚀 Chạy Scraper

```powershell
python batch_runner.py --limit 1 --force
```

## 👀 Khi Nào Cần Can Thiệp?

### Thấy Thông Báo Này → Hành Động Ngay!

```
======================================================================
🛑 CLOUDFLARE CHALLENGE DETECTED - MANUAL HELP NEEDED!
======================================================================
👉 Please solve the CAPTCHA in the browser window NOW.
```

### Làm Gì?

1. **Chuyển sang cửa sổ Chrome** (đang mở)
2. **Giải captcha:**
   - Click ✅ "Verify you are human"  
   - Hoặc chọn hình nếu có
3. **Đợi tick xanh**
4. **Quay lại terminal** → Bot tự động chạy tiếp!

## ✅ Dấu Hiệu Thành Công

```
✅ Cloudflare challenge solved! Resuming scraper...
📋 Scraping Metadata...
📌 Title: House of the Dragon: oh Geez!
```

## ⚠️ Lưu Ý

- **Không tắt browser** khi đang chạy
- **Có thể cần giải captcha nhiều lần** (mỗi chapter page)
- **Script sẽ tự đợi** - không cần restart
- **Headless mode không hoạt động** - phải visible browser

## 🐛 Nếu Stuck

1. Check xem browser có mở không
2. Solve captcha thủ công
3. Đợi 10-20s
4. Nếu vẫn stuck → Ctrl+C và chạy lại

---

**Đơn Giản:** Khi script hét "🛑 MANUAL HELP" → Bạn bấm captcha → Xong! 🎉
