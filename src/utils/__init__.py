# Utils package
import os
import requests
from src.config import IMAGES_DIR

def download_image(image_url, fiction_id):
    """
    Tải ảnh từ URL và lưu vào folder local.
    Trả về: Đường dẫn file (Path) để lưu vào JSON.
    
    Args:
        image_url: URL của ảnh từ web
        fiction_id: Story ID để tạo tên file
    
    Returns:
        Đường dẫn file nếu download thành công, None nếu thất bại
    """
    if not image_url or "http" not in image_url:
        return None
    
    try:
        # Tạo tên file: ví dụ 11963741_cover.jpg
        filename = f"{fiction_id}_cover.jpg"
        file_path = os.path.join(IMAGES_DIR, filename)
        
        # Tải về
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path  # Trả về đường dẫn để lưu vào JSON
    except Exception as e:
        from src.scrapers.base import safe_print
        safe_print(f"      ⚠️ Lỗi tải ảnh: {e}")
    
    return None
