"""
ScribbleHub Scraper Engine - Main scraper class
"""
import os
import json
import time
import re
from src.handlers.base_handler import BaseHandler
from src.handlers.mongo_handler import MongoHandler
from src.handlers.story_handler import StoryHandler
from src.handlers.chapter_handler import ChapterHandler
from src.handlers.comment_handler import CommentHandler
from src.handlers.review_handler import ReviewHandler
from src.handlers.user_handler import UserHandler
from src.handlers.glossary_handler import GlossaryHandler
from src import config
from src.utils import safe_print, generate_id


class ScribbleHubScraper(BaseHandler):
    """Main scraper class cho ScribbleHub"""
    
    def __init__(self, max_workers=None):
        # Gọi __init__ của BaseHandler để khởi tạo browser attributes
        super().__init__()
        
        # Khởi tạo MongoDB handler
        self.mongo = MongoHandler()
        
        # Handlers sẽ được khởi tạo sau khi có page
        self.story_handler = None
        self.chapter_handler = None
        self.comment_handler = None
        self.review_handler = None
        self.user_handler = None
        self.glossary_handler = None

    def start(self):
        """Khởi động trình duyệt và khởi tạo handlers"""
        # Sử dụng method từ BaseHandler
        self.start_browser()
        
        # Khởi tạo handlers sau khi có page
        self.comment_handler = CommentHandler(self.page, self.mongo)
        self.review_handler = ReviewHandler(self.page, self.mongo)
        self.story_handler = StoryHandler(self.page, self.mongo)
        self.user_handler = UserHandler(self.page, self.mongo)
        self.glossary_handler = GlossaryHandler(self.page, self.mongo)
        # Truyền context vào ChapterHandler để dùng cho requests
        self.chapter_handler = ChapterHandler(self.mongo, self.comment_handler, self.context)

    def stop(self):
        """Đóng trình duyệt và MongoDB connection"""
        # Sử dụng method từ BaseHandler để đóng browser
        self.stop_browser()
        
        # Đóng MongoDB connection
        if self.mongo:
            self.mongo.close()

    def scrape_best_rated_stories(self, ranking_url, num_stories=10, start_from=0):
        """
        Cào các bộ truyện từ trang series-ranking
        Args:
            ranking_url: URL của trang ranking
            num_stories: Số lượng bộ truyện muốn cào
            start_from: Bắt đầu từ vị trí thứ mấy
        """
        try:
            safe_print(f"🔍 Đang lấy danh sách {num_stories} bộ truyện từ ranking...")
            safe_print(f"📄 Ranking URL: {ranking_url}")
            
            # Lấy danh sách URL từ ranking page
            story_urls = self.story_handler.get_story_urls_from_best_rated(ranking_url, num_stories, start_from)
            
            safe_print(f"📚 Tìm thấy {len(story_urls)} bộ truyện")
            
            # Cào từng bộ truyện
            for i, story_url in enumerate(story_urls, 1):
                safe_print(f"\n{'='*80}")
                safe_print(f"📖 [{i}/{len(story_urls)}] Đang cào: {story_url}")
                safe_print(f"{'='*80}")
                
                try:
                    self.scrape_story(story_url)
                except Exception as e:
                    safe_print(f"❌ Lỗi khi cào story {i}: {e}")
                    continue
                
                # Delay giữa các story (tăng lên để tránh bị chặn khi cào nhiều bộ truyện)
                if i < len(story_urls):
                    delay = getattr(config, 'SCRIBBLEHUB_DELAY_BETWEEN_REQUESTS', 8)
                    safe_print(f"\n⏳ Đợi {delay} giây trước khi cào bộ truyện tiếp theo...")
                    time.sleep(delay)
            
            safe_print(f"\n✅ Đã hoàn thành cào {len(story_urls)} bộ truyện!")
            
        except Exception as e:
            safe_print(f"❌ Lỗi khi cào best rated stories: {e}")
            import traceback
            safe_print(traceback.format_exc())

    def scrape_story(self, story_url):
        """
        Cào một bộ truyện cụ thể
        Args:
            story_url: URL của story (ví dụ: https://www.scribblehub.com/series/123456/story-name/)
        """
        try:
            # Extract web_story_id từ URL
            web_story_id = ""
            try:
                # Pattern: /series/123456/ hoặc /read/123456-
                match = re.search(r'/(?:series|read)/(\d+)', story_url)
                if match:
                    web_story_id = match.group(1)
            except:
                pass
            
            if not web_story_id:
                safe_print("⚠️ Không thể lấy web_story_id từ URL")
                return
            
            safe_print(f"📖 Web Story ID: {web_story_id}")
            
            # 1. Goto story page và xử lý Cloudflare
            safe_print("... Đang truy cập trang story...")
            try:
                # Thử với networkidle trước (nếu có thể)
                self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="networkidle")
            except Exception as e:
                # Nếu timeout, thử lại với load (chỉ đợi trang load xong, không đợi network idle)
                safe_print(f"⚠️ networkidle timeout, thử lại với load: {e}")
                try:
                    self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="load")
                except Exception as e2:
                    # Nếu vẫn timeout, thử với domcontentloaded (nhanh hơn)
                    safe_print(f"⚠️ load timeout, thử lại với domcontentloaded: {e2}")
                    self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Đợi Cloudflare challenge nếu có
            self.wait_for_cloudflare_challenge(self.page)
            
            # 2. Scrape story metadata (hoặc lấy từ DB nếu đã có)
            story_data, story_id, author_profile_url = self.story_handler.scrape_story_metadata(story_url, web_story_id)
            
            # QUAN TRỌNG: Chỉ cần story_id để tiếp tục scrape chapters
            # Không return sớm nếu story_data là None (có thể đã có trong DB)
            if not story_id:
                safe_print("⚠️ Không thể lấy story_id, không thể tiếp tục scrape chapters")
                return
            
            if not story_data:
                safe_print("ℹ️ Story đã có trong DB, bỏ qua metadata nhưng vẫn tiếp tục scrape chapters...")
                # Lấy story_data từ DB để có thể dùng sau này
                try:
                    existing_story = self.mongo.get_story_by_web_id(web_story_id)
                    if existing_story:
                        story_data = existing_story
                        safe_print(f"✅ Đã lấy story_data từ DB (story_id: {story_id})")
                except Exception as e:
                    safe_print(f"⚠️ Không thể lấy story_data từ DB: {e}")
            
            # 3. Scrape author profile nếu có URL
            if author_profile_url:
                try:
                    safe_print("... Đang cào author profile...")
                    user_id = self.user_handler.scrape_user_profile(author_profile_url)
                    if user_id:
                        # Cập nhật userId vào story_data (không dùng user_id nữa)
                        story_data["userId"] = user_id
                        # Xóa user_id nếu có
                        if "user_id" in story_data:
                            del story_data["user_id"]
                        self.mongo.save_story(story_data, None, None)  # Chưa có chapter 1 ở đây
                        safe_print(f"✅ Đã cập nhật userId: {user_id}")
                    else:
                        safe_print("⚠️ Không thể lấy author user_id")
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi cào author profile: {e}")

            # 3. Lấy danh sách link chương từ TẤT CẢ các trang phân trang
            safe_print("... Đang lấy danh sách chương từ tất cả các trang")
            chapter_info_list = self.story_handler.get_all_chapters_from_pagination(story_url)
            
            safe_print(f"--> Tổng cộng tìm thấy {len(chapter_info_list)} chương từ tất cả các trang.")

            # 3.4. Lưu chapter metadata vào MongoDB ngay khi lấy được từ table of contents
            # 📌 Collection: "chapters" trong MongoDB
            safe_print("... Đang lưu chapter metadata từ table of contents vào MongoDB...")
            safe_print(f"   📦 Collection: 'chapters'")
            saved_metadata_count = 0
            skipped_count = 0
            error_count = 0
            
            for index, chapter_info in enumerate(chapter_info_list, 1):
                web_chapter_id = chapter_info.get("webChapterId", "") or chapter_info.get("web_chapter_id", "")
                chapter_url = chapter_info.get("url", "")
                
                # Fallback: Nếu web_chapter_id rỗng, thử parse từ URL
                if not web_chapter_id and chapter_url:
                    try:
                        match = re.search(r'/chapter/(\d+)', chapter_url)
                        if match:
                            web_chapter_id = match.group(1)
                    except:
                        pass
                
                if not web_chapter_id:
                    safe_print(f"    ⚠️ Chapter {index}: Không lấy được webChapterId từ URL: {chapter_url}")
                    error_count += 1
                    continue
                
                # Kiểm tra đã có trong DB chưa
                if self.mongo.is_chapter_scraped(web_chapter_id):
                    skipped_count += 1
                    continue
                
                # Tạo chapter_id và lưu metadata (chưa có content)
                chapter_id = generate_id()
                order = chapter_info.get("order", "")
                if not order:
                    order = str(index)  # Fallback: dùng index làm order
                chapter_name = chapter_info.get("chapterName", "") or chapter_info.get("chapter_name", "")
                published_time = chapter_info.get("publishedTime", "") or chapter_info.get("published_time", "")
                
                chapter_metadata = {
                    "chapterId": chapter_id,
                    "webChapterId": web_chapter_id,
                    "order": order,
                    "chapterName": chapter_name,
                    "chapterUrl": chapter_url,
                    "publishedTime": published_time,
                    "storyId": story_id,
                    "voted": None,  # Sẽ được update khi scrape chapter content
                    "views": None,  # Sẽ được update khi scrape chapter content
                    "totalComments": "0"
                }
                
                try:
                    self.mongo.save_chapter(chapter_metadata)
                    saved_metadata_count += 1
                    if saved_metadata_count <= 5:  # Hiển thị 5 chapters đầu tiên
                        safe_print(f"    ✅ Đã lưu chapter {index}: {chapter_name[:50]}... (webChapterId: {web_chapter_id})")
                except Exception as e:
                    safe_print(f"    ❌ Lỗi khi lưu metadata cho chapter {index} (webChapterId: {web_chapter_id}): {e}")
                    error_count += 1
            
            # Tóm tắt kết quả
            safe_print(f"\n📊 Tóm tắt lưu chapter metadata:")
            safe_print(f"   ✅ Đã lưu: {saved_metadata_count} chapters")
            safe_print(f"   ⏭️  Đã có sẵn: {skipped_count} chapters")
            safe_print(f"   ❌ Lỗi: {error_count} chapters")
            safe_print(f"   📦 Collection: 'chapters' trong MongoDB")
            if saved_metadata_count > 0:
                safe_print(f"   💡 Kiểm tra MongoDB collection 'chapters' để xem danh sách chapters")

            # 3.5. Lấy reviews cho toàn bộ truyện (chỉ nếu có reviews)
            # Kiểm tra total_reviews từ story_info_data trước
            total_reviews_str = ""
            try:
                reviews_section = self.page.locator(".wi_novel_title.tags.pedit_body.nreview").first
                if reviews_section.count() > 0:
                    cnt_toc = reviews_section.locator(".cnt_toc").first
                    if cnt_toc.count() > 0:
                        total_reviews_str = cnt_toc.inner_text().strip()
            except:
                pass
            
            # Chỉ scrape reviews nếu có reviews (total_reviews > 0)
            reviews = []
            try:
                total_reviews_num = int(total_reviews_str) if total_reviews_str and total_reviews_str.isdigit() else 0
                if total_reviews_num > 0:
                    safe_print(f"... Đang lấy reviews cho toàn bộ truyện (có {total_reviews_num} reviews)")
                    reviews = self.review_handler.scrape_reviews(story_url, story_id)
                    safe_print(f"✅ Đã lấy được {len(reviews)} reviews")
                else:
                    safe_print(f"... Bỏ qua reviews (không có reviews: {total_reviews_str})")
            except Exception as e:
                safe_print(f"⚠️ Lỗi khi kiểm tra/scrape reviews: {e}")
                # Nếu lỗi, vẫn thử scrape (fallback)
                reviews = self.review_handler.scrape_reviews(story_url, story_id)
                if reviews:
                    safe_print(f"✅ Đã lấy được {len(reviews)} reviews (fallback)")

            # 3.6. Lấy glossary cho toàn bộ truyện (nếu có)
            glossary_items = []
            try:
                glossary_items = self.glossary_handler.scrape_glossary(story_url, story_id)
                if glossary_items:
                    safe_print(f"✅ Đã lấy được {len(glossary_items)} glossary items")
            except Exception as e:
                safe_print(f"⚠️ Lỗi khi scrape glossary: {e}")

            # 4. Cào các chương song song với ThreadPoolExecutor (GIỮ ĐÚNG THỨ TỰ)
            # Lọc ra các chapters chưa được cào content (để tránh cào trùng)
            chapters_to_scrape = []
            for index, chapter_info in enumerate(chapter_info_list):
                # Dùng webChapterId từ chapter_info (đã lấy từ table of contents)
                web_chapter_id = chapter_info.get("webChapterId", "") or chapter_info.get("web_chapter_id", "")
                
                # Fallback: Nếu chưa có web_chapter_id, parse từ URL
                if not web_chapter_id:
                    chap_url = chapter_info.get("url", "")
                    try:
                        # Tìm pattern /chapter/789012
                        match = re.search(r'/chapter/(\d+)', chap_url)
                        if match:
                            web_chapter_id = match.group(1)
                        else:
                            # Fallback: split theo /chapter/
                            url_parts = chap_url.split("/chapter/")
                            if len(url_parts) > 1:
                                web_chapter_id = url_parts[1].split("/")[0]
                    except Exception as e:
                        safe_print(f"    ⚠️ Lỗi khi lấy web_chapter_id từ URL: {e}")
                        web_chapter_id = ""
                
                # Kiểm tra chapter đã có content chưa (check xem đã có chapter_content chưa)
                # Nếu chỉ có metadata (chưa có content) thì vẫn cần scrape content
                if web_chapter_id:
                    # Tìm chapter trong DB
                    existing_chapter = None
                    if self.mongo.mongo_collection_chapters:
                        try:
                            existing_chapter = self.mongo.mongo_collection_chapters.find_one({"web_chapter_id": web_chapter_id})
                        except:
                            pass
                    
                    # Nếu đã có chapter và đã có content thì bỏ qua
                    if existing_chapter:
                        chapter_id = existing_chapter.get("chapter_id")
                        if chapter_id and self.mongo.mongo_collection_chapter_contents:
                            try:
                                content_doc = self.mongo.mongo_collection_chapter_contents.find_one({"chapter_id": chapter_id})
                                if content_doc and content_doc.get("content"):
                                    safe_print(f"    ⏭️  Bỏ qua chapter {index + 1} (đã có content trong DB): {web_chapter_id}")
                                    continue
                            except:
                                pass
                    
                    chapters_to_scrape.append((index, chapter_info))
                else:
                    chapters_to_scrape.append((index, chapter_info))
            
            # ✅ CÁCH TỐI ƯU: Dùng browser chính (đã vượt Cloudflare) thay vì requests hoặc tạo browser mới
            # → Không bị 403 Forbidden (vì dùng browser đã verify)
            # → Không bị lỗi Playwright Sync API (vì không tạo browser mới)
            # → Ổn định nhất, reliable nhất
            
            safe_print(f"🚀 Bắt đầu cào {len(chapters_to_scrape)}/{len(chapter_info_list)} chương bằng Browser Chính (Sequential)...")
            safe_print("   ✅ Dùng browser chính → không bị 403 Forbidden")
            safe_print("   ✅ Không tạo browser mới → không bị lỗi Playwright Sync API")
            safe_print("   ✅ Scrape tuần tự → tránh bị flag bot")
            
            chapter_results = [None] * len(chapter_info_list)
            completed = 0
            
            for index, chapter_info in chapters_to_scrape:
                order = chapter_info.get("order", "")
                if not order:
                    order = str(index + 1)
                chap_url = chapter_info["url"]
                published_time_from_table = chapter_info.get("publishedTime", "") or chapter_info.get("published_time", "")
                chapter_name_from_table = chapter_info.get("chapterName", "") or chapter_info.get("chapter_name", "")
                
                try:
                    # ✅ GỌI HÀM MỚI, TRUYỀN self.page VÀO (browser chính đã mở)
                    chapter_data = self.chapter_handler.scrape_single_chapter_using_browser(
                        self.page,  # <--- QUAN TRỌNG: Dùng lại page đã mở (đã vượt Cloudflare)
                        chap_url, 
                        index, 
                        story_id, 
                        order, 
                        published_time_from_table,
                        chapter_name_from_table
                    )
                    
                    chapter_results[index] = chapter_data
                    if chapter_data:
                        completed += 1
                        status = "✅"
                    else:
                        status = "⚠️"
                    safe_print(f"    {status} Hoàn thành chương {index + 1}/{len(chapter_info_list)} (đã xong {completed}/{len(chapters_to_scrape)})")
                    
                    # Delay nhẹ giữa các chương để không bị ban
                    import random
                    time.sleep(random.uniform(1.0, 2.0))
                    
                except Exception as e:
                    safe_print(f"    ❌ Lỗi khi cào chương {index + 1}: {e}")
                    chapter_results[index] = None
            
            safe_print(f"✅ Đã hoàn thành cào {completed}/{len(chapters_to_scrape)} chương!")
            
            # SAU KHI TẤT CẢ XONG: Đếm số chapters đã cào thành công
            safe_print(f"📝 Đang kiểm tra kết quả...")
            successful_chapters = sum(1 for ch in chapter_results if ch is not None)
            safe_print(f"✅ Đã hoàn thành {successful_chapters}/{len(chapter_info_list)} chương (theo đúng thứ tự)")
            
            # 5. Cập nhật story trong MongoDB (chapters và reviews đã được lưu vào collections riêng)
            # Nếu story_data chưa có, lấy từ DB
            if not story_data and web_story_id:
                try:
                    story_data = self.mongo.get_story_by_web_id(web_story_id)
                    if story_data:
                        safe_print(f"✅ Đã lấy story_data từ DB để lưu JSON")
                except Exception as e:
                    safe_print(f"⚠️ Không thể lấy story_data từ DB: {e}")
            
            # ✅ Lấy chapter 1 content và URL để check duplicate
            chapter_1_content = None
            chapter_1_url = None
            
            if chapter_info_list and len(chapter_info_list) > 0:
                # Tìm chapter 1 (order = 1)
                chapter_1_info = None
                for ch in chapter_info_list:
                    if str(ch.get("order", "")) == "1":
                        chapter_1_info = ch
                        break
                
                if chapter_1_info:
                    chapter_1_url = chapter_1_info.get("url", "")
                    
                    # Scrape chapter 1 content để check duplicate (chỉ nếu chưa có trong DB)
                    if chapter_1_url:
                        try:
                            # Kiểm tra xem chapter 1 đã có content trong DB chưa
                            web_chapter_1_id = chapter_1_info.get("web_chapter_id", "")
                            if web_chapter_1_id:
                                existing_chapter = self.mongo.get_chapter_by_web_id(web_chapter_1_id)
                                if existing_chapter:
                                    chapter_1_id = existing_chapter.get("chapter_id")
                                    if chapter_1_id:
                                        chapter_1_content = self.mongo.get_chapter_1_content(story_id)
                            
                            # Nếu chưa có trong DB, scrape nhanh bằng requests
                            if not chapter_1_content:
                                from src.utils.requests_helper import get_session_from_context, scrape_chapter_with_requests
                                
                                if self.context:
                                    session = get_session_from_context(self.context)
                                    if session:
                                        safe_print("        🔍 Đang scrape chapter 1 để check duplicate...")
                                        chapter_data = scrape_chapter_with_requests(session, chapter_1_url)
                                        if chapter_data:
                                            chapter_1_content = chapter_data.get("content", "")
                                            if chapter_1_content:
                                                safe_print("        ✅ Đã lấy chapter 1 content để check duplicate")
                        except Exception as e:
                            safe_print(f"        ⚠️ Không thể scrape chapter 1 để check duplicate: {e}")
            
            if story_data:
                self.mongo.save_story(story_data, chapter_1_content, chapter_1_url)
                
                # 6. Lưu JSON backup vào data/json/ (lưu cả MongoDB và JSON file)
                try:
                    # Lấy story_info từ MongoDB
                    story_info_data = None
                    if self.mongo.mongo_collection_story_info and story_id:
                        story_info_data = self.mongo.mongo_collection_story_info.find_one({"story_id": story_id})
                    
                    self.save_story_to_json(story_id, story_data, story_info_data)
                except Exception as e:
                    safe_print(f"⚠️ Lỗi khi lưu JSON backup: {e}")
            else:
                safe_print("⚠️ Không có story_data để lưu, nhưng đã scrape chapters thành công")
        except Exception as e:
            safe_print(f"❌ Lỗi khi scrape story: {e}")
            import traceback
            safe_print(traceback.format_exc())
    
    def _remove_mongo_id(self, obj):
        """Helper function để loại bỏ _id từ MongoDB document một cách an toàn"""
        try:
            if isinstance(obj, dict):
                # Copy dict để không ảnh hưởng original
                result = {}
                for key, value in obj.items():
                    if key == "_id":
                        continue  # Bỏ qua _id
                    # Xử lý ObjectId và các kiểu không serialize được
                    if hasattr(value, '__class__') and 'ObjectId' in str(type(value)):
                        continue  # Bỏ qua ObjectId
                    result[key] = self._remove_mongo_id(value)
                return result
            elif isinstance(obj, list):
                return [self._remove_mongo_id(item) for item in obj]
            else:
                # Xử lý ObjectId và các kiểu không serialize được
                if hasattr(obj, '__class__') and 'ObjectId' in str(type(obj)):
                    return None  # Trả về None thay vì ObjectId
                return obj
        except Exception as e:
            # Nếu có lỗi, trả về string representation
            try:
                return str(obj)
            except:
                return None
    
    def _to_number(self, value):
        """Convert string number to number, return None if empty/invalid"""
        if value is None or value == "":
            return None
        try:
            if isinstance(value, (int, float)):
                return value
            # Remove commas and convert
            cleaned = str(value).replace(",", "").strip()
            if not cleaned:
                return None
            # Try int first, then float
            if "." in cleaned:
                return float(cleaned)
            return int(cleaned)
        except:
            return None
    
    def _to_date(self, value):
        """Convert string date to date format, return None if empty/invalid"""
        if value is None or value == "":
            return None
        # Return as-is for now (can be parsed later if needed)
        return value
    
    def _map_story_to_schema(self, story_data_clean, story_info_data_clean):
        """
        Map story data và story_info data theo schema mới (camelCase)
        Returns: dict với tất cả fields theo schema, null cho fields không có
        """
        # Schema fields cho stories (camelCase)
        stories_schema = {
            "storyId": story_data_clean.get("story_id"),
            "webStoryId": story_data_clean.get("web_story_id", ""),
            "storyName": story_data_clean.get("story_name", ""),
            "storyUrl": story_data_clean.get("story_url", ""),
            "coverImage": story_data_clean.get("cover_image", ""),
            "category": story_data_clean.get("category", ""),
            "status": story_data_clean.get("status", ""),
            "genres": story_data_clean.get("genres", []),
            "tags": story_data_clean.get("tags", []),
            "description": story_data_clean.get("description", ""),
            "userId": story_data_clean.get("user_id"),
            "totalChapters": self._to_number(story_data_clean.get("total_chapters", ""))
        }
        
        # Schema fields cho storyInfo (camelCase, number types)
        story_info_schema = {
            "infoId": story_info_data_clean.get("info_id"),
            "storyId": story_data_clean.get("story_id"),
            "websiteId": story_info_data_clean.get("website_id") or story_data_clean.get("website_id"),
            "totalViews": self._to_number(story_info_data_clean.get("total_views", "")),
            "averageViews": self._to_number(story_info_data_clean.get("average_views", "")),
            "followers": self._to_number(story_info_data_clean.get("followers", "")),
            "favorites": self._to_number(story_info_data_clean.get("favorites", "")),
            "pageViews": self._to_number(story_info_data_clean.get("page_views", "")),
            "overallScore": self._to_number(story_info_data_clean.get("overall_score", "")),
            "styleScore": self._to_number(story_info_data_clean.get("style_score")),  # ScribbleHub không có, để null
            "storyScore": self._to_number(story_info_data_clean.get("story_score")),  # ScribbleHub không có, để null
            "grammarScore": self._to_number(story_info_data_clean.get("grammar_score")),  # ScribbleHub không có, để null
            "characterScore": self._to_number(story_info_data_clean.get("character_score")),  # ScribbleHub không có, để null
            "voted": self._to_number(story_info_data_clean.get("voted", "")),
            "freeChapter": self._to_number(story_info_data_clean.get("freeChapter", "")),
            "timeToFinish": story_info_data_clean.get("timeToFinish", story_info_data_clean.get("time", "")),  # Ưu tiên timeToFinish, fallback cho data cũ
            "releaseRate": self._to_number(story_info_data_clean.get("release_rate", "")),
            "numberOfReader": self._to_number(story_info_data_clean.get("number_of_reader", "")),
            "ratingTotal": self._to_number(story_info_data_clean.get("rating_total", "")),
            "totalViewsChapters": self._to_number(story_info_data_clean.get("total_views_chapters", "")),
            "totalWord": self._to_number(story_info_data_clean.get("total_word", "")),
            "averageWords": self._to_number(story_info_data_clean.get("average_words", "")),
            "lastUpdated": self._to_date(story_info_data_clean.get("last_updated", "")),
            "totalReviews": self._to_number(story_info_data_clean.get("total_reviews", "")),
            "userReading": self._to_number(story_info_data_clean.get("user_reading", "")),
            "userPlanToRead": self._to_number(story_info_data_clean.get("user_plan_to_read", "")),
            "userCompleted": self._to_number(story_info_data_clean.get("user_completed", "")),
            "userPaused": self._to_number(story_info_data_clean.get("user_paused", "")),
            "userDropped": self._to_number(story_info_data_clean.get("user_dropped", ""))
        }
        
        return stories_schema, story_info_schema

    def _map_chapter_to_schema(self, chapter_clean):
        """Map chapter data theo schema mới (camelCase)"""
        return {
            "chapterId": chapter_clean.get("chapter_id"),
            "webChapterId": chapter_clean.get("web_chapter_id", ""),
            "storyId": chapter_clean.get("story_id"),
            "order": self._to_number(chapter_clean.get("order", "")),
            "chapterName": chapter_clean.get("chapter_name", ""),
            "chapterUrl": chapter_clean.get("chapter_url", ""),
            "publishedTime": self._to_date(chapter_clean.get("published_time", "")),
            "voted": self._to_number(chapter_clean.get("voted", "")),
            "views": self._to_number(chapter_clean.get("views", "")),
            "totalComments": self._to_number(chapter_clean.get("total_comments", ""))
        }

    def _map_chapter_content_to_schema(self, content_clean):
        """Map chapter content theo schema mới (camelCase)"""
        return {
            "contentId": content_clean.get("contentId", content_clean.get("id", content_clean.get("content_id"))),  # Ưu tiên contentId, fallback cho data cũ
            "chapterId": content_clean.get("chapterId", content_clean.get("chapter_id")),
            "content": content_clean.get("content", "")
        }

    def _map_comment_to_schema(self, comment_clean):
        """Map comment data theo schema mới (camelCase)"""
        return {
            "commentId": comment_clean.get("comment_id"),
            "webCommentId": comment_clean.get("web_comment_id", ""),
            "chapterId": comment_clean.get("chapter_id"),
            "userId": comment_clean.get("user_id"),
            "commentText": comment_clean.get("comment_text", ""),
            "time": self._to_date(comment_clean.get("time", "")),
            "replyToUserId": comment_clean.get("reply_to_user_id"),
            "parentId": comment_clean.get("parent_id"),
            "isRoot": comment_clean.get("is_root", False),
            "react": self._to_number(comment_clean.get("react", "")),
            "websiteId": comment_clean.get("website_id")
        }

    def _map_review_to_schema(self, review_clean):
        """Map review data theo schema mới (camelCase)"""
        return {
            "reviewId": review_clean.get("reviewId", review_clean.get("review_id")),
            "webReviewId": review_clean.get("webReviewId", review_clean.get("web_review_id", "")),
            "storyId": review_clean.get("storyId", review_clean.get("story_id")),
            "chapterId": review_clean.get("chapterId", review_clean.get("chapter_id")),
            "userId": review_clean.get("userId", review_clean.get("user_id")),
            "title": review_clean.get("title", ""),
            "content": review_clean.get("content", ""),
            "time": review_clean.get("time", ""),  # Giữ nguyên format từ DB
            "isReviewSwap": review_clean.get("isReviewSwap", review_clean.get("is_review_swap", False)),
            "scoreId": review_clean.get("scoreId", review_clean.get("score_id")),
            "websiteId": review_clean.get("websiteId", review_clean.get("website_id")),
            "isDeleted": review_clean.get("isDeleted", review_clean.get("is_deleted", False))
        }

    def _map_user_to_schema(self, user_clean):
        """Map user data theo schema mới (camelCase)"""
        return {
            "userId": user_clean.get("userId", user_clean.get("user_id")),
            "webUserId": user_clean.get("webUserId", user_clean.get("web_user_id", "")),
            "username": user_clean.get("username", ""),
            "userUrl": user_clean.get("userUrl", user_clean.get("user_url", "")),
            "createdDate": user_clean.get("createdDate", user_clean.get("created_date", "")),
            "gender": user_clean.get("gender", ""),
            "location": user_clean.get("location", ""),
            "followers": user_clean.get("followers", ""),
            "following": user_clean.get("following", ""),
            "comments": user_clean.get("comments", ""),
            "bio": user_clean.get("bio", ""),
            "favorites": user_clean.get("favorites", ""),
            "ratings": user_clean.get("ratings", ""),
            "reviews": user_clean.get("reviews", ""),
            "numberOfStories": user_clean.get("numberOfStories", user_clean.get("number_of_stories", user_clean.get("series", ""))),
            "totalWords": user_clean.get("totalWords", user_clean.get("total_words", "")),
            "totalReviewsReceived": user_clean.get("totalReviewsReceived", user_clean.get("total_reviews_received", user_clean.get("reviews_received", ""))),
            "totalRatingsReceived": user_clean.get("totalRatingsReceived", user_clean.get("total_ratings_received", user_clean.get("ratings", ""))),
            "totalFavoritesReceived": user_clean.get("totalFavoritesReceived", user_clean.get("total_favorites_received", user_clean.get("favorites", "")))
        }

    def _map_ranking_to_schema(self, ranking_clean):
        """Map ranking data theo schema mới (camelCase)"""
        return {
            "rankId": ranking_clean.get("rank_id"),
            "rankName": ranking_clean.get("rank_name", ""),
            "rankNumber": self._to_number(ranking_clean.get("rank_number", "")),
            "websiteId": ranking_clean.get("website_id"),
            "storyId": ranking_clean.get("story_id")
        }

    def _map_website_to_schema(self, website_clean):
        """Map website data theo schema mới (camelCase)"""
        return {
            "websiteId": website_clean.get("website_id"),
            "websiteName": website_clean.get("website_name", "")
        }

    def _map_score_to_schema(self, score_clean):
        """Map score data theo schema mới (camelCase)"""
        return {
            "scoreId": score_clean.get("scoreId", score_clean.get("score_id")),
            "overallScore": score_clean.get("overallScore", score_clean.get("overall_score", "")),
            "styleScore": score_clean.get("styleScore", score_clean.get("style_score")),  # ScribbleHub không có, để null
            "storyScore": score_clean.get("storyScore", score_clean.get("story_score")),  # ScribbleHub không có, để null
            "grammarScore": score_clean.get("grammarScore", score_clean.get("grammar_score")),  # ScribbleHub không có, để null
            "characterScore": score_clean.get("characterScore", score_clean.get("character_score")),  # ScribbleHub không có, để null
            "reviewId": score_clean.get("reviewId", score_clean.get("review_id"))  # Link đến review
        }

    def save_story_to_json(self, story_id, story_data, story_info_data):
        """
        Lưu toàn bộ dữ liệu story vào file JSON trong data/json/ (backup local)
        Cấu trúc JSON theo schema mới (camelCase): stories, storyInfo, chapters, chapterContents, comments, reviews, rankings, users, websites, scores
        Args:
            story_id: ID của story
            story_data: Dict chứa story data
            story_info_data: Dict chứa story info data (có thể None)
        """
        try:
            if not story_data:
                safe_print("⚠️ Không có story_data để lưu JSON")
                return
            
            web_story_id = story_data.get("web_story_id", "")
            story_name = story_data.get("story_name", "Unknown")
            
            # Tạo tên file an toàn (loại bỏ ký tự đặc biệt)
            safe_filename = "".join(c for c in story_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_filename = safe_filename.replace(' ', '_')
            json_filename = f"{web_story_id}_{safe_filename}.json"
            json_path = os.path.join(config.JSON_DIR, json_filename)
            
            # Loại bỏ _id từ story_data và story_info_data
            story_data_clean = self._remove_mongo_id(story_data)
            story_info_data_clean = self._remove_mongo_id(story_info_data) if story_info_data else {}
            
            # Map theo schema tổng
            stories_mapped, story_info_mapped = self._map_story_to_schema(story_data_clean, story_info_data_clean)
            
            # Khởi tạo cấu trúc JSON theo schema mới (camelCase)
            json_data = {
                "stories": stories_mapped,
                "storyInfo": story_info_mapped,  # camelCase
                "chapters": [],  # Array of chapter metadata
                "chapterContents": [],  # camelCase
                "comments": [],  # Array of comments
                "reviews": [],  # Array of reviews
                "rankings": [],  # Array of rankings
                "users": [],  # Array of users
                "websites": {},  # Website object
                "scores": {}  # Scores object (tách riêng)
            }
            
            # Lấy chapters từ MongoDB (chỉ metadata, không có content/comments)
            if self.mongo.mongo_collection_chapters and story_id:
                try:
                    safe_print(f"      🔍 Đang query chapters từ MongoDB với story_id: {story_id}")
                    chapters = list(self.mongo.mongo_collection_chapters.find({"story_id": story_id}))
                    safe_print(f"      📚 Tìm thấy {len(chapters)} chapters trong MongoDB")
                    
                    if len(chapters) == 0:
                        safe_print(f"      ⚠️ Không tìm thấy chapters nào với story_id: {story_id}")
                        # Thử query bằng web_story_id
                        if web_story_id:
                            safe_print(f"      🔍 Thử query bằng web_story_id: {web_story_id}")
                            story_doc = self.mongo.mongo_collection_stories.find_one({"web_story_id": web_story_id})
                            if story_doc:
                                story_id_from_db = story_doc.get("story_id")
                                if story_id_from_db:
                                    safe_print(f"      🔍 Tìm thấy story_id từ DB: {story_id_from_db}")
                                    chapters = list(self.mongo.mongo_collection_chapters.find({"story_id": story_id_from_db}))
                                    safe_print(f"      📚 Tìm thấy {len(chapters)} chapters với story_id từ DB")
                                    story_id = story_id_from_db  # Update story_id để dùng cho reviews và glossary
                    
                    # Lấy chapterContents riêng
                    chapter_contents_list = []
                    all_comments_list = []
                    
                    for chapter in chapters:
                        chapter_clean = self._remove_mongo_id(chapter)
                        chapter_id = chapter_clean.get("chapter_id")
                        
                        # Map chapter theo schema
                        chapter_mapped = self._map_chapter_to_schema(chapter_clean)
                        json_data["chapters"].append(chapter_mapped)
                        
                        # Lấy content riêng vào chapter_contents
                        if chapter_id and self.mongo.mongo_collection_chapter_contents:
                            try:
                                content_doc = self.mongo.mongo_collection_chapter_contents.find_one({"chapter_id": chapter_id})
                                if content_doc:
                                    content_clean = self._remove_mongo_id(content_doc)
                                    # Map field names theo schema mới
                                    chapter_content_mapped = self._map_chapter_content_to_schema(content_clean)
                                    chapter_contents_list.append(chapter_content_mapped)
                            except Exception as e:
                                safe_print(f"        ⚠️ Lỗi khi lấy content cho chapter {chapter_id}: {e}")
                        
                        # Lấy comments riêng (tất cả comments ở root level)
                        if chapter_id and self.mongo.mongo_collection_comments:
                            try:
                                comments = list(self.mongo.mongo_collection_comments.find({"chapter_id": chapter_id}))
                                for comment in comments:
                                    comment_clean = self._remove_mongo_id(comment)
                                    comment_mapped = self._map_comment_to_schema(comment_clean)
                                    all_comments_list.append(comment_mapped)
                            except Exception as e:
                                safe_print(f"        ⚠️ Lỗi khi lấy comments cho chapter {chapter_id}: {e}")
                    
                    json_data["chapterContents"] = chapter_contents_list
                    json_data["comments"] = all_comments_list
                    safe_print(f"      📄 Tìm thấy {len(chapter_contents_list)} chapter contents")
                    safe_print(f"      💬 Tìm thấy {len(all_comments_list)} comments")
                    
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy chapters từ MongoDB: {e}")
            
            # Lấy reviews từ MongoDB
            if self.mongo.mongo_collection_reviews and story_id:
                try:
                    reviews = list(self.mongo.mongo_collection_reviews.find({"storyId": story_id}))
                    safe_print(f"      📝 Tìm thấy {len(reviews)} reviews trong MongoDB")
                    json_data["reviews"] = [self._map_review_to_schema(self._remove_mongo_id(r)) for r in reviews]
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy reviews từ MongoDB: {e}")
            
            # Lấy rankings từ MongoDB
            if self.mongo.mongo_collection_rankings and story_id:
                try:
                    rankings = list(self.mongo.mongo_collection_rankings.find({"story_id": story_id}))
                    safe_print(f"      🏆 Tìm thấy {len(rankings)} rankings trong MongoDB")
                    json_data["rankings"] = [self._map_ranking_to_schema(self._remove_mongo_id(r)) for r in rankings]
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy rankings từ MongoDB: {e}")
            
            # Lấy scores từ MongoDB (thông qua reviews của story)
            # Scores được link đến reviews, reviews được link đến story
            if self.mongo.mongo_collection_scores and story_id:
                try:
                    # Lấy tất cả reviews của story
                    reviews = []
                    if self.mongo.mongo_collection_reviews:
                        reviews = list(self.mongo.mongo_collection_reviews.find({"storyId": story_id}))
                    
                    # Lấy tất cả scoreIds từ reviews
                    score_ids = [r.get("scoreId") for r in reviews if r.get("scoreId")]
                    
                    # Lấy tất cả scores từ scoreIds
                    scores_list = []
                    if score_ids:
                        scores = list(self.mongo.mongo_collection_scores.find({"scoreId": {"$in": score_ids}}))
                        scores_list = [self._map_score_to_schema(self._remove_mongo_id(s)) for s in scores]
                    
                    json_data["scores"] = scores_list
                    if scores_list:
                        safe_print(f"      ⭐ Tìm thấy {len(scores_list)} scores trong MongoDB")
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy scores từ MongoDB: {e}")
            
            # Lấy users từ MongoDB (tất cả users liên quan đến story)
            if self.mongo.mongo_collection_users:
                try:
                    # Lấy user của author
                    user_id = story_data_clean.get("user_id")
                    users_list = []
                    if user_id:
                        user_doc = self.mongo.mongo_collection_users.find_one({"user_id": user_id})
                        if user_doc:
                            users_list.append(self._map_user_to_schema(self._remove_mongo_id(user_doc)))
                    
                    # Lấy users từ comments
                    comment_user_ids = set()
                    for comment in json_data["comments"]:
                        comment_user_id = comment.get("user_id")
                        if comment_user_id:
                            comment_user_ids.add(comment_user_id)
                    
                    # Lấy users từ reviews
                    review_user_ids = set()
                    for review in json_data["reviews"]:
                        review_user_id = review.get("user_id")
                        if review_user_id:
                            review_user_ids.add(review_user_id)
                    
                    # Lấy tất cả unique user IDs
                    all_user_ids = {user_id} if user_id else set()
                    all_user_ids.update(comment_user_ids)
                    all_user_ids.update(review_user_ids)
                    
                    # Query tất cả users
                    for uid in all_user_ids:
                        if uid:
                            user_doc = self.mongo.mongo_collection_users.find_one({"user_id": uid})
                            if user_doc:
                                user_clean = self._map_user_to_schema(self._remove_mongo_id(user_doc))
                                # Chỉ thêm nếu chưa có (tránh duplicate)
                                if not any(u.get("user_id") == uid for u in users_list):
                                    users_list.append(user_clean)
                    
                    json_data["users"] = users_list
                    safe_print(f"      👥 Tìm thấy {len(users_list)} users trong MongoDB")
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy users từ MongoDB: {e}")
            
            # Lấy website từ MongoDB
            if self.mongo.mongo_collection_websites:
                try:
                    website_id = story_data_clean.get("website_id") or story_info_data_clean.get("website_id")
                    if website_id:
                        website_doc = self.mongo.mongo_collection_websites.find_one({"website_id": website_id})
                        if website_doc:
                            website_clean = self._remove_mongo_id(website_doc)
                            json_data["websites"] = self._map_website_to_schema(website_clean)
                            safe_print(f"      🌐 Tìm thấy website trong MongoDB")
                except Exception as e:
                    safe_print(f"      ⚠️ Lỗi khi lấy website từ MongoDB: {e}")
            
            # Lưu vào file JSON với error handling tốt hơn
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)
                
                safe_print(f"💾 Đã lưu JSON backup vào: {json_path}")
                safe_print(f"   - Stories: ✅")
                safe_print(f"   - Story Info: ✅")
                safe_print(f"   - Chapters: {len(json_data['chapters'])}")
                safe_print(f"   - Chapter Contents: {len(json_data['chapterContents'])}")
                safe_print(f"   - Comments: {len(json_data['comments'])}")
                safe_print(f"   - Reviews: {len(json_data['reviews'])}")
                safe_print(f"   - Rankings: {len(json_data['rankings'])}")
                safe_print(f"   - Users: {len(json_data['users'])}")
                safe_print(f"   - Websites: {'✅' if json_data['websites'] else '❌'}")
                safe_print(f"   - Scores: {'✅' if json_data['scores'] else '❌'}")
            except TypeError as e:
                # Nếu có lỗi serialize, thử lại với default=str
                safe_print(f"      ⚠️ Lỗi serialize, thử lại với default=str...")
                try:
                    # Loại bỏ tất cả ObjectId và các kiểu không serialize được
                    json_data_clean = json.loads(json.dumps(json_data, default=str))
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(json_data_clean, f, ensure_ascii=False, indent=2)
                    safe_print(f"💾 Đã lưu JSON backup (sau khi clean): {json_path}")
                except Exception as e2:
                    safe_print(f"      ❌ Lỗi khi lưu JSON (sau khi clean): {e2}")
                    # Lưu ít nhất story
                    try:
                        minimal_data = {
                            "stories": stories_mapped,
                            "storyInfo": story_info_mapped,
                            "chapters": [],
                            "chapterContents": [],
                            "comments": [],
                            "reviews": [],
                            "rankings": [],
                            "users": [],
                            "websites": {},
                            "scores": {},
                            "error": f"Lỗi khi serialize đầy đủ: {str(e2)}"
                        }
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(minimal_data, f, ensure_ascii=False, indent=2)
                        safe_print(f"💾 Đã lưu JSON tối thiểu (chỉ story + story_info): {json_path}")
                    except Exception as e3:
                        safe_print(f"      ❌ Không thể lưu JSON: {e3}")
            
        except Exception as e:
            safe_print(f"⚠️ Lỗi khi lưu JSON: {e}")
            import traceback
            safe_print(traceback.format_exc())
