#!/usr/bin/env python3
"""Unit test for v5 comment mapping and page processing (offline)."""
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../')

from src.scrapers.comment import CommentScraper


def test_process_v5_comments_page_basic():
    # Minimal v5-like page with one comment and no pagination
    sample = {
        "comments": [
            {
                "commentId": {"resourceId": "c1"},
                "created": "2025-12-01T12:00:00Z",
                "modified": "2025-12-01T12:00:00Z",
                "user": {"name": "tester", "avatar": "https://img"},
                "text": "Hello world",
                "replyCount": 0,
                "resource": {"namespace": "parts", "resourceId": "p1"},
                "sentiments": {":like:": {"count": 2}}
            }
        ],
        "pagination": {}
    }

    mapped_list, parents, next_cursor = CommentScraper.process_v5_comments_page(sample, chapter_id="p1", namespace='paragraphs')

    assert isinstance(mapped_list, list)
    assert len(mapped_list) == 1
    c = mapped_list[0]
    assert c.get('commentId') == 'c1'
    assert c.get('userName') == 'tester'
    assert c.get('commentText') == 'Hello world'
    assert parents == []
    assert next_cursor is None


if __name__ == '__main__':
    test_process_v5_comments_page_basic()
    print('OK')
