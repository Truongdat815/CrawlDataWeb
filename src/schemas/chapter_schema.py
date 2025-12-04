"""
Chapter schema definition for Wattpad
Maps window.prefetched data to Wattpad chapter schema
"""

CHAPTER_SCHEMA = {
    "chapterId": "id",                    # Unique chapter ID
    "webChapterId": None,                 # Website-specific chapter ID
    "order": "order",                     # Chapter index/order
    "chapterName": "title",               # Chapter title
    "chapterUrl": "url",                  # Chapter URL
    "publishedTime": "createDate",        # Publish date
    "storyId": None,                      # Parent story ID
    "voted": "voteCount",                 # Vote count
    "views": "readCount",                 # View count
    "totalComments": "commentCount",      # Number of comments
}
