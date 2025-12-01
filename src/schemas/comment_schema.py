"""
Comment schema definition for Wattpad
Maps API response to Wattpad comment schema
"""

COMMENT_SCHEMA = {
    "commentId": "id",                    # Unique comment ID
    "parentId": "parentId",               # Parent comment ID (if reply)
    "react": "voteCount",                 # Reaction count
    "userId": "author.name",              # User who commented
    "chapterId": None,                    # Chapter being commented on
    "createdAt": "createdAt",             # Creation timestamp
    "commentText": "body",                # Comment content
    "paragraphIndex": "paragraphIndex",   # Inline comment position
    "type": "inline",                     # "inline" or "chapter_end"
}
