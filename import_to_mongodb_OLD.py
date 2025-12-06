"""
MongoDB Import Script - Final Schema Transformation
Transforms scraped Webnovel JSON into Team's Final Schema with UUID v7 BSON Binary

COLLECTIONS STRUCTURE:
- websites: Platform information (Webnovel, RoyalRoad, etc.)
- users: Author and commenter information
- stories: Novel metadata (links to website_id, user_id)
- chapters: Chapter metadata (links to story_id)
- chapter_contents: Chapter text content (links to chapter_id)
- comments: User comments (links to story_id, user_id)

UUID v7 Strategy:
- Generate new UUID v7 for all primary keys (_id)
- Store original Webnovel IDs in platform_id fields for traceability
- Convert UUIDs to BSON Binary (Standard) for optimal MongoDB performance
"""

import os
import sys
import json
from pathlib import Path
from uuid import UUID
import uuid6
from bson.binary import Binary, UuidRepresentation
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from datetime import datetime
import re

# Import config
sys.path.append(str(Path(__file__).parent))
from src import config

# MongoDB Configuration
MONGO_URI = config.MONGODB_URI
DB_NAME = config.DB_NAME
COL_WEBSITES = config.COL_WEBSITES
COL_USERS = config.COL_USERS
COL_STORIES = config.COL_STORIES
COL_CHAPTERS = config.COL_CHAPTERS
COL_CHAPTER_CONTENTS = config.COL_CHAPTER_CONTENTS
COL_COMMENTS = config.COL_COMMENTS
COL_REVIEWS = config.COL_REVIEWS
COL_RANKINGS = config.COL_RANKINGS
COL_SCORES = config.COL_SCORES

JSON_DIR = Path('data/json')

# UUID Conversion Helpers
def generate_uuid7_binary():
    """Generate UUID v7 and convert to BSON Binary (Standard representation)"""
    return Binary.from_uuid(uuid6.uuid7(), UuidRepresentation.STANDARD)

def uuid_to_binary(uuid_obj):
    """Convert UUID object to BSON Binary"""
    if isinstance(uuid_obj, UUID):
        return Binary.from_uuid(uuid_obj, UuidRepresentation.STANDARD)
    elif isinstance(uuid_obj, str):
        try:
            return Binary.from_uuid(UUID(uuid_obj), UuidRepresentation.STANDARD)
        except:
            return None
    return None


class SchemaTransformer:
    """Transforms Webnovel JSON to Final Schema and imports to MongoDB"""
    
    def __init__(self, db):
        self.db = db
        self.websites_col = db[COL_WEBSITES]
        self.users_col = db[COL_USERS]
        self.stories_col = db[COL_STORIES]
        self.chapters_col = db[COL_CHAPTERS]
        self.chapter_contents_col = db[COL_CHAPTER_CONTENTS]
        self.comments_col = db[COL_COMMENTS]
        self.reviews_col = db[COL_REVIEWS]
        self.rankings_col = db[COL_RANKINGS]
        self.scores_col = db[COL_SCORES]
        
        # Cache for generated IDs
        self.website_id_cache = {}
        self.user_id_cache = {}
        
        # Ensure indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for efficient querying"""
        try:
            # Websites: unique platform_name
            self.websites_col.create_index([("platform_name", ASCENDING)], unique=True)
            
            # Users: unique platform_user_id
            self.users_col.create_index([("platform_user_id", ASCENDING)])
            
            # Stories: platform_id for upsert checks
            self.stories_col.create_index([("platform_id", ASCENDING)], unique=True)
            
            # Chapters: story_id + order for efficient queries
            self.chapters_col.create_index([("story_id", ASCENDING), ("order", ASCENDING)])
            
            # Comments: story_id for queries
            self.comments_col.create_index([("story_id", ASCENDING)])
            
            # Reviews: story_id for queries
            self.reviews_col.create_index([("story_id", ASCENDING)])
            
            # Rankings: story_id for queries
            self.rankings_col.create_index([("story_id", ASCENDING)])
            
            # Scores: story_id for queries
            self.scores_col.create_index([("story_id", ASCENDING)])
            
            print("✅ Database indexes ensured")
        except Exception as e:
            print(f"⚠️  Index creation warning: {e}")
    
    def get_or_create_website(self, platform_name="Webnovel", platform_url="https://www.webnovel.com"):
        """Get or create website document"""
        if platform_name in self.website_id_cache:
            return self.website_id_cache[platform_name]
        
        # Check if exists
        existing = self.websites_col.find_one({"platform_name": platform_name})
        if existing:
            website_id = existing['_id']
        else:
            # Create new website
            website_id = generate_uuid7_binary()
            website_doc = {
                "_id": website_id,
                "platform_name": platform_name,
                "platform_url": platform_url,
                "created_at": datetime.utcnow()
            }
            self.websites_col.insert_one(website_doc)
            print(f"   ✅ Created website: {platform_name}")
        
        self.website_id_cache[platform_name] = website_id
        return website_id
    
    def get_or_create_user(self, username, platform_user_id=None, website_id=None):
        """Get or create user document"""
        if not username or username == "Anonymous":
            return None
        
        # Create cache key
        cache_key = f"{platform_user_id or username}"
        if cache_key in self.user_id_cache:
            return self.user_id_cache[cache_key]
        
        # Check if exists
        query = {"platform_user_id": platform_user_id} if platform_user_id else {"username": username}
        existing = self.users_col.find_one(query)
        
        if existing:
            user_id = existing['_id']
        else:
            # Create new user
            user_id = generate_uuid7_binary()
            user_doc = {
                "_id": user_id,
                "username": username,
                "platform_user_id": platform_user_id,
                "website_id": website_id,
                "created_at": datetime.utcnow()
            }
            self.users_col.insert_one(user_doc)
        
        self.user_id_cache[cache_key] = user_id
        return user_id
    
    def parse_published_time(self, time_str):
        """Parse various time formats to datetime or None"""
        if not time_str:
            return None
        
        try:
            # Try ISO format first
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        except:
            pass
        
        # Handle relative times like "2 days ago"
        try:
            now = datetime.utcnow()
            if 'second' in time_str:
                seconds = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(seconds=seconds)
            elif 'minute' in time_str:
                minutes = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(minutes=minutes)
            elif 'hour' in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(hours=hours)
            elif 'day' in time_str:
                days = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(days=days)
            elif 'week' in time_str:
                weeks = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(weeks=weeks)
            elif 'month' in time_str:
                months = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(days=months * 30)
            elif 'year' in time_str:
                years = int(re.search(r'(\d+)', time_str).group(1))
                return now - timedelta(days=years * 365)
        except:
            pass
        
        return None
    
    def transform_and_import(self, json_data, filename):
        """Transform JSON to Final Schema and import to MongoDB"""
        stats = {
            'story': False,
            'chapters': 0,
            'contents': 0,
            'comments': 0,
            'reviews': 0,
            'rankings': 0,
            'scores': 0,
            'users': 0
        }
        
        try:
            # Get website ID (Webnovel)
            website_id = self.get_or_create_website("Webnovel", "https://www.webnovel.com")
            
            # Extract platform_id from JSON
            platform_id = json_data.get('platform_id')
            if not platform_id:
                # Try to extract from URL
                url = json_data.get('url', '')
                match = re.search(r'_(\d+)$', url)
                platform_id = f"wn_{match.group(1)}" if match else None
            
            if not platform_id:
                print(f"   ⚠️  No platform_id found, using generated ID")
                platform_id = f"wn_{uuid6.uuid7().hex[:12]}"
            
            # Check if story already exists (for resume capability)
            existing_story = self.stories_col.find_one({"platform_id": platform_id})
            if existing_story:
                print(f"   ⏩ Story already exists: {json_data.get('name')} ({platform_id})")
                return stats
            
            # CREATE AUTHOR USER
            author_name = json_data.get('author', 'Unknown Author')
            author_user_id = self.get_or_create_user(
                username=author_name,
                platform_user_id=None,  # Webnovel doesn't provide author ID
                website_id=website_id
            )
            stats['users'] += 1
            
            # CREATE STORY DOCUMENT
            story_id = generate_uuid7_binary()
            
            # Parse ratings
            ratings = json_data.get('ratings', {})
            
            story_doc = {
                "_id": story_id,
                "platform_id": platform_id,
                "website_id": website_id,
                "story_name": json_data.get('name'),
                "story_url": json_data.get('url'),
                "user_id": author_user_id,  # Author
                "description": json_data.get('description'),
                "cover_image_url": json_data.get('cover_image'),
                "status": json_data.get('status'),  # Ongoing/Completed
                "category": json_data.get('category'),
                "tags": json_data.get('tags', []),
                "total_views": self._parse_view_count(json_data.get('total_views', '0')),
                "total_chapters": json_data.get('total_chapters', 0),
                "power_ranking_position": json_data.get('power_ranking_position'),
                "power_ranking_title": json_data.get('power_ranking_title'),
                # Ratings
                "overall_rating": ratings.get('overall_score', 0.0),
                "total_ratings": ratings.get('total_ratings', 0),
                "writing_quality": ratings.get('writing_quality', 0.0),
                "stability_of_updates": ratings.get('stability_of_updates', 0.0),
                "story_development": ratings.get('story_development', 0.0),
                "character_design": ratings.get('character_design', 0.0),
                "world_background": ratings.get('world_background', 0.0),
                # Metadata
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                # Schema fields not available in Webnovel
                "language": None,
                "is_completed": json_data.get('status') == 'Completed' if json_data.get('status') else None,
                "last_chapter_published_at": None,
            }
            
            self.stories_col.insert_one(story_doc)
            stats['story'] = True
            print(f"   ✅ Created story: {story_doc['story_name']}")
            
            # CREATE RANKING DOCUMENT (if power ranking exists)
            if json_data.get('power_ranking_position') or json_data.get('power_ranking_title'):
                try:
                    ranking_doc = {
                        "_id": generate_uuid7_binary(),
                        "story_id": story_id,
                        "website_id": website_id,
                        "ranking_title": json_data.get('power_ranking_title'),
                        "position": json_data.get('power_ranking_position'),
                        "recorded_at": datetime.utcnow(),
                        "created_at": datetime.utcnow()
                    }
                    self.rankings_col.insert_one(ranking_doc)
                    stats['rankings'] += 1
                    print(f"   🏆 Created ranking: #{ranking_doc['position']} in {ranking_doc['ranking_title']}")
                except Exception as e:
                    print(f"   ⚠️  Ranking creation error: {e}")
            
            # CREATE SCORES DOCUMENT (rating breakdown)
            if ratings and ratings.get('overall_score', 0) > 0:
                try:
                    score_doc = {
                        "_id": generate_uuid7_binary(),
                        "story_id": story_id,
                        "website_id": website_id,
                        "overall_score": ratings.get('overall_score', 0.0),
                        "total_ratings": ratings.get('total_ratings', 0),
                        "writing_quality": ratings.get('writing_quality', 0.0),
                        "stability_of_updates": ratings.get('stability_of_updates', 0.0),
                        "story_development": ratings.get('story_development', 0.0),
                        "character_design": ratings.get('character_design', 0.0),
                        "world_background": ratings.get('world_background', 0.0),
                        "recorded_at": datetime.utcnow(),
                        "created_at": datetime.utcnow()
                    }
                    self.scores_col.insert_one(score_doc)
                    stats['scores'] += 1
                    print(f"   ⭐ Created score: {score_doc['overall_score']} ({score_doc['total_ratings']} ratings)")
                except Exception as e:
                    print(f"   ⚠️  Score creation error: {e}")
            
            # CREATE CHAPTERS
            chapters_data = json_data.get('chapters', [])
            for chapter_json in chapters_data:
                try:
                    chapter_id = generate_uuid7_binary()
                    
                    # Parse published time
                    published_at = self.parse_published_time(chapter_json.get('published_time'))
                    
                    chapter_doc = {
                        "_id": chapter_id,
                        "platform_id": chapter_json.get('source_id') or chapter_json.get('id'),
                        "story_id": story_id,
                        "order": chapter_json.get('order', 0),
                        "title": chapter_json.get('name'),
                        "chapter_url": chapter_json.get('url'),
                        "published_at": published_at,
                        "created_at": datetime.utcnow(),
                        # Schema fields not in Webnovel
                        "view_count": None,
                        "is_locked": len(chapter_json.get('content', '')) < 50,  # Assume locked if very short
                    }
                    
                    self.chapters_col.insert_one(chapter_doc)
                    stats['chapters'] += 1
                    
                    # CREATE CHAPTER CONTENT (separate collection)
                    content_text = chapter_json.get('content', '')
                    if content_text and len(content_text) > 0:
                        content_doc = {
                            "_id": generate_uuid7_binary(),
                            "chapter_id": chapter_id,
                            "content_text": content_text,
                            "word_count": len(content_text.split()),
                            "created_at": datetime.utcnow()
                        }
                        self.chapter_contents_col.insert_one(content_doc)
                        stats['contents'] += 1
                    
                    # CREATE CHAPTER COMMENTS
                    chapter_comments = chapter_json.get('comments', [])
                    for comment_json in chapter_comments:
                        self._create_comment(comment_json, story_id, chapter_id, website_id, stats)
                
                except Exception as e:
                    print(f"   ⚠️  Chapter {chapter_json.get('order')} error: {e}")
                    continue
            
            # CREATE BOOK-LEVEL COMMENTS
            book_comments = json_data.get('comments', [])
            for comment_json in book_comments:
                # Check if this is a review (has score) or regular comment
                if comment_json.get('score', {}).get('overall'):
                    self._create_review(comment_json, story_id, website_id, stats)
                else:
                    self._create_comment(comment_json, story_id, None, website_id, stats)
            
            return stats
            
        except Exception as e:
            print(f"   ❌ Transform error: {e}")
            import traceback
            traceback.print_exc()
            return stats
    
    def _parse_view_count(self, view_str):
        """Parse view count strings like '1.2M', '500K' to integers"""
        if isinstance(view_str, int):
            return view_str
        
        if not view_str or not isinstance(view_str, str):
            return 0
        
        view_str = view_str.upper().replace(',', '').strip()
        
        try:
            if 'M' in view_str:
                return int(float(view_str.replace('M', '')) * 1000000)
            elif 'K' in view_str:
                return int(float(view_str.replace('K', '')) * 1000)
            else:
                return int(re.sub(r'[^\d]', '', view_str))
        except:
            return 0
    
    def _create_comment(self, comment_json, story_id, chapter_id, website_id, stats):
        """Create comment and handle nested replies"""
        try:
            # Get or create commenter user
            user_name = comment_json.get('user_name', 'Anonymous')
            platform_user_id = comment_json.get('user_id')
            commenter_user_id = self.get_or_create_user(user_name, platform_user_id, website_id)
            if commenter_user_id:
                stats['users'] += 1
            
            # Parse comment time
            posted_at = self.parse_published_time(comment_json.get('time'))
            
            # Create comment document
            comment_doc = {
                "_id": generate_uuid7_binary(),
                "platform_id": comment_json.get('source_id') or comment_json.get('comment_id'),
                "story_id": story_id,
                "chapter_id": chapter_id,  # None for book-level comments
                "user_id": commenter_user_id,
                "parent_comment_id": None,  # Top-level comment
                "content": comment_json.get('content'),
                "posted_at": posted_at,
                "score": comment_json.get('score', {}).get('overall'),
                "created_at": datetime.utcnow(),
                # Schema fields not in Webnovel
                "like_count": None,
                "is_edited": False,
            }
            
            comment_id = comment_doc['_id']
            self.comments_col.insert_one(comment_doc)
            stats['comments'] += 1
            
            # Handle nested replies
            replies = comment_json.get('replies', [])
            for reply_json in replies:
                self._create_reply(reply_json, story_id, chapter_id, comment_id, website_id, stats)
        
        except Exception as e:
            print(f"   ⚠️  Comment creation error: {e}")
    
    def _create_reply(self, reply_json, story_id, chapter_id, parent_comment_id, website_id, stats):
        """Create reply comment"""
        try:
            # Get or create reply user
            user_name = reply_json.get('user_name', 'Anonymous')
            platform_user_id = reply_json.get('user_id')
            user_id = self.get_or_create_user(user_name, platform_user_id, website_id)
            
            posted_at = self.parse_published_time(reply_json.get('time'))
            
            reply_doc = {
                "_id": generate_uuid7_binary(),
                "platform_id": reply_json.get('source_id') or reply_json.get('comment_id'),
                "story_id": story_id,
                "chapter_id": chapter_id,
                "user_id": user_id,
                "parent_comment_id": parent_comment_id,  # Link to parent
                "content": reply_json.get('content'),
                "posted_at": posted_at,
                "score": reply_json.get('score', {}).get('overall'),
                "created_at": datetime.utcnow(),
                "like_count": None,
                "is_edited": False,
            }
            
            self.comments_col.insert_one(reply_doc)
            stats['comments'] += 1
        
        except Exception as e:
            print(f"   ⚠️  Reply creation error: {e}")
    
    def _create_review(self, review_json, story_id, website_id, stats):
        """Create review document (comment with rating score)"""
        try:
            # Get or create reviewer user
            user_name = review_json.get('user_name', 'Anonymous')
            platform_user_id = review_json.get('user_id')
            reviewer_user_id = self.get_or_create_user(user_name, platform_user_id, website_id)
            if reviewer_user_id:
                stats['users'] += 1
            
            posted_at = self.parse_published_time(review_json.get('time'))
            
            # Create review document
            review_doc = {
                "_id": generate_uuid7_binary(),
                "platform_id": review_json.get('source_id') or review_json.get('comment_id'),
                "story_id": story_id,
                "user_id": reviewer_user_id,
                "content": review_json.get('content'),
                "rating": review_json.get('score', {}).get('overall'),
                "posted_at": posted_at,
                "created_at": datetime.utcnow(),
                # Schema fields not in Webnovel
                "helpful_count": None,
                "is_verified_purchase": False,
            }
            
            self.reviews_col.insert_one(review_doc)
            stats['reviews'] += 1
        
        except Exception as e:
            print(f"   ⚠️  Review creation error: {e}")


def main():
    print("="*80)
    print("📦 MONGODB IMPORT - FINAL SCHEMA TRANSFORMATION (UUID v7 BSON)")
    print("="*80)
    print()
    
    print(f"⚙️  Configuration:")
    print(f"   MongoDB URI: {MONGO_URI[:50]}...")
    print(f"   Database: {DB_NAME}")
    print(f"   Collections: {COL_STORIES}, {COL_CHAPTERS}, {COL_CHAPTER_CONTENTS}, {COL_COMMENTS}, {COL_REVIEWS}, {COL_RANKINGS}, {COL_SCORES}, {COL_USERS}, {COL_WEBSITES}")
    print(f"   JSON Directory: {JSON_DIR}")
    print()
    
    # Check JSON directory
    if not JSON_DIR.exists():
        print(f"❌ Error: JSON directory not found: {JSON_DIR}")
        return 1
    
    # Find JSON files
    json_files = list(JSON_DIR.glob('*.json'))
    if not json_files:
        print(f"❌ Error: No JSON files found in {JSON_DIR}")
        return 1
    
    print(f"📋 Found {len(json_files)} JSON files to import")
    print()
    
    # Connect to MongoDB
    print("🔌 Connecting to MongoDB Team Server...")
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            uuidRepresentation='standard'  # Use standard UUID representation
        )
        client.server_info()
        print("✅ Connected successfully!")
        print()
    except PyMongoError as e:
        print(f"❌ Failed to connect: {e}")
        return 1
    
    # Get database
    db = client[DB_NAME]
    transformer = SchemaTransformer(db)
    
    # Import statistics
    total_stats = {
        'stories': 0,
        'chapters': 0,
        'contents': 0,
        'comments': 0,
        'reviews': 0,
        'rankings': 0,
        'scores': 0,
        'users': 0,
        'errors': 0
    }
    
    # Process each JSON file
    for i, json_file in enumerate(json_files, 1):
        print(f"📚 [{i}/{len(json_files)}] Processing: {json_file.name}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            stats = transformer.transform_and_import(json_data, json_file.name)
            
            if stats['story']:
                total_stats['stories'] += 1
            total_stats['chapters'] += stats['chapters']
            total_stats['contents'] += stats['contents']
            total_stats['comments'] += stats['comments']
            total_stats['reviews'] += stats['reviews']
            total_stats['rankings'] += stats['rankings']
            total_stats['scores'] += stats['scores']
            total_stats['users'] += stats['users']
            
            print(f"   📊 Imported: {stats['chapters']} chapters, {stats['contents']} contents, {stats['comments']} comments, {stats['reviews']} reviews")
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON: {e}")
            total_stats['errors'] += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            total_stats['errors'] += 1
        
        print()
    
    # Final summary
    print("="*80)
    print("🎉 IMPORT COMPLETE - FINAL SCHEMA")
    print("="*80)
    print(f"📊 Total Imported:")
    print(f"   ✅ Stories: {total_stats['stories']}")
    print(f"   ✅ Chapters: {total_stats['chapters']}")
    print(f"   ✅ Chapter Contents: {total_stats['contents']}")
    print(f"   ✅ Comments: {total_stats['comments']}")
    print(f"   ✅ Reviews: {total_stats['reviews']}")
    print(f"   ✅ Rankings: {total_stats['rankings']}")
    print(f"   ✅ Scores: {total_stats['scores']}")
    print(f"   ✅ Users: {total_stats['users']}")
    print(f"   ❌ Errors: {total_stats['errors']}")
    print("="*80)
    print()
    
    # Verify collections
    print("🔍 Verifying MongoDB collections...")
    for col_name in [COL_WEBSITES, COL_USERS, COL_STORIES, COL_CHAPTERS, COL_CHAPTER_CONTENTS, COL_COMMENTS, COL_REVIEWS, COL_RANKINGS, COL_SCORES]:
        try:
            count = db[col_name].count_documents({})
            print(f"   {col_name}: {count} documents")
        except Exception as e:
            print(f"   {col_name}: Error - {e}")
    
    print()
    print("✅ Import complete! Check MongoDB Compass to verify UUID Binary format and schema structure.")
    
    client.close()
    return 0 if total_stats['errors'] == 0 else 1


if __name__ == '__main__':
    from datetime import timedelta  # Import here for parse_published_time
    sys.exit(main())
