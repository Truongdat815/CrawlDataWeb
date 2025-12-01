"""
Scrapers package - modular scraper modules for different collections.

Each module handles one collection:
- story: Story metadata (title, description, stats, scores)
- chapter: Chapter content and metadata
- review: Story reviews
- comment: Chapter/story comments
- user: User/author information
- score: Rating scores
"""

from src.scrapers.story import StoryScraper
from src.scrapers.chapter import ChapterScraper
from src.scrapers.review import ReviewScraper
from src.scrapers.comment import CommentScraper
from src.scrapers.user import UserScraper
from src.scrapers.base import BaseScraper, safe_print

__all__ = [
    'StoryScraper',
    'ChapterScraper',
    'ReviewScraper',
    'CommentScraper',
    'UserScraper',
    'BaseScraper',
    'safe_print'
]
