import os
import requests
from src.config import IMAGES_DIR

def clean_text(text):
    """Hàm làm sạch văn bản, xóa khoảng trắng thừa"""
    if not text:
        return ""
    return text.strip()

def download_image(image_url, fiction_id):
    """
    Tải ảnh từ URL và lưu vào folder local.
    Trả về: Đường dẫn file (Path) để lưu vào JSON.
    """
    if not image_url or "http" not in image_url:
        return None
    
    try:
        # Tạo tên file: ví dụ 21220_cover.jpg
        filename = f"{fiction_id}_cover.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Tải về
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path # Trả về đường dẫn để lưu DB
    except Exception as e:
        print(f"❌ Lỗi tải ảnh: {e}")
    
    return None