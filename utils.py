import unicodedata
import re
import hashlib
from simhash import Simhash

def normalize_text(text: str) -> str:
    """Chuẩn hóa text để so sánh Title/Author."""
    if not text: return ""
    text = str(text).lower().strip()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def calculate_simhash(text: str) -> str:
    """Tính SimHash cơ bản."""
    if not text: return "0000000000000000"
    try:
        sh = Simhash(text)
        return format(sh.value, 'x')
    except:
        return hashlib.md5(text.encode()).hexdigest()[:16]

def calculate_story_hash(chapter_1_content: str) -> str:
    """
    Tạo mã SimHash từ 500 ký tự đầu của Chapter 1 (Fingerprint).
    """
    if not chapter_1_content or len(chapter_1_content) < 50:
        return "0000000000000000"
    
    # YÊU CẦU: Chỉ lấy 500 ký tự đầu tiên
    sample_text = chapter_1_content[:500]
    return calculate_simhash(sample_text)

def get_hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
    """Tính khoảng cách Hamming."""
    try:
        val1 = int(hash1_hex, 16)
        val2 = int(hash2_hex, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count('1')
    except:
        return 100