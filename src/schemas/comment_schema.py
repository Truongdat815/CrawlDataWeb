"""
Comment schema definition for Wattpad
Maps API response to Wattpad comment schema
"""

COMMENT_SCHEMA = {
    "commentId": "id",                    # Unique comment ID
    "parentId": "parentId",               # Parent comment ID (if reply)
    "react": "voteCount",                 # Reaction count
    "userId": "author.id",                # User ID (UUID nếu không có từ web)
    "userName": "author.name",            # Username/display name
    "chapterId": None,                    # Chapter being commented on
    "createdAt": "createdAt",             # Creation timestamp
    "modified": None,                       # Modified timestamp
    "commentText": "body",                # Comment content
    "deeplink": None,                       # Direct URL to the comment
    "replyCount": None,                     # Number of replies
    "resourceNamespace": None,              # Resource namespace (paragraphs/parts)
    "resourceId": None,                     # Resource ID referenced by the comment
    "sentiments": None,                     # Raw sentiments object (likes, reactions)
    "status": None,                         # Comment status (public/private)
    "userAvatar": None,                     # Commenter's avatar URL
    "paragraphIndex": "paragraphIndex",   # Inline comment position (for inline comments)
    "type": "inline",                     # "inline" or "chapter_end" (location of comment)
}
