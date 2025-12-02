#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Quick test: map sample API JSON to story document"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scrapers.story import StoryScraper

sample = {
  "id": "399709711",
  "title": "Haikyuu | You and Me (Fanfic couples)",
  "length": 108031,
  "createDate": "2025-08-10T13:53:12Z",
  "modifyDate": "2025-11-29T12:01:39Z",
  "voteCount": 97,
  "commentCount": 0,
  "language": {"id": 19, "name": "Tiếng Việt"},
  "user": {"name": "Julietran1012", "avatar": "https://img.wattpad.com/useravatar/Julietran1012.128.142464.jpg", "fullname": "Nấm", "verified": False},
  "description": "Sample description...",
  "cover": "https://img.wattpad.com/cover/399709711-256-k515995.jpg",
  "cover_timestamp": "2025-08-30T08:06:35Z",
  "completed": False,
  "categories": [6, 0],
  "tags": ["asahi", "bl", "bokuto"],
  "rating": 1,
  "mature": False,
  "copyright": 1,
  "url": "https://www.wattpad.com/story/399709711-haikyuu-you-and-me-fanfic-couples",
  "firstPartId": 1570044979,
  "numParts": 25,
  "firstPublishedPart": {"id":1572830265, "createDate":"2025-08-30T08:24:20Z"},
  "lastPublishedPart": {"id":1580905229, "createDate":"2025-11-29T12:01:39Z"},
  "parts": [
    {"id":1570044979, "title":"Trăng đêm nay đẹp nhỉ? (TsukiYama)", "url":"https://www.wattpad.com/1570044979-haikyuu-you-and-me-fanfic-couples-trăng-đêm-nay", "length":7686, "createDate":"2025-09-28T13:13:38Z", "modifyDate":"2025-09-28T13:13:38Z", "commentCount":0, "voteCount":5, "readCount":28}
  ]
}

mapped = StoryScraper.map_api_to_story(sample, extra_info=None)
print("Mapped keys:", list(mapped.keys()))
print("Category:", mapped.get('category'))
print("Tags (count):", len(mapped.get('tags', [])))
print("Parts saved in story?", 'parts' in mapped)
