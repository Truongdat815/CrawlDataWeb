"""
Glossary handler - xử lý glossary scraping
"""
import time
import re
from src import config
from src.utils import safe_print, generate_id, convert_html_to_formatted_text


class GlossaryHandler:
    """Handler cho glossary scraping"""
    
    def __init__(self, page, mongo_handler):
        """
        Args:
            page: Playwright page object
            mongo_handler: MongoHandler instance
        """
        self.page = page
        self.mongo = mongo_handler
    
    def scrape_glossary(self, story_url, story_id):
        """
        Cào glossary từ trang story
        Args:
            story_url: URL của story
            story_id: ID của story (FK)
        Returns:
            List các glossary items đã lưu
        """
        try:
            safe_print("      📚 Đang lấy glossary từ trang story...")
            
            # Đảm bảo đang ở trang story
            current_url = self.page.url
            if story_url not in current_url:
                self.page.goto(story_url, timeout=config.TIMEOUT, wait_until="domcontentloaded")
                time.sleep(2)
            
            # Tìm container glossary
            glossary_container = self.page.locator(".fic_row.glossary").first
            if glossary_container.count() == 0:
                safe_print("      ℹ️ Không tìm thấy glossary trên trang này")
                return []
            
            # Click "Show All" nếu có để expand tất cả items
            try:
                show_all_btn = glossary_container.locator(".gloss_show").first
                if show_all_btn.count() > 0:
                    is_hidden = show_all_btn.get_attribute("ishidden")
                    if is_hidden == "0":  # Chưa expand
                        show_all_btn.click()
                        time.sleep(1)  # Đợi expand
            except:
                pass
            
            # Lấy tất cả categories
            categories = glossary_container.locator(".gloss_main").all()
            
            all_glossary_items = []
            
            for category_idx, category_elem in enumerate(categories):
                try:
                    # Lấy category name
                    category_name = ""
                    category_name_elem = category_elem.locator(".fic_gloss_item").first
                    if category_name_elem.count() > 0:
                        category_name = category_name_elem.inner_text().strip()
                    
                    if not category_name:
                        continue
                    
                    safe_print(f"        📂 Category: {category_name}")
                    
                    # Lấy tất cả items trong category này
                    # Mỗi item có: .fic_gloss-title và .fic_gloss-description
                    item_containers = category_elem.locator("div[style*='padding-bottom:12px']").all()
                    
                    for item_idx, item_container in enumerate(item_containers):
                        try:
                            # Lấy title
                            title = ""
                            title_elem = item_container.locator(".gloss_hover_title, .fic_gloss-title span.gloss_hover_title").first
                            if title_elem.count() > 0:
                                title = title_elem.inner_text().strip()
                            
                            if not title:
                                # Fallback: lấy từ .fic_gloss-title
                                title_elem = item_container.locator(".fic_gloss-title").first
                                if title_elem.count() > 0:
                                    # Lấy text nhưng bỏ qua icon
                                    title = title_elem.inner_text().strip()
                                    # Xóa các ký tự đặc biệt từ icon nếu có
                                    title = re.sub(r'[^\w\s\-\(\)]', '', title).strip()
                            
                            # Lấy description
                            description = ""
                            # Tìm description element (có thể có class như .fic_gloss-description.1_1, .fic_gloss-description.4_1, etc.)
                            description_elem = item_container.locator("div[class*='fic_gloss-description']").first
                            if description_elem.count() > 0:
                                # Lấy HTML content
                                html_content = description_elem.inner_html()
                                # Convert sang text có format
                                description = convert_html_to_formatted_text(html_content)
                            
                            if title:
                                glossary_id = generate_id()
                                
                                glossary_data = {
                                    "glossary_id": glossary_id,
                                    "storyId": story_id,
                                    "category": category_name,
                                    "title": title,
                                    "description": description,
                                    "order": item_idx + 1  # Thứ tự trong category
                                }
                                
                                # Lưu vào MongoDB
                                self.mongo.save_glossary(glossary_data)
                                all_glossary_items.append(glossary_data)
                                
                                safe_print(f"          ✅ {title} ({category_name})")
                        except Exception as e:
                            safe_print(f"          ⚠️ Lỗi khi parse glossary item: {e}")
                            continue
                    
                except Exception as e:
                    safe_print(f"        ⚠️ Lỗi khi parse category: {e}")
                    continue
            
            if all_glossary_items:
                safe_print(f"      ✅ Đã lấy được {len(all_glossary_items)} glossary items")
            else:
                safe_print(f"      ℹ️ Không tìm thấy glossary items nào")
            
            return all_glossary_items
            
        except Exception as e:
            safe_print(f"      ⚠️ Lỗi khi scrape glossary: {e}")
            return []

