"""
User schema definition for Wattpad
Maps API response to Wattpad user schema
"""

USER_SCHEMA = {
    "userId": "name",                     # User ID/username
    "userName": "name",                   # Display name
    "avatar": "avatar",                   # Avatar URL
    "isFollowing": "isFollowing",         # Following status
}
