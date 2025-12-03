# 🔒 Hướng dẫn Manual Verify Cloudflare

## ✅ Đã thêm chế độ Manual Verify

Khi gặp Cloudflare challenge, code sẽ:
1. Phát hiện challenge
2. Hướng dẫn bạn verify thủ công
3. Đợi bạn verify và bấm ENTER
4. Hoặc tự động detect khi challenge pass

## 🚀 Cách sử dụng

### Bước 1: Chạy code

```bash
python main.py
```

### Bước 2: Khi thấy Cloudflare challenge

Code sẽ hiển thị:
```
⚠️ PHÁT HIỆN CLOUDFLARE CHALLENGE!

📋 HƯỚNG DẪN:
   1. Nhìn vào browser window
   2. Verify Cloudflare challenge (tick checkbox)
   3. Đợi challenge hoàn thành (thường 5-15 giây)
   4. Khi thấy page load xong (có title, có content)
   5. Bấm ENTER trong terminal này để tiếp tục

⌨️  BẤM ENTER KHI ĐÃ VERIFY XONG...
```

### Bước 3: Verify trong browser

1. Nhìn vào browser window
2. Tick checkbox để verify
3. Đợi challenge hoàn thành (thường 5-15 giây)
4. Khi thấy page load xong (có title, có content)

### Bước 4: Bấm ENTER

Bấm ENTER trong terminal để code tiếp tục.

## ⚙️ Cấu hình

**File: `src/config.py`**

```python
ENABLE_MANUAL_VERIFY = True  # Bật chế độ đợi verify thủ công
HEADLESS = False  # QUAN TRỌNG: Phải False để thấy browser
```

## 💡 Tips

1. **Nếu code tự động detect:**
   - Code sẽ tự động detect khi challenge pass
   - Không cần bấm ENTER

2. **Nếu code không detect:**
   - Bấm ENTER sau khi verify xong
   - Code sẽ tiếp tục

3. **Lần sau:**
   - Cookies đã được lưu
   - Không cần verify lại

## 🎯 Kết quả

- ✅ Verify 1 lần duy nhất
- ✅ Cookies được lưu tự động
- ✅ Lần sau không cần verify lại
- ✅ Code đợi bạn verify thủ công
- ✅ Không bị loop

