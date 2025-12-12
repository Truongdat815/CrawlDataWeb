# Utils package
import io
import os
import requests
from urllib.parse import urlparse
from .. import config as cfg
try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    HAS_PIL = False

def download_image(image_url, fiction_id):
    """
    Tải ảnh từ URL -> ưu tiên upload lên API -> fallback: lưu local.

    Trả về: đường dẫn remote (API) nếu upload thành công, ngược lại đường dẫn local.
    """
    if not image_url or "http" not in image_url:
        return None

    try:
        # Tạo tên file local
        filename = f"{fiction_id}_cover.jpg"
        file_path = os.path.join(cfg.IMAGES_DIR, filename)

        # Tải ảnh về (bytes)
        response = requests.get(image_url, timeout=cfg.REQUEST_TIMEOUT if hasattr(cfg, 'REQUEST_TIMEOUT') else 10)
        if response.status_code != 200:
            return None
        raw_bytes = response.content

        # Convert to JPEG bytes (server expects JPG). If Pillow available, convert reliably.
        jpeg_bytes = None
        if HAS_PIL:
            try:
                # narrow type for static checkers: ensure Image is not None
                assert Image is not None
                im = Image.open(io.BytesIO(raw_bytes))
                # convert to RGB to ensure JPEG compatible
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
            print("   ⚠️ Pillow not installed — cannot guarantee JPG conversion. Server may reject non-JPEG files.")
            jpeg_bytes = None

        # Use jpeg_bytes if we have them, otherwise use raw bytes
        image_bytes = jpeg_bytes if jpeg_bytes is not None else raw_bytes

        # If configured, try upload
        if getattr(cfg, 'IMAGE_UPLOAD_URL', None):
            # prepare headers only if API key present
            pass

        # If there is no upload config, we'll just save the file locally below and return local path
        if not getattr(cfg, 'IMAGE_UPLOAD_URL', None):
            # Fallback: lưu file local
            with open(file_path, 'wb') as f:
                f.write(image_bytes)
            print(f"   ✅ Image saved locally: {file_path}")
            return file_path

        # Try upload (we still fall back to local save on failure)
        if getattr(cfg, 'IMAGE_UPLOAD_URL', None):
            try:
                headers = {}
                if getattr(cfg, 'IMAGE_UPLOAD_API_KEY', None):
                    headers['x-api-key'] = cfg.IMAGE_UPLOAD_API_KEY
                files = {'image': ('cover.jpg', image_bytes, 'image/jpeg')}
                data = {'fiction_id': fiction_id}
                upload_timeout = getattr(cfg, 'IMAGE_UPLOAD_TIMEOUT', 30)
                upload_resp = requests.post(cfg.IMAGE_UPLOAD_URL, files=files, data=data, headers=headers, timeout=upload_timeout)

                try:
                    result = upload_resp.json()
                except Exception:
                    print(f"   ⚠️ Invalid JSON response from upload: {upload_resp.text}")
                    result = None

                if result and result.get('success', False):
                    image_link = result.get('data', {}).get('local_path') or result.get('data', {}).get('url') or result.get('data', {}).get('path')
                    if image_link:
                        # If image_link is a relative path (starts with '/'), convert to absolute using upload host
                        if isinstance(image_link, str) and image_link.startswith('/'):
                            try:
                                parsed = urlparse(cfg.IMAGE_UPLOAD_URL)
                                base = f"{parsed.scheme}://{parsed.netloc}"
                                image_link = base + image_link
                            except Exception:
                                pass
                        print(f"   ✅ Image uploaded: {image_link}")
                        # also persist a local copy for caching
                        try:
                            with open(file_path, 'wb') as f:
                                f.write(image_bytes)
                        except Exception:
                            pass
                        return image_link
                    else:
                        print(f"   ⚠️ Upload succeeded but no link returned: {result}")
                else:
                    print(f"   ⚠️ Upload failed or not configured: {getattr(result, 'text', result)}")
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Upload request failed: {e}")
            try:
                headers = {'x-api-key': cfg.IMAGE_UPLOAD_API_KEY}
                files = {'image': ('cover.jpg', image_bytes, 'image/jpeg')}
                data = {'fiction_id': fiction_id}
                upload_timeout = getattr(cfg, 'IMAGE_UPLOAD_TIMEOUT', 30)
                upload_resp = requests.post(cfg.IMAGE_UPLOAD_URL, files=files, data=data, headers=headers, timeout=upload_timeout)

                try:
                    result = upload_resp.json()
                except Exception:
                    print(f"   ⚠️ Invalid JSON response from upload: {upload_resp.text}")
                    # fallback to save local below
                    result = None

                if result and result.get('success', False):
                    image_link = result.get('data', {}).get('local_path')
                    if image_link:
                        print(f"   ✅ Image uploaded: {image_link}")
                        return image_link
                    else:
                        print(f"   ⚠️ Upload succeeded but no link returned: {result}")
                else:
                    print(f"   ⚠️ Upload failed or not configured: {getattr(result, 'text', result)}")
            except requests.exceptions.RequestException as e:
                print(f"   ⚠️ Upload request failed: {e}")

        # Fallback: lưu file local
        try:
            with open(file_path, 'wb') as f:
                f.write(image_bytes)
            print(f"   ✅ Image saved locally: {file_path}")
            return file_path
        except Exception as e:
            print(f"   ⚠️ Failed to save fallback local image: {e}")
            return None

    except Exception as e:
        from ..scrapers.base import safe_print
        safe_print(f"      ⚠️ Lỗi tải ảnh: {e}")

    return None
