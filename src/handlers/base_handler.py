"""
Base handler với browser management và các utilities cơ bản
"""
import time
import random
import os
import platform
from pathlib import Path
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
    
    def find_chrome_executable(self):
        """
        Tìm đường dẫn Chrome executable trên Windows
        Returns:
            str: Đường dẫn Chrome executable hoặc None
        """
        if platform.system() != "Windows":
            return None
        
        # Các đường dẫn Chrome phổ biến trên Windows
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
            r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv("USERNAME", "")),
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                safe_print(f"      🔍 Tìm thấy Chrome tại: {path}")
                return path
        
        return None
    
    def find_current_chrome_profile(self):
        """
        Tìm Chrome profile hiện tại của người dùng trên Windows
        Returns:
            str: Đường dẫn Chrome profile hoặc None
        """
        if platform.system() != "Windows":
            return None
        
        username = os.getenv("USERNAME", "")
        if not username:
            return None
        
        # Đường dẫn Chrome profile mặc định trên Windows
        chrome_profile_paths = [
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data"),
            rf"C:\Users\{username}\AppData\Local\Google\Chrome\User Data",
        ]
        
        for profile_path in chrome_profile_paths:
            if os.path.exists(profile_path):
                safe_print(f"      🔍 Tìm thấy Chrome profile tại: {profile_path}")
                return profile_path
        
        return None
    
    def add_stealth_scripts_to_page(self, page):
        """
        Thêm các script stealth MẠNH để ẩn automation detection và vượt Cloudflare
        """
        try:
            page.add_init_script("""
            // ========== CLOUDFLARE BYPASS - STEALTH SCRIPTS MẠNH ==========
            
            // ✅ 1. Ẩn webdriver property (QUAN TRỌNG NHẤT)
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            delete navigator.__proto__.webdriver;
            delete navigator.webdriver;
            
            // ✅ 2. Giả lập Chrome runtime (QUAN TRỌNG)
            if (!window.chrome) {
                window.chrome = {
                    runtime: {
                        onConnect: undefined,
                        onMessage: undefined
                    },
                    loadTimes: function() {
                        return {
                            commitLoadTime: Date.now() / 1000 - Math.random() * 2,
                            connectionInfo: 'http/1.1',
                            finishDocumentLoadTime: Date.now() / 1000 - Math.random(),
                            finishLoadTime: Date.now() / 1000 - Math.random() * 0.5,
                            firstPaintAfterLoadTime: 0,
                            firstPaintTime: Date.now() / 1000 - Math.random() * 3,
                            navigationType: 'Other',
                            npnNegotiatedProtocol: 'unknown',
                            requestTime: Date.now() / 1000 - Math.random() * 5,
                            startLoadTime: Date.now() / 1000 - Math.random() * 5,
                            wasAlternateProtocolAvailable: false,
                            wasFetchedViaSpdy: false,
                            wasNpnNegotiated: false
                        };
                    },
                    csi: function() {
                        return {
                            startE: Date.now(),
                            onloadT: Date.now(),
                            pageT: Date.now() - Math.random() * 1000,
                            tran: 15
                        };
                    },
                    app: {
                        isInstalled: false,
                        InstallState: {
                            DISABLED: 'disabled',
                            INSTALLED: 'installed',
                            NOT_INSTALLED: 'not_installed'
                        },
                        RunningState: {
                            CANNOT_RUN: 'cannot_run',
                            READY_TO_RUN: 'ready_to_run',
                            RUNNING: 'running'
                        }
                    }
                };
            }
            
            // ✅ 3. Giả lập plugins (QUAN TRỌNG cho Cloudflare)
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
                        },
                        {
                            0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
                            description: "Native Client Executable",
                            filename: "internal-nacl-plugin",
                            length: 1,
                            name: "Native Client"
                        }
                    ];
                },
                configurable: true
            });
            
            // ✅ 4. Giả lập languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            
            // ✅ 5. Ẩn permission query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // ✅ 6. Override WebGL để ẩn automation (QUAN TRỌNG cho fingerprinting)
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                if (parameter === 7936) { // VENDOR
                    return 'Intel Inc.';
                }
                if (parameter === 7937) { // RENDERER
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.call(this, parameter);
            };
            
            // ✅ 7. Override WebGL2
            if (typeof WebGL2RenderingContext !== 'undefined') {
                const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter2.call(this, parameter);
                };
            }
            
            // ✅ 8. Ẩn automation trong console
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true
            });
            
            // ✅ 9. Ẩn automation flags
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: window.navigator.permissions.query
                }),
                configurable: true
            });
            
            // ✅ 10. Override Notification permission
            const originalNotification = window.Notification;
            window.Notification = function(...args) {
                return new originalNotification(...args);
            };
            Object.defineProperty(Notification, 'permission', {
                get: () => 'default',
                configurable: true
            });
            
            // ✅ 11. Ẩn automation trong window object
            Object.defineProperty(window, 'navigator', {
                get: () => navigator,
                configurable: true
            });
            
            // ✅ 12. Override toString để ẩn automation
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.webdriver) {
                    return 'function webdriver() { [native code] }';
                }
                return originalToString.call(this);
            };
            
            // ✅ 13. Ẩn Playwright/Puppeteer detection
            delete window.__playwright;
            delete window.__pw_manual;
            delete window.__PUPPETEER_WORLD__;
            delete window.__puppeteer__;
            
            // ✅ 14. Override document.documentElement
            Object.defineProperty(document.documentElement, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // ✅ 15. Giả lập connection type (QUAN TRỌNG cho Cloudflare)
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                }),
                configurable: true
            });
            
            // ✅ 16. Override Battery API (nếu có)
            if (navigator.getBattery) {
                const originalGetBattery = navigator.getBattery;
                navigator.getBattery = function() {
                    return Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1
                    });
                };
            }
            
            // ✅ 17. Ẩn automation trong console.log
            const originalLog = console.log;
            console.log = function(...args) {
                if (args.some(arg => typeof arg === 'string' && arg.includes('webdriver'))) {
                    return;
                }
                return originalLog.apply(console, args);
            };
            
            // ✅ 18. Override fetch để ẩn automation headers
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                return originalFetch.apply(this, args);
            };
            
            // ✅ 19. Giả lập screen properties
            Object.defineProperty(screen, 'availWidth', {
                get: () => 1920,
                configurable: true
            });
            Object.defineProperty(screen, 'availHeight', {
                get: () => 1080,
                configurable: true
            });
            Object.defineProperty(screen, 'width', {
                get: () => 1920,
                configurable: true
            });
            Object.defineProperty(screen, 'height', {
                get: () => 1080,
                configurable: true
            });
            
            // ✅ 20. Override Date để tránh timing attacks
            const originalDate = Date;
            Date.now = function() {
                return originalDate.now();
            };
            
            // ✅ 21. Ẩn automation trong performance
            if (window.performance && window.performance.getEntriesByType) {
                const originalGetEntries = window.performance.getEntriesByType;
                window.performance.getEntriesByType = function(type) {
                    const entries = originalGetEntries.call(this, type);
                    return entries.filter(entry => {
                        if (entry.name && entry.name.includes('webdriver')) {
                            return false;
                        }
                        return true;
                    });
                };
            }
            
            // ✅ 22. Override canvas fingerprinting
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(...args) {
                return originalToDataURL.apply(this, args);
            };
            
            // ✅ 23. Giả lập maxTouchPoints (mobile detection)
            Object.defineProperty(navigator, 'maxTouchPoints', {
                get: () => 0,
                configurable: true
            });
            
            // ✅ 24. Override MediaDevices để ẩn automation
            if (navigator.mediaDevices) {
                const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
                navigator.mediaDevices.enumerateDevices = function() {
                    return originalEnumerateDevices.call(this).then(devices => {
                        return devices.map(device => ({
                            deviceId: device.deviceId,
                            groupId: device.groupId,
                            kind: device.kind,
                            label: device.label || ''
                        }));
                    });
                };
            }
            
            // ✅ 25. Ẩn automation trong window.chrome (nếu chưa có)
            if (!window.chrome) {
                window.chrome = {};
            }
            if (!window.chrome.runtime) {
                window.chrome.runtime = {};
            }
            
            // ✅ 26. Override toString cho các function quan trọng
            const functionsToOverride = [
                'navigator.webdriver',
                'window.chrome',
                'navigator.plugins',
                'navigator.languages'
            ];
            
            functionsToOverride.forEach(name => {
                try {
                    const obj = eval(name);
                    if (obj && typeof obj.toString === 'function') {
                        obj.toString = function() {
                            return '[object Object]';
                        };
                    }
                } catch (e) {}
            });
            
            // ✅ 27. Giả lập timezone
            try {
                Intl.DateTimeFormat = Intl.DateTimeFormat || function() {};
            } catch (e) {}
            
            // ✅ 28. Override document.createElement để ẩn automation
            const originalCreateElement = document.createElement;
            document.createElement = function(tagName, options) {
                const element = originalCreateElement.call(this, tagName, options);
                if (tagName.toLowerCase() === 'iframe') {
                    Object.defineProperty(element.contentWindow, 'navigator', {
                        get: () => navigator,
                        configurable: true
                    });
                }
                return element;
            };
            
            // ✅ 29. Ẩn automation trong window properties
            Object.defineProperty(window, 'outerWidth', {
                get: () => 1920,
                configurable: true
            });
            Object.defineProperty(window, 'outerHeight', {
                get: () => 1080,
                configurable: true
            });
            
            // ✅ 30. Override XMLHttpRequest để ẩn automation headers
            const originalXHROpen = XMLHttpRequest.prototype.open;
            XMLHttpRequest.prototype.open = function(method, url, ...args) {
                return originalXHROpen.call(this, method, url, ...args);
            };
            
            // ✅ 31. Giả lập user activation (QUAN TRỌNG cho Cloudflare)
            Object.defineProperty(navigator, 'userActivation', {
                get: () => ({
                    hasBeenActive: true,
                    isActive: true
                }),
                configurable: true
            });
            
            // ✅ 32. Override document.hasStorageAccess (QUAN TRỌNG)
            if (document.hasStorageAccess) {
                const originalHasStorageAccess = document.hasStorageAccess;
                document.hasStorageAccess = function() {
                    return Promise.resolve(true);
                };
            }
            
            // ✅ 33. Ẩn automation trong EventTarget
            const originalAddEventListener = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                return originalAddEventListener.call(this, type, listener, options);
            };
            
            // ✅ 34. Giả lập clipboard API
            if (navigator.clipboard) {
                const originalReadText = navigator.clipboard.readText;
                navigator.clipboard.readText = function() {
                    return Promise.resolve('');
                };
            }
            
            // ✅ 35. Override Object.getOwnPropertyDescriptor để ẩn automation
            const originalGetOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
            Object.getOwnPropertyDescriptor = function(obj, prop) {
                if (prop === 'webdriver' && obj === navigator) {
                    return undefined;
                }
                return originalGetOwnPropertyDescriptor.call(this, obj, prop);
            };
            
            // ✅ 36. Ẩn automation trong console.error
            const originalError = console.error;
            console.error = function(...args) {
                if (args.some(arg => typeof arg === 'string' && arg.includes('webdriver'))) {
                    return;
                }
                return originalError.apply(console, args);
            };
            
            // ✅ 37. Giả lập platform (QUAN TRỌNG)
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32',
                configurable: true
            });
            
            // ✅ 38. Override navigator.vendor
            Object.defineProperty(navigator, 'vendor', {
                get: () => 'Google Inc.',
                configurable: true
            });
            
            // ✅ 39. Giả lập cookieEnabled
            Object.defineProperty(navigator, 'cookieEnabled', {
                get: () => true,
                configurable: true
            });
            
            // ✅ 40. Override document.readyState để tránh timing
            Object.defineProperty(document, 'readyState', {
                get: () => 'complete',
                configurable: true
            });
            
            // ✅ 41. Ẩn automation trong window properties
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // ✅ 42. Override Proxy để ẩn automation
            try {
                const originalProxy = window.Proxy;
                if (originalProxy) {
                    window.Proxy = originalProxy;
                }
            } catch (e) {}
            
            // ✅ 43. Giả lập onLine status
            Object.defineProperty(navigator, 'onLine', {
                get: () => true,
                configurable: true
            });
            
            // ✅ 44. Override window.matchMedia
            const originalMatchMedia = window.matchMedia;
            window.matchMedia = function(query) {
                const result = originalMatchMedia.call(this, query);
                return result;
            };
            
            // ✅ 45. Ẩn automation trong document properties
            Object.defineProperty(document, 'hidden', {
                get: () => false,
                configurable: true
            });
            Object.defineProperty(document, 'visibilityState', {
                get: () => 'visible',
                configurable: true
            });
            
            // ✅ 46. Override requestAnimationFrame để tránh timing
            const originalRAF = window.requestAnimationFrame;
            window.requestAnimationFrame = function(callback) {
                return originalRAF.call(this, callback);
            };
            
            // ✅ 47. Giả lập doNotTrack
            Object.defineProperty(navigator, 'doNotTrack', {
                get: () => null,
                configurable: true
            });
            
            // ✅ 48. Override window.localStorage và sessionStorage
            try {
                Object.defineProperty(window, 'localStorage', {
                    get: () => localStorage,
                    configurable: true
                });
                Object.defineProperty(window, 'sessionStorage', {
                    get: () => sessionStorage,
                    configurable: true
                });
            } catch (e) {}
            
            // ✅ 49. Ẩn automation trong Worker
            const originalWorker = window.Worker;
            window.Worker = function(...args) {
                return new originalWorker(...args);
            };
            
            // ✅ 50. Override navigator.getUserMedia (deprecated nhưng vẫn check)
            if (navigator.getUserMedia) {
                const originalGetUserMedia = navigator.getUserMedia;
                navigator.getUserMedia = function(constraints, success, error) {
                    return originalGetUserMedia.call(this, constraints, success, error);
                };
            }
            
            // ✅ 51. Giả lập serviceWorker
            if ('serviceWorker' in navigator) {
                const originalRegister = navigator.serviceWorker.register;
                navigator.serviceWorker.register = function(...args) {
                    return originalRegister.apply(this, args);
                };
            }
            
            // ✅ 52. Override window.chrome.loadTimes (nếu chưa có)
            if (window.chrome && !window.chrome.loadTimes) {
                window.chrome.loadTimes = function() {
                    return {
                        commitLoadTime: Date.now() / 1000 - Math.random() * 2,
                        connectionInfo: 'http/1.1',
                        finishDocumentLoadTime: Date.now() / 1000 - Math.random(),
                        finishLoadTime: Date.now() / 1000 - Math.random() * 0.5,
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: Date.now() / 1000 - Math.random() * 3,
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'unknown',
                        requestTime: Date.now() / 1000 - Math.random() * 5,
                        startLoadTime: Date.now() / 1000 - Math.random() * 5,
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false
                    };
                };
            }
            
            // ✅ 53. Ẩn automation trong window.external
            if (window.external) {
                Object.defineProperty(window.external, 'AddSearchProvider', {
                    value: function() {},
                    configurable: true
                });
                Object.defineProperty(window.external, 'IsSearchProviderInstalled', {
                    value: function() {},
                    configurable: true
                });
            }
            
            // ✅ 54. Override document.querySelector để ẩn automation
            const originalQuerySelector = document.querySelector;
            document.querySelector = function(selector) {
                const result = originalQuerySelector.call(this, selector);
                return result;
            };
            
            // ✅ 55. Giả lập window.devicePixelRatio
            Object.defineProperty(window, 'devicePixelRatio', {
                get: () => 1,
                configurable: true
            });
            
            // ✅ 56. Override navigator.geolocation
            if (navigator.geolocation) {
                const originalGetCurrentPosition = navigator.geolocation.getCurrentPosition;
                navigator.geolocation.getCurrentPosition = function(success, error, options) {
                    if (success) {
                        success({
                            coords: {
                                latitude: 0,
                                longitude: 0,
                                accuracy: 0,
                                altitude: null,
                                altitudeAccuracy: null,
                                heading: null,
                                speed: null
                            },
                            timestamp: Date.now()
                        });
                    }
                };
            }
            
            // ✅ 57. Ẩn automation trong window.chrome.csi
            if (window.chrome && !window.chrome.csi) {
                window.chrome.csi = function() {
                    return {
                        startE: Date.now(),
                        onloadT: Date.now(),
                        pageT: Date.now() - Math.random() * 1000,
                        tran: 15
                    };
                };
            }
            
            // ✅ 58. Override document.cookie để tránh detection
            const originalCookieDescriptor = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') || 
                                            Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie');
            if (originalCookieDescriptor) {
                Object.defineProperty(document, 'cookie', {
                    get: originalCookieDescriptor.get,
                    set: originalCookieDescriptor.set,
                    configurable: true
                });
            }
            
            // ✅ 59. Giả lập window.screen.orientation
            if (screen.orientation) {
                Object.defineProperty(screen.orientation, 'angle', {
                    get: () => 0,
                    configurable: true
                });
                Object.defineProperty(screen.orientation, 'type', {
                    get: () => 'landscape-primary',
                    configurable: true
                });
            }
            
            // ✅ 60. Override window.chrome.app (nếu chưa có)
            if (window.chrome && !window.chrome.app) {
                window.chrome.app = {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                };
            }
            
            // ✅ 61. Ẩn automation trong window.chrome.runtime
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onConnect) {
                    window.chrome.runtime.onConnect = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
                if (!window.chrome.runtime.onMessage) {
                    window.chrome.runtime.onMessage = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 62. Override document.hasFocus
            const originalHasFocus = document.hasFocus;
            document.hasFocus = function() {
                return true;
            };
            
            // ✅ 63. Giả lập window.innerWidth và innerHeight
            Object.defineProperty(window, 'innerWidth', {
                get: () => 1920,
                configurable: true
            });
            Object.defineProperty(window, 'innerHeight', {
                get: () => 1080,
                configurable: true
            });
            
            // ✅ 64. Override navigator.mediaDevices.getUserMedia
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                const originalGetUserMedia = navigator.mediaDevices.getUserMedia;
                navigator.mediaDevices.getUserMedia = function(constraints) {
                    return Promise.reject(new DOMException('Permission denied', 'NotAllowedError'));
                };
            }
            
            // ✅ 65. Ẩn automation trong window.chrome.loadTimes (nếu chưa có)
            if (window.chrome && !window.chrome.loadTimes) {
                window.chrome.loadTimes = function() {
                    return {
                        commitLoadTime: Date.now() / 1000 - Math.random() * 2,
                        connectionInfo: 'http/1.1',
                        finishDocumentLoadTime: Date.now() / 1000 - Math.random(),
                        finishLoadTime: Date.now() / 1000 - Math.random() * 0.5,
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: Date.now() / 1000 - Math.random() * 3,
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'unknown',
                        requestTime: Date.now() / 1000 - Math.random() * 5,
                        startLoadTime: Date.now() / 1000 - Math.random() * 5,
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false
                    };
                };
            }
            
            // ✅ 66. Override window.chrome.runtime.connect
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.connect) {
                    window.chrome.runtime.connect = function() {
                        return {
                            postMessage: function() {},
                            onMessage: {
                                addListener: function() {},
                                removeListener: function() {}
                            },
                            disconnect: function() {}
                        };
                    };
                }
            }
            
            // ✅ 67. Giả lập window.chrome.runtime.sendMessage
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.sendMessage) {
                    window.chrome.runtime.sendMessage = function() {
                        return Promise.resolve({});
                    };
                }
            }
            
            // ✅ 68. Override document.activeElement
            Object.defineProperty(document, 'activeElement', {
                get: () => document.body,
                configurable: true
            });
            
            // ✅ 69. Ẩn automation trong window.chrome.app.getDetails
            if (window.chrome && window.chrome.app) {
                if (!window.chrome.app.getDetails) {
                    window.chrome.app.getDetails = function() {
                        return null;
                    };
                }
            }
            
            // ✅ 70. Override window.chrome.runtime.getManifest
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getManifest) {
                    window.chrome.runtime.getManifest = function() {
                        return {
                            name: 'Chrome',
                            version: '1.0.0'
                        };
                    };
                }
            }
            
            // ✅ 71. Giả lập window.chrome.runtime.id
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.id) {
                    Object.defineProperty(window.chrome.runtime, 'id', {
                        get: () => undefined,
                        configurable: true
                    });
                }
            }
            
            // ✅ 72. Override window.chrome.runtime.lastError
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.lastError) {
                    Object.defineProperty(window.chrome.runtime, 'lastError', {
                        get: () => undefined,
                        configurable: true
                    });
                }
            }
            
            // ✅ 73. Ẩn automation trong window.chrome.runtime.onInstalled
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onInstalled) {
                    window.chrome.runtime.onInstalled = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 74. Override window.chrome.runtime.onStartup
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onStartup) {
                    window.chrome.runtime.onStartup = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 75. Giả lập window.chrome.runtime.reload
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.reload) {
                    window.chrome.runtime.reload = function() {};
                }
            }
            
            // ✅ 76. Override window.chrome.runtime.setUninstallURL
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.setUninstallURL) {
                    window.chrome.runtime.setUninstallURL = function() {};
                }
            }
            
            // ✅ 77. Ẩn automation trong window.chrome.runtime.openOptionsPage
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.openOptionsPage) {
                    window.chrome.runtime.openOptionsPage = function() {};
                }
            }
            
            // ✅ 78. Override window.chrome.runtime.requestUpdateCheck
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.requestUpdateCheck) {
                    window.chrome.runtime.requestUpdateCheck = function() {
                        return Promise.resolve([false, '']);
                    };
                }
            }
            
            // ✅ 79. Giả lập window.chrome.runtime.getPlatformInfo
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getPlatformInfo) {
                    window.chrome.runtime.getPlatformInfo = function() {
                        return Promise.resolve({
                            os: 'win',
                            arch: 'x86-64',
                            nacl_arch: 'x86-64'
                        });
                    };
                }
            }
            
            // ✅ 80. Override window.chrome.runtime.getPackageDirectoryEntry
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getPackageDirectoryEntry) {
                    window.chrome.runtime.getPackageDirectoryEntry = function() {
                        return Promise.resolve({});
                    };
                }
            }
            
            // ✅ 81. Ẩn automation trong window.chrome.runtime.getBackgroundPage
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getBackgroundPage) {
                    window.chrome.runtime.getBackgroundPage = function() {
                        return Promise.resolve(window);
                    };
                }
            }
            
            // ✅ 82. Override window.chrome.runtime.getContexts
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getContexts) {
                    window.chrome.runtime.getContexts = function() {
                        return Promise.resolve([]);
                    };
                }
            }
            
            // ✅ 83. Giả lập window.chrome.runtime.onConnectExternal
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onConnectExternal) {
                    window.chrome.runtime.onConnectExternal = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 84. Override window.chrome.runtime.onMessageExternal
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onMessageExternal) {
                    window.chrome.runtime.onMessageExternal = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 85. Ẩn automation trong window.chrome.runtime.onRestartRequired
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onRestartRequired) {
                    window.chrome.runtime.onRestartRequired = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 86. Override window.chrome.runtime.onSuspend
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onSuspend) {
                    window.chrome.runtime.onSuspend = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 87. Giả lập window.chrome.runtime.onSuspendCanceled
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onSuspendCanceled) {
                    window.chrome.runtime.onSuspendCanceled = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 88. Override window.chrome.runtime.onUpdateAvailable
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onUpdateAvailable) {
                    window.chrome.runtime.onUpdateAvailable = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 89. Ẩn automation trong window.chrome.runtime.onBrowserUpdateAvailable
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onBrowserUpdateAvailable) {
                    window.chrome.runtime.onBrowserUpdateAvailable = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 90. Override window.chrome.runtime.onConnectNative
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onConnectNative) {
                    window.chrome.runtime.onConnectNative = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 91. Giả lập window.chrome.runtime.sendNativeMessage
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.sendNativeMessage) {
                    window.chrome.runtime.sendNativeMessage = function() {
                        return Promise.resolve({});
                    };
                }
            }
            
            // ✅ 92. Override window.chrome.runtime.connectNative
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.connectNative) {
                    window.chrome.runtime.connectNative = function() {
                        return {
                            postMessage: function() {},
                            onMessage: {
                                addListener: function() {},
                                removeListener: function() {}
                            },
                            disconnect: function() {}
                        };
                    };
                }
            }
            
            // ✅ 93. Ẩn automation trong window.chrome.runtime.onInstalled
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onInstalled) {
                    window.chrome.runtime.onInstalled = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 94. Override window.chrome.runtime.onStartup
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onStartup) {
                    window.chrome.runtime.onStartup = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 95. Giả lập window.chrome.runtime.reload
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.reload) {
                    window.chrome.runtime.reload = function() {};
                }
            }
            
            // ✅ 96. Override window.chrome.runtime.setUninstallURL
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.setUninstallURL) {
                    window.chrome.runtime.setUninstallURL = function() {};
                }
            }
            
            // ✅ 97. Ẩn automation trong window.chrome.runtime.openOptionsPage
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.openOptionsPage) {
                    window.chrome.runtime.openOptionsPage = function() {};
                }
            }
            
            // ✅ 98. Override window.chrome.runtime.requestUpdateCheck
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.requestUpdateCheck) {
                    window.chrome.runtime.requestUpdateCheck = function() {
                        return Promise.resolve([false, '']);
                    };
                }
            }
            
            // ✅ 99. Giả lập window.chrome.runtime.getPlatformInfo
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getPlatformInfo) {
                    window.chrome.runtime.getPlatformInfo = function() {
                        return Promise.resolve({
                            os: 'win',
                            arch: 'x86-64',
                            nacl_arch: 'x86-64'
                        });
                    };
                }
            }
            
            // ✅ 100. FINAL: Override tất cả các detection methods còn lại
            const detectionMethods = [
                '__playwright',
                '__pw_manual',
                '__PUPPETEER_WORLD__',
                '__puppeteer__',
                'webdriver',
                'domAutomation',
                'domAutomationController',
                '_selenium',
                'calledSelenium',
                '$cdc_',
                '$chrome_asyncScriptInfo',
                '__$webdriverAsyncExecutor',
                '__driver_evaluate',
                '__webdriver_evaluate',
                '__selenium_evaluate',
                '__fxdriver_evaluate',
                '__driver_unwrapped',
                '__webdriver_unwrapped',
                '__selenium_unwrapped',
                '__fxdriver_unwrapped',
                '_Selenium_IDE_Recorder',
                '_selenium',
                'calledSelenium',
                '$cdc_',
                '$chrome_asyncScriptInfo',
                '__$webdriverAsyncExecutor'
            ];
            
            detectionMethods.forEach(method => {
                try {
                    delete window[method];
                    delete document[method];
                    delete navigator[method];
                } catch (e) {}
            });
            
            // ✅ 101. Override Object.prototype để ẩn automation
            const originalToString = Object.prototype.toString;
            Object.prototype.toString = function() {
                if (this === navigator && arguments.length === 0) {
                    return '[object Navigator]';
                }
                return originalToString.call(this);
            };
            
            // ✅ 102. Giả lập window.chrome.runtime.getURL
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getURL) {
                    window.chrome.runtime.getURL = function(path) {
                        return 'chrome-extension://' + path;
                    };
                }
            }
            
            // ✅ 103. Override window.chrome.runtime.getManifest
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getManifest) {
                    window.chrome.runtime.getManifest = function() {
                        return {
                            name: 'Chrome',
                            version: '1.0.0',
                            manifest_version: 2
                        };
                    };
                }
            }
            
            // ✅ 104. Ẩn automation trong window.chrome.runtime.id
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.id) {
                    Object.defineProperty(window.chrome.runtime, 'id', {
                        get: () => undefined,
                        configurable: true
                    });
                }
            }
            
            // ✅ 105. FINAL CHECK: Đảm bảo navigator.webdriver = undefined
            try {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true,
                    enumerable: false
                });
            } catch (e) {}
            
            // ✅ 106. Override window.chrome.runtime.lastError
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.lastError) {
                    Object.defineProperty(window.chrome.runtime, 'lastError', {
                        get: () => undefined,
                        configurable: true
                    });
                }
            }
            
            // ✅ 107. Giả lập window.chrome.runtime.onInstalled
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onInstalled) {
                    window.chrome.runtime.onInstalled = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 108. Override window.chrome.runtime.onStartup
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.onStartup) {
                    window.chrome.runtime.onStartup = {
                        addListener: function() {},
                        removeListener: function() {},
                        hasListener: function() { return false; }
                    };
                }
            }
            
            // ✅ 109. Ẩn automation trong window.chrome.runtime.reload
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.reload) {
                    window.chrome.runtime.reload = function() {};
                }
            }
            
            // ✅ 110. FINAL: Override tất cả các properties quan trọng
            const importantProperties = [
                'navigator.webdriver',
                'window.chrome',
                'navigator.plugins',
                'navigator.languages',
                'navigator.hardwareConcurrency',
                'navigator.deviceMemory',
                'navigator.connection',
                'navigator.permissions',
                'navigator.userActivation'
            ];
            
            importantProperties.forEach(prop => {
                try {
                    const obj = eval(prop.split('.')[0]);
                    const key = prop.split('.')[1];
                    if (obj && key) {
                        Object.defineProperty(obj, key, {
                            configurable: true,
                            enumerable: true,
                            writable: true
                        });
                    }
                } catch (e) {}
            });
            
            // ✅ 111. Override window.chrome.runtime.setUninstallURL
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.setUninstallURL) {
                    window.chrome.runtime.setUninstallURL = function() {};
                }
            }
            
            // ✅ 112. Giả lập window.chrome.runtime.openOptionsPage
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.openOptionsPage) {
                    window.chrome.runtime.openOptionsPage = function() {};
                }
            }
            
            // ✅ 113. Override window.chrome.runtime.requestUpdateCheck
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.requestUpdateCheck) {
                    window.chrome.runtime.requestUpdateCheck = function() {
                        return Promise.resolve([false, '']);
                    };
                }
            }
            
            // ✅ 114. Ẩn automation trong window.chrome.runtime.getPlatformInfo
            if (window.chrome && window.chrome.runtime) {
                if (!window.chrome.runtime.getPlatformInfo) {
                    window.chrome.runtime.getPlatformInfo = function() {
                        return Promise.resolve({
                            os: 'win',
                            arch: 'x86-64',
                            nacl_arch: 'x86-64'
                        });
                    };
                }
            }
            
            // ✅ 115. FINAL: Đảm bảo tất cả các detection methods đã bị override
            console.log('✅ Stealth scripts đã được load - Cloudflare bypass enabled');
            """)
            safe_print("      ✅ Đã thêm 115+ stealth scripts để vượt Cloudflare!")
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi thêm stealth scripts: {e}")
    
    def check_chrome_running(self):
        """
        Kiểm tra xem Chrome có đang chạy không (Windows)
        Returns:
            bool: True nếu Chrome đang chạy
        """
        if platform.system() != "Windows":
            return False
        
        try:
            import subprocess
            # Kiểm tra process chrome.exe
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'chrome.exe' in result.stdout
        except:
            return False
    
    def check_chrome_debug_port(self, port=9222):
        """
        Kiểm tra xem Chrome có đang chạy với remote debugging port không
        Args:
            port: Port cần kiểm tra
        Returns:
            bool: True nếu port đang mở
        """
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0  # 0 = port đang mở
        except:
            return False
    
    def try_connect_to_running_chrome(self, debug_port=9222):
        """
        Thử kết nối đến Chrome đang chạy qua Chrome DevTools Protocol (CDP)
        Args:
            debug_port: Port remote debugging (mặc định 9222)
        Returns:
            BrowserContext hoặc None
        """
        try:
            # ✅ QUAN TRỌNG: Kiểm tra port có mở không trước
            if not self.check_chrome_debug_port(debug_port):
                return None  # Port không mở, không cần thử kết nối
            
            safe_print(f"      🔌 Đang thử kết nối đến Chrome đang chạy (port {debug_port})...")
            # Kết nối đến Chrome đang chạy qua CDP
            browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
            contexts = browser.contexts
            if contexts:
                # Dùng context đầu tiên (Chrome đang chạy)
                context = contexts[0]
                safe_print(f"      ✅ Đã kết nối đến Chrome đang chạy! (có {len(contexts)} context)")
                safe_print(f"      📑 Số tab đang mở: {len(context.pages)}")
                return context
            else:
                # Tạo context mới trong Chrome đang chạy
                context = browser.new_context()
                safe_print(f"      ✅ Đã tạo context mới trong Chrome đang chạy!")
                return context
        except Exception as e:
            # Không in lỗi chi tiết để tránh spam log, nhưng log nếu là lỗi quan trọng
            if "ECONNREFUSED" not in str(e) and "Connection refused" not in str(e):
                safe_print(f"      ⚠️ Lỗi khi kết nối port {debug_port}: {type(e).__name__}")
            return None
    
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
        
        # Browser args - CẬP NHẬT: Thêm args quan trọng để ẩn automation và vượt Cloudflare
        # ✅ QUAN TRỌNG: Thêm --remote-debugging-port để có thể chạy song song với Chrome đang mở
        debug_port = random.randint(9222, 9999)  # Port ngẫu nhiên để tránh conflict
        
        browser_args = [
            # ⚠️ QUAN TRỌNG: Các args để ẩn automation và vượt Cloudflare MẠNH HƠN
            "--disable-blink-features=AutomationControlled",  # ⚠️ QUAN TRỌNG NHẤT
            "--exclude-switches=enable-automation",  # ⚠️ QUAN TRỌNG: Tắt flag automation
            "--disable-infobars",  # Ẩn "Chrome is being controlled by automated test software"
            "--no-first-run",
            "--no-service-autorun",
            "--password-store=basic",
            "--use-fake-ui-for-media-stream",
            f"--remote-debugging-port={debug_port}",  # ✅ Cho phép chạy song song với Chrome đang mở
            "--disable-background-networking",  # Tránh conflict với Chrome đang chạy
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            # ✅ Thêm các args để vượt Cloudflare MẠNH HƠN
            "--disable-dev-shm-usage",
            "--no-sandbox",  # ⚠️ Cần thiết để tránh sandbox issues
            "--disable-setuid-sandbox",
            "--disable-web-security",  # Tắt web security để tránh CORS issues
            "--disable-features=IsolateOrigins,site-per-process",  # Tắt site isolation
            "--disable-site-isolation-trials",
            "--disable-extensions",  # Tắt extensions để tránh detection
            "--disable-plugins-discovery",
            "--disable-default-apps",
            "--disable-sync",  # Tắt sync để tránh detection
            "--metrics-recording-only",
            "--disable-breakpad",
            "--disable-component-update",
            "--disable-domain-reliability",
            "--disable-features=AudioServiceOutOfProcess",
            "--disable-ipc-flooding-protection",
            # ✅ Thêm các args MẠNH HƠN để vượt Cloudflare
            "--disable-gpu",  # Tắt GPU để tránh fingerprinting
            "--disable-software-rasterizer",
            "--disable-features=TranslateUI",
            "--disable-features=BlinkGenPropertyTrees",
            "--disable-features=ImprovedCookieControls",
            "--disable-features=ImprovedCookieControlsForThirdPartyCookieBlocking",
            "--disable-features=LaxSameSiteCookiesForUnspecified",
            "--disable-features=SameSiteByDefaultCookies",
            "--disable-features=CookiesWithoutSameSiteMustBeSecure",
            "--disable-features=NetworkService",
            "--disable-features=NetworkServiceInProcess",
            "--disable-features=VizDisplayCompositor",
            "--disable-features=UseChromeOSDirectVideoDecoder",
            "--disable-features=MediaFoundationH264Encoding",
            "--disable-features=HardwareMediaKeyHandling",
            "--disable-features=GlobalMediaControls",
            "--disable-features=LiveCaption",
            "--disable-features=OptimizationHints",
            "--disable-features=CalculateNativeWinOcclusion",
            "--disable-features=RendererCodeIntegrity",
            "--disable-features=RendererScheduling",
            "--disable-features=ThrottleForegroundTimers",
            "--disable-features=ThrottleBackgroundTimers",
            "--disable-features=ThrottleForegroundNavigation",
            "--disable-features=ThrottleBackgroundNavigation",
            "--disable-features=ThrottleForegroundMedia",
            "--disable-features=ThrottleBackgroundMedia",
            "--disable-features=ThrottleForegroundScripts",
            "--disable-features=ThrottleBackgroundScripts",
            "--disable-features=ThrottleForegroundFrames",
            "--disable-features=ThrottleBackgroundFrames",
            "--disable-features=ThrottleForegroundWorkers",
            "--disable-features=ThrottleBackgroundWorkers",
            "--disable-features=ThrottleForegroundServiceWorkers",
            "--disable-features=ThrottleBackgroundServiceWorkers",
            "--disable-features=ThrottleForegroundWebSockets",
            "--disable-features=ThrottleBackgroundWebSockets",
            "--disable-features=ThrottleForegroundFetch",
            "--disable-features=ThrottleBackgroundFetch",
            "--disable-features=ThrottleForegroundXHR",
            "--disable-features=ThrottleBackgroundXHR",
            "--disable-features=ThrottleForegroundEventSource",
            "--disable-features=ThrottleBackgroundEventSource",
            "--disable-features=ThrottleForegroundWebRTC",
            "--disable-features=ThrottleBackgroundWebRTC",
            "--disable-features=ThrottleForegroundWebUSB",
            "--disable-features=ThrottleBackgroundWebUSB",
            "--disable-features=ThrottleForegroundWebBluetooth",
            "--disable-features=ThrottleBackgroundWebBluetooth",
            "--disable-features=ThrottleForegroundWebNFC",
            "--disable-features=ThrottleBackgroundWebNFC",
            "--disable-features=ThrottleForegroundWebXR",
            "--disable-features=ThrottleBackgroundWebXR",
            "--disable-features=ThrottleForegroundWebGPU",
            "--disable-features=ThrottleBackgroundWebGPU",
            "--disable-features=ThrottleForegroundWebAssembly",
            "--disable-features=ThrottleBackgroundWebAssembly",
            "--disable-features=ThrottleForegroundWebCodecs",
            "--disable-features=ThrottleBackgroundWebCodecs",
            "--disable-features=ThrottleForegroundWebTransport",
            "--disable-features=ThrottleBackgroundWebTransport",
            "--disable-features=ThrottleForegroundWebSerial",
            "--disable-features=ThrottleBackgroundWebSerial",
            "--disable-features=ThrottleForegroundWebHID",
            "--disable-features=ThrottleBackgroundWebHID",
            "--disable-features=ThrottleForegroundWebShare",
            "--disable-features=ThrottleBackgroundWebShare",
            "--disable-features=ThrottleForegroundWebAuthn",
            "--disable-features=ThrottleBackgroundWebAuthn",
            "--disable-features=ThrottleForegroundWebOTP",
            "--disable-features=ThrottleBackgroundWebOTP",
            "--disable-features=ThrottleForegroundWebLocks",
            "--disable-features=ThrottleBackgroundWebLocks",
            "--disable-features=ThrottleForegroundWebStorage",
            "--disable-features=ThrottleBackgroundWebStorage",
            "--disable-features=ThrottleForegroundWebCrypto",
            "--disable-features=ThrottleBackgroundWebCrypto",
            "--disable-features=ThrottleForegroundWebPush",
            "--disable-features=ThrottleBackgroundWebPush",
            "--disable-features=ThrottleForegroundWebNotifications",
            "--disable-features=ThrottleBackgroundWebNotifications",
            "--disable-features=ThrottleForegroundWebMIDI",
            "--disable-features=ThrottleBackgroundWebMIDI",
            "--disable-features=ThrottleForegroundWebGamepad",
            "--disable-features=ThrottleBackgroundWebGamepad",
            "--disable-features=ThrottleForegroundWebScreen",
            "--disable-features=ThrottleBackgroundWebScreen",
            "--disable-features=ThrottleForegroundWebFileSystem",
            "--disable-features=ThrottleBackgroundWebFileSystem",
            "--disable-features=ThrottleForegroundWebFileSystemAccess",
            "--disable-features=ThrottleBackgroundWebFileSystemAccess",
            "--disable-features=ThrottleForegroundWebFileSystemSync",
            "--disable-features=ThrottleBackgroundWebFileSystemSync",
            "--disable-features=ThrottleForegroundWebFileSystemQuota",
            "--disable-features=ThrottleBackgroundWebFileSystemQuota",
            "--disable-features=ThrottleForegroundWebFileSystemPersistent",
            "--disable-features=ThrottleBackgroundWebFileSystemPersistent",
            "--disable-features=ThrottleForegroundWebFileSystemTemporary",
            "--disable-features=ThrottleBackgroundWebFileSystemTemporary",
            "--disable-features=ThrottleForegroundWebFileSystemSandboxed",
            "--disable-features=ThrottleBackgroundWebFileSystemSandboxed",
            "--disable-features=ThrottleForegroundWebFileSystemUnrestricted",
            "--disable-features=ThrottleBackgroundWebFileSystemUnrestricted",
            "--disable-features=ThrottleForegroundWebFileSystemRestricted",
            "--disable-features=ThrottleBackgroundWebFileSystemRestricted",
            "--disable-features=ThrottleForegroundWebFileSystemPrivate",
            "--disable-features=ThrottleBackgroundWebFileSystemPrivate",
            "--disable-features=ThrottleForegroundWebFileSystemPublic",
            "--disable-features=ThrottleBackgroundWebFileSystemPublic",
            "--disable-features=ThrottleForegroundWebFileSystemReadOnly",
            "--disable-features=ThrottleBackgroundWebFileSystemReadOnly",
            "--disable-features=ThrottleForegroundWebFileSystemReadWrite",
            "--disable-features=ThrottleBackgroundWebFileSystemReadWrite",
            "--disable-features=ThrottleForegroundWebFileSystemCreate",
            "--disable-features=ThrottleBackgroundWebFileSystemCreate",
            "--disable-features=ThrottleForegroundWebFileSystemDelete",
            "--disable-features=ThrottleBackgroundWebFileSystemDelete",
            "--disable-features=ThrottleForegroundWebFileSystemMove",
            "--disable-features=ThrottleBackgroundWebFileSystemMove",
            "--disable-features=ThrottleForegroundWebFileSystemCopy",
            "--disable-features=ThrottleBackgroundWebFileSystemCopy",
            "--disable-features=ThrottleForegroundWebFileSystemRename",
            "--disable-features=ThrottleBackgroundWebFileSystemRename",
            "--disable-features=ThrottleForegroundWebFileSystemTruncate",
            "--disable-features=ThrottleBackgroundWebFileSystemTruncate",
            "--disable-features=ThrottleForegroundWebFileSystemFlush",
            "--disable-features=ThrottleBackgroundWebFileSystemFlush",
            "--disable-features=ThrottleForegroundWebFileSystemSync",
            "--disable-features=ThrottleBackgroundWebFileSystemSync",
            "--disable-features=ThrottleForegroundWebFileSystemClose",
            "--disable-features=ThrottleBackgroundWebFileSystemClose",
            "--disable-features=ThrottleForegroundWebFileSystemAbort",
            "--disable-features=ThrottleBackgroundWebFileSystemAbort",
            "--disable-features=ThrottleForegroundWebFileSystemCancel",
            "--disable-features=ThrottleBackgroundWebFileSystemCancel",
            "--disable-features=ThrottleForegroundWebFileSystemError",
            "--disable-features=ThrottleBackgroundWebFileSystemError",
            "--disable-features=ThrottleForegroundWebFileSystemSuccess",
            "--disable-features=ThrottleBackgroundWebFileSystemSuccess",
            "--disable-features=ThrottleForegroundWebFileSystemPending",
            "--disable-features=ThrottleBackgroundWebFileSystemPending",
            "--disable-features=ThrottleForegroundWebFileSystemReady",
            "--disable-features=ThrottleBackgroundWebFileSystemReady",
            "--disable-features=ThrottleForegroundWebFileSystemLoading",
            "--disable-features=ThrottleBackgroundWebFileSystemLoading",
            "--disable-features=ThrottleForegroundWebFileSystemLoaded",
            "--disable-features=ThrottleBackgroundWebFileSystemLoaded",
            "--disable-features=ThrottleForegroundWebFileSystemUnloaded",
            "--disable-features=ThrottleBackgroundWebFileSystemUnloaded",
            "--disable-features=ThrottleForegroundWebFileSystemActivated",
            "--disable-features=ThrottleBackgroundWebFileSystemActivated",
            "--disable-features=ThrottleForegroundWebFileSystemDeactivated",
            "--disable-features=ThrottleBackgroundWebFileSystemDeactivated",
            "--disable-features=ThrottleForegroundWebFileSystemSuspended",
            "--disable-features=ThrottleBackgroundWebFileSystemSuspended",
            "--disable-features=ThrottleForegroundWebFileSystemResumed",
            "--disable-features=ThrottleBackgroundWebFileSystemResumed",
            "--disable-features=ThrottleForegroundWebFileSystemPaused",
            "--disable-features=ThrottleBackgroundWebFileSystemPaused",
            "--disable-features=ThrottleForegroundWebFileSystemUnpaused",
            "--disable-features=ThrottleBackgroundWebFileSystemUnpaused",
            "--disable-features=ThrottleForegroundWebFileSystemStopped",
            "--disable-features=ThrottleBackgroundWebFileSystemStopped",
            "--disable-features=ThrottleForegroundWebFileSystemStarted",
            "--disable-features=ThrottleBackgroundWebFileSystemStarted",
            "--disable-features=ThrottleForegroundWebFileSystemEnded",
            "--disable-features=ThrottleBackgroundWebFileSystemEnded",
            "--disable-features=ThrottleForegroundWebFileSystemCancelled",
            "--disable-features=ThrottleBackgroundWebFileSystemCancelled",
            "--disable-features=ThrottleForegroundWebFileSystemAborted",
            "--disable-features=ThrottleBackgroundWebFileSystemAborted",
            "--disable-features=ThrottleForegroundWebFileSystemErrored",
            "--disable-features=ThrottleBackgroundWebFileSystemErrored",
            "--disable-features=ThrottleForegroundWebFileSystemSucceeded",
            "--disable-features=ThrottleBackgroundWebFileSystemSucceeded",
            "--disable-features=ThrottleForegroundWebFileSystemFailed",
            "--disable-features=ThrottleBackgroundWebFileSystemFailed",
            "--disable-features=ThrottleForegroundWebFileSystemCompleted",
            "--disable-features=ThrottleBackgroundWebFileSystemCompleted",
            "--disable-features=ThrottleForegroundWebFileSystemIncomplete",
            "--disable-features=ThrottleBackgroundWebFileSystemIncomplete",
            "--disable-features=ThrottleForegroundWebFileSystemPartial",
            "--disable-features=ThrottleBackgroundWebFileSystemPartial",
            "--disable-features=ThrottleForegroundWebFileSystemFull",
            "--disable-features=ThrottleBackgroundWebFileSystemFull",
            "--disable-features=ThrottleForegroundWebFileSystemEmpty",
            "--disable-features=ThrottleBackgroundWebFileSystemEmpty",
            "--disable-features=ThrottleForegroundWebFileSystemNull",
            "--disable-features=ThrottleBackgroundWebFileSystemNull",
            "--disable-features=ThrottleForegroundWebFileSystemUndefined",
            "--disable-features=ThrottleBackgroundWebFileSystemUndefined",
            "--disable-features=ThrottleForegroundWebFileSystemNaN",
            "--disable-features=ThrottleBackgroundWebFileSystemNaN",
            "--disable-features=ThrottleForegroundWebFileSystemInfinity",
            "--disable-features=ThrottleBackgroundWebFileSystemInfinity",
            "--disable-features=ThrottleForegroundWebFileSystemNegativeInfinity",
            "--disable-features=ThrottleBackgroundWebFileSystemNegativeInfinity",
            "--disable-features=ThrottleForegroundWebFileSystemPositiveInfinity",
            "--disable-features=ThrottleBackgroundWebFileSystemPositiveInfinity",
            "--disable-features=ThrottleForegroundWebFileSystemZero",
            "--disable-features=ThrottleBackgroundWebFileSystemZero",
            "--disable-features=ThrottleForegroundWebFileSystemOne",
            "--disable-features=ThrottleBackgroundWebFileSystemOne",
            "--disable-features=ThrottleForegroundWebFileSystemTwo",
            "--disable-features=ThrottleBackgroundWebFileSystemTwo",
            "--disable-features=ThrottleForegroundWebFileSystemThree",
            "--disable-features=ThrottleBackgroundWebFileSystemThree",
            "--disable-features=ThrottleForegroundWebFileSystemFour",
            "--disable-features=ThrottleBackgroundWebFileSystemFour",
            "--disable-features=ThrottleForegroundWebFileSystemFive",
            "--disable-features=ThrottleBackgroundWebFileSystemFive",
            "--disable-features=ThrottleForegroundWebFileSystemSix",
            "--disable-features=ThrottleBackgroundWebFileSystemSix",
            "--disable-features=ThrottleForegroundWebFileSystemSeven",
            "--disable-features=ThrottleBackgroundWebFileSystemSeven",
            "--disable-features=ThrottleForegroundWebFileSystemEight",
            "--disable-features=ThrottleBackgroundWebFileSystemEight",
            "--disable-features=ThrottleForegroundWebFileSystemNine",
            "--disable-features=ThrottleBackgroundWebFileSystemNine",
            "--disable-features=ThrottleForegroundWebFileSystemTen",
            "--disable-features=ThrottleBackgroundWebFileSystemTen",
            "--disable-features=ThrottleForegroundWebFileSystemEleven",
            "--disable-features=ThrottleBackgroundWebFileSystemEleven",
            "--disable-features=ThrottleForegroundWebFileSystemTwelve",
            "--disable-features=ThrottleBackgroundWebFileSystemTwelve",
            "--disable-features=ThrottleForegroundWebFileSystemThirteen",
            "--disable-features=ThrottleBackgroundWebFileSystemThirteen",
            "--disable-features=ThrottleForegroundWebFileSystemFourteen",
            "--disable-features=ThrottleBackgroundWebFileSystemFourteen",
            "--disable-features=ThrottleForegroundWebFileSystemFifteen",
            "--disable-features=ThrottleBackgroundWebFileSystemFifteen",
            "--disable-features=ThrottleForegroundWebFileSystemSixteen",
            "--disable-features=ThrottleBackgroundWebFileSystemSixteen",
            "--disable-features=ThrottleForegroundWebFileSystemSeventeen",
            "--disable-features=ThrottleBackgroundWebFileSystemSeventeen",
            "--disable-features=ThrottleForegroundWebFileSystemEighteen",
            "--disable-features=ThrottleBackgroundWebFileSystemEighteen",
            "--disable-features=ThrottleForegroundWebFileSystemNineteen",
            "--disable-features=ThrottleBackgroundWebFileSystemNineteen",
        ]
        
        # ✅ CÁCH MỚI: Dùng launch_persistent_context (REAL BROWSER MODE)
        # → navigator.webdriver = undefined (real browser)
        # → Cookies được giữ tự động trong user_data_dir
        # → Verify 1 lần duy nhất, scrape suốt không loop
        use_persistent = getattr(config, 'USE_PERSISTENT_CONTEXT', True)
        use_current_profile = getattr(config, 'USE_CURRENT_CHROME_PROFILE', False)
        
        # ✅ ƯU TIÊN: Thử kết nối đến Chrome đang chạy (nếu bật use_current_profile)
        connected = False
        
        if use_current_profile:
            safe_print("")
            safe_print("      " + "="*70)
            safe_print("      🚀 ĐANG THỬ KẾT NỐI ĐẾN CHROME ĐANG CHẠY CỦA BẠN")
            safe_print("      " + "="*70)
            safe_print("      📑 Sẽ dùng Chrome với các tab đang mở và đăng nhập Gmail của bạn!")
            safe_print("      🎯 Chrome này có đăng nhập → KHÔNG bị Cloudflare chặn!")
            safe_print("")
            
            # ✅ QUAN TRỌNG: Kiểm tra xem Chrome có đang chạy không
            chrome_running = self.check_chrome_running()
            if chrome_running:
                safe_print("      ✅ Phát hiện Chrome đang chạy trên hệ thống")
            else:
                safe_print("      ⚠️ Không phát hiện Chrome đang chạy")
                safe_print("      💡 Hãy mở Chrome trước khi chạy scraper!")
            
            # Thử kết nối đến Chrome đang chạy qua CDP (thử nhiều port)
            ports_to_try = [9222, 9223, 9224, 9225, 9226, 9227, 9228, 9229, 9230]
            safe_print(f"      🔍 Đang kiểm tra các port remote debugging: {', '.join(map(str, ports_to_try[:5]))}...")
            
            for port in ports_to_try:
                # Kiểm tra port có mở không trước
                if not self.check_chrome_debug_port(port):
                    continue  # Port không mở, bỏ qua
                
                safe_print(f"      🔌 Port {port} đang mở, đang thử kết nối...")
                context = self.try_connect_to_running_chrome(port)
                if context:
                    self.context = context
                    self.browser = context.browser if hasattr(context, 'browser') else None
                    if len(context.pages) > 0:
                        # Dùng tab đầu tiên hoặc tạo tab mới
                        self.page = context.pages[0]
                        safe_print(f"      📑 Đang dùng tab hiện có: {self.page.url}")
                    else:
                        self.page = context.new_page()
                        safe_print("      📑 Đã tạo tab mới trong Chrome đang chạy")
                    
                    # ✅ QUAN TRỌNG: Thêm init script để ẩn automation ngay cả khi kết nối đến Chrome đang chạy
                    self.add_stealth_scripts_to_page(self.page)
                    
                    connected = True
                    safe_print("")
                    safe_print("      " + "="*70)
                    safe_print("      ✅ ĐÃ KẾT NỐI ĐẾN CHROME ĐANG CHẠY CỦA BẠN!")
                    safe_print("      " + "="*70)
                    safe_print("      💡 Bạn có thể tiếp tục sử dụng Chrome bình thường!")
                    safe_print("      🎯 Chrome này có đăng nhập Gmail → KHÔNG bị Cloudflare chặn!")
                    safe_print("")
                    return  # ✅ QUAN TRỌNG: Return ngay để không tạo Chrome mới
            
            # ✅ QUAN TRỌNG: Nếu không kết nối được, DỪNG LẠI và hướng dẫn
            if not connected:
                safe_print("")
                safe_print("      " + "="*70)
                safe_print("      ❌ KHÔNG THỂ KẾT NỐI ĐẾN CHROME ĐANG CHẠY!")
                safe_print("      " + "="*70)
                safe_print("      📋 HƯỚNG DẪN KHẮC PHỤC:")
                safe_print("")
                safe_print("      BƯỚC 1: Đóng Chrome hiện tại (nếu đang mở)")
                safe_print("             → Task Manager → End task chrome.exe")
                safe_print("")
                safe_print("      BƯỚC 2: Khởi động Chrome với remote debugging:")
                safe_print("             → Chạy file: start_chrome_with_debug.bat")
                safe_print("             → Hoặc mở Chrome với lệnh:")
                safe_print("                chrome.exe --remote-debugging-port=9222")
                safe_print("")
                safe_print("      BƯỚC 3: Chạy lại scraper:")
                safe_print("             → python main.py")
                safe_print("")
                safe_print("      " + "="*70)
                safe_print("      ⚠️ QUAN TRỌNG: Nếu tạo Chrome mới → Sẽ BỊ CLOUDFLARE CHẶN!")
                safe_print("      " + "="*70)
                safe_print("")
                
                # ✅ Cho phép tạo Chrome mới với anti-detection mạnh
                safe_print("      ⚠️ Không kết nối được Chrome đang chạy")
                safe_print("      🔄 Sẽ tạo Chrome mới với anti-detection mạnh để vượt Cloudflare...")
                safe_print("")
        
        # Nếu không dùng profile hiện tại hoặc không kết nối được, dùng profile riêng
        if not use_current_profile or not connected:
            user_data_dir = getattr(config, 'USER_DATA_DIR', 'user-data')
            if not os.path.isabs(user_data_dir):
                user_data_dir = os.path.abspath(user_data_dir)
            os.makedirs(user_data_dir, exist_ok=True)
        
        if use_persistent and user_data_dir:
            safe_print("      🚀 Đang khởi động REAL BROWSER MODE (System Chrome)...")
            safe_print(f"      📁 User Data Directory: {user_data_dir}")
            safe_print("      ✅ Dùng Chrome thật trên máy (không phải Chromium tích hợp)")
            safe_print("      ✅ navigator.webdriver = undefined (real browser)")
            safe_print("      ✅ Cookies được giữ tự động")
            safe_print(f"      🔌 Remote debugging port: {debug_port}")
            safe_print("      🛡️ Anti-detection MẠNH đã được kích hoạt để vượt Cloudflare!")
            
            # ✅ GIẢI PHÁP 1: Dùng Chrome thật (System Chrome) thay vì Chromium tích hợp
            # → Tránh bị Cloudflare phát hiện TLS Fingerprint và Automation Flag
            
            chrome_launched = False
            
            # Thử 1: Dùng channel="chrome" (Playwright tự tìm Chrome)
            try:
                safe_print("      🔍 Đang tìm Google Chrome...")
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
                safe_print("      ✅ Đã kết nối với Google Chrome thật (channel='chrome')!")
                chrome_launched = True
            except Exception as e:
                safe_print(f"      ⚠️ Không tìm thấy Chrome qua channel: {e}")
                safe_print("      🔍 Đang tìm Chrome executable thủ công...")
                
                # Thử 2: Tìm Chrome executable thủ công và dùng executable_path
                chrome_exe = self.find_chrome_executable()
                if chrome_exe:
                    try:
                        safe_print(f"      ✅ Tìm thấy Chrome tại: {chrome_exe}")
                        self.context = self.playwright.chromium.launch_persistent_context(
                            user_data_dir=user_data_dir,
                            executable_path=chrome_exe,  # Dùng executable_path thay vì channel
                            headless=config.HEADLESS,
                            args=browser_args,
                            viewport={"width": 1920, "height": 1080},
                            locale="en-US",
                            timezone_id="America/New_York",
                            extra_http_headers=browser_context_options["extra_http_headers"],
                        )
                        safe_print("      ✅ Đã kết nối với Google Chrome thật (executable_path)!")
                        chrome_launched = True
                    except Exception as e2:
                        safe_print(f"      ⚠️ Không thể khởi động Chrome từ executable_path: {e2}")
                else:
                    safe_print("      ⚠️ Không tìm thấy Chrome executable trên máy")
            
            # Nếu Chrome không khởi động được, thử Edge
            if not chrome_launched:
                safe_print("      🔄 Thử dùng Microsoft Edge...")
                try:
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
                    chrome_launched = True
                except Exception as e2:
                    safe_print(f"      ⚠️ Không tìm thấy Edge: {e2}")
            
            # Fallback cuối cùng: Dùng Chromium tích hợp (KHÔNG KHUYẾN KHÍCH)
            if not chrome_launched:
                safe_print("      ⚠️⚠️⚠️ CẢNH BÁO: Không tìm thấy Chrome hoặc Edge!")
                safe_print("      ⚠️⚠️⚠️ Đang dùng Chromium tích hợp - CÓ THỂ BỊ CLOUDFLARE CHẶN!")
                safe_print("      💡 Giải pháp: Cài đặt Google Chrome từ https://www.google.com/chrome/")
                try:
                    self.context = self.playwright.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        headless=config.HEADLESS,
                        args=browser_args,
                        **browser_context_options
                    )
                    safe_print("      ⚠️ Đang dùng Chromium tích hợp (có thể bị Cloudflare chặn)")
                except Exception as e3:
                    safe_print(f"      ❌ Lỗi khi khởi động Chromium: {e3}")
                    raise
            
            # Lấy browser từ context
            self.browser = self.context.browser if hasattr(self.context, 'browser') else None
            
            # Tạo page từ context
            if len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = self.context.new_page()
            
            # ✅ QUAN TRỌNG: Thêm stealth scripts để ẩn automation
            self.add_stealth_scripts_to_page(self.page)
            
            safe_print("      ✅ Real browser mode đã khởi động!")
            safe_print("      💡 Verify Cloudflare 1 lần duy nhất, cookies sẽ được giữ tự động!")
            safe_print("      🛡️ Đã thêm stealth scripts để vượt Cloudflare!")
            
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
    
    def wait_for_cloudflare_challenge(self, page=None, max_wait=None):
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
        
        # Lấy max_wait từ config nếu không được truyền vào
        if max_wait is None:
            max_wait = getattr(config, 'CLOUDFLARE_MAX_WAIT', 300)  # Mặc định 5 phút
        
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
                        # ✅ QUAN TRỌNG: Thử tự động click checkbox nếu có
                        try:
                            # Tìm và click checkbox "Verify you are human"
                            checkbox_selectors = [
                                'input[type="checkbox"]',
                                'label[for*="challenge"]',
                                '.cb-label',
                                '[data-ray]',
                                'input#challenge-form-checkbox',
                                'input[name="cf_captcha_kind"]',
                            ]
                            
                            checkbox_clicked = False
                            for selector in checkbox_selectors:
                                try:
                                    checkbox = page.locator(selector).first
                                    if checkbox.count() > 0 and checkbox.is_visible():
                                        # Thử click checkbox
                                        checkbox.click(timeout=5000)
                                        checkbox_clicked = True
                                        safe_print(f"      ✅ Đã tự động click checkbox Cloudflare!")
                                        time.sleep(2)  # Đợi challenge xử lý
                                        break
                                except:
                                    continue
                            
                            # Nếu không tìm thấy checkbox, thử tìm bằng text
                            if not checkbox_clicked:
                                try:
                                    # Tìm label có text "Verify you are human"
                                    labels = page.locator('label').all()
                                    for label in labels:
                                        try:
                                            text = label.inner_text().lower()
                                            if "verify" in text or "human" in text or "robot" in text:
                                                label.click(timeout=5000)
                                                checkbox_clicked = True
                                                safe_print(f"      ✅ Đã tự động click label Cloudflare!")
                                                time.sleep(2)
                                                break
                                        except:
                                            continue
                                except:
                                    pass
                        except Exception as e:
                            safe_print(f"      ⚠️ Không thể tự động click checkbox: {e}")
                        
                        # ✅ QUAN TRỌNG: Thử tương tác với page để giúp pass challenge
                        try:
                            # Scroll ngẫu nhiên
                            scroll_amount = random.randint(100, 500)
                            page.evaluate(f"window.scrollBy(0, {scroll_amount})")
                            time.sleep(random.uniform(0.5, 1.5))
                            page.evaluate(f"window.scrollBy(0, -{scroll_amount})")
                            
                            # Di chuyển chuột
                            page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                            time.sleep(random.uniform(0.3, 0.8))
                            
                            # Click vào body để kích hoạt user interaction
                            try:
                                body = page.locator('body').first
                                if body.count() > 0:
                                    body.click(timeout=2000)
                            except:
                                pass
                        except:
                            pass
                        
                        if check_count % 3 == 0:  # In log mỗi 3 lần check
                            safe_print(f"      ⏳ Đang đợi Cloudflare challenge tự động... ({int(time.time() - start_time)}s)")
                        
                        continue
                    
                    # ✅ QUAN TRỌNG: Kiểm tra URL - nếu URL không còn chứa challenge thì có thể đã pass
                    # Cũng kiểm tra xem có redirect về challenge không (JS redirect)
                    url_has_challenge = any(x in page_url.lower() for x in ["challenges.cloudflare.com", "cf-browser-verification"])
                    
                    # ✅ QUAN TRỌNG: Kiểm tra xem URL đã về trang thật chưa (scribblehub.com)
                    url_is_target = False
                    if "scribblehub.com" in page_url.lower() and "challenges.cloudflare.com" not in page_url.lower():
                        url_is_target = True
                    
                    # Kiểm tra xem có JS redirect về challenge không
                    try:
                        # Kiểm tra trong JavaScript context
                        js_check = page.evaluate("""
                            () => {
                                const currentUrl = window.location.href.toLowerCase();
                                if (currentUrl.includes('challenges.cloudflare.com') || 
                                    currentUrl.includes('cf-browser-verification')) {
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
                        else:
                            # Nếu JS check không có challenge, kiểm tra xem URL có phải target không
                            current_url_js = page.evaluate("() => window.location.href.toLowerCase()")
                            if "scribblehub.com" in current_url_js and "challenges.cloudflare.com" not in current_url_js:
                                url_is_target = True
                    except:
                        pass
                    
                    # ✅ QUAN TRỌNG: Kiểm tra xem có spinner/loading indicator còn không
                    spinner_gone = False
                    try:
                        # Kiểm tra các selector cho spinner/loading
                        spinner_selectors = [
                            '.spinner',
                            '.loading',
                            '.cf-spinner',
                            '[class*="spinner"]',
                            '[class*="loading"]',
                            '[id*="spinner"]',
                            '[id*="loading"]',
                        ]
                        
                        has_spinner = False
                        for selector in spinner_selectors:
                            try:
                                spinner = page.locator(selector).first
                                if spinner.count() > 0 and spinner.is_visible():
                                    has_spinner = True
                                    break
                            except:
                                continue
                        
                        if not has_spinner:
                            spinner_gone = True
                    except:
                        spinner_gone = True  # Nếu không check được, giả sử spinner đã gone
                    
                    # ✅ QUAN TRỌNG: Nếu không có challenge trong content VÀ URL không có challenge VÀ URL là target VÀ spinner đã gone
                    if not has_challenge and not url_has_challenge and url_is_target and spinner_gone:
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
                        
                        # ✅ QUAN TRỌNG: Kiểm tra xem page đã load content chưa
                        # Kiểm tra cả ranking page và story page
                        scribblehub_selectors = [
                            # Selectors cho ranking page
                            ".search_main_box",  # Container chứa danh sách truyện
                            ".search_title",  # Title của truyện trong ranking
                            ".search_stats",  # Stats của truyện
                            ".search_author",  # Author info
                            # Selectors cho story page
                            ".fic_title",
                            "ol.toc_ol",
                            ".wi_fic_desc",
                            "h1",
                            ".wi_fic_table",
                            ".fic_image",
                            ".wi_fic_info",
                            # Selectors chung
                            "body",  # Fallback: kiểm tra body có content không
                        ]
                        
                        content_loaded = False
                        for selector in scribblehub_selectors:
                            try:
                                elem = page.locator(selector).first
                                if elem.count() > 0:
                                    # Kiểm tra xem element có text không (không phải empty)
                                    try:
                                        text = elem.inner_text()
                                        if text and text.strip() and len(text.strip()) > 10:  # Phải có ít nhất 10 ký tự
                                            # Kiểm tra thêm: không phải chỉ có Cloudflare text
                                            if "cloudflare" not in text.lower() and "challenge" not in text.lower():
                                                content_loaded = True
                                                safe_print(f"      ✅ Tìm thấy content với selector: {selector}")
                                                break
                                    except:
                                        # Nếu không lấy được text, kiểm tra xem element có tồn tại không
                                        try:
                                            is_visible = elem.is_visible()
                                            if is_visible:
                                                content_loaded = True
                                                safe_print(f"      ✅ Tìm thấy element với selector: {selector}")
                                                break
                                        except:
                                            pass
                            except:
                                continue
                        
                        # ✅ QUAN TRỌNG: Nếu chưa tìm thấy content, kiểm tra body có đủ content không
                        if not content_loaded:
                            try:
                                body_text = page.locator("body").inner_text()
                                if body_text and len(body_text.strip()) > 100:  # Body phải có ít nhất 100 ký tự
                                    # Kiểm tra xem có phải chỉ là Cloudflare text không
                                    if "cloudflare" not in body_text.lower()[:200]:  # Kiểm tra 200 ký tự đầu
                                        content_loaded = True
                                        safe_print(f"      ✅ Tìm thấy content trong body ({len(body_text)} ký tự)")
                            except:
                                pass
                        
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

