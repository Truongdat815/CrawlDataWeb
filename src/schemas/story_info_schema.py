"""
Story Info schema definition - metrics and statistics
Stores all stats/metrics separate from core story data
"""

STORY_INFO_SCHEMA = {
    "infoId": None,                       # Auto-generated wp_uuid_v7 (unique per story)
    "storyId": "id",                      # Reference to story (wp_uuid_v7 format)
    "websiteId": None,                    # Reference to website
    "totalViews": "readCount",            # Total story views
    "averageViews": None,                 # Average views per chapter
    "followers": None,                    # Story followers
    "favorites": None,                    # Story favorites
    "pageViews": None,                    # Page views
    "overallScore": "rating",             # Overall rating/score
    "styleScore": None,                   # Style/world background score
    "storyScore": None,                   # Story development score
    "grammarScore": None,                 # Writing quality score
    "characterScore": None,               # Character design score
    "stabilityOfUpdates": None,           # Update stability score
    "voted": "voteCount",                 # Total votes across chapters
    "freeChapter": "isPaywalled",         # Free chapters flag
    "time": "createDate",                 # Reading time estimate
    "releaseRate": None,                  # Release rate
    "numberOfReader": None,               # Number of readers
    "ratingTotal": None,                  # Total rating count
    "totalViewsChapters": None,           # Sum of all chapter views
    "totalWord": "length",                # Total word count
    "averageWords": None,                 # Average words per chapter
    "lastUpdated": "modifyDate",          # Last update time
    "totalReviews": None,                 # Total reviews
    "userReading": None,                  # Users currently reading
    "userPlanToRead": None,               # Users planning to read
    "userCompleted": None,                # Users completed
    "userPaused": None,                   # Users paused
    "userDropped": None,                  # Users dropped
}
