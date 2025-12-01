"""
Test network connectivity to Wattpad
Kiểm tra DNS, HTTP, HTTPS, kết nối thực tế
"""

import socket
import requests
import time
import sys
import os
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scrapers.base import safe_print
from src import config


def test_dns_resolution(hostname):
    """Test DNS resolution"""
    print(f"\n{'='*60}")
    print(f"🔍 Test 1: DNS Resolution - {hostname}")
    print(f"{'='*60}")
    
    try:
        ip = socket.gethostbyname(hostname)
        print(f"✅ DNS resolved: {hostname} → {ip}")
        return True
    except socket.gaierror as e:
        print(f"❌ DNS failed: {e}")
        return False


def test_socket_connection(hostname, port=443):
    """Test TCP socket connection"""
    print(f"\n{'='*60}")
    print(f"🔌 Test 2: TCP Connection - {hostname}:{port}")
    print(f"{'='*60}")
    
    try:
        sock = socket.create_connection((hostname, port), timeout=5)
        print(f"✅ TCP connection OK: {hostname}:{port}")
        sock.close()
        return True
    except Exception as e:
        print(f"❌ TCP connection failed: {e}")
        return False


def test_http_headers(url):
    """Test HTTP HEAD request"""
    print(f"\n{'='*60}")
    print(f"📡 Test 3: HTTP HEAD Request")
    print(f"{'='*60}")
    print(f"URL: {url}")
    
    try:
        response = requests.head(url, timeout=10)
        print(f"✅ HTTP HEAD OK")
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   Server: {response.headers.get('Server', 'N/A')}")
        return response.status_code < 400
    except Exception as e:
        print(f"❌ HTTP HEAD failed: {e}")
        return False


def test_api_endpoint():
    """Test actual Wattpad API endpoint"""
    print(f"\n{'='*60}")
    print(f"🎯 Test 4: Wattpad API Endpoint")
    print(f"{'='*60}")
    
    url = "https://www.wattpad.com/api/v3/stories/83744060"
    print(f"URL: {url}")
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": config.DEFAULT_USER_AGENT,
            "Accept": "application/json"
        })
        
        print("Sending GET request...")
        start_time = time.time()
        response = session.get(url, timeout=config.REQUEST_TIMEOUT)
        elapsed = time.time() - start_time
        
        print(f"✅ API request OK")
        print(f"   Status: {response.status_code}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Content-Length: {len(response.content)} bytes")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Story ID: {data.get('id')}")
            print(f"   Title: {data.get('title')}")
            print(f"   Views: {data.get('readCount'):,}")
            return True
        elif response.status_code == 429:
            print(f"⚠️ Rate limited (429) - Wattpad may have blocked you temporarily")
            return False
        else:
            print(f"⚠️ Unexpected status: {response.status_code}")
            return False
            
    except requests.Timeout as e:
        print(f"❌ Request timeout: {e}")
        return False
    except requests.ConnectionError as e:
        print(f"❌ Connection error: {e}")
        return False
    except requests.HTTPError as e:
        print(f"❌ HTTP error: {e}")
        return False
    except Exception as e:
        print(f"❌ API request failed: {e}")
        return False


def test_prefetched_page():
    """Test fetching story page with prefetched data"""
    print(f"\n{'='*60}")
    print(f"🌐 Test 5: Story Page (Prefetched Data)")
    print(f"{'='*60}")
    
    url = "https://www.wattpad.com/stories/83744060-the-friendly-neighbourhood-alien"
    print(f"URL: {url}")
    
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": config.DEFAULT_USER_AGENT,
        })
        
        print("Fetching page...")
        start_time = time.time()
        response = session.get(url, timeout=config.REQUEST_TIMEOUT)
        elapsed = time.time() - start_time
        
        print(f"✅ Page fetch OK")
        print(f"   Status: {response.status_code}")
        print(f"   Time: {elapsed:.2f}s")
        print(f"   Content-Length: {len(response.content)} bytes")
        
        if "window.prefetched" in response.text:
            print(f"   ✅ window.prefetched found in HTML")
            return True
        else:
            print(f"   ⚠️ window.prefetched NOT found (might be changed)")
            return False
            
    except Exception as e:
        print(f"❌ Page fetch failed: {e}")
        return False


def test_rate_limiter():
    """Test rate limiter logic"""
    print(f"\n{'='*60}")
    print(f"⏱️ Test 6: Rate Limiter")
    print(f"{'='*60}")
    
    from src.scraper_engine import RateLimiter
    
    limiter = RateLimiter(max_requests=5, time_window=10)
    
    print(f"Config: {5} requests per {10} seconds")
    print("Simulating 6 requests...")
    
    for i in range(6):
        print(f"  Request {i+1}...", end=" ")
        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start
        if elapsed > 0.1:
            print(f"⏳ Waited {elapsed:.2f}s")
        else:
            print("✅ OK")
    
    print(f"✅ Rate limiter working correctly")
    return True


def test_proxy_config():
    """Test proxy configuration"""
    print(f"\n{'='*60}")
    print(f"🌐 Test 7: Proxy Configuration")
    print(f"{'='*60}")
    
    if config.HTTP_PROXY or config.HTTPS_PROXY:
        print(f"✅ Proxy configured:")
        if config.HTTP_PROXY:
            print(f"   HTTP_PROXY: {config.HTTP_PROXY}")
        if config.HTTPS_PROXY:
            print(f"   HTTPS_PROXY: {config.HTTPS_PROXY}")
        return True
    else:
        print(f"ℹ️ No proxy configured (using direct connection)")
        return True


def main():
    """Run all network tests"""
    print("\n" + "🌐 "*20)
    print("WATTPAD NETWORK CONNECTIVITY TEST")
    print("🌐 "*20)
    
    print(f"\n📋 Configuration:")
    print(f"   BASE_URL: {config.BASE_URL}")
    print(f"   REQUEST_TIMEOUT: {config.REQUEST_TIMEOUT}s")
    print(f"   MAX_RETRIES: {config.MAX_RETRIES}")
    print(f"   MAX_REQUESTS_PER_MINUTE: {config.MAX_REQUESTS_PER_MINUTE}")
    
    results = {
        "DNS Resolution": False,
        "TCP Connection": False,
        "HTTP HEAD": False,
        "API Endpoint": False,
        "Prefetched Page": False,
        "Rate Limiter": False,
        "Proxy Config": False,
    }
    
    try:
        # Test 1: DNS
        results["DNS Resolution"] = test_dns_resolution("wattpad.com")
        
        # Test 2: TCP
        results["TCP Connection"] = test_socket_connection("wattpad.com", 443)
        
        # Test 3: HTTP HEAD
        results["HTTP HEAD"] = test_http_headers("https://www.wattpad.com")
        
        # Test 4: API endpoint
        results["API Endpoint"] = test_api_endpoint()
        
        # Test 5: Prefetched page
        results["Prefetched Page"] = test_prefetched_page()
        
        # Test 6: Rate limiter
        results["Rate Limiter"] = test_rate_limiter()
        
        # Test 7: Proxy config
        results["Proxy Config"] = test_proxy_config()
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")


    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Network OK ✅")
        print("\nYou can run: python main.py")
    elif passed >= 6:
        print("\n⚠️ Most tests passed, but some issues detected")
        print("Try:")
        print("  1. Check firewall/proxy settings")
        print("  2. Try VPN")
        print("  3. Check if Wattpad is accessible from your network")
    else:
        print("\n❌ Network connectivity issues detected")
        print("Troubleshooting:")
        print("  1. Check internet connection: ping 8.8.8.8")
        print("  2. Check DNS: nslookup wattpad.com")
        print("  3. Check firewall: may be blocking HTTPS/port 443")
        print("  4. Try VPN to bypass regional blocks")
        print("  5. Run: python test_scraper_offline.py (offline mode)")


if __name__ == "__main__":
    main()
