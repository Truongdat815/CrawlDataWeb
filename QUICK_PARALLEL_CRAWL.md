# ⚡ Crawl Nhiều Fictions Song Song - Quick Guide

## 🚀 Cách bật (30 giây)

### Bước 1: Mở `src/config.py`

### Bước 2: Thêm dòng này:
```python
MAX_FICTION_WORKERS = 2  # Crawl 2 fictions cùng lúc
```

### Bước 3: Chạy như bình thường
```bash
python main.py
```

**Xong!** Bây giờ sẽ crawl 2 fictions song song thay vì tuần tự.

## 📊 Kết quả

- ✅ **Tốc độ:** Tăng ~2x (với 2 workers)
- ✅ **Thời gian:** Crawl 10 fictions từ ~5 giờ → ~2.5 giờ

## ⚙️ Tùy chỉnh

```python
MAX_FICTION_WORKERS = 1  # Tuần tự (như cũ)
MAX_FICTION_WORKERS = 2  # 2 fictions cùng lúc (khuyến nghị)
MAX_FICTION_WORKERS = 3  # 3 fictions cùng lúc (nhanh hơn, tốn RAM hơn)
MAX_FICTION_WORKERS = 4  # 4 fictions cùng lúc (rất nhanh, cần nhiều RAM)
```

## ⚠️ Lưu ý

- ⚠️ Tăng workers = tăng RAM usage (~500MB mỗi worker)
- ⚠️ Có thể bị ban IP nếu quá nhiều requests cùng lúc
- ✅ Khuyến nghị: Bắt đầu với 2 workers, test xem có bị ban không

## 🎯 Kết hợp với tối ưu khác

```python
MAX_FICTION_WORKERS = 2      # 2 fictions cùng lúc
MAX_WORKERS = 8              # Mỗi fiction: 8 chapters cùng lúc
DELAY_BETWEEN_REQUESTS = 1   # Delay ngắn
```

**Kết quả:** Tốc độ tổng thể tăng **~10-15x** 🚀

