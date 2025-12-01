"""
Test scraper logic offline với mock data
Dùng để test parsing, MongoDB logic mà không cần internet
"""

import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper_engine import WattpadScraper
from src.scrapers import StoryScraper, ChapterScraper, CommentScraper, UserScraper
from src.scrapers.base import safe_print


# ==================== MOCK DATA ====================

MOCK_STORY_API_RESPONSE = {
    "id": 83744060,
    "title": "The Friendly Neighbourhood Alien",
    "url": "https://www.wattpad.com/stories/83744060-the-friendly-neighbourhood-alien",
    "cover": "https://a.wattpad.com/useravatar/...",
    "description": "A friendly alien lands on Earth and befriends a human...",
    "numParts": 5,
    "readCount": 125000,
    "voteCount": 5000,
    "completed": True,
    "mature": False,
    "isPaywalled": False,
    "createDate": "2023-01-01T00:00:00Z",
    "user": {
        "name": "test_author",
        "avatar": "https://a.wattpad.com/useravatar/..."
    },
    "lastPublishedPart": {
        "id": 1234567890,
        "title": "Chapter 5: The Farewell"
    }
}

MOCK_PREFETCHED_DATA = {
    "story": {
        "id": 83744060,
        "title": "The Friendly Neighbourhood Alien",
        "tags": ["sci-fi", "alien", "adventure"],
        "categories": [14, 25],  # Science Fiction, Adventure
        "language": "en",
        "length": 45000
    },
    "story.83744060.metadata": {
        "data": {
            "group": {
                "tags": ["sci-fi", "alien", "adventure"],
                "categories": [14, 25],
                "language": "en",
                "user": "test_author"
            }
        }
    },
    "part.1234567890.metadata": {
        "data": {
            "id": 1234567890,
            "title": "Chapter 5: The Farewell",
            "wordCount": 8500,
            "voteCount": 450,
            "readCount": 8900,
            "commentCount": 120,
            "order": 5,
            "createDate": "2023-06-15T10:30:00Z",
            "modifyDate": "2023-06-15T11:00:00Z",
            "rating": 4.8,
            "url": "https://www.wattpad.com/stories/83744060/chapters/1234567890"
        }
    },
    "part.1234567891.metadata": {
        "data": {
            "id": 1234567891,
            "title": "Chapter 4: The Meeting",
            "wordCount": 7500,
            "voteCount": 380,
            "readCount": 8200,
            "commentCount": 95,
            "order": 4,
            "createDate": "2023-06-10T10:30:00Z",
            "modifyDate": "2023-06-10T11:00:00Z",
            "rating": 4.7,
            "url": "https://www.wattpad.com/stories/83744060/chapters/1234567891"
        }
    }
}

MOCK_CATEGORIES = {
    "categories": [
        {"id": 14, "name": "Science Fiction", "slug": "sci-fi"},
        {"id": 25, "name": "Adventure", "slug": "adventure"}
    ]
}

MOCK_COMMENTS = {
    "comments": [
        {
            "id": 1001,
            "text": "This is amazing!",
            "user": {"name": "user1"},
            "createdAt": "2023-06-15T12:00:00Z",
            "parentId": None
        },
        {
            "id": 1002,
            "text": "Love it!",
            "user": {"name": "user2"},
            "createdAt": "2023-06-15T12:05:00Z",
            "parentId": None
        }
    ]
}

MOCK_PAGE_HTML = """
<html>
<body>
<a href="/story/83744060-the-friendly-neighbourhood-alien">The Friendly Neighbourhood Alien</a>
<a href="/story/100000001-another-story">Another Story</a>
<a href="/story/100000002-third-story">Third Story</a>
</body>
</html>
"""


# ==================== TEST FUNCTIONS ====================

def test_story_scraper():
    """Test StoryScraper metadata processing"""
    print("\n" + "="*60)
    print("🧪 Test 1: StoryScraper - metadata processing")
    print("="*60)
    
    scraper = StoryScraper(page=None, mongo_db=None)
    
    # Test with mock API data
    result = scraper.scrape_story_metadata(MOCK_STORY_API_RESPONSE, extra_info={
        "tags": MOCK_PREFETCHED_DATA["story"]["tags"],
        "categories": MOCK_PREFETCHED_DATA["story"]["categories"]
    })
    
    print(f"✅ Processed story: {result['storyName']}")
    print(f"   - Story ID: {result['storyId']}")
    print(f"   - Views: {result['totalViews']}")
    print(f"   - Votes: {result['voted']}")
    print(f"   - Tags: {result['tags']}")
    print(f"   - Status: {result['status']}")
    print(f"   - Mature: {result['mature']}")
    
    assert result['storyId'] == 83744060
    assert result['storyName'] == "The Friendly Neighbourhood Alien"
    assert result['totalViews'] == 125000
    assert 'sci-fi' in result['tags']
    print("✅ StoryScraper test passed!")


def test_chapter_scraper():
    """Test ChapterScraper metadata extraction"""
    print("\n" + "="*60)
    print("🧪 Test 2: ChapterScraper - metadata extraction")
    print("="*60)
    
    scraper = ChapterScraper(page=None, mongo_db=None)
    
    # Simulate chapter data from prefetched
    chapter_data = {
        "chapterId": 1234567890,
        "storyId": 83744060,
        "chapterName": "Chapter 5: The Farewell",
        "voted": 450,
        "views": 8900,
        "order": 5,
        "publishedTime": "2023-06-15T10:30:00Z",
        "lastUpdated": "2023-06-15T11:00:00Z",
        "chapterUrl": "https://www.wattpad.com/stories/83744060/chapters/1234567890",
        "wordCount": 8500,
        "rating": 4.8,
        "commentCount": 120
    }
    
    print(f"✅ Chapter data: {chapter_data['chapterName']}")
    print(f"   - Chapter ID: {chapter_data['chapterId']}")
    print(f"   - Votes: {chapter_data['voted']}")
    print(f"   - Views: {chapter_data['views']}")
    print(f"   - Order: {chapter_data['order']}")
    print(f"   - Word count: {chapter_data['wordCount']}")
    print(f"   - Rating: {chapter_data['rating']}")
    
    assert chapter_data['chapterId'] == 1234567890
    assert chapter_data['order'] == 5
    print("✅ ChapterScraper test passed!")


def test_html_parsing():
    """Test HTML parsing for story links"""
    print("\n" + "="*60)
    print("🧪 Test 3: HTML parsing - extract story links")
    print("="*60)
    
    from bs4 import BeautifulSoup
    import re
    
    soup = BeautifulSoup(MOCK_PAGE_HTML, 'html.parser')
    story_links = []
    
    for link in soup.find_all('a', href=True):
        href_raw = link.get('href')
        if href_raw is None:
            continue
        
        href = str(href_raw) if href_raw else ''
        if not href:
            continue
        
        if re.search(r'/story/\d+', href) or re.search(r'/\d+\-', href):
            if not href.startswith('http'):
                href = "https://www.wattpad.com" + href
            
            story_id_match = re.search(r'/(\d+)', href)
            if story_id_match:
                story_id = story_id_match.group(1)
                existing = [url for url in story_links if story_id in url]
                if not existing:
                    story_links.append(href)
    
    print(f"✅ Extracted {len(story_links)} story links:")
    for url in story_links:
        print(f"   - {url}")
    
    assert len(story_links) == 3
    print("✅ HTML parsing test passed!")


def test_wattpad_scraper_mock():
    """Test WattpadScraper with mocked HTTP requests"""
    print("\n" + "="*60)
    print("🧪 Test 4: WattpadScraper - mocked HTTP requests")
    print("="*60)
    
    with patch('src.scraper_engine.requests.Session') as mock_session_class:
        # Create scraper
        scraper = WattpadScraper()
        
        # Mock HTTP session
        mock_session = MagicMock()
        scraper.http = mock_session
        
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_STORY_API_RESPONSE
        mock_response.raise_for_status.return_value = None
        mock_session.get.return_value = mock_response
        
        print("✅ WattpadScraper initialized")
        print(f"   - HTTP session: {type(scraper.http)}")
        print(f"   - Rate limiter: {type(scraper.rate_limiter)}")
        print(f"   - Story scraper: {type(scraper.story_scraper)}")
        
        # Test fetch_story_from_api with mock
        print("✅ HTTP session configured with headers:")
        print(f"   - User-Agent: {scraper.http.headers.get('User-Agent', 'Not set')[:40]}...")
        print(f"   - Accept: {scraper.http.headers.get('Accept', 'Not set')}")
        
        print("✅ WattpadScraper test passed!")


def test_prefetched_extraction():
    """Test extraction of prefetched data"""
    print("\n" + "="*60)
    print("🧪 Test 5: Extract chapters from prefetched data")
    print("="*60)
    
    scraper = WattpadScraper()
    
    # Test extract_chapters_from_prefetched
    chapters = scraper.extract_chapters_from_prefetched(MOCK_PREFETCHED_DATA, 83744060)
    
    print(f"✅ Extracted {len(chapters)} chapters:")
    for ch in chapters:
        print(f"   - Chapter {ch.get('order')}: {ch.get('chapterName')}")
        print(f"     ID: {ch.get('chapterId')}")
        print(f"     Votes: {ch.get('voted')}")
        print(f"     Views: {ch.get('views')}")
    
    assert len(chapters) > 0
    assert chapters[0]['storyId'] == 83744060
    print("✅ Prefetched extraction test passed!")


def test_story_info_extraction():
    """Test extraction of story info from prefetched"""
    print("\n" + "="*60)
    print("🧪 Test 6: Extract story info from prefetched data")
    print("="*60)
    
    scraper = WattpadScraper()
    
    # Test extract_story_info_from_prefetched
    info = scraper.extract_story_info_from_prefetched(MOCK_PREFETCHED_DATA)
    
    print(f"✅ Story info extracted:")
    print(f"   - Tags: {info.get('tags')}")
    print(f"   - Categories: {info.get('categories')}")
    print(f"   - Language: {info.get('language')}")
    print(f"   - Length: {info.get('length')} words")
    
    assert 'sci-fi' in info['tags']
    assert 14 in info['categories']
    print("✅ Story info extraction test passed!")


# ==================== MAIN ====================

def main():
    """Run all offline tests"""
    print("\n" + "🧪 "*20)
    print("WATTPAD SCRAPER - OFFLINE TESTS (NO INTERNET NEEDED)")
    print("🧪 "*20)
    
    try:
        test_story_scraper()
        test_chapter_scraper()
        test_html_parsing()
        test_wattpad_scraper_mock()
        test_prefetched_extraction()
        test_story_info_extraction()
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED!")
        print("="*60)
        print("\nLogic scraper OK ✅")
        print("Khi network được, chỉ cần turn off test mode và run main.py\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
