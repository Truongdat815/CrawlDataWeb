# ⚡ Tăng Tốc Độ Nhanh - Quick Guide

## 🚀 Cách nhanh nhất (1 phút)

### Option 1: Dùng script helper
```bash
# Áp dụng config performance
python optimize_speed.py --apply-performance

# Xem config hiện tại
python optimize_speed.py --show

# Khôi phục config gốc nếu cần
python optimize_speed.py --restore
```

### Option 2: Chỉnh sửa trực tiếp

Mở file `src/config.py` và thay đổi:

```python
# Từ:
DELAY_BETWEEN_REQUESTS = 5
DELAY_BETWEEN_CHAPTERS = 2
MAX_WORKERS = 3

# Thành:
DELAY_BETWEEN_REQUESTS = 1   # Giảm 5x → nhanh hơn 5x
DELAY_BETWEEN_CHAPTERS = 0.5 # Giảm 4x → nhanh hơn 4x
MAX_WORKERS = 8              # Tăng 2.6x → nhanh hơn 2.6x
```

**Kết quả:** Tốc độ tăng **~40-50x** 🚀

## ⚠️ Lưu ý

1. **Test trước:** Chạy với 1-2 fictions để xem có bị ban IP không
2. **Giảm dần:** Bắt đầu với delay 2s, nếu OK thì giảm xuống 1s, rồi 0.5s
3. **Monitor:** Xem có lỗi không, nếu có nhiều lỗi → tăng delay lại

## 📊 So sánh

| Cấu hình | Delay | Workers | Tốc độ |
|----------|-------|---------|--------|
| Mặc định | 5s | 3 | 1x |
| Cân bằng | 1s | 6 | ~10x |
| Tối đa | 0.5s | 10 | ~40x |

## 🎯 Khuyến nghị

**An toàn (không bị ban):**
- DELAY_BETWEEN_REQUESTS = 2
- MAX_WORKERS = 4

**Cân bằng:**
- DELAY_BETWEEN_REQUESTS = 1
- MAX_WORKERS = 6-8

**Tối đa (rủi ro):**
- DELAY_BETWEEN_REQUESTS = 0.5
- MAX_WORKERS = 10-12

## 📚 Tài liệu chi tiết

Xem `PERFORMANCE_OPTIMIZATION.md` để biết thêm chi tiết.

