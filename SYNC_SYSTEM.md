# Hệ thống Sync - Incremental Sync với Hash-based Detection

## 📋 Tổng quan

Hệ thống sync này giải quyết bài toán **Crawl Consistency & Incremental Sync** - một vấn đề quan trọng trong crawler thực tế:

- ❌ **Vấn đề**: Khi đang crawl giữa chừng (12 tiếng), dữ liệu đã crawl trước đó có thể thay đổi → không đồng bộ
- ❌ **Không thể**: Crawl lại từ đầu vì tốn 12 tiếng
- ✅ **Giải pháp**: Incremental Sync với Hash-based Detection

## 🎯 Cơ chế hoạt động

### 1. Hash-based Content Detection

**Hash là gì?**
- Hash = một dãy ký tự đại diện cho nội dung
- Ví dụ: `"Hello"` → `"2cf24dba5fb0a30e26e83b2ac5b..."`
- Đặc điểm:
  - Nội dung không đổi → hash không đổi
  - Chỉ sửa 1 dấu phẩy → hash hoàn toàn khác
  - Hash rất nhỏ (64 ký tự)
  - Tính hash rất nhanh (vài micro giây)

**Cách hoạt động:**
1. Lần đầu crawl → lưu `content_hash` vào DB
2. Khi sync → tính hash mới
3. So sánh: `hash_cũ == hash_mới`?
   - ✅ Giống → không thay đổi → bỏ qua
   - ❌ Khác → content đã sửa → update DB

### 2. Metadata Sync

**Sync metadata (title, stats, tags) dựa trên metadata_hash:**
- Chỉ crawl metadata (rất nhẹ, không crawl chapters)
- So sánh hash → update nếu khác
- Chạy định kỳ (mỗi 10 phút)

### 3. Chapter Sync

**Sync chapters dựa trên content_hash:**
- Lấy danh sách chapters từ web (metadata only)
- Với mỗi chapter:
  - Fetch content → tính hash
  - So sánh với hash trong DB
  - Update nếu khác
- Chạy định kỳ (mỗi 30 phút)

## 📁 Cấu trúc dữ liệu mới

### Fiction Document
```json
{
  "id": "36735",
  "title": "The Perfect Run",
  "fiction_url": "https://www.royalroad.com/fiction/36735",
  "author": "...",
  "category": "...",
  "status": "...",
  "tags": [...],
  "description": "...",
  "stats": {...},
  "metadata_hash": "abc123...",  // Hash của metadata
  "created_at": "2025-02-11T10:00:00",
  "updated_at": "2025-02-11T10:00:00",
  "last_synced_at": "2025-02-11T15:30:00",
  "chapters": [...]
}
```

### Chapter Document
```json
{
  "chapter_id": "569225",
  "url": "https://www.royalroad.com/fiction/36735/chapter/569225/1-quicksave",
  "title": "1: Quicksave",
  "content_text": "...",
  "content_hash": "def456...",  // Hash của content
  "content_length": 5000,
  "created_at": "2025-02-11T10:00:00",
  "updated_at": "2025-02-11T10:00:00",
  "last_synced_at": "2025-02-11T15:30:00",
  "comments": [...]
}
```

## 🚀 Cách sử dụng

### 1. Chạy Metadata Sync Worker

```bash
# Sync metadata một lần
python -m src.sync_metadata_worker

# Hoặc import và dùng trong code
from src.sync_metadata_worker import MetadataSyncWorker

worker = MetadataSyncWorker()
worker.start()
worker.sync_batch(num_fictions=10, max_age_hours=24)
worker.stop()
```

### 2. Chạy Chapter Sync Worker

```bash
# Sync chapters một lần
python -m src.sync_chapter_worker

# Hoặc import và dùng trong code
from src.sync_chapter_worker import ChapterSyncWorker

worker = ChapterSyncWorker()
worker.start()
worker.sync_batch(num_fictions=5, max_chapters_per_fiction=10)
worker.stop()
```

### 3. Chạy Sync Scheduler (Background)

```bash
# Chạy scheduler (loop định kỳ)
python -m src.sync_scheduler

# Chạy sync một lần rồi thoát
python -m src.sync_scheduler --once

# Tùy chỉnh intervals
python -m src.sync_scheduler --metadata-interval 300 --chapter-interval 900
```

## ⚙️ Cấu hình

### Intervals (mặc định)
- **Metadata Sync**: 600 giây (10 phút)
- **Chapter Sync**: 1800 giây (30 phút)

### Batch Sizes (mặc định)
- **Metadata Batch**: 10 fictions mỗi lần
- **Chapter Batch**: 5 fictions, mỗi fiction 10 chapters

## 📊 Flowchart

```
Main Crawler
    ↓
Crawl Fiction → Lưu với hash + timestamps
    ↓
Background Sync Workers (chạy song song)
    ├─ Metadata Sync Worker (mỗi 10 phút)
    │   └─ Fetch metadata → So sánh hash → Update nếu khác
    │
    └─ Chapter Sync Worker (mỗi 30 phút)
        └─ Fetch chapter list → So sánh hash từng chapter → Update nếu khác
```

## 🔍 Ví dụ cụ thể

### Ví dụ 1: Metadata thay đổi

**Lần đầu crawl:**
- Title: "The Perfect Run"
- Metadata hash: `abc123...`

**Sau này tác giả sửa:**
- Title: "The Perfect Run (Revised)"
- Metadata hash mới: `xyz789...`

**Sync worker:**
1. Fetch metadata mới → hash = `xyz789...`
2. So sánh: `abc123...` ≠ `xyz789...` → **Có thay đổi**
3. Update DB với metadata mới

### Ví dụ 2: Chapter content thay đổi

**Lần đầu crawl:**
- Content: "John walked into the dungeon."
- Content hash: `3a7bd3e2360a3af66...`

**Sau này tác giả sửa:**
- Content: "John cautiously walked into the dungeon."
- Content hash mới: `627cfa2231ad3aa11...`

**Sync worker:**
1. Fetch content mới → hash = `627cfa2231ad3aa11...`
2. So sánh: `3a7bd3e2360a3af66...` ≠ `627cfa2231ad3aa11...` → **Có thay đổi**
3. Update DB với content mới

**Thời gian sync:** 0.3 giây (chỉ 1 chapter)
**Nếu crawl lại full:** 12 tiếng

## ✅ Lợi ích

1. **Không bao giờ crawl lại từ đầu** → tiết kiệm thời gian
2. **Chỉ sync phần thay đổi** → cực nhanh
3. **Hash-based detection** → chính xác 100%
4. **Background sync** → không ảnh hưởng main crawler
5. **Incremental sync** → dữ liệu luôn đồng bộ

## 📝 Lưu ý

- Sync workers chạy độc lập với main crawler
- Có thể chạy song song với main crawler
- MongoDB upsert tự động xử lý update/insert
- Hash SHA256 đảm bảo phát hiện thay đổi chính xác

## 🔧 Tùy chỉnh

Có thể điều chỉnh trong code:
- `sync_metadata_worker.py`: Batch size, max age hours
- `sync_chapter_worker.py`: Batch size, chapters per fiction
- `sync_scheduler.py`: Intervals, batch sizes

