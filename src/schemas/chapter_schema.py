"""
Chapter schema definition for Wattpad
Maps window.prefetched data to Wattpad chapter schema
"""

CHAPTER_SCHEMA = {
    "chapterId": "id",                    # Unique chapter ID
    "storyId": None,                      # Parent story ID
    "chapterName": "title",               # Chapter title
    "voted": "voteCount",                 # Vote count
    "views": "readCount",                 # View count
    "order": "order",                     # Chapter index/order
    "publishedTime": "createDate",        # Publish date
    "lastUpdated": "modifyDate",          # Last update date
    "chapterUrl": "url",                  # Chapter URL
    "commentCount": "commentCount",       # Number of comments
    "wordCount": "wordCount",             # Word count
    "rating": "rating",                   # Chapter rating
    "pages": "pages",                     # Number of pages
}
