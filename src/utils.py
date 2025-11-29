import os
import requests
import hashlib
from datetime import datetime
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

# ========== HASH UTILITIES ==========

def sha256_hash(text):
    """
    Tính SHA256 hash của một chuỗi text.
    Dùng để phát hiện thay đổi nội dung.
    
    Args:
        text: Chuỗi text cần hash
        
    Returns:
        str: Hash SHA256 (64 ký tự hex)
    """
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def hash_content(content):
    """
    Hash nội dung chapter/content.
    Alias cho sha256_hash để dễ đọc.
    """
    return sha256_hash(content)

def hash_metadata(metadata_dict):
    """
    Hash metadata (title, stats, tags, etc.) để phát hiện thay đổi.
    Chuyển dict thành string JSON rồi hash.
    
    Args:
        metadata_dict: Dictionary chứa metadata
        
    Returns:
        str: Hash SHA256 của metadata
    """
    import json
    if not metadata_dict:
        return ""
    # Sắp xếp keys để đảm bảo hash nhất quán
    sorted_metadata = json.dumps(metadata_dict, sort_keys=True, ensure_ascii=False)
    return sha256_hash(sorted_metadata)

def is_content_changed(old_hash, new_content):
    """
    Kiểm tra xem content có thay đổi không bằng cách so sánh hash.
    
    Args:
        old_hash: Hash cũ từ database
        new_content: Nội dung mới cần kiểm tra
        
    Returns:
        tuple: (is_changed: bool, new_hash: str)
    """
    if not old_hash:
        # Nếu chưa có hash cũ, coi như đã thay đổi
        new_hash = hash_content(new_content)
        return True, new_hash
    
    new_hash = hash_content(new_content)
    is_changed = (old_hash != new_hash)
    return is_changed, new_hash

def is_metadata_changed(old_hash, new_metadata):
    """
    Kiểm tra xem metadata có thay đổi không bằng cách so sánh hash.
    
    Args:
        old_hash: Hash cũ từ database
        new_metadata: Metadata mới cần kiểm tra (dict)
        
    Returns:
        tuple: (is_changed: bool, new_hash: str)
    """
    if not old_hash:
        new_hash = hash_metadata(new_metadata)
        return True, new_hash
    
    new_hash = hash_metadata(new_metadata)
    is_changed = (old_hash != new_hash)
    return is_changed, new_hash

# ========== TIMESTAMP UTILITIES ==========

def get_current_timestamp():
    """
    Lấy timestamp hiện tại dạng ISO format.
    
    Returns:
        str: Timestamp ISO format (YYYY-MM-DDTHH:MM:SS.ffffff)
    """
    return datetime.utcnow().isoformat()

def get_current_timestamp_simple():
    """
    Lấy timestamp đơn giản hơn (YYYY-MM-DD HH:MM:SS).
    
    Returns:
        str: Timestamp đơn giản
    """
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")