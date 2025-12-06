"""
MongoDB Import Script - Final Schema ETL Pipeline
Complete Extract-Transform-Load process for Webnovel JSON → Team's 9-Collection Schema

COLLECTIONS (9 Total):
1. websites     - Platform information (Webnovel, etc.)
2. users        - Authors and commenters
3. stories      - Novel metadata
4. chapters     - Chapter metadata
5. chapter_contents - Chapter text (normalized)
6. rankings     - Power rankings
7. scores       - Rating breakdowns
8. reviews      - User reviews (comments with ratings)
9. comments     - User comments (no ratings)

UUID v7 Strategy:
- All _id fields are UUID v7 BSON Binary (Standard)
- Original Webnovel IDs stored in web_story_id/web_user_id for traceability
- Upsert based on web IDs to prevent duplicates
"""

import os
import sys
import json
from pathlib import Path
from uuid import UUID
import uuid6
from bson.binary import Binary, UuidRepresentation
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError, DuplicateKeyError
from datetime import datetime, timedelta
import re

# Import config
sys.path.append(str(Path(__file__).parent))
from src import config

# MongoDB Configuration from config.py
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


def generate_uuid7_binary():
    """Generate UUID v7 and convert to BSON Binary (Standard representation)"""
    return Binary.from_uuid(uuid6.uuid7(), UuidRepresentation.STANDARD)


def uuid_to_binary(uuid_obj):
    """Convert UUID object or string to BSON Binary"""
    if isinstance(uuid_obj, Binary):
        return uuid_obj
    if isinstance(uuid_obj, UUID):
        return Binary.from_uuid(uuid_obj, UuidRepresentation.STANDARD)
    elif isinstance(uuid_obj, str):
        try:
            return Binary.from_uuid(UUID(uuid_obj), UuidRepresentation.STANDARD)
        except:
            return None
    return None


class WebnovelETL:
    """Complete ETL Pipeline for Webnovel JSON → MongoDB Final Schema"""
    
    def __init__(self, db):
        self.db = db
        
        # Collection references
        self.websites_col = db[COL_WEBSITES]
        self.users_col = db[COL_USERS]
        self.stories_col = db[COL_STORIES]
        self.chapters_col = db[COL_CHAPTERS]
        self.chapter_contents_col = db[COL_CHAPTER_CONTENTS]
        self.comments_col = db[COL_COMMENTS]
        self.reviews_col = db[COL_REVIEWS]
        self.rankings_col = db[COL_RANKINGS]
        self.scores_col = db[COL_SCORES]
        
        # ID caches for performance
        self.website_cache = {}  # platform_name → Binary UUID
        self.user_cache = {}     # web_user_id → Binary UUID
        
        # Ensure indexes
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for efficient querying and upserts"""
        try:
            print("📋 Creating database indexes...")
            
            # Websites: unique platform_name
            self.websites_col.create_index(
                [("platform_name", ASCENDING)],
                unique=True,
                name="idx_platform_name"
            )
            
            # Users: index on web_user_id for lookups
            self.users_col.create_index(
                [("web_user_id", ASCENDING)],
                name="idx_web_user_id"
            )
            self.users_col.create_index(
                [("username", ASCENDING)],
                name="idx_username"
            )
            
            # Stories: unique web_story_id (Webnovel book ID)
            self.stories_col.create_index(
                [("web_story_id", ASCENDING)],
                unique=True,
                name="idx_web_story_id"
            )
            
            # Chapters: composite index on story_id + order
            self.chapters_col.create_index(
                [("story_id", ASCENDING), ("order", ASCENDING)],
                name="idx_story_order"
            )
            self.chapters_col.create_index(
                [("web_chapter_id", ASCENDING)],
                unique=True,
                name="idx_web_chapter_id"
            )
            
            # Chapter Contents: index on chapter_id
            self.chapter_contents_col.create_index(
                [("chapter_id", ASCENDING)],
                name="idx_chapter_id"
            )
            
            # Comments: index on story_id and chapter_id
            self.comments_col.create_index(
                [("story_id", ASCENDING)],
                name="idx_comment_story"
            )
            self.comments_col.create_index(
                [("chapter_id", ASCENDING)],
                name="idx_comment_chapter"
            )
            
            # Reviews: index on story_id
            self.reviews_col.create_index(
                [("story_id", ASCENDING)],
                name="idx_review_story"
            )
            
            # Rankings: index on story_id
            self.rankings_col.create_index(
                [("story_id", ASCENDING)],
                name="idx_ranking_story"
            )
            
            # Scores: index on story_id
            self.scores_col.create_index(
                [("story_id", ASCENDING)],
                name="idx_score_story"
            )
            
            print("   ✅ Indexes created successfully")
        except Exception as e:
            print(f"   ⚠️  Index creation warning: {e}")
    
    def get_or_create_website(self, platform_name="Webnovel", platform_url="https://www.webnovel.com"):
        """Get or create website document with upsert"""
        if platform_name in self.website_cache:
            return self.website_cache[platform_name]
        
        try:
            # Try to find existing
            existing = self.websites_col.find_one({"platform_name": platform_name})
            if existing:
                website_id = existing['_id']
            else:
                # Create new with UUID v7
                website_id = generate_uuid7_binary()
                website_doc = {
                    "_id": website_id,
                    "platform_name": platform_name,
                    "platform_url": platform_url,
                    "created_at": datetime.utcnow()
                }
                self.websites_col.insert_one(website_doc)
                print(f"   ✅ Created website: {platform_name}")
            
            self.website_cache[platform_name] = website_id
            return website_id
            
        except DuplicateKeyError:
            # Race condition - fetch again
            existing = self.websites_col.find_one({"platform_name": platform_name})
            self.website_cache[platform_name] = existing['_id']
            return existing['_id']
    
    def get_or_create_user(self, username, web_user_id=None, website_id=None):
        """
        Get or create user with upsert logic
        Uses web_user_id as unique identifier if available, otherwise username
        """
        if not username or username.lower() == "anonymous":
            return None
        
        # Check cache
        cache_key = web_user_id if web_user_id else username
        if cache_key in self.user_cache:
            return self.user_cache[cache_key]
        
        try:
            # Search by web_user_id first (most reliable)
            if web_user_id:
                query = {"web_user_id": web_user_id}
            else:
                query = {"username": username}
            
            existing = self.users_col.find_one(query)
            
            if existing:
                user_id = existing['_id']
            else:
                # Create new user with UUID v7
                user_id = generate_uuid7_binary()
                user_doc = {
                    "_id": user_id,
                    "username": username,
                    "web_user_id": web_user_id,
                    "website_id": website_id,
                    # Schema fields not available in Webnovel (set to None)
                    "email": None,
                    "gender": None,
                    "location": None,
                    "bio": None,
                    "profile_image_url": None,
                    "created_at": datetime.utcnow()
                }
                self.users_col.insert_one(user_doc)
            
            self.user_cache[cache_key] = user_id
            return user_id
            
        except Exception as e:
            print(f"   ⚠️  User creation error for {username}: {e}")
            return None
    
    def parse_time(self, time_str):
        """Parse various time formats to datetime"""
        if not time_str:
            return None
        
        try:
            # Try ISO format
            if 'T' in str(time_str) or 'Z' in str(time_str):
                return datetime.fromisoformat(str(time_str).replace('Z', '+00:00'))
        except:
            pass
        
        # Parse relative times
        try:
            now = datetime.utcnow()
            time_str_lower = str(time_str).lower()
            
            patterns = {
                r'(\d+)\s*second': lambda m: now - timedelta(seconds=int(m.group(1))),
                r'(\d+)\s*minute': lambda m: now - timedelta(minutes=int(m.group(1))),
                r'(\d+)\s*hour': lambda m: now - timedelta(hours=int(m.group(1))),
                r'(\d+)\s*day': lambda m: now - timedelta(days=int(m.group(1))),
                r'(\d+)\s*week': lambda m: now - timedelta(weeks=int(m.group(1))),
                r'(\d+)\s*month': lambda m: now - timedelta(days=int(m.group(1))*30),
                r'(\d+)\s*year': lambda m: now - timedelta(days=int(m.group(1))*365),
            }
            
            for pattern, calc in patterns.items():
                match = re.search(pattern, time_str_lower)
                if match:
                    return calc(match)
        except:
            pass
        
        return None
    
    def parse_views(self, view_str):
        """Parse view count strings like '1.2M', '500K' to integers"""
        if isinstance(view_str, int):
            return view_str
        
        if not view_str or not isinstance(view_str, str):
            return 0
        
        view_str = str(view_str).upper().replace(',', '').strip()
        
        try:
            if 'M' in view_str:
                return int(float(view_str.replace('M', '')) * 1000000)
            elif 'K' in view_str:
                return int(float(view_str.replace('K', '')) * 1000)
            else:
                # Remove any non-digit characters
                return int(re.sub(r'[^\d]', '', view_str))
        except:
            return 0
    
    def transform_and_import(self, json_data, filename):
        """
        Complete ETL pipeline for one JSON file
        Returns statistics dict
        """
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
            print(f"   🔄 Processing: {json_data.get('name', 'Unknown')}")
            
            # STEP 1: Get/Create Website
            website_id = self.get_or_create_website("Webnovel", "https://www.webnovel.com")
            
            # STEP 2: Extract Webnovel Story ID
            web_story_id = json_data.get('platform_id')
            if not web_story_id:
                # Fallback: extract from URL
                url = json_data.get('url', '')
                match = re.search(r'_(\d+)$', url)
                web_story_id = f"wn_{match.group(1)}" if match else f"wn_{uuid6.uuid7().hex[:12]}"
            
            # Check if story already exists (UPSERT logic)
            existing_story = self.stories_col.find_one({"web_story_id": web_story_id})
            if existing_story:
                print(f"   ⏩ Story already exists: {web_story_id}")
                return stats
            
            # STEP 3: Get/Create Author User
            author_name = json_data.get('author', 'Unknown Author')
            author_user_id = self.get_or_create_user(
                username=author_name,
                web_user_id=None,  # Webnovel doesn't provide author ID
                website_id=website_id
            )
            stats['users'] += 1
            
            # STEP 4: Create Story Document
            story_id = generate_uuid7_binary()
            ratings = json_data.get('ratings', {})
            
            story_doc = {
                "_id": story_id,
                "web_story_id": web_story_id,  # Original Webnovel ID
                "website_id": website_id,
                "user_id": author_user_id,  # Author
                "title": json_data.get('name'),
                "story_url": json_data.get('url'),
                "description": json_data.get('description'),
                "cover_image_url": json_data.get('cover_image'),
                "status": json_data.get('status'),  # Ongoing/Completed
                "category": json_data.get('category'),
                "tags": json_data.get('tags', []),
                "total_views": self.parse_views(json_data.get('total_views', '0')),
                "total_chapters": json_data.get('total_chapters', 0),
                # Schema fields not in Webnovel
                "language": None,
                "is_completed": json_data.get('status') == 'Completed' if json_data.get('status') else None,
                "release_rate": None,
                "time_to_finish": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            self.stories_col.insert_one(story_doc)
            stats['story'] = True
            print(f"   ✅ Story created: {story_doc['title']}")
            
            # STEP 5: Create Rankings (if exists)
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
                    print(f"   🏆 Ranking: #{ranking_doc['position']} in {ranking_doc['ranking_title']}")
                except Exception as e:
                    print(f"   ⚠️  Ranking error: {e}")
            
            # STEP 6: Create Scores (rating breakdown)
            if ratings and ratings.get('overall_score', 0) > 0:
                try:
                    score_doc = {
                        "_id": generate_uuid7_binary(),
                        "story_id": story_id,
                        "website_id": website_id,
                        "overall_score": float(ratings.get('overall_score', 0.0)),
                        "total_ratings": int(ratings.get('total_ratings', 0)),
                        "writing_quality": float(ratings.get('writing_quality', 0.0)),
                        "stability_of_updates": float(ratings.get('stability_of_updates', 0.0)),
                        "story_development": float(ratings.get('story_development', 0.0)),
                        "character_design": float(ratings.get('character_design', 0.0)),
                        "world_background": float(ratings.get('world_background', 0.0)),
                        "recorded_at": datetime.utcnow(),
                        "created_at": datetime.utcnow()
                    }
                    self.scores_col.insert_one(score_doc)
                    stats['scores'] += 1
                    print(f"   ⭐ Score: {score_doc['overall_score']} ({score_doc['total_ratings']} ratings)")
                except Exception as e:
                    print(f"   ⚠️  Score error: {e}")
            
            # STEP 7: Process Chapters
            chapters_data = json_data.get('chapters', [])
            chapter_map = {}  # order → chapter_id mapping
            
            for chapter_json in chapters_data:
                try:
                    # Extract chapter ID
                    web_chapter_id = chapter_json.get('source_id') or chapter_json.get('id') or f"wn_ch_{uuid6.uuid7().hex[:12]}"
                    chapter_order = chapter_json.get('order', 0)
                    
                    # Check if chapter already exists
                    existing_chapter = self.chapters_col.find_one({"web_chapter_id": web_chapter_id})
                    if existing_chapter:
                        chapter_map[chapter_order] = existing_chapter['_id']
                        continue
                    
                    chapter_id = generate_uuid7_binary()
                    chapter_map[chapter_order] = chapter_id
                    
                    # Create chapter metadata
                    chapter_doc = {
                        "_id": chapter_id,
                        "web_chapter_id": web_chapter_id,
                        "story_id": story_id,
                        "order": chapter_order,
                        "chapter_name": chapter_json.get('name'),
                        "chapter_url": chapter_json.get('url'),
                        "published_at": self.parse_time(chapter_json.get('published_time')),
                        "created_at": datetime.utcnow(),
                        # Schema fields not in Webnovel
                        "view_count": None,
                        "is_locked": len(chapter_json.get('content', '')) < 50,
                    }
                    
                    self.chapters_col.insert_one(chapter_doc)
                    stats['chapters'] += 1
                    
                    # STEP 8: Create Chapter Content (separate collection)
                    content_text = chapter_json.get('content', '')
                    if content_text and len(content_text) > 0:
                        content_doc = {
                            "_id": generate_uuid7_binary(),
                            "chapter_id": chapter_id,
                            "content": content_text,
                            "word_count": len(content_text.split()),
                            "created_at": datetime.utcnow()
                        }
                        self.chapter_contents_col.insert_one(content_doc)
                        stats['contents'] += 1
                    
                    # STEP 9: Process Chapter Comments
                    chapter_comments = chapter_json.get('comments', [])
                    for comment_json in chapter_comments:
                        self._process_comment(
                            comment_json,
                            story_id,
                            chapter_id,
                            website_id,
                            stats,
                            is_chapter_comment=True
                        )
                
                except Exception as e:
                    print(f"   ⚠️  Chapter {chapter_json.get('order')} error: {e}")
                    continue
            
            # STEP 10: Process Book-Level Comments (Reviews vs Comments)
            book_comments = json_data.get('comments', [])
            for comment_json in book_comments:
                self._process_comment(
                    comment_json,
                    story_id,
                    None,  # No chapter_id for book comments
                    website_id,
                    stats,
                    is_chapter_comment=False
                )
            
            print(f"   📊 Imported: {stats['chapters']} chapters, {stats['contents']} contents, " +
                  f"{stats['comments']} comments, {stats['reviews']} reviews")
            
            return stats
            
        except Exception as e:
            print(f"   ❌ Transform error: {e}")
            import traceback
            traceback.print_exc()
            return stats
    
    def _process_comment(self, comment_json, story_id, chapter_id, website_id, stats, is_chapter_comment):
        """
        Process a comment: decide if it's a review or comment
        Reviews: book-level comments WITH score
        Comments: chapter comments OR book comments WITHOUT score
        """
        try:
            # Get commenter user
            user_name = comment_json.get('user_name', 'Anonymous')
            web_user_id = comment_json.get('user_id')
            commenter_user_id = self.get_or_create_user(user_name, web_user_id, website_id)
            if commenter_user_id:
                stats['users'] += 1
            
            posted_at = self.parse_time(comment_json.get('time'))
            content = comment_json.get('content')
            score_data = comment_json.get('score', {})
            rating = score_data.get('overall') if isinstance(score_data, dict) else None
            
            # DECISION: Review or Comment?
            # Review: book-level comment WITH rating
            # Comment: chapter comment OR book comment WITHOUT rating
            is_review = (not is_chapter_comment) and (rating is not None)
            
            if is_review:
                # Create REVIEW
                review_doc = {
                    "_id": generate_uuid7_binary(),
                    "web_review_id": comment_json.get('source_id') or comment_json.get('comment_id'),
                    "story_id": story_id,
                    "user_id": commenter_user_id,
                    "content": content,
                    "rating": float(rating) if rating else None,
                    "posted_at": posted_at,
                    "created_at": datetime.utcnow(),
                    # Schema fields not in Webnovel
                    "helpful_count": None,
                    "is_verified_purchase": False,
                }
                self.reviews_col.insert_one(review_doc)
                stats['reviews'] += 1
            else:
                # Create COMMENT
                comment_doc = {
                    "_id": generate_uuid7_binary(),
                    "web_comment_id": comment_json.get('source_id') or comment_json.get('comment_id'),
                    "story_id": story_id,
                    "chapter_id": chapter_id,  # None for book comments
                    "user_id": commenter_user_id,
                    "parent_comment_id": None,  # Top-level comment
                    "content": content,
                    "posted_at": posted_at,
                    "created_at": datetime.utcnow(),
                    # Schema fields not in Webnovel
                    "like_count": None,
                    "is_edited": False,
                }
                self.comments_col.insert_one(comment_doc)
                stats['comments'] += 1
                
                # Process replies recursively
                comment_id = comment_doc['_id']
                replies = comment_json.get('replies', [])
                for reply_json in replies:
                    self._process_reply(reply_json, story_id, chapter_id, comment_id, website_id, stats)
        
        except Exception as e:
            print(f"   ⚠️  Comment processing error: {e}")
    
    def _process_reply(self, reply_json, story_id, chapter_id, parent_comment_id, website_id, stats):
        """Process a reply (nested comment)"""
        try:
            # Get reply user
            user_name = reply_json.get('user_name', 'Anonymous')
            web_user_id = reply_json.get('user_id')
            user_id = self.get_or_create_user(user_name, web_user_id, website_id)
            
            reply_doc = {
                "_id": generate_uuid7_binary(),
                "web_comment_id": reply_json.get('source_id') or reply_json.get('comment_id'),
                "story_id": story_id,
                "chapter_id": chapter_id,
                "user_id": user_id,
                "parent_comment_id": parent_comment_id,  # Link to parent
                "content": reply_json.get('content'),
                "posted_at": self.parse_time(reply_json.get('time')),
                "created_at": datetime.utcnow(),
                "like_count": None,
                "is_edited": False,
            }
            
            self.comments_col.insert_one(reply_doc)
            stats['comments'] += 1
        
        except Exception as e:
            print(f"   ⚠️  Reply processing error: {e}")


def main():
    """Main ETL execution"""
    print("="*80)
    print("📦 WEBNOVEL ETL PIPELINE - FINAL SCHEMA (9 Collections)")
    print("="*80)
    print()
    
    print(f"⚙️  Configuration:")
    print(f"   MongoDB URI: {MONGO_URI[:50]}...")
    print(f"   Database: {DB_NAME}")
    print(f"   Collections: {COL_WEBSITES}, {COL_USERS}, {COL_STORIES}, {COL_CHAPTERS},")
    print(f"                {COL_CHAPTER_CONTENTS}, {COL_COMMENTS}, {COL_REVIEWS},")
    print(f"                {COL_RANKINGS}, {COL_SCORES}")
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
    
    print(f"📋 Found {len(json_files)} JSON files to process")
    print()
    
    # Connect to MongoDB
    print("🔌 Connecting to Team MongoDB VPS...")
    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=10000,
            uuidRepresentation='standard'
        )
        client.server_info()
        print("✅ Connected successfully!")
        print()
    except PyMongoError as e:
        print(f"❌ MongoDB connection failed: {e}")
        return 1
    
    # Get database and initialize ETL
    db = client[DB_NAME]
    etl = WebnovelETL(db)
    
    # Statistics
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
    print("🚀 Starting ETL process...")
    print()
    
    for i, json_file in enumerate(json_files, 1):
        print(f"📚 [{i}/{len(json_files)}] {json_file.name}")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            stats = etl.transform_and_import(json_data, json_file.name)
            
            # Accumulate statistics
            if stats['story']:
                total_stats['stories'] += 1
            total_stats['chapters'] += stats['chapters']
            total_stats['contents'] += stats['contents']
            total_stats['comments'] += stats['comments']
            total_stats['reviews'] += stats['reviews']
            total_stats['rankings'] += stats['rankings']
            total_stats['scores'] += stats['scores']
            total_stats['users'] += stats['users']
            
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON: {e}")
            total_stats['errors'] += 1
        except Exception as e:
            print(f"   ❌ Processing error: {e}")
            total_stats['errors'] += 1
        
        print()
    
    # Final summary
    print("="*80)
    print("🎉 ETL COMPLETE - FINAL SCHEMA")
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
    collections = [
        COL_WEBSITES, COL_USERS, COL_STORIES, COL_CHAPTERS,
        COL_CHAPTER_CONTENTS, COL_COMMENTS, COL_REVIEWS,
        COL_RANKINGS, COL_SCORES
    ]
    
    for col_name in collections:
        try:
            count = db[col_name].count_documents({})
            print(f"   {col_name}: {count} documents")
        except Exception as e:
            print(f"   {col_name}: Error - {e}")
    
    print()
    print("✅ ETL Pipeline complete! Verify UUID Binary format in MongoDB Compass.")
    print(f"   Connection: {MONGO_URI}")
    
    client.close()
    return 0 if total_stats['errors'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
