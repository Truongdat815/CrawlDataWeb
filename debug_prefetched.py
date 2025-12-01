"""
Debug window.prefetched structure
"""

import json
from playwright.sync_api import sync_playwright
from src import config
from src.scrapers.base import safe_print


def debug_prefetched():
    """Debug window.prefetched structure"""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Show browser
        page = browser.new_page()
        
        # Đăng nhập trước
        from src.login_service import WattpadLoginService
        login_service = WattpadLoginService()
        
        if not login_service.load_cookies_from_file():
            safe_print("🔑 Đăng nhập...")
            login_service.login_with_playwright(page, config.WATTPAD_USERNAME, config.WATTPAD_PASSWORD)
        else:
            safe_print("✅ Load cookies từ file")
            login_service.apply_cookies_to_browser(page)
        
        # Navigate to story
        url = "https://www.wattpad.com/1585675450-sidelined-2-intercepted"
        safe_print(f"\n🌐 Navigate to: {url}")
        page.goto(url, wait_until="load")
        
        # Wait for JS to render
        safe_print("⏳ Wait 5s for JS to render...")
        page.wait_for_timeout(5000)
        
        # Check what's in window
        safe_print("\n🔍 Checking window object...")
        result = page.evaluate("""() => {
            return {
                has_prefetched: typeof window.prefetched !== 'undefined',
                prefetched_keys: window.prefetched ? Object.keys(window.prefetched).slice(0, 20) : [],
                prefetched_sample: window.prefetched ? JSON.stringify(window.prefetched).substring(0, 500) : 'N/A',
                window_keys: Object.keys(window).filter(k => k.toLowerCase().includes('prefetch') || k.toLowerCase().includes('data') || k.toLowerCase().includes('story')).slice(0, 20),
                document_title: document.title,
                location: window.location.href
            }
        }""")
        
        print("\n" + "="*60)
        print("📊 DEBUG RESULTS:")
        print("="*60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Thêm check HTML content
        safe_print("\n🔍 Checking HTML content...")
        html_check = page.evaluate("""() => {
            return {
                has_script_tags: document.querySelectorAll('script').length,
                script_with_prefetched: Array.from(document.querySelectorAll('script')).filter(s => s.textContent && s.textContent.includes('prefetched')).length,
                first_script_sample: document.querySelectorAll('script')[0]?.textContent?.substring(0, 200) || 'N/A'
            }
        }""")
        
        print("\n" + "="*60)
        print("📄 HTML STRUCTURE:")
        print("="*60)
        print(json.dumps(html_check, indent=2, ensure_ascii=False))
        
        browser.close()
        safe_print("\n✅ Debug xong!")


if __name__ == "__main__":
    debug_prefetched()
