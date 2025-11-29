# Quick Start - Hệ thống Sync

## 🚀 Chạy nhanh

### 1. Chạy Main Crawler (như bình thường)
```bash
python main.py
```

### 2. Chạy Sync Workers

#### Option A: Chạy từng worker riêng lẻ

**Metadata Sync** (sync title, stats, tags):
```bash
python -m src.sync_metadata_worker
```

**Chapter Sync** (sync chapters dựa trên hash):
```bash
python -m src.sync_chapter_worker
```

#### Option B: Chạy Scheduler (khuyến nghị)

**Chạy scheduler - tự động sync định kỳ:**
```bash
python -m src.sync_scheduler
```

**Chạy sync một lần rồi thoát:**
```bash
python -m src.sync_scheduler --once
```

## ⚙️ Cấu hình

### Intervals (mặc định)
- Metadata sync: **10 phút** (600 giây)
- Chapter sync: **30 phút** (1800 giây)

### Batch Sizes (mặc định)
- Metadata: **10 fictions** mỗi lần
- Chapter: **5 fictions**, mỗi fiction **10 chapters**

### Tùy chỉnh intervals:
```bash
python -m src.sync_scheduler --metadata-interval 300 --chapter-interval 900
```

## 📊 Cách hoạt động

1. **Main Crawler** crawl fiction → Lưu với hash + timestamps
2. **Sync Workers** chạy background:
   - Fetch metadata/content mới
   - Tính hash
   - So sánh với hash trong DB
   - Update nếu khác

## ✅ Kết quả

- ✅ Dữ liệu luôn đồng bộ
- ✅ Không cần crawl lại từ đầu
- ✅ Chỉ sync phần thay đổi (rất nhanh)
- ✅ Hash-based detection (chính xác 100%)

## 📝 Lưu ý

- Sync workers có thể chạy song song với main crawler
- Có thể chạy trong terminal riêng hoặc background service
- MongoDB tự động xử lý update/insert

## 📚 Tài liệu chi tiết

- `SYNC_SYSTEM.md`: Giải thích chi tiết về hệ thống sync
- `IMPROVEMENTS.md`: Tóm tắt các cải tiến

