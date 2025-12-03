"""
Script debug để test selector chapters trên ScribbleHub
"""
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print
import time

def test_selectors():
    """Test các selector khác nhau để tìm chapters"""
    playwright = sync_playwright().start()
    
    # Browser context với anti-detection
    browser_context_options = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "extra_http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    }
    
    browser = playwright.chromium.launch(headless=False)  # Hiện browser để debug
    context = browser.new_context(**browser_context_options)
    page = context.new_page()
    
    # URL test
    story_url = "https://www.scribblehub.com/series/1266790/dao-of-money-xianxia-business/"
    
    safe_print("=" * 60)
    safe_print("🔍 DEBUG SELECTOR - SCRIBBLEHUB")
    safe_print("=" * 60)
    safe_print(f"URL: {story_url}")
    safe_print("=" * 60)
    
    try:
        safe_print("\n📄 Đang load trang...")
        page.goto(story_url, timeout=config.TIMEOUT)
        time.sleep(3)
        
        # Scroll để lazy load
        safe_print("\n📜 Đang scroll để load content...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(2)
        
        # Test các selector
        selectors = [
            "ol.toc_ol",
            "ol.toc_ol li.toc_w",
            ".wi_fic_table.toc ol.toc_ol li.toc_w",
            "li.toc_w",
            ".toc_ol li",
            "a.toc_a",
        ]
        
        safe_print("\n🔍 Testing selectors...")
        for selector in selectors:
            try:
                elements = page.locator(selector).all()
                count = len(elements)
                safe_print(f"  {selector}: {count} elements")
                
                if count > 0:
                    # Lấy một vài ví dụ
                    for i, elem in enumerate(elements[:3]):
                        try:
                            if "a.toc_a" in selector:
                                href = elem.get_attribute("href")
                                text = elem.inner_text()
                                safe_print(f"    [{i+1}] {text[:50]} -> {href[:80]}")
                            elif "li.toc_w" in selector:
                                order = elem.get_attribute("order")
                                link = elem.locator("a.toc_a").first
                                if link.count() > 0:
                                    href = link.get_attribute("href")
                                    text = link.inner_text()
                                    safe_print(f"    [{i+1}] Order: {order}, {text[:50]} -> {href[:80]}")
                        except Exception as e:
                            safe_print(f"    [{i+1}] Error: {e}")
            except Exception as e:
                safe_print(f"  {selector}: ERROR - {e}")
        
        # Kiểm tra HTML structure
        safe_print("\n📋 Checking HTML structure...")
        try:
            # Kiểm tra xem có ol.toc_ol không
            toc_ol = page.locator("ol.toc_ol").first
            if toc_ol.count() > 0:
                safe_print("  ✅ Tìm thấy ol.toc_ol")
                # Lấy HTML của nó
                html = toc_ol.inner_html()
                safe_print(f"  📝 HTML (first 500 chars): {html[:500]}")
            else:
                safe_print("  ❌ Không tìm thấy ol.toc_ol")
        except Exception as e:
            safe_print(f"  ⚠️ Lỗi khi check HTML: {e}")
        
        # Kiểm tra xem có bị chặn không
        safe_print("\n🔒 Checking for blocking...")
        page_title = page.title()
        page_url = page.url
        safe_print(f"  Title: {page_title}")
        safe_print(f"  URL: {page_url}")
        
        if "access denied" in page_title.lower() or "blocked" in page_title.lower():
            safe_print("  ⚠️ Có thể bị chặn!")
        else:
            safe_print("  ✅ Không bị chặn")
        
        safe_print("\n" + "=" * 60)
        safe_print("✅ Debug hoàn thành!")
        safe_print("=" * 60)
        safe_print("\n⚠️ Browser sẽ mở trong 30 giây để bạn kiểm tra...")
        time.sleep(30)
        
    except Exception as e:
        safe_print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    test_selectors()


