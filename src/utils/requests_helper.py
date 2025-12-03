"""
Requests Helper - Dùng requests với cookies từ Playwright để scrape content
Tránh dùng Playwright cho mỗi chapter → giảm detection
"""
import requests
from bs4 import BeautifulSoup
from src.utils import safe_print, convert_html_to_formatted_text

def get_session_from_context(context, user_agent=None):
    """
    Tạo requests session với cookies từ Playwright context
    Args:
        context: Playwright browser context
        user_agent: User agent (nếu None thì lấy từ context)
    Returns:
        requests.Session với cookies đã set
    """
    session = requests.Session()
    
    try:
        # Lấy cookies từ context
        cookies = context.cookies()
        
        # Convert Playwright cookies format sang requests format
        for cookie in cookies:
            domain = cookie.get('domain', '')
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            path = cookie.get('path', '/')
            
            if name and value:
                # Set cookie vào session (requests tự động xử lý domain)
                session.cookies.set(name, value, domain=domain, path=path)
    except Exception as e:
        safe_print(f"      ⚠️ Lỗi khi lấy cookies từ context: {e}")
    
    # Set headers
    if not user_agent:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Referer': 'https://www.scribblehub.com/',
    })
    
    return session

def scrape_chapter_with_requests(session, url):
    """
    Scrape chapter content bằng requests (không dùng Playwright)
    Args:
        session: requests.Session với cookies đã set
        url: URL của chapter
    Returns:
        dict với title, content, published_time hoặc None nếu lỗi
    """
    try:
        # Dùng requests để get HTML
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML với BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Lấy title
        title_elem = soup.select_one('h1')
        title = title_elem.get_text(strip=True) if title_elem else ""
        
        # Lấy content từ div.chp_raw (giữ đúng format như UI)
        content_elem = soup.select_one('#chp_raw, .chp_raw')
        if content_elem:
            html_content = str(content_elem)
            content = convert_html_to_formatted_text(html_content)
        else:
            # Fallback: Thử .chapter-inner
            content_elem = soup.select_one('.chapter-inner')
            if content_elem:
                html_content = str(content_elem)
                content = convert_html_to_formatted_text(html_content)
            else:
                content = ""
        
        # Lấy published_time
        published_time = ""
        time_elem = soup.select_one('time[datetime]')
        if time_elem:
            published_time = time_elem.get('datetime', '')
        
        return {
            'title': title,
            'content': content,
            'published_time': published_time
        }
        
    except Exception as e:
        safe_print(f"      ⚠️ Lỗi khi scrape chapter bằng requests: {e}")
        return None

