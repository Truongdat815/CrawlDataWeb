"""
Wattpad Login Service
Handle authentication và cookie management
"""

import os
import json
import time
from pathlib import Path
from .scrapers.base import safe_print
from src import config


class WattpadLoginService:
    """Quản lý đăng nhập và cookies cho Wattpad"""
    
    def __init__(self):
        self.cookies = None
        self.is_authenticated = False
        self.last_refresh_time = None
    
    def load_cookies_from_file(self):
        """Load cookies từ file nếu có"""
        if os.path.exists(config.COOKIE_FILE):
            try:
                with open(config.COOKIE_FILE, 'r') as f:
                    self.cookies = json.load(f)
                    self.is_authenticated = True
                    self.last_refresh_time = time.time()
                    safe_print(f"✅ Loaded cookies từ file: {config.COOKIE_FILE}")
                    return True
            except Exception as e:
                safe_print(f"⚠️ Lỗi load cookies: {e}")
                return False
        return False
    
    def save_cookies_to_file(self, cookies):
        """Lưu cookies vào file"""
        try:
            os.makedirs(os.path.dirname(config.COOKIE_FILE), exist_ok=True)
            with open(config.COOKIE_FILE, 'w') as f:
                json.dump(cookies, f, indent=2)
                safe_print(f"✅ Lưu cookies vào file: {config.COOKIE_FILE}")
                self.cookies = cookies
                self.is_authenticated = True
                self.last_refresh_time = time.time()
                return True
        except Exception as e:
            safe_print(f"❌ Lỗi lưu cookies: {e}")
            return False
    
    def should_refresh_cookies(self):
        """Check xem có cần refresh cookies không (mỗi 30 phút)"""
        if not self.last_refresh_time:
            return False
        elapsed = time.time() - self.last_refresh_time
        return elapsed > config.COOKIE_REFRESH_INTERVAL
    
    def is_already_logged_in(self, page):
        """
        Kiểm tra xem đã đăng nhập hay chưa bằng cách check URL hoặc cookies
        
        Args:
            page: Playwright page object
        
        Returns:
            True nếu đã đăng nhập
        """
        if page is None:
            return False
        
        try:
            # Method 1: Check cookies có auth token không
            cookies = page.context.cookies()
            for cookie in cookies:
                # Wattpad auth cookies thường có tên như 'token', 'auth', 'session', etc.
                if cookie.get('name') in ['token', 'auth', 'wp_id', 'session_id', '_session_id']:
                    if cookie.get('value'):
                        safe_print("   ✅ Phát hiện auth cookie - Đã đăng nhập rồi")
                        self.is_authenticated = True
                        self.cookies = cookies
                        return True
            
            # Method 2: Navigate to home and check if redirected to login
            current_url = page.url
            if 'wattpad.com' in current_url and '/login' not in current_url:
                # If we're on Wattpad but not on login page, try checking if user menu exists
                try:
                    # Check for user avatar/menu (indicates logged in)
                    user_menu_selectors = [
                        '.avatar',
                        '[data-test="user-menu"]',
                        'button[aria-label*="user" i]',
                        '.user-avatar',
                        'img[alt*="avatar" i]'
                    ]
                    
                    for selector in user_menu_selectors:
                        if page.locator(selector).count() > 0:
                            safe_print(f"   ✅ Phát hiện user menu - Đã đăng nhập rồi")
                            self.is_authenticated = True
                            self.cookies = cookies
                            return True
                except:
                    pass
            
            return False
        except Exception as e:
            safe_print(f"   ⚠️ Lỗi khi check login status: {e}")
            return False

    def login_with_playwright(self, page, username, password):
        """
        Đăng nhập vào Wattpad dùng Playwright
        
        Args:
            page: Playwright page object
            username: Email hoặc username
            password: Password
        
        Returns:
            True nếu đăng nhập thành công
        """
        if page is None:
            safe_print("❌ Playwright page chưa init")
            return False
        
        try:
            safe_print(f"🔑 Đang đăng nhập vào Wattpad...")
            
            # Navigate to login page
            page.goto("https://www.wattpad.com/login", timeout=30000)
            time.sleep(3)
            
            # Step 1: Click "Đăng nhập với email" button to show email/password form
            safe_print(f"   🖱️ Click 'Đăng nhập với email'...")
            email_login_clicked = False
            email_button_selectors = [
                'button.btn-block.btn-primary.submit-btn-new',  # From screenshot
                'button:has-text("Đăng nhập với email")',
                'button:has-text("Log in with email")',
                'button:has-text("Sign in with email")',
                '.submit-btn-new',
                'button.submit-btn-new'
            ]
            
            for selector in email_button_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector, timeout=5000)
                        email_login_clicked = True
                        safe_print(f"      ✓ Clicked: {selector}")
                        time.sleep(2)  # Wait for form to appear
                        break
                except Exception as e:
                    continue
            
            if not email_login_clicked:
                safe_print(f"   ⚠️ Không tìm thấy button 'Đăng nhập với email', thử tiếp form trực tiếp...")
            
            # Step 2: Fill username/email input
            safe_print(f"   📝 Nhập email/username...")
            
            # Try different selectors for username field
            username_filled = False
            username_selectors = [
                'input[name="username"]',
                'input[name="email"]', 
                'input[type="text"]',
                'input[type="email"]',
                '#username',
                '#email'
            ]
            
            for selector in username_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, username, timeout=5000)
                        username_filled = True
                        safe_print(f"      ✓ Used selector: {selector}")
                        break
                except:
                    continue
            
            if not username_filled:
                safe_print(f"   ❌ Không tìm thấy username/email input field")
                return False
            
            time.sleep(0.5)
            
            # Fill password
            safe_print(f"   🔐 Nhập password...")
            password_filled = False
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                '#password'
            ]
            
            for selector in password_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.fill(selector, password, timeout=5000)
                        password_filled = True
                        safe_print(f"      ✓ Used selector: {selector}")
                        break
                except:
                    continue
            
            if not password_filled:
                safe_print(f"   ❌ Không tìm thấy password input field")
                return False
            
            time.sleep(0.5)
            
            # Click login button
            safe_print(f"   ⬆️ Submit form...")
            button_clicked = False
            button_selectors = [
                'button[type="submit"]',
                'button:has-text("Log in"):not(:has-text("Google")):not(:has-text("Facebook"))',
                'input[type="submit"]',
                '.submit-button'
            ]
            
            for selector in button_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector, timeout=5000)
                        button_clicked = True
                        safe_print(f"      ✓ Used selector: {selector}")
                        break
                except:
                    continue
            
            if not button_clicked:
                safe_print(f"   ⚠️ Không tìm thấy submit button, thử enter key...")
                page.keyboard.press("Enter")
            
            # Wait for login to complete (redirect to home or profile)
            try:
                page.wait_for_url("**/home**", timeout=10000)
            except:
                # Nếu không redirect, check xem cookies có được set không
                pass
            
            time.sleep(2)
            
            # Get cookies
            cookies = page.context.cookies()
            
            if cookies:
                self.save_cookies_to_file(cookies)
                safe_print(f"✅ Đăng nhập thành công!")
                return True
            else:
                safe_print(f"❌ Đăng nhập thất bại (không có cookies)")
                return False
                
        except Exception as e:
            safe_print(f"❌ Lỗi đăng nhập: {e}")
            return False
    
    def apply_cookies_to_browser(self, page):
        """
        Áp dụng cookies vào Playwright page
        
        Args:
            page: Playwright page object
        
        Returns:
            True nếu áp dụng thành công
        """
        if page is None or not self.cookies:
            return False
        
        try:
            page.context.add_cookies(self.cookies)
            safe_print(f"✅ Applied cookies to browser")
            self.is_authenticated = True
            return True
        except Exception as e:
            safe_print(f"⚠️ Lỗi áp dụng cookies: {e}")
            return False
    
    def is_logged_in(self):
        """Check xem đã đăng nhập hay không"""
        return self.is_authenticated and self.cookies is not None
    
    def clear_cookies(self):
        """Xóa cookies"""
        try:
            if os.path.exists(COOKIES_FILE):
                os.remove(COOKIES_FILE)
                safe_print(f"✅ Xóa cookies")
        except Exception as e:
            safe_print(f"⚠️ Lỗi xóa cookies: {e}")
        
        self.cookies = None
        self.is_authenticated = False


def login_if_needed(page, username=None, password=None):
    """
    Helper function để đăng nhập nếu cần
    
    Args:
        page: Playwright page object
        username: Email/username (optional)
        password: Password (optional)
    
    Returns:
        LoginService object
    """
    login_service = WattpadLoginService()
    
    # Thử load cookies từ file trước
    if login_service.load_cookies_from_file():
        if page:
            login_service.apply_cookies_to_browser(page)
        safe_print(f"✅ Đã có cookies, sử dụng để đăng nhập")
        return login_service
    
    # Nếu không có cookies, đăng nhập mới
    if username and password and page:
        if login_service.login_with_playwright(page, username, password):
            return login_service
        else:
            safe_print(f"⚠️ Đăng nhập thất bại, tiếp tục mà không đăng nhập")
            return login_service
    else:
        safe_print(f"⚠️ Không có credentials hoặc page, bỏ qua đăng nhập")
        return login_service


if __name__ == "__main__":
    # Test
    from playwright.sync_api import sync_playwright
    
    print("\n" + "="*60)
    print("🔑 WATTPAD LOGIN TEST")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Nhập credentials
        username = input("Email/Username: ")
        password = input("Password: ")
        
        # Đăng nhập
        login_service = login_if_needed(page, username, password)
        
        if login_service.is_logged_in():
            print("\n✅ Đăng nhập thành công!")
            print(f"Cookies lưu tại: {COOKIES_FILE}")
        else:
            print("\n❌ Đăng nhập thất bại")
        
        browser.close()
