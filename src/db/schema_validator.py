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
            "required": ["commentId", "userId", "chapterId"],
            "properties": {
                "commentId": {"bsonType": "string"},
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
            "required": ["storyId", "storyName"],
            "properties": {
                "storyId": {"bsonType": "string"},
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
            "required": ["chapterId", "storyId", "chapterName"],
            "properties": {
                "chapterId": {"bsonType": ["string", "int"]},
                "storyId": {"bsonType": "string"},
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
