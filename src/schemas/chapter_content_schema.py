"""
Chapter Content schema definition for Wattpad
Maps chapter text content to schema
"""

CHAPTER_CONTENT_SCHEMA = {
    "contentId": None,                    # Unique content ID (generated from chapterId)
    "chapterId": "id",                    # Parent chapter ID
    "content": "text",                    # Chapter text content (HTML or plain text)
}
