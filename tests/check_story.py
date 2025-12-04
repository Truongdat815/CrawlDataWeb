import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pymongo import MongoClient
from src import config

client = MongoClient(config.MONGODB_URI)
db = client[config.MONGODB_DB_NAME]

# Get newest story
story = db["stories"].find_one({"storyId": "36735"})
if story:
    print("📚 Story 36735:")
    print(f"   Fields: {list(story.keys())}")
    print(f"\n   storyName: {story.get('storyName')}")
    print(f"   webStoryId: {story.get('webStoryId')}")
    print(f"   coverImage: {story.get('coverImage')}")
    print(f"   coverImg: {story.get('coverImg')}")
    print(f"   genres: {story.get('genres')}")
else:
    print("Story not found")

client.close()
