"""
Story schema definition for Wattpad
Maps API response to Wattpad story schema
"""

STORY_SCHEMA = {
    "storyId": "id",                      # Unique story ID
    "storyName": "title",                 # Story title
    "storyUrl": "url",                    # Story URL
    "coverImg": "cover",                  # Cover image URL
    "category": None,                     # Category ID (from prefetched)
    "status": "completed",                # "completed" or "ongoing"
    "tags": [],                           # Tag list (from prefetched)
    "description": "description",         # Story description
    "totalChapters": "numParts",          # Number of chapters
    "totalViews": "readCount",            # Total views
    "voted": "voteCount",                 # Total votes
    "mature": "mature",                   # Mature content flag
    "freeChapter": "isPaywalled",         # Free chapter flag
    "time": "createDate",                 # Creation date
    "userId": "user.name",                # Author/User ID
    "length": "length",
    "modifyDate": "modifyDate",
    "cover_timestamp": "cover_timestamp",
    "commentCount": "commentCount",
    "rating": "rating",
    
}
