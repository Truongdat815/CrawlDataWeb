# Hướng dẫn cấu hình MongoDB

## ✅ Đã cấu hình:
- Username: `ngohoangtruongdat2_db_user`
- Password: `X!ZmPN8BBPaplFPC`
- Cluster URL: `project.uoeyhrh.mongodb.net`
- Database: `royalroad_db`
- Collection: `fictions`

## ⚠️ Lỗi "authentication failed" - Cách khắc phục:

### 1. Kiểm tra IP Whitelist trong MongoDB Atlas:
- Đăng nhập vào [MongoDB Atlas](https://cloud.mongodb.com)
- Vào **Network Access** (hoặc **IP Access List**)
- Thêm IP hiện tại của bạn:
  - Click **Add IP Address**
  - Chọn **Add Current IP Address** (tự động lấy IP của bạn)
  - Hoặc chọn **Allow Access from Anywhere** (0.0.0.0/0) - **CHỈ DÙNG CHO TEST, KHÔNG AN TOÀN CHO PRODUCTION**

### 2. Kiểm tra Database User:
- Vào **Database Access** trong MongoDB Atlas
- Đảm bảo user `ngohoangtruongdat2_db_user` đã được tạo và có quyền đọc/ghi
- Nếu chưa có, tạo user mới với password `X!ZmPN8BBPaplFPC`

### 3. Test kết nối:
```bash
python test_mongodb.py
```

### 4. Nếu vẫn lỗi, thử connection string trực tiếp:
Copy connection string từ MongoDB Atlas:
- Vào **Database** → Click **Connect** → **Connect your application**
- Copy connection string và set vào biến môi trường:

```powershell
$env:MONGODB_URI="mongodb+srv://ngohoangtruongdat2_db_user:X!ZmPN8BBPaplFPC@project.uoeyhrh.mongodb.net/?retryWrites=true&w=majority&appName=Project"
python test_mongodb.py
```

## 📝 Lưu ý:
- Password có ký tự đặc biệt `!` nên đã được URL encode thành `%21`
- Connection string đã được cấu hình tự động trong `src/config.py`
- Nếu MongoDB không kết nối được, scraper vẫn sẽ lưu vào file JSON

