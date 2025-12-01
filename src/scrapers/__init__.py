"""
Scrapers package - modular scraper modules for different Wattpad collections.

Each module handles one collection:
- story: Story metadata (title, description, stats)
- chapter: Chapter metadata and index
- comment: Chapter comments
- user: User/author information
- content: Chapter content (separate from metadata)
"""

from src.scrapers.story import StoryScraper
from src.scrapers.chapter import ChapterScraper
from src.scrapers.comment import CommentScraper
from src.scrapers.user import UserScraper
from src.scrapers.chapter_content import ChapterContentScraper
from src.scrapers.base import BaseScraper, safe_print

__all__ = [
    'StoryScraper',
    'ChapterScraper',
    'CommentScraper',
    'UserScraper',
    'ChapterContentScraper',
    'BaseScraper',
    'safe_print'
]
