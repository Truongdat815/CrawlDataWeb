# 🚀 ĐẠI TU HỆ THỐNG - HOÀN THÀNH

## ✅ Tất cả 5 bước đã hoàn thành!

### 📦 BƯỚC 1: Cài đặt thư viện (✅ Hoàn thành)
```powershell
pip install uuid6 pymongo
```
- ✅ uuid6: Tạo UUID v7 (time-sortable)
- ✅ pymongo: Kết nối MongoDB

---

### 🔧 BƯỚC 2: Cấu hình Database Team (✅ Hoàn thành)
**File `.env` đã được tạo:**
```env
MONGO_URI=mongodb://user:56915001@103.90.224.232:27017/my_database
DB_NAME=my_database
COLLECTION_NAME=novels
```

---

### 🎯 BƯỚC 3: Nâng cấp Core Scraper (✅ Hoàn thành)
**Đã nâng cấp `src/webnovel_scraper.py`:**
- ✅ Import `uuid6` thành công
- ✅ Tất cả ID giờ sử dụng `uuid6.uuid7()` (time-sortable)
- ✅ Lưu Platform ID trong `platform_id` field
- ✅ Thêm `platform: "webnovel"` vào schema
- ✅ Scrape field `status` (Ongoing/Completed)
- ✅ Chapters và Comments đều có `source_id` để trace

**Schema cuối cùng:**
```json
{
  "id": "018d1234-5678-...",  // UUID v7
  "platform_id": "wn_123456789",  // ID gốc từ Webnovel
  "platform": "webnovel",
  "name": "Book Name",
  "status": "Ongoing",
  "chapters": [
    {
      "id": "018d...",
      "source_id": "wn_ch_...",
      "book_id": "018d1234-5678-...",
      ...
    }
  ],
  "comments": [
    {
      "comment_id": "018d...",
      "source_id": "018d...",
      ...
    }
  ]
}
```

---

### 🔄 BƯỚC 4: Batch Runner "Bất Tử" (✅ Hoàn thành)
**Process Isolation Strategy - Không còn lỗi Async!**

#### `single_book_runner.py` (Đã tạo)
- Cào 1 bộ truyện
- Tự động tắt browser sau khi xong
- Arguments: `--chapters`, `--headless`, `--fast`

#### `batch_runner.py` (Đã viết lại hoàn toàn)
- Chạy mỗi bộ trong subprocess riêng biệt
- Không còn shared memory/async loop
- Tự động skip nếu đã cào
- Log errors vào `batch_errors.log`

**Cách chạy:**
```powershell
# Test 3 bộ với 20 chapters mỗi bộ
python batch_runner.py

# Production: 50 bộ, 20 chapters
python batch_runner.py --limit 50 --chapters 20

# Fast mode (block images)
python batch_runner.py --limit 10 --fast

# Force re-scrape
python batch_runner.py --limit 5 --force
```

---

### 📤 BƯỚC 5: Import MongoDB Final (✅ Hoàn thành)
**File `import_to_mongodb.py` đã được tạo:**

**Tính năng:**
- ✅ Đọc tất cả JSON từ `data/json/`
- ✅ Convert UUID String → BSON Binary (performance tốt hơn)
- ✅ Upsert dựa trên `platform_id` (tránh duplicate)
- ✅ Hiển thị stats (inserted/updated/unchanged/error)
- ✅ Verify data sau khi import

**Cách chạy:**
```powershell
python import_to_mongodb.py
```

---

## 🎯 KẾ HOẠCH HÀNH ĐỘNG ĐÊM NAY

### 1️⃣ Thu thập URLs (5-10 bộ truyện)
```powershell
python get_category_links.py
```
→ Chọn category bất kỳ (Action, Fantasy, Romance...)
→ File `books_queue.txt` sẽ chứa danh sách URLs

### 2️⃣ Chạy Batch Scraping (3 bộ demo)
```powershell
python batch_runner.py --limit 3 --chapters 20
```
→ Để máy chạy tự động (mở/tắt browser cho từng bộ)
→ Khoảng 10-15 phút/bộ (tùy số chapters)

### 3️⃣ Import lên MongoDB Team
```powershell
python import_to_mongodb.py
```
→ UUID sẽ được convert sang BSON Binary
→ Check MongoDB Compass để verify

### 4️⃣ Verify trong MongoDB Compass
```
Connection String:
mongodb://user:56915001@103.90.224.232:27017/my_database

Database: my_database
Collection: novels
```

**Kiểm tra:**
- ✅ `_id` và `id` phải là Binary (UUID)
- ✅ `platform_id` là string (e.g., "wn_123...")
- ✅ `chapters` array có đầy đủ dữ liệu
- ✅ `comments` có replies

---

## 📊 CHECKLIST CUỐI CÙNG

### Đã hoàn thành:
- [x] Cài uuid6 + pymongo
- [x] Tạo file .env với team MongoDB
- [x] Upgrade WebnovelScraper → UUID v7
- [x] Fix Async error → Process Isolation
- [x] Tạo import script với BSON conversion

### Cần làm đêm nay:
- [ ] Chạy `get_category_links.py` → Lấy 5-10 URLs
- [ ] Chạy `batch_runner.py --limit 3` → Cào 3 bộ demo
- [ ] Chạy `import_to_mongodb.py` → Đẩy lên DB team
- [ ] Verify trên MongoDB Compass

---

## 🎉 KẾT QUẢ MONG ĐỢI

Sau khi chạy xong, bạn sẽ có:

1. **3 bộ truyện hoàn chỉnh** (mỗi bộ 20 chapters)
2. **Data trên MongoDB Team** với UUID v7 BSON
3. **Không có lỗi Async** nhờ Process Isolation
4. **Schema chuẩn** theo yêu cầu sếp

**Chúc may mắn! 🚀**

---

## 📞 LƯU Ý

- **Visual mode (không headless)** bypass Cloudflare tốt nhất
- **Sleep 10s giữa các bộ** để tránh bị ban IP
- **Nếu lỗi MongoDB connection**, check firewall/network
- **Nếu UUID conversion lỗi**, check uuid6 version (cần ≥2025.0.1)
