# Wattpad API Response → MongoDB Schema Mapping

## Quick Reference

### Stories Mapping
```python
# API Response Structure (from https://www.wattpad.com/api/v3/stories/...)
{
    "id": "83744060",                           # → storyId
    "title": "15 Days With The Possessive...",  # → storyName
    "url": "https://www.wattpad.com/story/...", # → storyUrl
    "cover": "https://img.wattpad.com/cover/...",# → coverImg
    "description": "Story description text...",  # → description
    "numParts": 49,                             # → totalChapters
    "readCount": 687809,                        # → totalViews
    "voteCount": 16782,                         # → voted
    "completed": true,                          # → status ("completed"/"ongoing")
    "mature": true,
    "isPaywalled": false,                       # → freeChapter (!isPaywalled)
    "paidModel": "",
    "createDate": "2016-09-05T16:27:28Z",      # → time
    "lastPublishedPart": {
        "id": 903430552,
        "createDate": "2020-12-06T18:37:20Z"
    },
    "user": {
        "name": "oneperson100feelings",         # → userId
        "avatar": "https://img.wattpad.com/..."
    }
}

# MongoDB Document (stories collection)
{
    "storyId": "83744060",
    "storyName": "15 Days With The Possessive...",
    "storyUrl": "https://www.wattpad.com/story/...",
    "coverImg": "https://img.wattpad.com/cover/...",
    "category": null,                           # TODO: Query categories API
    "status": "completed",
    "tags": [],                                 # TODO: Extract from API or page
    "description": "Story description text...",
    "totalChapters": 49,
    "totalViews": 687809,
    "voted": 16782,
    "freeChapter": true,
    "time": "2016-09-05T16:27:28Z",
    "userId": "oneperson100feelings"
}
```

---

### Comments Mapping
```python
# API Response Structure (from https://www.wattpad.com/api/v3/stories/{storyId}/parts/{partId}/comments)
{
    "comments": [
        {
            "commentId": {
                "namespace": "comments",
                "resourceId": "1455298714__1764501355_db06a063f9"
            },
            "created": "2025-11-30T11:15:55Z",
            "deeplink": "https://www.wattpad.com/1455298714/comment/...",
            "modified": "2025-11-30T11:15:55Z",
            "replyCount": 0,
            "resource": {
                "namespace": "parts",
                "resourceId": "1455298714"
            },
            "sentiments": {},
            "status": "public",
            "text": "congratulations ❤️",
            "user": {
                "avatar": "https://a.wattpad.com/useravatar/...",
                "name": "chinonsolexi"
            }
        }
    ],
    "pagination": {
        "after": {...}
    }
}

# MongoDB Document (comments collection)
{
    "commentId": "1455298714__1764501355_db06a063f9",      # from: commentId.resourceId
    "parentId": null,                                       # from: embedded in API (need to extract)
    "react": {},                                           # from: sentiments
    "userId": "chinonsolexi",                             # from: user.name
    "chapterId": "1455298714",                            # from: resource.resourceId
    "createdAt": "2025-11-30T11:15:55Z",                 # from: created
    "commentText": "congratulations ❤️",                  # from: text
    "paragraphIndex": null,                               # TODO: Extract if inline comment
    "type": "chapter_end"                                 # TODO: Determine from API response
}
```

---

### Categories Mapping
```python
# API Response Structure (from https://www.wattpad.com/api/v3/categories)
[
    {
        "id": 4,
        "name": "Lãng mạn",
        "name_english": "Romance",
        "roles": ["onboarding", "writing", "searching"]
    },
    {
        "id": 5,
        "name": "Khoa học viễn tưởng",
        "name_english": "Science Fiction",
        "roles": ["onboarding", "writing", "searching"]
    }
]

# Usage: Map story category via name_english
# Example: If story has category "Romance", save name_english as category field
```

---

## Implementation Code Examples

### Story Processing
```python
def scrape_story_metadata(self, story_data):
    processed_story = {
        "storyId": story_data.get("id"),
        "storyName": story_data.get("title"),
        "storyUrl": story_data.get("url"),
        "coverImg": story_data.get("cover"),
        "category": None,  # TODO: Query categories API to get name_english
        "status": "completed" if story_data.get("completed") else "ongoing",
        "tags": [],  # TODO: Extract from story metadata or page
        "description": story_data.get("description", ""),
        "totalChapters": story_data.get("numParts", 0),
        "totalViews": story_data.get("readCount", 0),
        "voted": story_data.get("voteCount", 0),
        "freeChapter": not story_data.get("isPaywalled", False),
        "time": story_data.get("createDate"),
        "userId": story_data.get("user", {}).get("name")
    }
    self.save_story_to_mongo(processed_story)
    return processed_story
```

### Comment Processing
```python
def process_comments(self, comments_response, chapter_id):
    processed_comments = []
    for comment in comments_response.get("comments", []):
        comment_data = {
            "commentId": comment["commentId"]["resourceId"],
            "parentId": None,  # TODO: Extract from API if nested
            "react": comment.get("sentiments", {}),
            "userId": comment["user"]["name"],
            "chapterId": comment["resource"]["resourceId"],
            "createdAt": comment["created"],
            "commentText": comment["text"],
            "paragraphIndex": None,  # TODO: Determine from API
            "type": "chapter_end"  # TODO: Parse from API response
        }
        processed_comments.append(comment_data)
    return processed_comments
```

---

## Field Transformation Rules

| Target Field | Source | Transformation |
|---|---|---|
| `storyId` | `id` | Direct string |
| `status` | `completed` | Boolean → "completed" or "ongoing" |
| `freeChapter` | `isPaywalled` | Inverted boolean (!value) |
| `time` | `createDate` | ISO 8601 string (no change) |
| `userId` | `user.name` | Nested object access |
| `commentId` | `commentId.resourceId` | Nested object access |
| `chapterId` | `resource.resourceId` | Nested object access |
| `createdAt` | `created` | ISO 8601 string (no change) |

---

## TODO Items

- [ ] Categories API: Query and cache all categories
- [ ] Category mapping: Create function to match story category to name_english
- [ ] Tags extraction: Identify source (API or page scraping)
- [ ] Nested comments: Determine how to identify and handle parent-child relationships
- [ ] Inline comments: Determine how to identify inline vs chapter_end comments
- [ ] Paragraph indexing: Extract paragraph index for inline comments
- [ ] Chapter content: Implement separate collection for full chapter text
- [ ] Rate limiting: Add to respect Wattpad API rate limits
- [ ] Error handling: Add retry logic for failed API calls
- [ ] Data validation: Validate all required fields before saving

---

## Code Location References

- **StoryScraper**: `src/scrapers/story.py` - `scrape_story_metadata()`
- **CommentScraper**: `src/scrapers/comment.py` - `save_comment_to_mongo()`
- **Main Engine**: `src/scraper_engine.py` - `RoyalRoadScraper` class

---

## API Documentation Links

- Stories API: https://www.wattpad.com/api/v3/stories/{id}
- Categories: https://www.wattpad.com/api/v3/categories
- Comments: https://www.wattpad.com/api/v3/stories/{storyId}/parts/{partId}/comments
