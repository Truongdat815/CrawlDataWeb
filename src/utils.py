import os
import re
import time
import requests
import uuid6
import html as html_module
from urllib.parse import urlparse, urlunparse
from src.config import IMAGES_DIR, IMAGE_UPLOAD_API_URL, IMAGE_UPLOAD_API_KEY, IMAGE_SERVER_BASE_URL

def clean_text(text):
    """Hàm làm sạch văn bản, xóa khoảng trắng thừa"""
    if not text:
        return ""
    return text.strip()

def upload_image(file_path):
    """
    Upload ảnh lên server qua API.
    Args:
        file_path: Đường dẫn đến file ảnh cần upload (ví dụ: "data/images/21220_cover.jpg")
    Returns:
        URL của ảnh trên server nếu thành công, None nếu thất bại
    """
    if not file_path or not os.path.exists(file_path):
        safe_print(f"❌ File không tồn tại: {file_path}")
        return None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'image': (os.path.basename(file_path), f, 'image/jpeg')}
            headers = {'x-api-key': IMAGE_UPLOAD_API_KEY}
            
            response = requests.post(
                IMAGE_UPLOAD_API_URL,
                headers=headers,
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                # API trả về URL trực tiếp hoặc trong JSON
                image_url = None
                try:
                    json_response = response.json()
                    # Thử các field phổ biến
                    image_url = json_response.get('url') or json_response.get('data') or json_response.get('image_url')
                    # Nếu response là string URL
                    if not image_url and isinstance(json_response, str):
                        image_url = json_response
                except (ValueError, AttributeError):
                    # Nếu response không phải JSON, có thể là URL trực tiếp
                    response_text = response.text.strip()
                    if response_text:
                        image_url = response_text
                
                if image_url:
                    # Nếu là relative path (bắt đầu bằng /), thêm base URL
                    if image_url.startswith('/'):
                        image_url = IMAGE_SERVER_BASE_URL + image_url
                    safe_print(f"✅ Upload thành công: {image_url}")
                    return image_url
                else:
                    safe_print(f"⚠️ Upload thành công nhưng không parse được URL: {response.text}")
                    return None
            else:
                safe_print(f"❌ Lỗi upload: Status {response.status_code}, Response: {response.text}")
                return None
                
    except Exception as e:
        safe_print(f"❌ Lỗi upload ảnh: {e}")
        return None

def download_image(image_url, fiction_id):
    """
    Tải ảnh từ URL, lưu vào folder local, và tự động upload lên server.
    Trả về: URL của ảnh trên server (nếu upload thành công) hoặc đường dẫn local (nếu upload thất bại).
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
            
            # Tự động upload lên server
            # safe_print(f"📤 Đang upload ảnh lên server...")
            # uploaded_url = upload_image(file_path)
            
            # if uploaded_url:
            #     # Trả về URL từ server
            #     return uploaded_url
            # else:
                # Nếu upload thất bại, trả về đường dẫn local
                safe_print(f"⚠️ Upload thất bại, sử dụng đường dẫn local: {file_path}")
                return file_path
    except Exception as e:
        safe_print(f"❌ Lỗi tải ảnh: {e}")
    
    return None

def normalize_url(url):
    """
    Normalize URL để so sánh: loại bỏ query params, fragment, trailing slash
    Args:
        url: URL cần normalize
    Returns:
        normalized_url: URL đã được normalize
    """
    if not url:
        return None
    
    try:
        # Parse URL
        parsed = urlparse(url)
        # Tạo URL mới không có query và fragment
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),  # Loại bỏ trailing slash
            '',  # params
            '',  # query
            ''   # fragment
        ))
        return normalized.lower()  # Convert về lowercase để so sánh
    except:
        return url.strip().lower()

def create_simhash(content, hash_bits=64):
    """
    Tạo SimHash từ content (locality-sensitive hashing)
    SimHash cho phép so sánh similarity: văn bản tương tự sẽ có hash gần nhau (lệch ít bit)
    Args:
        content: Nội dung text
        hash_bits: Số bit của hash (mặc định 64)
    Returns:
        simhash_int: SimHash dưới dạng integer
    """
    if not content:
        return None
    
    try:
        # Normalize: lowercase, remove whitespace thừa
        normalized = content.lower().strip()
        if not normalized:
            return None
        
        # Tách thành từ (tokens)
        import re
        # Tách theo word boundaries, giữ lại chữ và số
        words = re.findall(r'\b\w+\b', normalized)
        if not words:
            return None
        
        # Feature vector: mỗi bit position có một giá trị tổng
        feature_vector = [0] * hash_bits
        
        # Với mỗi token, hash nó và cập nhật feature vector
        for word in words:
            # Hash token thành integer (dùng built-in hash() của Python)
            # hash() trả về signed integer, chuyển sang unsigned 64-bit
            token_hash = hash(word.encode('utf-8')) & 0xFFFFFFFFFFFFFFFF
            
            # Cập nhật feature vector cho từng bit
            for i in range(hash_bits):
                # Kiểm tra bit i của token_hash
                if token_hash & (1 << i):
                    feature_vector[i] += 1
                else:
                    feature_vector[i] -= 1
        
        # Tạo SimHash: bit i = 1 nếu feature_vector[i] > 0, else 0
        simhash_int = 0
        for i in range(hash_bits):
            if feature_vector[i] > 0:
                simhash_int |= (1 << i)
        
        return simhash_int
    except Exception as e:
        safe_print(f"⚠️ Lỗi khi tạo simhash: {e}")
        return None

def create_content_hash(content, max_words=500):
    """
    Tạo SimHash string từ chapter content (lấy 500 từ đầu tiên)
    SimHash cho phép so sánh similarity: văn bản tương tự sẽ có hash gần nhau (lệch ít bit)
    Args:
        content: Nội dung chapter (text)
        max_words: Số từ tối đa để tạo hash (mặc định 500)
    Returns:
        hash_string: SimHash string (hex của integer, 16 ký tự cho 64-bit)
    """
    if not content:
        return None
    
    try:
        # Tách thành từ (split by whitespace)
        words = content.split()
        # Lấy 500 từ đầu tiên
        content_sample = ' '.join(words[:max_words]) if len(words) > max_words else ' '.join(words)
        
        # Dùng SimHash (locality-sensitive hashing)
        simhash_int = create_simhash(content_sample, hash_bits=64)
        if simhash_int is None:
            return None
        # Convert integer sang hex string (16 ký tự cho 64-bit)
        return format(simhash_int, '016x')
    except Exception as e:
        safe_print(f"⚠️ Lỗi khi tạo hash: {e}")
        return None

def hamming_distance(hash1, hash2):
    """
    Tính Hamming distance (số bit khác nhau) giữa 2 hash string
    Với SimHash: distance nhỏ = văn bản tương tự, distance lớn = văn bản khác nhau
    Args:
        hash1: Hash string thứ nhất (hex string)
        hash2: Hash string thứ hai (hex string)
    Returns:
        distance: Số bit khác nhau (0 = giống hệt, càng lớn càng khác)
    """
    if not hash1 or not hash2:
        return float('inf')
    
    try:
        # Convert hex string sang integer
        int1 = int(hash1, 16)
        int2 = int(hash2, 16)
        # XOR để tìm bit khác nhau
        xor_result = int1 ^ int2
        # Đếm số bit 1 (bit khác nhau)
        distance = bin(xor_result).count('1')
        return distance
    except:
        return float('inf')

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
    Tạo ID theo format rr_{uuid}
    Sử dụng UUID v7 (có timestamp, sortable theo thời gian)
    Returns: string với format "rr_{uuid}"
    """
    return f"rr_{uuid6.uuid7().hex}"

def goto_with_retry(page, url, timeout, max_retries=3, retry_delay=5, context_name=""):
    """
    Navigate đến URL với retry mechanism khi timeout
    
    Args:
        page: Playwright page object
        url: URL cần navigate
        timeout: Timeout cho mỗi lần thử (ms)
        max_retries: Số lần retry tối đa (mặc định 3)
        retry_delay: Delay giữa các lần retry (giây, mặc định 5)
        context_name: Tên context để log (ví dụ: "Thread-1", "Chapter 5")
    
    Returns:
        None nếu thành công
    
    Raises:
        Exception nếu hết retry vẫn lỗi
    """
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            page.goto(url, timeout=timeout)
            if retry_count > 0:
                safe_print(f"      ✅ {context_name}: Retry thành công sau {retry_count} lần thử")
            return
        except Exception as e:
            retry_count += 1
            last_error = e
            error_msg = str(e)
            
            # Chỉ retry nếu là timeout hoặc network error
            is_timeout = "timeout" in error_msg.lower() or "Timeout" in error_msg
            is_network = "network" in error_msg.lower() or "net::" in error_msg
            
            if retry_count < max_retries and (is_timeout or is_network):
                safe_print(f"      ⚠️ {context_name}: Timeout/Network error lần {retry_count}/{max_retries}, thử lại sau {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                # Nếu không phải timeout/network hoặc hết retry, raise lỗi
                if not (is_timeout or is_network):
                    # Lỗi khác không phải timeout, raise ngay
                    raise
                # Hết retry, raise lỗi cuối cùng
                safe_print(f"      ❌ {context_name}: Hết retry ({max_retries} lần), không thể load URL")
                raise last_error
    
    # Nếu đến đây thì đã hết retry
    raise last_error

def wait_for_selector_with_retry(page, selector, timeout, max_retries=3, retry_delay=2, context_name=""):
    """
    Wait for selector với retry mechanism khi timeout
    
    Args:
        page: Playwright page object
        selector: CSS selector
        timeout: Timeout cho mỗi lần thử (ms)
        max_retries: Số lần retry tối đa (mặc định 3)
        retry_delay: Delay giữa các lần retry (giây, mặc định 2)
        context_name: Tên context để log
    
    Returns:
        None nếu thành công
    
    Raises:
        Exception nếu hết retry vẫn lỗi
    """
    retry_count = 0
    last_error = None
    
    while retry_count < max_retries:
        try:
            page.wait_for_selector(selector, timeout=timeout)
            if retry_count > 0:
                safe_print(f"      ✅ {context_name}: Wait selector thành công sau {retry_count} lần thử")
            return
        except Exception as e:
            retry_count += 1
            last_error = e
            error_msg = str(e)
            
            is_timeout = "timeout" in error_msg.lower() or "Timeout" in error_msg
            
            if retry_count < max_retries and is_timeout:
                safe_print(f"      ⚠️ {context_name}: Timeout khi chờ selector, thử lại sau {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                if not is_timeout:
                    raise
                safe_print(f"      ❌ {context_name}: Hết retry khi chờ selector ({max_retries} lần)")
                raise last_error
    
    raise last_error

def parse_and_format_date(date_str):
    """
    Parse và format date từ string (có thể từ title attribute hoặc text content của thẻ <time>)
    Format input: "6/30/2025, 1:48:03 AM" hoặc "4/24/2024, 3:28 AM" (MM/DD/YYYY)
    Format output: "30/6/2025, 1:48 AM" (DD/MM/YYYY, chỉ giờ:phút, bỏ giây)
    
    Args:
        date_str: String date, ví dụ "6/30/2025, 1:48:03 AM" hoặc "4/24/2024, 3:28 AM"
    Returns:
        Formatted date string với format DD/MM/YYYY hoặc None nếu parse lỗi
    """
    if not date_str:
        return None
    
    try:
        # Parse format: "6/30/2025, 1:48:03 AM" hoặc "4/24/2024, 3:28 AM"
        # Tách phần date và time
        parts = date_str.split(',', 1)
        if len(parts) != 2:
            return None
        
        date_part = parts[0].strip()  # "6/30/2025"
        time_part = parts[1].strip()  # "1:48:03 AM"
        
        # Parse date: MM/DD/YYYY
        date_components = date_part.split('/')
        if len(date_components) != 3:
            return None
        
        month = int(date_components[0])
        day = int(date_components[1])
        year = int(date_components[2])
        
        # Parse time: "1:48:03 AM" -> chỉ lấy giờ:phút và AM/PM
        # Tách theo dấu hai chấm
        time_parts = time_part.split(':')
        if len(time_parts) >= 2:
            hour = time_parts[0].strip()
            # Phần minute có thể là "48" hoặc "48:03 AM" hoặc "48 AM"
            minute_with_rest = time_parts[1].strip()
            
            # Tách minute và phần còn lại (giây và AM/PM)
            minute_rest_parts = minute_with_rest.split()
            minute = minute_rest_parts[0]  # Lấy phần đầu (phút)
            
            # Tìm AM/PM trong time_part
            am_pm = ""
            if "AM" in time_part.upper():
                am_pm = "AM"
            elif "PM" in time_part.upper():
                am_pm = "PM"
            
            # Format time chỉ với giờ:phút AM/PM
            if am_pm:
                formatted_time = f"{hour}:{minute} {am_pm}"
            else:
                formatted_time = f"{hour}:{minute}"
        else:
            formatted_time = time_part
        
        # Format lại: DD/MM/YYYY, giờ:phút AM/PM
        formatted_date = f"{day}/{month}/{year}, {formatted_time}"
        return formatted_date
    except Exception as e:
        safe_print(f"⚠️ Lỗi khi parse date từ title: {e}")
        return None

def parse_and_format_datetime(datetime_str):
    """
    Parse và format date từ datetime attribute của thẻ <time>
    Format input: "2024-10-15T21:21:47.0000000Z" (ISO 8601)
    Format output: "16/10/2024, 4:21 AM" (DD/MM/YYYY, HH:MM AM/PM)
    
    Args:
        datetime_str: String từ datetime attribute, ví dụ "2024-10-15T21:21:47.0000000Z"
    Returns:
        Formatted date string với format DD/MM/YYYY, HH:MM AM/PM hoặc None nếu parse lỗi
    """
    if not datetime_str:
        return None
    
    try:
        from datetime import datetime
        
        # Parse ISO format, xử lý cả Z và timezone
        if datetime_str.endswith('Z'):
            datetime_str = datetime_str.replace('Z', '+00:00')
        
        # Parse ISO format
        dt = datetime.fromisoformat(datetime_str)
        
        # Format lại: DD/MM/YYYY, HH:MM AM/PM
        hour = dt.hour
        minute = dt.minute
        am_pm = "AM" if hour < 12 else "PM"
        hour_12 = hour if hour <= 12 else hour - 12
        if hour_12 == 0:
            hour_12 = 12
        
        formatted_date = f"{dt.day}/{dt.month}/{dt.year}, {hour_12}:{minute:02d} {am_pm}"
        return formatted_date
    except Exception as e:
        safe_print(f"⚠️ Lỗi khi parse datetime: {e}")
        return None

def parse_and_format_comment_date(title_str):
    """
    Parse và format date từ title attribute của thẻ <time> trong comment
    Format input: "Sunday, October 28, 2018 9:35:24 PM"
    Format output: "28/10/2018, 9:35 PM" (DD/MM/YYYY, chỉ giờ:phút, bỏ giây)
    
    Args:
        title_str: String từ title attribute, ví dụ "Sunday, October 28, 2018 9:35:24 PM"
    Returns:
        Formatted date string với format DD/MM/YYYY hoặc None nếu parse lỗi
    """
    if not title_str:
        return None
    
    try:
        # Parse format: "Sunday, October 28, 2018 9:35:24 PM"
        # Tách theo dấu phẩy
        parts = title_str.split(',')
        if len(parts) < 3:
            return None
        
        # Bỏ qua phần đầu (day name: "Sunday")
        month_day_part = parts[1].strip()  # "October 28"
        year_time_part = parts[2].strip()  # "2018 9:35:24 PM"
        
        # Parse month và day: "October 28"
        month_day_parts = month_day_part.split()
        if len(month_day_parts) != 2:
            return None
        
        month_name = month_day_parts[0]  # "October"
        day = int(month_day_parts[1])    # "28"
        
        # Convert month name sang số
        month_map = {
            "January": 1, "February": 2, "March": 3, "April": 4,
            "May": 5, "June": 6, "July": 7, "August": 8,
            "September": 9, "October": 10, "November": 11, "December": 12
        }
        month = month_map.get(month_name)
        if not month:
            return None
        
        # Parse year và time: "2018 9:35:24 PM"
        year_time_parts = year_time_part.split()
        if len(year_time_parts) < 2:
            return None
        
        year = int(year_time_parts[0])  # "2018"
        time_str = ' '.join(year_time_parts[1:])  # "9:35:24 PM"
        
        # Parse time: "9:35:24 PM" -> chỉ lấy giờ:phút và AM/PM
        time_parts = time_str.split(':')
        if len(time_parts) >= 2:
            hour = time_parts[0].strip()
            minute_with_rest = time_parts[1].strip()
            
            # Tách minute và phần còn lại (giây và AM/PM)
            minute_rest_parts = minute_with_rest.split()
            minute = minute_rest_parts[0]  # Lấy phần đầu (phút)
            
            # Tìm AM/PM trong time_str
            am_pm = ""
            if "AM" in time_str.upper():
                am_pm = "AM"
            elif "PM" in time_str.upper():
                am_pm = "PM"
            
            # Format time chỉ với giờ:phút AM/PM
            if am_pm:
                formatted_time = f"{hour}:{minute} {am_pm}"
            else:
                formatted_time = f"{hour}:{minute}"
        else:
            formatted_time = time_str
        
        # Format lại: DD/MM/YYYY, giờ:phút AM/PM
        formatted_date = f"{day}/{month}/{year}, {formatted_time}"
        return formatted_date
    except Exception as e:
        safe_print(f"⚠️ Lỗi khi parse date từ comment title: {e}")
        return None

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