"""
Scrapers package - modular scraper modules for different Wattpad collections.

Each module handles one collection:
- story: Story metadata (title, description, stats)
- chapter: Chapter metadata and index
- comment: Chapter comments
- user: User/author information
- content: Chapter content (separate from metadata)
- website: Website source management (multi-source support)
"""

from .story import StoryScraper
from .chapter import ChapterScraper
from .comment import CommentScraper
from .user import UserScraper
from .chapter_content import ChapterContentScraper
from .website import WebsiteScraper
from .base import BaseScraper, safe_print

__all__ = [
    'StoryScraper',
    'ChapterScraper',
    'CommentScraper',
    'UserScraper',
    'ChapterContentScraper',
    'WebsiteScraper',
    'BaseScraper',
    'safe_print'
]
