"""
Strict Schema MongoDB Pipeline - ROBUST EDITION
- Fixes missing chapterId
- Fixes missing content/commentText
- Handles both Raw and Transformed input formats
- Enforces String IDs and Nulls
"""

import logging
import uuid6
from datetime import datetime
from pymongo import MongoClient, UpdateOne
from utils import calculate_story_hash

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class StorySyncPipeline:
    def __init__(self, db_client_or_uri, db_name='webnovel_database'):
        if isinstance(db_client_or_uri, str):
            self.client = MongoClient(db_client_or_uri)
        else:
            self.client = db_client_or_uri
            
        self.db = self.client[db_name]
        
        # 10 Collections
        self.stories = self.db['stories']
        self.story_info = self.db['storyInfo']
        self.chapters = self.db['chapters']
        self.chapter_contents = self.db['chapterContents']
        self.websites = self.db['websites']
        self.rankings = self.db['rankings']
        self.comments = self.db['comments']
        self.users = self.db['users']
        self.reviews = self.db['reviews']
        self.scores = self.db['scores']

    def _to_str(self, value):
        if value is None: return None
        return str(value)

    def _now_str(self):
        return datetime.utcnow().isoformat()

    def _generate_wn_id(self):
        return f"wn_{uuid6.uuid7()}"

    def process_story(self, data):
        # 1. WEBSITE
        web_id_input = data.get('websiteId') or "wn_019b3870-1234-7567-89ab-cdef01234567"
        web_name = data.get('websiteName', 'Webnovel')
        website_id = self._ensure_website(web_id_input, web_name)

        # 2. USER
        author_data = data.get('author', {})
        author_id = self._ensure_user(author_data)

        # 3. STORY
        chap1_content = ""
        chapters_data = data.get('chapters', [])
        if chapters_data:
            sorted_chaps = sorted(chapters_data, key=lambda x: x.get('order', 0))
            chap1_content = sorted_chaps[0].get('content', '')
        
        story_hash = calculate_story_hash(chap1_content)
        input_story_id = data.get('storyId')
        story_id = self._find_or_create_story(data, input_story_id, author_id, story_hash)

        # 4. INFO & RANKING
        self._upsert_story_info(story_id, website_id, data)
        self._upsert_ranking(story_id, website_id, data)

        # 5. CHAPTERS
        self._sync_chapters_strict(story_id, chapters_data)

        # 6. REVIEWS
        self._sync_reviews_strict(story_id, website_id, data.get('reviews', []))
        
        # 7. COMMENTS (Gom từ 2 nguồn: list comments chung và list trong chapters)
        all_comments = list(data.get('comments', [])) # Copy list
        
        # Gom comment từ chapter nếu có (để xử lý trường hợp raw)
        for ch in chapters_data:
            if ch.get('comments'):
                for c in ch['comments']:
                    # Gán tạm webChapterId để lát nữa map ra chapterId
                    if not c.get('chapterId'): 
                        c['_temp_chapter_web_id'] = ch.get('webChapterId')
                all_comments.extend(ch['comments'])
        
        self._sync_comments_strict(story_id, website_id, all_comments)

        return story_id

    # =========================================================================
    # CORE LOGIC
    # =========================================================================

    def _ensure_website(self, website_id, name):
        found = self.websites.find_one({"websiteName": name})
        if found:
            if found.get('websiteId') != website_id:
                self.websites.update_one({'_id': found['_id']}, {'$set': {'websiteId': website_id}})
                return website_id
            return found.get('websiteId')
        
        doc = {"_id": website_id, "websiteId": website_id, "websiteName": name}
        try: self.websites.insert_one(doc)
        except: pass
        return website_id

    def _ensure_user(self, user_data):
        username = user_data.get('username') or "Unknown"
        web_uid = user_data.get('webUserId')
        input_user_id = user_data.get('userId')

        if web_uid:
            found = self.users.find_one({'webUserId': web_uid})
            if found: return found['userId']
        found = self.users.find_one({'username': username})
        if found: return found['userId']

        final_user_id = input_user_id or self._generate_wn_id()
        doc = {
            "_id": final_user_id, "userId": final_user_id,
            "webUserId": web_uid, "username": username,
            "userUrl": user_data.get('userUrl'),
            "createdDate": self._now_str(),
            "numberOfStories": None, "gender": None, "location": None, 
            "followers": None, "following": None, "comments": None,
            "bio": None, "favorites": None, "ratings": None, "reviews": None,
            "totalWords": None, "totalReviewsReceived": None, 
            "totalRatingsReceived": None, "totalFavoritesReceived": None
        }
        try: self.users.insert_one(doc)
        except: pass
        return final_user_id

    def _find_or_create_story(self, data, input_story_id, author_id, story_hash):
        if story_hash and story_hash != "0"*16:
            found = self.stories.find_one({'storyHash': story_hash})
            if found:
                logger.info(f"   ⚠️ TRÙNG SimHash: {found['storyName']}")
                return found['storyId']

        story_name = data.get('storyName')
        found = self.stories.find_one({'storyName': story_name, 'userId': author_id})
        if found:
            if not found.get('storyHash'):
                self.stories.update_one({'_id': found['_id']}, {'$set': {'storyHash': story_hash}})
            return found['storyId']

        final_story_id = input_story_id or self._generate_wn_id()
        doc = {
            "_id": final_story_id, "storyId": final_story_id,
            "webStoryId": data.get('webStoryId'),
            "storyName": story_name, "storyUrl": data.get('storyUrl'),
            "coverImage": data.get('coverImage'), "category": data.get('category'),
            "status": data.get('status'), "genres": data.get('genres', []),
            "tags": data.get('tags', []), "description": data.get('description'),
            "userId": author_id,
            "totalChapters": self._to_str(data.get('totalChapters')),
            "language": data.get('language', 'English'),
            "storyHash": story_hash
        }
        try: self.stories.insert_one(doc)
        except: pass
        return final_story_id

    def _upsert_story_info(self, story_id, website_id, data):
        info = data.get('info', {})
        info_id = info.get('infoId') or self._generate_wn_id()
        update_doc = {
            "storyId": story_id, "websiteId": website_id,
            "totalViews": self._to_str(info.get('totalViews')),     
            "overallScore": self._to_str(info.get('overallScore')), 
            "ratingTotal": self._to_str(info.get('ratingTotal')),   
            "totalReviews": self._to_str(info.get('totalReviews')), 
            "lastUpdated": self._now_str(),                              
            "styleScore": self._to_str(info.get('styleScore')),
            "storyScore": self._to_str(info.get('storyScore')),
            "grammarScore": self._to_str(info.get('grammarScore')),
            "characterScore": self._to_str(info.get('characterScore')),
            "averageViews": None, "followers": None, "favorites": None, "pageViews": None,
            "voted": None, "freeChapter": None, "timeToFinish": None, "releaseRate": None,
            "numberOfReader": None, "totalViewsChapters": None, "totalWord": None, "averageWords": None,
            "userReading": None, "userPlanToRead": None, "userCompleted": None, "userPaused": None, "userDropped": None
        }
        self.story_info.update_one({'storyId': story_id, 'websiteId': website_id},
            {'$set': update_doc, '$setOnInsert': {"_id": info_id, "infoId": info_id}}, upsert=True)

    def _upsert_ranking(self, story_id, website_id, data):
        pass 

    def _sync_chapters_strict(self, story_id, chapters):
        if not chapters: return
        existing = list(self.chapters.find({'storyId': story_id}, {'webChapterId': 1}))
        existing_web_ids = {doc['webChapterId'] for doc in existing}
        new_chapters_meta = []
        new_contents = []

        for ch in chapters:
            web_id = ch.get('webChapterId')
            if web_id in existing_web_ids: continue
            
            chap_id = ch.get('chapterId') or self._generate_wn_id()
            meta = {
                "_id": chap_id, "chapterId": chap_id,
                "webChapterId": web_id, "storyId": story_id,
                "order": self._to_str(ch.get('order')),         
                "chapterName": ch.get('chapterName'),
                "chapterUrl": ch.get('chapterUrl'),
                "publishedTime": self._to_str(ch.get('publishedTime')), 
                "voted": self._to_str(ch.get('voted')), 
                "views": self._to_str(ch.get('views')), 
                "totalComments": self._to_str(ch.get('totalComments'))
            }
            new_chapters_meta.append(meta)
            
            # Content
            content_text = ch.get('content', '')
            # FIX: Nếu transform đã tạo contentId thì dùng, không thì tạo mới
            content_id = ch.get('contentId') or self._generate_wn_id()
            if content_text:
                new_contents.append({
                    "_id": content_id, "contentId": content_id,
                    "chapterId": chap_id, "content": content_text
                })
        
        if new_chapters_meta:
            self.chapters.insert_many(new_chapters_meta)
            logger.info(f"   📚 Đã thêm {len(new_chapters_meta)} chương mới.")
        if new_contents:
            self.chapter_contents.insert_many(new_contents)

    def _sync_reviews_strict(self, story_id, website_id, reviews):
        if not reviews: return
        existing = list(self.reviews.find({'storyId': story_id, 'websiteId': website_id}, {'webReviewId': 1, 'reviewId': 1}))
        existing_map = {r['webReviewId']: r['reviewId'] for r in existing}
        current_batch = set()
        bulk_reviews = []
        bulk_scores = []

        for rv in reviews:
            web_id = rv.get('webReviewId')
            if not web_id: continue
            current_batch.add(web_id)
            user_oid = self._ensure_user({'username': rv.get('user_name'), 'webUserId': rv.get('user_id'), 'userId': rv.get('userId')})
            
            is_update = web_id in existing_map
            review_id = existing_map[web_id] if is_update else (rv.get('reviewId') or self._generate_wn_id())
            score_id = rv.get('scoreId') or self._generate_wn_id()

            rv_doc = {
                "webReviewId": web_id, "title": rv.get('title'),
                "time": self._to_str(rv.get('time')), 
                "content": rv.get('content'), "userId": user_oid,
                "storyId": story_id, "websiteId": website_id,
                "scoreId": score_id, "isReviewSwap": False, "isDeleted": False
            }
            
            if is_update: bulk_reviews.append(UpdateOne({'_id': review_id}, {'$set': rv_doc}))
            else:
                rv_doc['_id'] = review_id; rv_doc['reviewId'] = review_id
                bulk_reviews.append(UpdateOne({'_id': review_id}, {'$set': rv_doc}, upsert=True))

            score_val = None
            if 'score' in rv:
                s = rv['score']
                score_val = s.get('overall') if isinstance(s, dict) else s
            
            score_doc = {
                "scoreId": score_id, "reviewId": review_id,
                "overallScore": self._to_str(score_val), 
                "styleScore": None, "storyScore": None, "grammarScore": None, "characterScore": None
            }
            bulk_scores.append(UpdateOne({'reviewId': review_id}, {'$set': score_doc, '$setOnInsert': {'_id': score_id}}, upsert=True))

        if bulk_reviews: self.reviews.bulk_write(bulk_reviews)
        if bulk_scores: self.scores.bulk_write(bulk_scores)
        ids_del = [rid for wid, rid in existing_map.items() if wid not in current_batch]
        if ids_del: self.reviews.update_many({'reviewId': {'$in': ids_del}}, {'$set': {'isDeleted': True}})

    def _sync_comments_strict(self, story_id, website_id, comments):
        if not comments: return
        existing = list(self.comments.find({'storyId': story_id, 'websiteId': website_id}, {'webCommentId': 1, 'commentId': 1}))
        existing_map = {c['webCommentId']: c['commentId'] for c in existing}
        current_batch = set()
        bulk_ops = []

        for cmt in comments:
            web_id = cmt.get('webCommentId') or cmt.get('comment_id')
            if not web_id: continue
            current_batch.add(web_id)
            user_oid = self._ensure_user({'username': cmt.get('user_name'), 'webUserId': cmt.get('user_id'), 'userId': cmt.get('userId')})
            
            # --- FIX CHAPTER ID ---
            # Ưu tiên 1: Lấy chapterId đã có sẵn từ transform (đây là cái bạn đang thiếu)
            chapter_id = cmt.get('chapterId')
            
            # Ưu tiên 2: Nếu không có, mới tìm theo webChapterId
            if not chapter_id and cmt.get('_temp_chapter_web_id'):
                found_ch = self.chapters.find_one({'storyId': story_id, 'webChapterId': cmt['_temp_chapter_web_id']})
                if found_ch: chapter_id = found_ch['chapterId']
            
            # Nếu là comment truyện (không thuộc chapter nào) thì chapter_id vẫn là None -> OK

            cmt_id = existing_map.get(web_id) or cmt.get('commentId') or self._generate_wn_id()

            # --- FIX CONTENT ---
            # Chấp nhận cả key 'commentText', 'content' hoặc 'body'
            text_val = cmt.get('commentText') or cmt.get('content') or cmt.get('body')

            doc = {
                "commentId": cmt_id,
                "webCommentId": web_id,
                "commentText": text_val, # Mapping vào commentText
                "time": self._to_str(cmt.get('time')), 
                "storyId": story_id,
                "chapterId": chapter_id, # Đã fix logic
                "userId": user_oid,
                "websiteId": website_id,
                "isDeleted": False,
                "isRoot": cmt.get('isRoot', True),
                "react": self._to_str(cmt.get('react') or cmt.get('likes')),
                "replyToUserId": cmt.get('replyToUserId'),
                "parentId": cmt.get('parentId')
            }
            
            bulk_ops.append(UpdateOne(
                {'webCommentId': web_id, 'websiteId': website_id},
                {'$set': doc, '$setOnInsert': {'_id': cmt_id}},
                upsert=True
            ))

        if bulk_ops: self.comments.bulk_write(bulk_ops)
        ids_del = [cid for wid, cid in existing_map.items() if wid not in current_batch]
        if ids_del:
            self.comments.update_many({'commentId': {'$in': ids_del}}, {'$set': {'isDeleted': True}})
            logger.info(f"   🗑️ Soft Deleted {len(ids_del)} comments.")