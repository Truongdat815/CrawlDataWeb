"""
Test script to verify reply detection and fetching
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper_engine import WattpadScraper
from src import config

# Set limit để test nhanh
config.MAX_COMMENTS_PER_CHAPTER = 20

scraper = WattpadScraper()
scraper.start()

# Test với chapter có reply
chapter_id = '1211987074'
print(f'Testing chapter {chapter_id}...')
comments = scraper.fetch_comments_from_api_v5(chapter_id)

print(f'\n=== RESULTS ===')
print(f'Total comments fetched: {len(comments)}')

# Count replies vs chapter-end
chapter_end = [c for c in comments if c.get('type') == 'chapter_end']
replies = [c for c in comments if c.get('type') != 'chapter_end']
print(f'Chapter-end comments: {len(chapter_end)}')
print(f'Replies: {len(replies)}')

# Show sample reply
if replies:
    print(f'\n=== Sample Reply ===')
    r = replies[0]
    print(f'ID: {r.get("commentId")}')
    print(f'Parent: {r.get("parentId")}')
    print(f'Type: {r.get("type")}')
    print(f'Text: {r.get("commentText", "")[:50]}...')

scraper.stop()
print('\n✅ Test completed')
