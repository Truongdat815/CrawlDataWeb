# -*- coding: utf-8 -*-
"""
URL utilities - Common functions for URL processing and story ID extraction
"""

import re
from typing import Optional, List


def extract_story_id_from_url(url: str) -> Optional[str]:
    """
    Extract story ID from Wattpad URL or return ID if already a number
    
    Args:
        url: Wattpad URL, story URL, or pure story ID
        
    Examples:
        - "12345" -> "12345"
        - "https://www.wattpad.com/story/12345-title" -> "12345"
        - "https://www.wattpad.com/12345-chapter" -> "12345"
        
    Returns:
        Story ID string or None if invalid
    """
    if not url:
        return None
    
    url = url.strip()
    
    # Case 1: Already a pure ID
    if url.isdigit():
        return url
    
    # Case 2: Extract from URL
    match = re.search(r'/(?:story/)?(\d+)', url)
    if match:
        return match.group(1)
    
    return None


def is_category_url(url: str) -> bool:
    """
    Check if URL is a category/browse page (not individual story)
    
    Args:
        url: URL to check
        
    Returns:
        True if category/browse page, False otherwise
    """
    if not url:
        return False
    
    url = url.strip().lower()
    
    # Category indicators (broader patterns to catch variations)
    category_patterns = [
        '/stories/',      # Genre pages
        '/stories',       # Genre pages (without trailing /)
        '/browse',        # Browse pages (with or without /)
        '/home',          # Home page
        '/tag/',          # Tag pages
        '/tag',           # Tag pages (without trailing /)
    ]
    
    return any(pattern in url for pattern in category_patterns)


def extract_story_ids_from_urls(urls: List[str]) -> List[str]:
    """
    Extract story IDs from mixed list of URLs (stories + categories)
    Handles duplicates automatically
    
    Args:
        urls: List of URLs (story URLs, IDs, or category pages)
        
    Returns:
        List of unique story IDs (categories NOT included - need separate processing)
    """
    story_ids = []
    seen = set()
    
    for url in urls:
        url = url.strip()
        
        # Skip category URLs (need separate processing)
        if is_category_url(url):
            continue
        
        # Extract ID
        story_id = extract_story_id_from_url(url)
        if story_id and story_id not in seen:
            story_ids.append(story_id)
            seen.add(story_id)
    
    return story_ids


def classify_urls(urls: List[str]) -> dict:
    """
    Classify URLs into story URLs and category URLs
    
    Args:
        urls: List of mixed URLs
        
    Returns:
        {
            'story_ids': [...],      # Direct story IDs
            'category_urls': [...],  # Category pages to crawl
        }
    """
    story_ids = []
    category_urls = []
    seen_stories = set()
    
    for url in urls:
        url = url.strip()
        if not url or url.startswith('#'):
            continue
        
        if is_category_url(url):
            category_urls.append(url)
        else:
            story_id = extract_story_id_from_url(url)
            if story_id and story_id not in seen_stories:
                story_ids.append(story_id)
                seen_stories.add(story_id)
    
    return {
        'story_ids': story_ids,
        'category_urls': category_urls,
    }
