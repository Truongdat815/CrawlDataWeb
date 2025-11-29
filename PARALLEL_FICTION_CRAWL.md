# Crawl Nhiều Fictions Song Song

## 🚀 Tính năng mới

Bây giờ bạn có thể crawl **nhiều fictions song song cùng lúc** thay vì tuần tự từng cái một!

## ⚡ Lợi ích

- ✅ **Tăng tốc độ:** Crawl 2-3 fictions cùng lúc → nhanh hơn 2-3x
- ✅ **Tận dụng tài nguyên:** Sử dụng nhiều CPU cores và RAM hiệu quả hơn
- ✅ **Tiết kiệm thời gian:** Crawl 10 fictions từ ~5 giờ → ~2 giờ

## 🔧 Cấu hình

### File: `src/config.py`

```python
# Số fiction crawl song song cùng lúc
MAX_FICTION_WORKERS = 2  # Crawl 2 fictions cùng lúc
```

### Khuyến nghị:

- **CPU 4 cores:** `MAX_FICTION_WORKERS = 2`
- **CPU 8 cores:** `MAX_FICTION_WORKERS = 3-4`
- **CPU 16+ cores:** `MAX_FICTION_WORKERS = 4-5`

## 📊 So sánh

### Trước (Tuần tự):
```
Fiction 1 → Fiction 2 → Fiction 3 → Fiction 4
Thời gian: 4 fictions × 1 giờ = 4 giờ
```

### Sau (Song song):
```
Fiction 1 ┐
Fiction 2 ├─ Crawl cùng lúc
Fiction 3 ┘
Thời gian: 3 fictions ÷ 3 = ~1.3 giờ (nhanh hơn 3x)
```

## 🎯 Cách sử dụng

### 1. Cấu hình số workers

Mở `src/config.py`:
```python
MAX_FICTION_WORKERS = 2  # Crawl 2 fictions cùng lúc
```

### 2. Chạy như bình thường

```bash
python main.py
```

Code sẽ tự động:
- Nếu `MAX_FICTION_WORKERS > 1` → crawl song song
- Nếu `MAX_FICTION_WORKERS = 1` → crawl tuần tự (như cũ)

## 🔍 Cách hoạt động

1. **Lấy danh sách fictions** từ trang best-rated
2. **Chia fictions thành batches** theo `MAX_FICTION_WORKERS`
3. **Mỗi worker có browser instance riêng** → không conflict
4. **Crawl song song** với ThreadPoolExecutor
5. **Tự động quản lý** threads và resources

## ⚠️ Lưu ý

### 1. Tài nguyên hệ thống
- ⚠️ Mỗi fiction worker = 1 browser instance (~200-500MB RAM)
- ✅ `MAX_FICTION_WORKERS = 2` → ~400-1000MB RAM
- ✅ `MAX_FICTION_WORKERS = 3` → ~600-1500MB RAM

### 2. Rate Limiting
- ⚠️ Crawl nhiều fictions cùng lúc = nhiều requests cùng lúc
- ✅ Có thể bị ban IP nếu quá nhiều
- ✅ Khuyến nghị: Bắt đầu với 2 workers, test xem có bị ban không

### 3. MongoDB Connection
- ✅ Tất cả workers dùng chung MongoDB connection pool
- ✅ Tự động xử lý concurrent writes

## 📈 Kết quả mong đợi

Với `MAX_FICTION_WORKERS = 2`:
- ✅ **Tốc độ:** Tăng ~2x
- ✅ **Thời gian crawl 10 fictions:** Từ ~5 giờ → ~2.5 giờ

Với `MAX_FICTION_WORKERS = 3`:
- ✅ **Tốc độ:** Tăng ~3x
- ✅ **Thời gian crawl 10 fictions:** Từ ~5 giờ → ~1.7 giờ

## 🔧 Tối ưu kết hợp

Kết hợp với các tối ưu khác:

```python
# Config tối ưu toàn diện
MAX_FICTION_WORKERS = 2      # Crawl 2 fictions cùng lúc
MAX_WORKERS = 8              # Mỗi fiction crawl 8 chapters cùng lúc
DELAY_BETWEEN_REQUESTS = 1   # Delay ngắn
```

**Kết quả:** Tốc độ tổng thể tăng **~10-15x** 🚀

## 🐛 Troubleshooting

### Lỗi: "Too many connections"
- ✅ Giảm `MAX_FICTION_WORKERS` xuống
- ✅ Tăng `DELAY_BETWEEN_REQUESTS`

### Lỗi: "Out of memory"
- ✅ Giảm `MAX_FICTION_WORKERS`
- ✅ Giảm `MAX_WORKERS` (chapters per fiction)

### Bị ban IP
- ✅ Giảm `MAX_FICTION_WORKERS` xuống 1 (tuần tự)
- ✅ Tăng `DELAY_BETWEEN_REQUESTS`

## 📝 Ví dụ

### Crawl 5 fictions với 2 workers:

```python
# config.py
MAX_FICTION_WORKERS = 2

# main.py
bot.scrape_best_rated_fictions(url, num_fictions=5)
```

**Kết quả:**
- Worker 1: Fiction 1, Fiction 3, Fiction 5
- Worker 2: Fiction 2, Fiction 4
- Thời gian: ~2.5 giờ (thay vì 5 giờ)

