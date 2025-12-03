"""
Cookie Manager - Lưu và load cookies để tránh phải verify Cloudflare nhiều lần
"""
import json
import os
from pathlib import Path
# Import safe_print từ src.utils (file, không phải package)
# Tránh conflict với src.utils package
import sys
import importlib.util
from pathlib import Path

# Import từ src.utils.py (file) trực tiếp
parent_dir = Path(__file__).parent.parent
utils_file = parent_dir / "utils.py"
if utils_file.exists():
    spec = importlib.util.spec_from_file_location("src_utils", utils_file)
    src_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(src_utils)
    safe_print = src_utils.safe_print
else:
    # Fallback
    def safe_print(*args, **kwargs):
        print(*args, **kwargs)

COOKIE_FILE = Path("cookies_scribblehub.json")

def save_cookies(context):
    """
    Lưu cookies từ browser context vào file
    Args:
        context: Playwright browser context
    """
    try:
        cookies = context.cookies()
        if cookies:
            with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            safe_print(f"      💾 Đã lưu {len(cookies)} cookies vào {COOKIE_FILE}")
            return True
    except Exception as e:
        safe_print(f"      ⚠️ Lỗi khi lưu cookies: {e}")
        return False

def load_cookies(context):
    """
    Load cookies từ file vào browser context
    Args:
        context: Playwright browser context
    Returns:
        bool: True nếu load thành công, False nếu không có cookies
    """
    try:
        if not COOKIE_FILE.exists():
            safe_print(f"      ℹ️ Không tìm thấy file cookies ({COOKIE_FILE})")
            return False
        
        with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        if cookies:
            # Chỉ add cookies cho domain scribblehub.com
            scribblehub_cookies = [
                cookie for cookie in cookies 
                if 'scribblehub.com' in cookie.get('domain', '')
            ]
            
            if scribblehub_cookies:
                context.add_cookies(scribblehub_cookies)
                safe_print(f"      ✅ Đã load {len(scribblehub_cookies)} cookies từ file")
                return True
            else:
                safe_print(f"      ⚠️ Không có cookies cho scribblehub.com trong file")
                return False
    except Exception as e:
        safe_print(f"      ⚠️ Lỗi khi load cookies: {e}")
        return False

def clear_cookies():
    """Xóa file cookies"""
    try:
        if COOKIE_FILE.exists():
            COOKIE_FILE.unlink()
            safe_print(f"      🗑️ Đã xóa file cookies")
            return True
    except Exception as e:
        safe_print(f"      ⚠️ Lỗi khi xóa cookies: {e}")
        return False

