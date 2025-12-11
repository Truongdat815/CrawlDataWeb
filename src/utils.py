import os
import requests
from .config import IMAGES_DIR

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
    
    try:
        # Step 1: Tạo thư mục nếu chưa có
        if not os.path.exists(IMAGES_DIR):
            os.makedirs(IMAGES_DIR)
        
        # Step 2: Tải ảnh từ Wattpad
        print(f"   📥 Downloading image from: {image_url}")
        response = requests.get(image_url, timeout=10)
        if response.status_code != 200:
            print(f"   ⚠️ Failed to download image: {response.status_code}")
            return None
        
        image_data = response.content
        
        # Step 3: Lưu ảnh local
        image_filename = f"{fiction_id}_cover.jpg"
        image_path = os.path.join(IMAGES_DIR, image_filename)
        
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        print(f"   ✅ Image saved locally: {image_path}")
        return image_path
        
        # ════════════════════════════════════════════════════════════════════
        # PHẦN UPLOAD API ĐƯỢC COMMENT TẠM THỜI - DỨA SAU THAY THẾ
        # ════════════════════════════════════════════════════════════════════
        # 
        # # Step 2: Upload ảnh lên API
        # print(f"   📤 Uploading image to API...")
        # upload_url = "https://api-image.techleaf.pro/api/upload"
        # 
        # # API key
        # api_key = "k8JdR4xP9uA2mQ7wF1zT0bVgN5yHcS3LrE8qWfU6pXjK2dM9sB4hY0vG7tC1n"
        # 
        # headers = {
        #     'x-api-key': api_key
        # }
        # 
        # files = {'image': ('cover.jpg', image_data, 'image/jpeg')}
        # data = {'fiction_id': fiction_id}
        # 
        # upload_response = requests.post(upload_url, files=files, data=data, headers=headers, timeout=30)
        # 
        # # Parse response
        # try:
        #     result = upload_response.json()
        # except:
        #     print(f"   ⚠️ Invalid JSON response: {upload_response.text}")
        #     return None
        # 
        # # Check response status
        # if not result.get('success', False):
        #     error_msg = result.get('message', 'Unknown error')
        #     print(f"   ⚠️ Upload failed: {error_msg}")
        #     return None
        # 
        # # Get image link from response
        # # API returns: {"success": true, "data": {"local_path": "/covers/2025-12-07/..."}}
        # data_obj = result.get('data', {})
        # image_link = data_obj.get('local_path')
        #       
        # if image_link:
        #     print(f"   ✅ Image uploaded: {image_link}")
        #     return image_link
        # else:
        #     print(f"   ⚠️ No image link in response: {result}")
        #     return None
            
    except Exception as e:
        print(f"   ❌ Error downloading image: {e}")
        return None