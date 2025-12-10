# Webnovel Scraper V7 🚀

**Latest Version:** V7 (Human-Assist Cloudflare Bypass)  
**Updated:** December 10, 2025

Công cụ tự động cào dữ liệu từ Webnovel.com với khả năng:
- ✅ **Vượt qua Cloudflare** với sự hỗ trợ của người dùng
- ✅ **Tự động tìm Chapter 1** từ reader sidebar
- ✅ **Scraping hoàn chỉnh:** metadata, chapters, comments, replies
- ✅ **Resume từ checkpoint** khi bị gián đoạn
- ✅ **Ảnh bìa truyện** tự động download

## 🆕 What's New in V7?

### Giải Quyết Vấn Đề Cloudflare
Phiên bản trước (V6) bị chặn bởi Cloudflare "Under Attack Mode". **V7 fix triệt để:**

```
🛡️ Cloudflare detected → Wait 60s auto-bypass
                       ↓
Still blocked? → 🛑 Prompt user to solve CAPTCHA manually
                       ↓
User clicks captcha → ✅ Auto-resume scraping!
```

**Xem chi tiết:** [CLOUDFLARE_FIX_V7.md](CLOUDFLARE_FIX_V7.md)

---

## Cài đặt

### 1. Cài đặt Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Cài đặt Playwright browsers

Playwright cần cài đặt browser drivers:

```bash
playwright install chromium
```

Hoặc cài tất cả browsers:

```bash
playwright install
```

## Cách chạy

### Chạy cơ bản

```bash
python main.py
```

Script sẽ:
1. Truy cập trang Writathon: `https://www.royalroad.com/fictions/writathon`
2. Lấy danh sách các bộ truyện
3. Cào từng bộ truyện (metadata, chapters, comments)
4. Lưu kết quả vào folder `data/json/` (file JSON)
5. Lưu ảnh bìa vào folder `data/images/`

## Cấu hình

Chỉnh sửa file `src/config.py` để thay đổi:

- `HEADLESS`: `True` = chạy ngầm (không hiện browser), `False` = hiện browser
- `MAX_WORKERS`: Số thread để cào chapters song song (mặc định: 3)
- `DELAY_BETWEEN_REQUESTS`: Thời gian delay giữa các request (giây)
- `DELAY_BETWEEN_CHAPTERS`: Thời gian delay giữa các chapters (giây)

## Cấu trúc dữ liệu

Sau khi chạy, dữ liệu được lưu tại:

```
data/
├── json/           # File JSON chứa dữ liệu truyện
│   └── {id}_{title}.json
└── images/         # Ảnh bìa truyện
    └── {id}_cover.jpg
```

## Cấu trúc JSON output

Mỗi file JSON chứa:

```json
{
    "id": "21220",
    "title": "Mother of Learning",
    "cover_image_local": "data/images/21220_cover.jpg",
    "author": "...",
    "category": "...",
    "status": "...",
    "tags": [...],
    "description": "...",
    "stats": {
        "score": {...},
        "views": {...}
    },
    "chapters": [
        {
            "url": "...",
            "title": "...",
            "content_text": "...",
            "comments": [...]
        }
    ]
}
```

## Lưu ý

- Script có delay giữa các request để tránh bị ban IP
- Có thể mất nhiều thời gian nếu truyện có nhiều chapters
- Đảm bảo có kết nối internet ổn định

