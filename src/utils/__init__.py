"""
Utils package - Các utilities cho scraper
"""
# Import từ src.utils.py (file) và export để tương thích với import cũ
import sys
import importlib.util
from pathlib import Path

# Import từ src.utils.py (file) trực tiếp để tránh circular import
parent_dir = Path(__file__).parent.parent
utils_file = parent_dir / "utils.py"
if utils_file.exists():
    spec = importlib.util.spec_from_file_location("src_utils_module", utils_file)
    src_utils_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(src_utils_module)
    
    # Export các functions để tương thích với import cũ: from src.utils import safe_print
    safe_print = src_utils_module.safe_print
    generate_id = src_utils_module.generate_id
    convert_html_to_formatted_text = src_utils_module.convert_html_to_formatted_text
    clean_text = src_utils_module.clean_text
    download_image = src_utils_module.download_image
else:
    # Fallback nếu không tìm thấy file
    def safe_print(*args, **kwargs):
        print(*args, **kwargs)
    
    def generate_id():
        import uuid6
        return f"sh_{uuid6.uuid7().hex}"
    
    def convert_html_to_formatted_text(html_content):
        return html_content or ""
    
    def clean_text(text):
        return text.strip() if text else ""
    
    def download_image(image_url, fiction_id):
        return None

