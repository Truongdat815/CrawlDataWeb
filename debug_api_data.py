"""
Debug: Fetch story data via API to determine actual data structure
"""
import requests
import json
from src.config import REQUEST_TIMEOUT

# Test story ID (from our previous config)
STORY_ID = 1585675450

# Try fetching story details via API
url = f"https://www.wattpad.com/api/v3/stories/{STORY_ID}"

print(f"🔍 Fetching story details from: {url}")
print(f"Timeout: {REQUEST_TIMEOUT}s\n")

try:
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Successfully fetched story data!")
        print(f"Keys in response: {list(data.keys())}\n")
        
        # Show structure
        print("Response structure:")
        print(json.dumps(data, indent=2, default=str)[:2000])
        print("\n... (truncated)")
        
        # Check for categories/tags
        print(f"\n📌 Categories/Tags found:")
        if 'tags' in data:
            print(f"   tags: {data['tags']}")
        if 'categories' in data:
            print(f"   categories: {data['categories']}")
        if 'cover' in data:
            print(f"   cover: {data['cover']}")
        if 'description' in data:
            print(f"   description: {data['description'][:200]}")
            
    else:
        print(f"❌ API returned status {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print(f"⏱️ Timeout after {REQUEST_TIMEOUT}s (firewall blocking)")
except requests.exceptions.ConnectionError as e:
    print(f"❌ Connection error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
