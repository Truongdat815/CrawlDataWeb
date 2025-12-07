"""
User schema definition for Wattpad
Maps API response to Wattpad user schema
API endpoint: https://www.wattpad.com/api/v3/users/{username}
"""

USER_SCHEMA = {
    "userId": None,                          # User ID (generated UUID v7: wp_uuid)
    "webUserId": None,                       # Website-specific user ID (not in API)
    "username": "username",                  # Username
    "userUrl": "deeplink",                   # User profile URL
    "createdDate": "createDate",             # Account creation date
    "gender": "gender",                      # User gender (full name like "Male")
    "location": "location",                  # User location
    "followers": "numFollowers",             # Follower count
    "following": "numFollowing",             # Following count
    "comments": None,                        # Comment count (not in API)
    "bio": "description",                    # User bio/description
    "favorites": None,                       # Favorites count (not in API)
    "ratings": None,                         # Ratings given (not in API)
    "reviews": None,                         # Reviews written (not in API)
    "numberOfStories": "numStoriesPublished", # Stories written
    "totalWords": None,                      # Total words written (not in API)
    "totalReviewsReceived": None,            # Reviews received (not in API)
    "totalRatingsReceived": "votesReceived", # Ratings received
    "totalFavoritesReceived": None,          # Favorites received (not in API)
}
