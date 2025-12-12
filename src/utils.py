import io
from urllib.parse import urlparse
import os
import time
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .config import (
    IMAGES_DIR,
    MAX_RETRIES,
    RETRY_BACKOFF,
    REQUEST_TIMEOUT,
    SKIP_IMAGE_DOWNLOAD,
    IMAGE_UPLOAD_URL,
    IMAGE_UPLOAD_API_KEY,
    IMAGE_UPLOAD_TIMEOUT,
)

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    HAS_PIL = False

def clean_text(text):
    """Hàm làm sạch văn bản, xóa khoảng trắng thừa"""
    if not text:
        return ""
    return text.strip()

def download_image(image_url, fiction_id):
    """
    Tạm thời: Lưu ảnh local thay vì upload lên API.
    
    Args:
        image_url: URL ảnh từ Wattpad
        fiction_id: ID của story/fiction
    
    Returns:
        str: Đường dẫn file ảnh local hoặc None nếu fail
    """
    if not image_url or "http" not in image_url:
        return None

    if SKIP_IMAGE_DOWNLOAD:
        print(f"   ⚠️ SKIP_IMAGE_DOWNLOAD enabled — not downloading image: {image_url}")
        return None

    # Ensure images dir exists
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR, exist_ok=True)

    # Create a requests session with retry logic
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    image_filename = f"{fiction_id}_cover.jpg"
    image_path = os.path.join(IMAGES_DIR, image_filename)

    attempt = 0
    while attempt <= MAX_RETRIES:
        attempt += 1
        try:
            print(f"   📥 Downloading image from: {image_url} (attempt {attempt})")
            resp = session.get(image_url, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                print(f"   ⚠️ Failed to download image (status={resp.status_code})")
                # If non-retriable status code and we've exhausted retries, break
                if attempt > MAX_RETRIES:
                    return None
                time.sleep(RETRY_BACKOFF * attempt)
                continue

            raw_bytes = resp.content

            # Convert to JPEG bytes when possible to ensure server accepts JPG
            jpeg_bytes = None
            if HAS_PIL:
                try:
                    # narrow type for static checkers: ensure Image is not None
                    assert Image is not None
                    im = Image.open(io.BytesIO(raw_bytes))
                    if im.mode in ("RGBA", "LA"):
                        background = Image.new("RGB", im.size, (255, 255, 255))
                        background.paste(im, mask=im.split()[-1])
                        im = background
                    else:
                        im = im.convert("RGB")
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG", quality=85)
                    jpeg_bytes = buf.getvalue()
                except Exception as e:
                    print(f"   ⚠️ Pillow conversion failed, falling back to raw bytes: {e}")
                    jpeg_bytes = None
            else:
                print("   ⚠️ Pillow not installed — saving raw bytes as .jpg (may be invalid)")

            image_data = jpeg_bytes if jpeg_bytes is not None else raw_bytes

            # Save locally first (always attempt to save as JPG)
            try:
                with open(image_path, 'wb') as f:
                    f.write(image_data)
                print(f"   💾 Saved local cover image: {image_path}")
            except Exception as e:
                print(f"   ⚠️ Failed to save local image: {e}")
                # proceed to attempt upload from memory nonetheless

            # Step 2: Upload image to API using configured endpoint/key
            if not IMAGE_UPLOAD_URL:
                print("   ⚠️ No IMAGE_UPLOAD_URL configured — skipping upload")
                return image_path

            print(f"   📤 Uploading image to API at {IMAGE_UPLOAD_URL}...")

            headers = {}
            if IMAGE_UPLOAD_API_KEY:
                headers['x-api-key'] = IMAGE_UPLOAD_API_KEY

            files = {'image': ('cover.jpg', image_data, 'image/jpeg')}
            data = {'fiction_id': fiction_id}

            try:
                upload_response = session.post(IMAGE_UPLOAD_URL, files=files, data=data, headers=headers, timeout=IMAGE_UPLOAD_TIMEOUT or 30)
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Upload request failed: {e}")
                # Return local path as fallback
                return image_path

            # Parse response
            try:
                result = upload_response.json()
            except Exception:
                print(f"   ⚠️ Invalid JSON response: {upload_response.text}")
                return image_path

            # Check response status
            if not result.get('success', False):
                error_msg = result.get('message', 'Unknown error')
                print(f"   ⚠️ Upload failed: {error_msg}")
                return image_path

            # Get image link from response (expecting 'data' -> 'local_path' or 'url')
            data_obj = result.get('data', {}) or {}
            image_link = data_obj.get('local_path') or data_obj.get('url') or data_obj.get('path')

            # If API returned a relative path (e.g. starting with '/covers/...'),
            # build an absolute URL using the upload service host.
            if image_link and isinstance(image_link, str) and image_link.startswith('/'):
                try:
                    parsed = urlparse(IMAGE_UPLOAD_URL)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    image_link = base + image_link
                except Exception:
                    # leave as-is if parsing fails
                    pass

            if image_link:
                print(f"   ✅ Image uploaded: {image_link}")
                return image_link
            else:
                print(f"   ⚠️ No image link in response: {result}")
                return image_path

        except requests.exceptions.RequestException as e:
            # Detect DNS resolution errors specifically to give clearer message
            err_msg = str(e)
            dns_issue = False
            try:
                # socket.gaierror will surface here sometimes
                if isinstance(e, requests.exceptions.ConnectionError) and e.__cause__:
                    if isinstance(e.__cause__, socket.gaierror):
                        dns_issue = True
                # Heuristic check for common DNS resolution text
                if "Name or service not known" in err_msg or "nodename nor servname provided" in err_msg or "getaddrinfo failed" in err_msg:
                    dns_issue = True
            except Exception:
                pass

            if dns_issue:
                print(f"   ⚠️ DNS resolution error when downloading image: {image_url} ({err_msg})")
                # No point retrying if host cannot be resolved — return None immediately
                return None

            # Generic request exception: retry with backoff until attempts exhausted
            print(f"   ❌ Error downloading image (attempt {attempt}): {e}")
            if attempt > MAX_RETRIES:
                return None
            time.sleep(RETRY_BACKOFF * attempt)
            continue
        
        
            
    