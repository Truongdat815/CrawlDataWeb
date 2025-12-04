"""
Story schema definition for Wattpad
Maps API response to Wattpad story schema
"""

STORY_SCHEMA = {
    "storyId": None,                      # Auto-generated wp_uuid_v7 (primary key)
    "webStoryId": "id",                  # Original story ID from website (e.g., Wattpad ID)
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
