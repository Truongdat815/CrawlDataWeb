"""
Interactive login script to capture authenticated cookies from webnovel.com
Waits for manual login and saves all cookies including HttpOnly ones.
"""

import json
import os
from playwright.sync_api import sync_playwright

def safe_print(*args, **kwargs):
    """Print with UTF-8 encoding support for Windows console"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        msg = ' '.join(str(a) for a in args)
        print(msg.encode('ascii', errors='replace').decode('ascii'), **kwargs)

def setup_authenticated_cookies():
    """Interactive login session to capture authenticated cookies"""
    
    safe_print("=" * 80)
    safe_print("🔐 WEBNOVEL.COM AUTHENTICATION SETUP")
    safe_print("=" * 80)
    safe_print("\nThis script will help you login and save authenticated cookies.\n")
    
    # Start Playwright - SYSTEM CHROME STRATEGY
    safe_print("🚀 Launching browser (using system Google Chrome)...")
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        channel="chrome",  # Use system Google Chrome instead of Chromium
        headless=False,    # Must be False for login
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security"
        ]
    )
    
    # Create context WITHOUT hardcoded User-Agent (let Chrome use its native UA)
    context = browser.new_context(
        # NO user_agent - let system Chrome provide its own native User-Agent
    )
    page = context.new_page()
    
    # Navigate to login page
    safe_print("🌐 Opening login page...")
    try:
        page.goto('https://www.webnovel.com/login', timeout=30000)
        safe_print("✅ Login page loaded\n")
    except Exception as e:
        safe_print(f"⚠️  Page load warning: {e}\n")
    
    # Wait for manual login
    safe_print("=" * 80)
    safe_print("🔴 PLEASE LOGIN MANUALLY IN THE BROWSER")
    safe_print("=" * 80)
    safe_print("\n   1️⃣  Enter your email/username and password")
    safe_print("   2️⃣  Complete any CAPTCHA challenges")
    safe_print("   3️⃣  Wait until you reach the homepage or profile")
    safe_print("   4️⃣  Make sure you are fully logged in")
    safe_print("   5️⃣  Press Enter here when done...\n")
    safe_print("=" * 80 + "\n")
    
    input(">>> Press ENTER when you have successfully logged in: ")
    
    # Capture cookies
    safe_print("\n💾 Capturing authenticated cookies...")
    try:
        # Get all cookies from context (includes HttpOnly and Secure cookies)
        all_cookies = context.cookies()
        
        # Save to cookies.json
        cookies_file = 'cookies.json'
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(all_cookies, f, indent=2, ensure_ascii=False)
        
        safe_print(f"   ✅ Saved {len(all_cookies)} cookies to {cookies_file}")
        
        # Display important cookies
        safe_print("\n📋 Key cookies captured:")
        important_cookies = ['cf_clearance', '_csrfToken', 'webnovel_uuid', 'session', 'auth', 'token']
        for cookie_name in important_cookies:
            cookie = next((c for c in all_cookies if c['name'] == cookie_name), None)
            if cookie:
                value_preview = cookie['value'][:30] + "..." if len(cookie['value']) > 30 else cookie['value']
                safe_print(f"   ✅ {cookie_name}: {value_preview}")
        
        # Check authentication
        safe_print("\n🔍 Checking authentication status...")
        current_url = page.url
        safe_print(f"   Current URL: {current_url}")
        
        if 'login' in current_url.lower():
            safe_print("   ⚠️  WARNING: Still on login page. Make sure you completed login!")
        else:
            safe_print("   ✅ Appears to be logged in successfully!")
        
        safe_print("\n" + "=" * 80)
        safe_print("✅ AUTHENTICATION SUCCESSFUL! COOKIES SAVED.")
        safe_print("=" * 80)
        safe_print(f"\n📁 Cookies saved to: {os.path.abspath(cookies_file)}")
        safe_print("🔧 You can now use these cookies with other scraping scripts.\n")
        
    except Exception as e:
        safe_print(f"\n❌ Error capturing cookies: {e}")
    
    # Cleanup
    safe_print("🔚 Closing browser...")
    page.close()
    context.close()
    browser.close()
    playwright.stop()
    
    safe_print("✅ Done!\n")

if __name__ == "__main__":
    setup_authenticated_cookies()
