import time
import os
from src.webnovel_scraper import WebnovelScraper

def get_links_test():
    print("🔗 WEBNOVEL LINK COLLECTOR (CHẾ ĐỘ TEST - LẤY ÍT LINK)")
    print("-" * 60)
    
    # Mặc định lấy 5 bộ để bạn có dư lựa chọn cho bài test 3 bộ
    TARGET_BOOKS = 5 
    
    url = input("Nhập Link Category (Ví dụ: https://www.webnovel.com/stories/fanfic): ").strip()
    if not url: return

    # Dùng Chrome thật để tránh bị chặn khi cuộn
    scraper = WebnovelScraper(headless=False, block_resources=False)
    scraper.start()
    
    try:
        print(f"\n🌐 Đang vào trang: {url}")
        scraper.page.goto(url, timeout=60000, wait_until='domcontentloaded')
        time.sleep(5) # Đợi load ban đầu

        # Click để focus
        try: scraper.page.mouse.click(500, 500)
        except: pass

        book_links = set()
        
        print(f"\n📜 Đang lấy link (Mục tiêu: {TARGET_BOOKS} truyện)...")
        
        # Cuộn vài lần là đủ
        for i in range(3):
            # Lấy link hiện tại
            elements = scraper.page.locator("a[href*='/book/']").all()
            for el in elements:
                try:
                    href = el.get_attribute("href")
                    if href and "/book/" in href:
                        if href.startswith("/"): href = "https://www.webnovel.com" + href
                        if "?" in href: href = href.split("?")[0]
                        if "webnovel.com/book/" in href:
                            book_links.add(href)
                except: pass
            
            print(f"   Đã tìm thấy: {len(book_links)} truyện.")
            
            if len(book_links) >= TARGET_BOOKS:
                break
                
            # Cuộn xuống
            scraper.page.keyboard.press("PageDown")
            time.sleep(1)
            scraper.page.keyboard.press("PageDown")
            time.sleep(2)

        # Lưu file
        if book_links:
            # Lấy đúng số lượng cần thiết
            final_links = list(book_links)[:TARGET_BOOKS]
            
            with open("books_queue.txt", "w", encoding="utf-8") as f:
                for link in final_links:
                    f.write(link + "\n")
            
            print(f"\n✅ Đã lưu {len(final_links)} link vào 'books_queue.txt'.")
            print("👉 Sẵn sàng cho bài test chạy Batch Runner!")
        else:
            print("❌ Không tìm thấy link nào.")

    except Exception as e:
        print(f"❌ Lỗi: {e}")
    finally:
        if scraper.browser: scraper.browser.close()
        if scraper.playwright: scraper.playwright.stop()

if __name__ == "__main__":
    get_links_test()