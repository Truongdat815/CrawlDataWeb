"""
Utility functions cho hash-based duplicate detection
- SimHash cho chapter content
- Hash 500 từ đầu tiên của chapter 1
"""
import hashlib
import re
from typing import Optional


def get_first_n_words(text: str, n: int = 500) -> str:
    """
    Lấy n từ đầu tiên từ text
    
    Args:
        text: Nội dung text
        n: Số từ cần lấy (mặc định 500)
    
    Returns:
        String chứa n từ đầu tiên
    """
    if not text:
        return ""
    
    # Tách thành từ (split by whitespace)
    words = text.split()
    
    # Lấy n từ đầu tiên
    first_n = words[:n]
    
    return " ".join(first_n)


def calculate_simhash(text: str, hash_bits: int = 64) -> int:
    """
    Tính SimHash cho text
    SimHash là locality-sensitive hashing algorithm
    - Similar texts sẽ có hash gần nhau (ít bit khác nhau)
    - Khác với MD5/SHA1 (1 bit khác = hoàn toàn khác)
    
    Args:
        text: Text cần hash
        hash_bits: Số bit của hash (mặc định 64)
    
    Returns:
        Integer hash value
    """
    if not text:
        return 0
    
    # Tokenize: tách thành words và tạo shingles (n-grams)
    words = re.findall(r'\w+', text.lower())
    
    # Tạo 3-grams (shingles)
    shingles = []
    for i in range(len(words) - 2):
        shingle = " ".join(words[i:i+3])
        shingles.append(shingle)
    
    if not shingles:
        # Fallback: dùng words nếu không đủ cho 3-grams
        shingles = words
    
    # Vector để lưu hash bits
    v = [0] * hash_bits
    
    # Với mỗi shingle, hash và cập nhật vector
    for shingle in shingles:
        # Hash shingle thành integer
        h = int(hashlib.md5(shingle.encode('utf-8')).hexdigest(), 16)
        
        # Cập nhật vector: bit 1 = +1, bit 0 = -1
        for i in range(hash_bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    
    # Tạo fingerprint: bit 1 nếu v[i] > 0, bit 0 nếu v[i] <= 0
    fingerprint = 0
    for i in range(hash_bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    
    return fingerprint


def hamming_distance(hash1: int, hash2: int) -> int:
    """
    Tính Hamming distance giữa 2 hash (số bit khác nhau)
    
    Args:
        hash1: Hash thứ nhất
        hash2: Hash thứ hai
    
    Returns:
        Số bit khác nhau
    """
    # XOR để tìm bit khác nhau
    xor = hash1 ^ hash2
    
    # Đếm số bit 1 trong XOR (bit khác nhau)
    distance = 0
    while xor:
        distance += xor & 1
        xor >>= 1
    
    return distance


def is_similar_hash(hash1: int, hash2: int, max_distance: int = 3) -> bool:
    """
    Kiểm tra 2 hash có tương tự không (dựa trên Hamming distance)
    
    Args:
        hash1: Hash thứ nhất
        hash2: Hash thứ hai
        max_distance: Độ lệch tối đa (mặc định 3 bit)
    
    Returns:
        True nếu distance <= max_distance
    """
    if hash1 == 0 or hash2 == 0:
        return False
    
    distance = hamming_distance(hash1, hash2)
    return distance <= max_distance


def create_chapter_hash(content: str, words: int = 500) -> Optional[int]:
    """
    Tạo hash cho chapter content (500 từ đầu tiên)
    
    Args:
        content: Nội dung chapter
        words: Số từ đầu tiên để hash (mặc định 500)
    
    Returns:
        SimHash value hoặc None nếu không có content
    """
    if not content:
        return None
    
    # Lấy 500 từ đầu tiên
    first_words = get_first_n_words(content, words)
    
    if not first_words:
        return None
    
    # Tính SimHash
    simhash = calculate_simhash(first_words)
    
    return simhash


def create_story_hash(content: str, words: int = 500) -> Optional[str]:
    """
    Tạo storyHash cho story (SimHash 500 từ đầu chapter 1, format hex string)
    
    Args:
        content: Nội dung chapter 1
        words: Số từ đầu tiên để hash (mặc định 500)
    
    Returns:
        Hex string hash (ví dụ: "8e7ea9285d0d6eed") hoặc None nếu không có content
    """
    if not content:
        return None
    
    # Lấy 500 từ đầu tiên
    first_words = get_first_n_words(content, words)
    
    if not first_words:
        return None
    
    # ✅ Dùng SimHash thay vì MD5
    simhash_value = calculate_simhash(first_words, hash_bits=64)
    
    # Convert SimHash integer sang hex string (16 ký tự)
    hex_hash = format(simhash_value, '016x')  # Format thành 16 ký tự hex
    
    return hex_hash
