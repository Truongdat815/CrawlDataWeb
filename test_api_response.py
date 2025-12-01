"""
Test API response structure
"""
import json
from src.scraper_engine import WattpadScraper
from src import config

bot = WattpadScraper()
bot.start()

# Test story ID
story_id = "402659967"

print(f"Fetching story {story_id}...")
story_data = bot.fetch_story_from_api(story_id)

if story_data:
    print(f"\n✅ Got story data")
    print(f"Keys: {list(story_data.keys())}")
    
    if "lastPublishedPart" in story_data:
        last_part = story_data["lastPublishedPart"]
        print(f"\n📌 lastPublishedPart:")
        print(f"   Keys: {list(last_part.keys())}")
        print(f"   Content: {json.dumps(last_part, indent=2, default=str)[:500]}")
    else:
        print(f"\n❌ No lastPublishedPart")
else:
    print(f"❌ Failed to fetch")

bot.stop()
