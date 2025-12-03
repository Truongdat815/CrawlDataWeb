"""
Base handler với browser management và các utilities cơ bản
"""
import time
import random
from playwright.sync_api import sync_playwright
from src import config
from src.utils import safe_print
from src.utils.cookie_manager import save_cookies, load_cookies

class BaseHandler:
    """Base class cho tất cả handlers với browser management"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
    
    def start_browser(self):
        """Khởi động trình duyệt với anti-detection - DÙNG REAL BROWSER MODE"""
        self.playwright = sync_playwright().start()
        
        # Cấu hình browser context với headers giống người dùng thật
        # ⚠️ QUAN TRỌNG: KHÔNG set user_agent cứng - để Chrome tự lấy đúng version
        browser_context_options = {
            # "user_agent": BỎ DÒNG NÀY - Chrome sẽ tự lấy user-agent đúng version
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
        
        # Browser args - CẬP NHẬT: Thêm args quan trọng để ẩn automation
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic",
            "--exclude-switches=enable-automation",  # ⚠️ QUAN TRỌNG: Tắt flag automation
            "--use-fake-ui-for-media-stream",
        ]
        
        # ✅ CÁCH MỚI: Dùng launch_persistent_context (REAL BROWSER MODE)
        # → navigator.webdriver = undefined (real browser)
        # → Cookies được giữ tự động trong user_data_dir
        # → Verify 1 lần duy nhất, scrape suốt không loop
        use_persistent = getattr(config, 'USE_PERSISTENT_CONTEXT', True)
        user_data_dir = getattr(config, 'USER_DATA_DIR', 'user-data')
        
        if use_persistent and user_data_dir:
            safe_print("      🚀 Đang khởi động REAL BROWSER MODE (System Chrome)...")
            safe_print(f"      📁 User Data Directory: {user_data_dir}")
            safe_print("      ✅ Dùng Chrome thật trên máy (không phải Chromium tích hợp)")
            safe_print("      ✅ navigator.webdriver = undefined (real browser)")
            safe_print("      ✅ Cookies được giữ tự động")
            
            # ✅ GIẢI PHÁP 1: Dùng Chrome thật (System Chrome) thay vì Chromium tích hợp
            # → Tránh bị Cloudflare phát hiện TLS Fingerprint và Automation Flag
            try:
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    channel="chrome",  # ⚠️ QUAN TRỌNG: Dùng Chrome thật trên máy
                    headless=config.HEADLESS,
                    args=browser_args,
                    viewport={"width": 1920, "height": 1080},  # Set cứng viewport
                    locale="en-US",
                    timezone_id="America/New_York",
                    extra_http_headers=browser_context_options["extra_http_headers"],
                    # KHÔNG set user_agent - để Chrome tự lấy đúng version
                )
                safe_print("      ✅ Đã kết nối với Google Chrome thật!")
            except Exception as e:
                safe_print(f"      ⚠️ Không tìm thấy Chrome, thử dùng Edge: {e}")
                try:
                    # Fallback: Thử dùng Edge
                    self.context = self.playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        channel="msedge",  # Thử Edge
                        headless=config.HEADLESS,
                        args=browser_args,
                        viewport={"width": 1920, "height": 1080},
                        locale="en-US",
                        timezone_id="America/New_York",
                        extra_http_headers=browser_context_options["extra_http_headers"],
                    )
                    safe_print("      ✅ Đã kết nối với Microsoft Edge!")
                except Exception as e2:
                    safe_print(f"      ⚠️ Không tìm thấy Edge, dùng Chromium tích hợp: {e2}")
                    # Fallback cuối cùng: Dùng Chromium tích hợp
                    self.context = self.playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=config.HEADLESS,
                        args=browser_args,
                        **browser_context_options
                    )
                    safe_print("      ⚠️ Đang dùng Chromium tích hợp (có thể bị Cloudflare chặn)")
            
            # Lấy browser từ context
            self.browser = self.context.browser if hasattr(self.context, 'browser') else None
            
            # Tạo page từ context
            if len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()
            
            safe_print("      ✅ Real browser mode đã khởi động!")
            safe_print("      💡 Verify Cloudflare 1 lần duy nhất, cookies sẽ được giữ tự động!")
            
            # Với persistent context, KHÔNG cần thêm init script vì đã là real browser
            # Init script có thể gây conflict với real browser
            
        else:
            # CÁCH CŨ: Dùng launch() (fallback)
            safe_print("      ⚠️ Dùng launch() mode (không phải real browser)")
            
            browser_args_full = browser_args + [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--window-size=1920,1080",
            ]
            
            self.browser = self.playwright.chromium.launch(
                headless=config.HEADLESS,
                args=browser_args_full
            )
            self.context = self.browser.new_context(**browser_context_options)
            self.page = self.context.new_page()
            
            # Load cookies từ file nếu có (CÁCH 1: Cookie Persistence)
            if config.ENABLE_COOKIE_PERSISTENCE:
                if load_cookies(self.context):
                    safe_print("      ✅ Đã load cookies từ file - có thể không cần verify lại!")
                else:
                    safe_print("      ℹ️ Chưa có cookies, sẽ verify lần đầu và lưu lại")
            
            # Thêm script MẠNH HƠN để ẩn webdriver property (CHỈ với launch() mode)
            self.context.add_init_script("""
            // Ẩn webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Giả lập Chrome runtime
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Giả lập plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: ""},
                            description: "",
                            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        }
                    ];
                }
            });
            
            // Giả lập languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            
            // Ẩn permission query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Ẩn automation flags
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: window.navigator.permissions.query
                })
            });
            
            // Override getParameter để ẩn automation
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
            
            // Ẩn automation trong console
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
            
            // Ẩn Playwright detection
            Object.defineProperty(navigator, 'userAgent', {
                get: () => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            });
        """)
        
        # Chỉ tạo page mới nếu chưa có (persistent context đã có page)
        if not hasattr(self, 'page') or self.page is None:
            self.page = self.context.new_page()
        
        # Thêm event listener để detect Cloudflare redirect
        def handle_response(response):
            """Handle response để detect Cloudflare"""
            url = response.url
            if "challenges.cloudflare.com" in url or "cf-browser-verification" in url:
                safe_print("      🔒 Phát hiện Cloudflare challenge trong response")
        
        self.page.on("response", handle_response)
        
        safe_print("✅ Bot đã khởi động với anti-detection mạnh!")
        if not config.HEADLESS:
            safe_print("   💡 Browser sẽ hiển thị - Cloudflare sẽ pass dễ hơn")
    
    def wait_for_cloudflare_challenge(self, page=None, max_wait=60):
        """
        Đợi Cloudflare challenge hoàn thành - CẢI THIỆN MẠNH HƠN
        Args:
            page: Playwright page object (nếu None thì dùng self.page)
            max_wait: Thời gian tối đa đợi (giây) - tăng lên 60 giây
        Returns:
            bool: True nếu pass challenge, False nếu bị chặn
        """
        if page is None:
            page = self.page
        
        if not page:
            return False
        
        try:
            safe_print("      🔒 Đang kiểm tra Cloudflare challenge...")
            start_time = time.time()
            check_count = 0
            
            while time.time() - start_time < max_wait:
                check_count += 1
                try:
                    # Đợi một chút trước khi check - tăng lên 5 giây để không check quá nhanh
                    time.sleep(5)  # Tăng từ 3s lên 5s
                    
                    # Kiểm tra page content
                    page_content = page.content().lower()
                    page_url = page.url
                    
                    # Kiểm tra các dấu hiệu Cloudflare challenge
                    cloudflare_indicators = [
                        "challenges.cloudflare.com",
                        "please unblock",
                        "checking your browser",
                        "just a moment",
                        "verifying you are human",  # Thêm indicator mới
                        "verifying...",  # Thêm indicator mới
                        "this may take a few seconds",  # Thêm indicator mới
                        "cf-browser-verification",
                        "cf-challenge",
                    ]
                    
                    has_challenge = False
                    for indicator in cloudflare_indicators:
                        if indicator in page_content:
                            has_challenge = True
                            break
                    
                    # Kiểm tra selectors Cloudflare
                    if not has_challenge:
                        challenge_selectors = [
                            "#challenge-form",
                            ".cf-browser-verification",
                            "#cf-wrapper",
                            "iframe[src*='cloudflare']",
                            "iframe[src*='challenges']",
                            ".cf-im-under-attack",
                        ]
                        
                        for selector in challenge_selectors:
                            try:
                                elem = page.locator(selector).first
                                if elem.count() > 0:
                                    has_challenge = True
                                    break
                            except:
                                continue
                    
                    if has_challenge:
                        if check_count % 5 == 0:  # In log mỗi 5 lần check
                            safe_print(f"      ⏳ Đang đợi Cloudflare challenge... ({int(time.time() - start_time)}s)")
                        
                        # Thử tương tác với page để giúp pass challenge
                        try:
                            # Scroll một chút
                            page.evaluate("window.scrollBy(0, 100)")
                            time.sleep(1)
                            page.evaluate("window.scrollBy(0, -100)")
                        except:
                            pass
                        
                        continue
                    
                    # Kiểm tra URL - nếu URL không còn chứa challenge thì có thể đã pass
                    # Cũng kiểm tra xem có redirect về challenge không (JS redirect)
                    url_has_challenge = any(x in page_url.lower() for x in ["challenges.cloudflare.com", "cf-browser-verification"])
                    
                    # Kiểm tra xem có JS redirect về challenge không
                    try:
                        # Kiểm tra trong JavaScript context
                        js_check = page.evaluate("""
                            () => {
                                if (window.location.href.includes('challenges.cloudflare.com') || 
                                    window.location.href.includes('cf-browser-verification')) {
                                    return true;
                                }
                                // Kiểm tra xem có script redirect không
                                const scripts = Array.from(document.scripts);
                                for (let script of scripts) {
                                    if (script.textContent && (
                                        script.textContent.includes('challenges.cloudflare.com') ||
                                        script.textContent.includes('cf-browser-verification')
                                    )) {
                                        return true;
                                    }
                                }
                                return false;
                            }
                        """)
                        if js_check:
                            url_has_challenge = True
                    except:
                        pass
                    
                    # Nếu không có challenge trong content VÀ URL không có challenge
                    if not has_challenge and not url_has_challenge:
                        # Đợi thêm 20-30 giây để đảm bảo challenge đã pass hoàn toàn và page đã load
                        post_pass_delay = getattr(config, 'CLOUDFLARE_POST_PASS_DELAY', 20)
                        safe_print(f"      ⏳ Phát hiện challenge đã pass, đợi {post_pass_delay} giây để đảm bảo page load xong...")
                        time.sleep(post_pass_delay)  # Tăng lên 20 giây
                        
                        # Đợi networkidle để đảm bảo page đã load hoàn toàn
                        try:
                            safe_print(f"      ⏳ Đang đợi page load hoàn toàn...")
                            page.wait_for_load_state("networkidle", timeout=30000)  # Đợi tối đa 30s
                        except:
                            pass  # Nếu timeout thì bỏ qua, tiếp tục
                        
                        # Kiểm tra lại nhiều lần để chắc chắn (3 lần)
                        all_checks_passed = True
                        for check_round in range(3):
                            time.sleep(2)  # Đợi 2s giữa mỗi lần check
                            page_content_again = page.content().lower()
                            page_url_again = page.url
                            
                            has_challenge_again = any(indicator in page_content_again for indicator in cloudflare_indicators)
                            url_has_challenge_again = any(x in page_url_again.lower() for x in ["challenges.cloudflare.com", "cf-browser-verification"])
                            
                            if has_challenge_again or url_has_challenge_again:
                                safe_print(f"      ⚠️ Vẫn còn challenge ở lần check {check_round + 1}/3, tiếp tục đợi...")
                                all_checks_passed = False
                                break
                        
                        if not all_checks_passed:
                            # Vẫn còn challenge, tiếp tục đợi
                            continue
                        
                        # Kiểm tra xem page đã load content chưa
                        scribblehub_selectors = [
                            ".fic_title",
                            "ol.toc_ol",
                            ".wi_fic_desc",
                            "h1",
                            ".wi_fic_table",
                            ".fic_image",
                            ".wi_fic_info",  # Thêm selector
                        ]
                        
                        content_loaded = False
                        for selector in scribblehub_selectors:
                            try:
                                elem = page.locator(selector).first
                                if elem.count() > 0:
                                    # Kiểm tra xem element có text không (không phải empty)
                                    try:
                                        text = elem.inner_text()
                                        if text and text.strip():
                                            content_loaded = True
                                            break
                                    except:
                                        content_loaded = True
                                        break
                            except:
                                continue
                        
                        if content_loaded:
                            safe_print(f"      ✅ Đã pass Cloudflare challenge! (sau {int(time.time() - start_time)}s)")
                            # Đợi thêm 5 giây để đảm bảo page đã load hoàn toàn và không reload lại
                            safe_print(f"      ⏳ Đợi thêm 5 giây để đảm bảo page ổn định...")
                            time.sleep(5)  # Tăng từ 2s lên 5s
                            
                            # Lưu cookies sau khi pass challenge (CÁCH 1: Cookie Persistence)
                            if config.ENABLE_COOKIE_PERSISTENCE:
                                if page and page.context:
                                    save_cookies(page.context)
                            
                            return True
                        else:
                            # Không có challenge nhưng cũng không có content
                            # Có thể page đang load, đợi thêm
                            if check_count < 10:
                                time.sleep(2)
                                continue
                    
                    # Nếu không có challenge và không có content, có thể page đang load
                    # Đợi thêm một chút
                    if check_count < 5:
                        time.sleep(2)
                        continue
                    else:
                        # Sau 5 lần check mà không có challenge và không có content
                        # Có thể page đã load nhưng không có content mong đợi
                        safe_print(f"      ⚠️ Không phát hiện challenge nhưng cũng không có content (sau {int(time.time() - start_time)}s)")
                        return True  # Trả về True để tiếp tục, có thể page đã load
                    
                except Exception as e:
                    time.sleep(2)
                    continue
            
            # Kiểm tra lần cuối
            try:
                page_content = page.content().lower()
                page_url = page.url
                
                # Kiểm tra các indicators
                cloudflare_indicators = [
                    "challenges.cloudflare.com",
                    "please unblock",
                    "checking your browser",
                    "just a moment",
                    "verifying you are human",
                    "verifying...",
                    "this may take a few seconds",
                ]
                
                has_challenge = any(indicator in page_content for indicator in cloudflare_indicators)
                url_has_challenge = any(x in page_url.lower() for x in ["challenges.cloudflare.com", "cf-browser-verification"])
                
                if has_challenge or url_has_challenge:
                    safe_print(f"      ❌ Vẫn bị Cloudflare chặn sau {max_wait} giây")
                    safe_print("      💡 Bạn có thể verify thủ công và chạy lại, hoặc đợi thêm một chút")
                    return False
                else:
                    # Kiểm tra xem có content không
                    scribblehub_selectors = [".fic_title", "ol.toc_ol", ".wi_fic_desc", "h1"]
                    has_content = False
                    for selector in scribblehub_selectors:
                        try:
                            elem = page.locator(selector).first
                            if elem.count() > 0:
                                text = elem.inner_text()
                                if text and text.strip():
                                    has_content = True
                                    break
                        except:
                            continue
                    
                    if has_content:
                        safe_print(f"      ✅ Đã pass Cloudflare challenge! (sau {max_wait}s)")
                        time.sleep(2)  # Đợi thêm để đảm bảo
                        return True
                    else:
                        safe_print(f"      ⚠️ Không phát hiện challenge nhưng cũng không có content (sau {max_wait}s)")
                        safe_print("      💡 Có thể page đang load, tiếp tục thử...")
                        return True  # Trả về True để tiếp tục
            except Exception as e:
                safe_print(f"      ⚠️ Lỗi khi kiểm tra lần cuối: {e}")
                return False
                
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi đợi Cloudflare challenge: {e}")
            return False
    
    def simulate_human_behavior(self, page=None):
        """
        Giả lập hành vi người dùng thật (scroll, mouse movement)
        Args:
            page: Playwright page object (nếu None thì dùng self.page)
        """
        if page is None:
            page = self.page
        
        if not page:
            return
        
        try:
            # Scroll ngẫu nhiên
            scroll_steps = random.randint(3, 6)
            for _ in range(scroll_steps):
                scroll_amount = random.randint(200, 800)
                page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                time.sleep(random.uniform(0.5, 1.5))
            
            # Scroll về đầu trang
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(random.uniform(0.5, 1.0))
            
            # Di chuyển chuột ngẫu nhiên
            page.mouse.move(
                random.randint(100, 800),
                random.randint(100, 600)
            )
            time.sleep(random.uniform(0.3, 0.8))
        except Exception as e:
            # Nếu lỗi thì bỏ qua, không ảnh hưởng đến scraping
            pass
    
    def goto_with_cloudflare(self, page, url, timeout=None, max_cloudflare_wait=30):
        """
        Goto URL và xử lý Cloudflare challenge
        Args:
            page: Playwright page object
            url: URL cần truy cập
            timeout: Timeout (mặc định từ config)
            max_cloudflare_wait: Thời gian tối đa đợi Cloudflare (giây)
        Returns:
            bool: True nếu thành công, False nếu bị chặn
        """
        if timeout is None:
            timeout = config.TIMEOUT
        
        try:
            # Goto với wait_until="networkidle" để đợi Cloudflare challenge
            page.goto(url, timeout=timeout, wait_until="networkidle")
            check_delay = getattr(config, 'CLOUDFLARE_CHECK_DELAY', 3)
            time.sleep(check_delay)  # Delay để đợi Cloudflare
            
            # Kiểm tra Cloudflare challenge
            try:
                time.sleep(getattr(config, 'CLOUDFLARE_CHECK_DELAY', 3))
                page_content = page.content()
                if "challenges.cloudflare.com" in page_content.lower():
                    safe_print("      ⏳ Phát hiện Cloudflare challenge, đợi...")
                    
                    # Đợi challenge hoàn thành
                    challenge_delay = getattr(config, 'CLOUDFLARE_CHALLENGE_DELAY', 10)
                    time.sleep(challenge_delay)
                    
                    start_time = time.time()
                    while time.time() - start_time < max_cloudflare_wait:
                        time.sleep(2)
                        page_content = page.content()
                        if "challenges.cloudflare.com" not in page_content.lower():
                            safe_print("      ✅ Đã pass Cloudflare challenge!")
                            return True
                    
                    # Kiểm tra lần cuối
                    page_content = page.content()
                    if "challenges.cloudflare.com" in page_content.lower():
                        safe_print("      ⚠️ Vẫn bị Cloudflare chặn sau khi đợi")
                        return False
                    else:
                        safe_print("      ✅ Đã pass Cloudflare challenge!")
                        return True
            except:
                pass
            
            return True
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi goto URL: {e}")
            return False
    
    def stop_browser(self):
        """Đóng trình duyệt"""
        try:
            # Nếu dùng persistent context, đóng context (sẽ tự động đóng browser)
            if hasattr(self, 'context') and self.context:
                # Kiểm tra xem có phải persistent context không
                if hasattr(self.context, 'browser') and self.context.browser is None:
                    # Persistent context - đóng context
                    self.context.close()
                elif self.browser:
                    # Normal context - đóng browser
                    self.browser.close()
            
            # Đóng playwright
            if self.playwright:
                self.playwright.stop()
            
            safe_print("zzz Bot đã tắt.")
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi đóng browser: {e}")
            try:
                if self.playwright:
                    self.playwright.stop()
            except:
                pass

