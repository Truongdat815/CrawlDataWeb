# 🚀 Hướng dẫn sử dụng Chrome hiện tại của bạn

## ✅ Cách 1: Khởi động Chrome với Remote Debugging (KHUYẾN KHÍCH)

### Bước 1: Khởi động Chrome với remote debugging

**Cách A: Dùng script tự động (Dễ nhất)**
```bash
# Chạy file batch
start_chrome_with_debug.bat
```

**Cách B: Khởi động thủ công**
1. Tìm đường dẫn Chrome của bạn (thường là):
   - `C:\Program Files\Google\Chrome\Application\chrome.exe`
   - `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`

2. Tạo shortcut mới hoặc chạy từ Command Prompt:
   ```cmd
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
   ```

**Cách C: Tạo shortcut vĩnh viễn**
1. Right-click vào desktop → New → Shortcut
2. Nhập đường dẫn:
   ```
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
   ```
3. Đặt tên: "Chrome (Debug Mode)"
4. Dùng shortcut này để mở Chrome mỗi khi muốn scrape

### Bước 2: Chạy scraper
```bash
python main.py
```

Scraper sẽ tự động kết nối đến Chrome đang chạy và dùng các tab đang mở của bạn!

---

## ✅ Cách 2: Dùng Chrome Profile hiện tại (Chrome phải đóng)

Nếu bạn không muốn dùng remote debugging, có thể dùng profile Chrome hiện tại:

1. **Đóng Chrome hoàn toàn** (kiểm tra Task Manager nếu cần)
2. Trong `src/config.py`, đảm bảo:
   ```python
   USE_CURRENT_CHROME_PROFILE = True
   ```
3. Chạy scraper:
   ```bash
   python main.py
   ```

⚠️ **LƯU Ý**: Chrome phải được đóng hoàn toàn, nếu không sẽ bị lỗi lock file!

---

## 🔧 Cấu hình

Trong `src/config.py`:

```python
# Dùng Chrome profile hiện tại (với các tab đang mở)
USE_CURRENT_CHROME_PROFILE = True  # ✅ Bật để dùng Chrome đang chạy

# Hoặc dùng profile riêng
USE_CURRENT_CHROME_PROFILE = False  # Dùng profile riêng trong thư mục "user-data"
```

---

## ❓ FAQ

**Q: Tại sao không kết nối được đến Chrome?**
A: Chrome phải được khởi động với flag `--remote-debugging-port=9222`. Dùng script `start_chrome_with_debug.bat` để khởi động đúng cách.

**Q: Có thể dùng Chrome bình thường khi scraper đang chạy không?**
A: Có! Khi kết nối qua remote debugging, bạn vẫn có thể duyệt web bình thường. Scraper sẽ tạo tab mới để scrape.

**Q: Scraper có ảnh hưởng đến các tab đang mở không?**
A: Không! Scraper chỉ tạo tab mới hoặc dùng tab mới, không ảnh hưởng đến tab hiện có.

**Q: Làm sao biết scraper đã kết nối thành công?**
A: Xem log, nếu thấy:
```
✅ Đã kết nối đến Chrome đang chạy của bạn!
💡 Bạn có thể tiếp tục sử dụng Chrome bình thường!
```
→ Đã kết nối thành công!

---

## 🎯 Tóm tắt nhanh

1. Chạy `start_chrome_with_debug.bat` để mở Chrome với remote debugging
2. Chạy `python main.py` để bắt đầu scrape
3. Tiếp tục dùng Chrome bình thường, scraper sẽ chạy trong background!
