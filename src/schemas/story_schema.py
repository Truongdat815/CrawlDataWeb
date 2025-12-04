"""
Story schema definition for Wattpad
Maps API response to Wattpad story schema
"""

STORY_SCHEMA = {
    "storyId": "id",                      # Unique story ID
    "webStoryId": None,                   # Website-specific story ID (for other sites)
    "storyName": "title",                 # Story title
    "storyUrl": "url",                    # Story URL
    "coverImage": "cover",                # Cover image URL
    "category": None,                     # Category ID
    "status": "completed",                # "completed" or "ongoing"
    "genres": None,                       # Genres list
    "tags": [],                           # Tag list
    "description": "description",         # Story description
    "userId": "user.name",                # Author/User ID
    "totalChapters": "numParts",          # Number of chapters
}
