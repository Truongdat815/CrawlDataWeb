"""
User schema definition for Wattpad
Maps API response to Wattpad user schema
"""

USER_SCHEMA = {
    "userId": "name",                     # User ID/username
    "webUserId": None,                    # Website-specific user ID
    "username": "name",                   # Display name
    "userUrl": None,                      # User profile URL
    "createdDate": None,                  # Account creation date
    "gender": None,                       # User gender
    "location": None,                     # User location
    "followers": None,                    # Follower count
    "following": None,                    # Following count
    "comments": None,                     # Comment count
    "bio": None,                          # User bio/description
    "favorites": None,                    # Favorites count
    "ratings": None,                      # Ratings given
    "reviews": None,                      # Reviews written
    "numberOfStories": None,              # Stories written
    "totalWords": None,                   # Total words written
    "totalReviewsReceived": None,         # Reviews received
    "totalRatingsReceived": None,         # Ratings received
    "totalFavoritesReceived": None,       # Favorites received
}
