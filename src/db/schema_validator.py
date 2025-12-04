"""
MongoDB schema validators
Defines validation rules for MongoDB collections
"""

from src.schemas import comment_schema, story_schema, chapter_schema, user_schema


def get_comment_validator():
    """Get MongoDB validation schema for comments collection"""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["commentId", "webCommentId", "userId", "chapterId"],
            "properties": {
                "commentId": {"bsonType": "string"},        # wp_uuid_v7
                "webCommentId": {"bsonType": "string"},    # Original web ID
                "parentId": {"bsonType": ["string", "null"]},
                "react": {"bsonType": "int"},
                "userId": {"bsonType": "string"},
                "chapterId": {"bsonType": ["string", "int"]},
                "createdAt": {"bsonType": "string"},
                "commentText": {"bsonType": "string"},
                "paragraphIndex": {"bsonType": ["int", "null"]},
                "type": {"enum": ["inline", "chapter_end"]},
            }
        }
    }


def get_story_validator():
    """Get MongoDB validation schema for stories collection"""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["storyId", "webStoryId", "storyName"],
            "properties": {
                "storyId": {"bsonType": "string"},          # wp_uuid_v7 format
                "webStoryId": {"bsonType": "string"},      # Original website ID
                "storyName": {"bsonType": "string"},
                "storyUrl": {"bsonType": "string"},
                "userId": {"bsonType": ["string", "null"]},
                "category": {"bsonType": ["array", "null"]},
                "tags": {"bsonType": "array"},
                "description": {"bsonType": "string"},
                "totalChapters": {"bsonType": "int"},
                "totalViews": {"bsonType": "int"},
                "voted": {"bsonType": "int"},
                "mature": {"bsonType": "bool"},
                "status": {"enum": ["completed", "ongoing"]},
                "time": {"bsonType": ["string", "null"]},
            }
        }
    }


def get_chapter_validator():
    """Get MongoDB validation schema for chapters collection"""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["chapterId", "webChapterId", "storyId", "chapterName"],
            "properties": {
                "chapterId": {"bsonType": "string"},        # wp_uuid_v7 format
                "webChapterId": {"bsonType": "string"},    # Original website ID
                "storyId": {"bsonType": "string"},         # Parent wp_uuid_v7
                "chapterName": {"bsonType": "string"},
                "voted": {"bsonType": "int"},
                "views": {"bsonType": "int"},
                "commentCount": {"bsonType": "int"},
                "wordCount": {"bsonType": "int"},
                "publishedTime": {"bsonType": ["string", "null"]},
                "lastUpdated": {"bsonType": ["string", "null"]},
                "chapterUrl": {"bsonType": "string"},
                "rating": {"bsonType": ["int", "null"]},
                "pages": {"bsonType": "int"},
                "order": {"bsonType": "int"},
            }
        }
    }


def get_user_validator():
    """Get MongoDB validation schema for users collection"""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["userId", "userName"],
            "properties": {
                "userId": {"bsonType": "string"},
                "userName": {"bsonType": "string"},
                "avatar": {"bsonType": ["string", "null"]},
                "isFollowing": {"bsonType": "bool"},
            }
        }
    }
