"""
Script test đơn giản để kiểm tra Cloudflare challenge
Chạy script này để xem browser có pass được Cloudflare không
"""
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print
import time

def test_cloudflare():
    """Test Cloudflare với anti-detection mạnh"""
    safe_print("=" * 60)
    safe_print("🧪 TEST CLOUDFLARE CHALLENGE")
    safe_print("=" * 60)
    
    # URL test
    test_url = "https://www.scribblehub.com/series/1266790/dao-of-money-xianxia-business/"
    safe_print(f"URL: {test_url}")
    safe_print("=" * 60)
    
    playwright = sync_playwright().start()
    
    # Browser context với anti-detection MẠNH
    browser_context_options = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "extra_http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
    }
    
    # Browser args MẠNH
    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-infobars",
        "--window-size=1920,1080",
        "--start-maximized",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-default-apps",
        "--disable-popup-blocking",
        "--disable-translate",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--disable-ipc-flooding-protection",
    ]
    
    # QUAN TRỌNG: headless=False để pass Cloudflare dễ hơn
    browser = playwright.chromium.launch(
        headless=False,  # Browser hiển thị
        args=browser_args
    )
    
    context = browser.new_context(**browser_context_options)
    
    # Stealth scripts MẠNH
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                return [
                    {
                        0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                        description: "Portable Document Format",
                        filename: "internal-pdf-viewer",
                        length: 1,
                        name: "Chrome PDF Plugin"
                    }
                ];
            }
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter(parameter);
        };
        
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8
        });
        
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8
        });
    """)
    
    page = context.new_page()
    
    safe_print("\n🌍 Đang truy cập URL...")
    safe_print("   Browser sẽ mở - bạn sẽ thấy Cloudflare challenge nếu có")
    safe_print("   Đợi challenge hoàn thành (thường 5-15 giây)...\n")
    
    try:
        # Goto URL
        page.goto(test_url, timeout=60000, wait_until="domcontentloaded")
        time.sleep(5)  # Đợi Cloudflare
        
        # Kiểm tra Cloudflare
        safe_print("\n🔍 Đang kiểm tra Cloudflare challenge...")
        max_wait = 60
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            page_content = page.content().lower()
            
            # Kiểm tra indicators
            cloudflare_indicators = [
                "challenges.cloudflare.com",
                "please unblock",
                "checking your browser",
                "just a moment",
            ]
            
            has_challenge = any(indicator in page_content for indicator in cloudflare_indicators)
            
            if has_challenge:
                elapsed = int(time.time() - start_time)
                safe_print(f"   ⏳ Cloudflare challenge đang chạy... ({elapsed}s)")
                time.sleep(3)
                continue
            
            # Kiểm tra content
            try:
                fic_title = page.locator(".fic_title").first
                if fic_title.count() > 0:
                    title = fic_title.inner_text()
                    safe_print(f"\n✅ ĐÃ PASS CLOUDFLARE!")
                    safe_print(f"   Title: {title}")
                    safe_print(f"   Thời gian: {int(time.time() - start_time)} giây")
                    
                    # Kiểm tra chapters
                    toc_ol = page.locator("ol.toc_ol").first
                    if toc_ol.count() > 0:
                        chapters = page.locator("ol.toc_ol li.toc_w").all()
                        safe_print(f"   Chapters: {len(chapters)} chapters tìm thấy")
                    
                    safe_print("\n" + "=" * 60)
                    safe_print("✅ TEST THÀNH CÔNG!")
                    safe_print("=" * 60)
                    safe_print("\n⚠️ Browser sẽ đóng sau 10 giây...")
                    time.sleep(10)
                    return True
            except:
                pass
            
            time.sleep(2)
        
        # Kiểm tra lần cuối
        page_content = page.content().lower()
        if any(indicator in page_content for indicator in cloudflare_indicators):
            safe_print(f"\n❌ VẪN BỊ CLOUDFLARE CHẶN sau {max_wait} giây")
            safe_print("   Có thể cần:")
            safe_print("   - Đợi lâu hơn (tăng CLOUDFLARE_MAX_WAIT)")
            safe_print("   - Dùng VPN/proxy")
            safe_print("   - Đợi một thời gian rồi thử lại")
            safe_print("\n⚠️ Browser sẽ đóng sau 30 giây để bạn kiểm tra...")
            time.sleep(30)
            return False
        else:
            safe_print("\n✅ Có vẻ đã pass Cloudflare!")
            safe_print("⚠️ Browser sẽ đóng sau 10 giây...")
            time.sleep(10)
            return True
            
    except Exception as e:
        safe_print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        safe_print("\n⚠️ Browser sẽ đóng sau 30 giây...")
        time.sleep(30)
        return False
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    test_cloudflare()

