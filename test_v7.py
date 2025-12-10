#!/usr/bin/env python
"""
V7 Verification Test
Quick test to verify V7 implementation is working correctly
"""

import sys
import os

def test_import():
    """Test if WebnovelScraper can be imported"""
    try:
        from src.webnovel_scraper import WebnovelScraper
        print("✅ Import successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_initialization():
    """Test if scraper can be initialized"""
    try:
        from src.webnovel_scraper import WebnovelScraper
        scraper = WebnovelScraper(headless=True)
        print("✅ Initialization successful")
        return True
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return False

def test_method_exists():
    """Test if new V7 methods exist"""
    try:
        from src.webnovel_scraper import WebnovelScraper
        scraper = WebnovelScraper(headless=True)
        
        # Check V7 methods
        assert hasattr(scraper, '_wait_for_cloudflare'), "Missing _wait_for_cloudflare method"
        assert hasattr(scraper, '_reset_to_chapter_one'), "Missing _reset_to_chapter_one method"
        assert hasattr(scraper, 'scrape_book'), "Missing scrape_book method"
        
        print("✅ All required methods exist")
        return True
    except AssertionError as e:
        print(f"❌ Method check failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_version_info():
    """Check if V7 version info is in docstring"""
    try:
        from src import webnovel_scraper
        docstring = webnovel_scraper.__doc__
        
        if docstring and 'V7' in docstring:
            print("✅ V7 version info found in docstring")
            return True
        else:
            print("⚠️  V7 version info not found in docstring")
            return False
    except Exception as e:
        print(f"❌ Version check failed: {e}")
        return False

def main():
    print("="*60)
    print("V7 VERIFICATION TEST")
    print("="*60)
    print()
    
    tests = [
        ("Import Test", test_import),
        ("Initialization Test", test_initialization),
        ("Method Existence Test", test_method_exists),
        ("Version Info Test", test_version_info)
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n🔍 Running: {name}")
        result = test_func()
        results.append(result)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - V7 is ready for use!")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Please check errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
