import os
import re
import requests
import uuid6
import html as html_module
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

def safe_print(*args, **kwargs):
    """Print function an toàn với encoding UTF-8 trên Windows"""
    try:
        # Thử print bình thường
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Nếu lỗi encoding, encode lại thành ASCII-safe
        message = ' '.join(str(arg) for arg in args)
        # Thay thế emoji và ký tự đặc biệt
        message = message.encode('ascii', 'replace').decode('ascii')
        print(message, **kwargs)

def generate_id():
    """
    Tạo ID theo format sh_{uuid} (cho tất cả khóa chính)
    Sử dụng UUID v7 (có timestamp, sortable theo thời gian)
    Returns: string với format "sh_{uuid}"
    """
    return f"sh_{uuid6.uuid7().hex}"

def convert_html_to_formatted_text(html_content):
    """
    Chuyển đổi HTML sang text với định dạng đúng (giữ nguyên xuống dòng như trong UI)
    - Mỗi thẻ <p> = một đoạn văn, các đoạn cách nhau bằng một dòng trống
    - Thẻ <br> = xuống dòng
    - Giữ nguyên cấu trúc như trong UI
    """
    if not html_content:
        return ""
    
    # Decode HTML entities trước
    html_content = html_module.unescape(html_content)
    
    # Xử lý theo thứ tự để đảm bảo định dạng đúng
    text = html_content
    
    # 1. Xử lý <br> và <br/> trước - xuống dòng ngay lập tức
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # 2. Xử lý các thẻ block: <p> - mỗi đoạn văn cách nhau 1 dòng trống
    # Thay thế </p> thành dấu phân cách đoạn (2 dòng xuống)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    # Xóa thẻ mở <p>
    text = re.sub(r'<p[^>]*>', '', text, flags=re.IGNORECASE)
    
    # 3. Xử lý các thẻ block khác: <div> - xuống dòng
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<div[^>]*>', '', text, flags=re.IGNORECASE)
    
    # 4. Xử lý các thẻ heading (h1, h2, h3, ...) - xuống dòng trước và sau
    text = re.sub(r'</h[1-6]>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h[1-6][^>]*>', '\n', text, flags=re.IGNORECASE)
    
    # 5. Xóa tất cả các thẻ HTML còn lại (giữ lại text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # 6. Làm sạch: xử lý các dòng trống và khoảng trắng thừa
    lines = text.split('\n')
    cleaned_lines = []
    
    prev_empty = False
    for line in lines:
        # Strip cả 2 bên để loại bỏ khoảng trắng thừa (từ HTML indentation)
        stripped_line = line.strip()
        
        # Xử lý dòng trống
        if not stripped_line:
            # Chỉ thêm 1 dòng trống giữa các đoạn (không thêm nhiều dòng trống liên tiếp)
            if not prev_empty:
                cleaned_lines.append('')
            prev_empty = True
        else:
            # Giữ nguyên dòng có nội dung (đã strip khoảng trắng thừa)
            cleaned_lines.append(stripped_line)
            prev_empty = False
    
    # Loại bỏ dòng trống ở đầu và cuối (nhưng giữ dòng trống giữa các đoạn)
    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    
    result = '\n'.join(cleaned_lines)
    
    # Loại bỏ khoảng trắng thừa ở đầu và cuối toàn bộ text
    # Nhưng vẫn giữ nguyên cấu trúc bên trong (các dòng trống giữa đoạn)
    result = result.strip()
    
    # Đảm bảo không có khoảng trắng thừa ở đầu mỗi dòng (từ HTML indentation)
    # Normalize lại để chắc chắn
    if result:
        lines = result.split('\n')
        final_lines = []
        for line in lines:
            # Strip từng dòng để loại bỏ khoảng trắng thừa
            clean_line = line.strip()
            # Giữ dòng trống nếu là dòng trống thật
            if not clean_line:
                final_lines.append('')
            else:
                final_lines.append(clean_line)
        result = '\n'.join(final_lines).strip()
    
    return result