"""
Comment schema definition for Wattpad
Maps API response to Wattpad comment schema
"""

COMMENT_SCHEMA = {
    "commentId": "id",                    # Unique comment ID
    "webCommentId": None,                 # Website-specific comment ID
    "commentText": "body",                # Comment content
    "time": "createdAt",                  # Creation timestamp
    "chapterId": None,                    # Chapter being commented on
    "userId": "author.id",                # User ID
    "replyToUserId": None,                # User ID being replied to
    "parentId": "parentId",               # Parent comment ID (for threading)
    "isRoot": None,                       # Whether this is a root comment
    "react": "voteCount",                 # Reaction count
    "websiteId": None,                    # Reference to website
}
