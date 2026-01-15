"""
S3 uploader service for uploading JPEG images to AWS S3 using pre-signed URLs.
"""
import requests
from pathlib import Path
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class S3Uploader:
    """Handles S3 uploads using pre-signed URLs"""

    def __init__(self):
        """Initialize S3 uploader"""
        pass

    @staticmethod
    def get_upload_urls(image_filenames: List[str], api_endpoint: str) -> tuple[Dict[str, str], Dict[str, str]]:
        """
        Request pre-signed URLs from the API.
        
        Args:
            image_filenames: List of image filenames (e.g., ["i1.jpeg", "i2.jpeg"])
            api_endpoint: API endpoint URL for getting upload URLs
            
        Returns:
            Tuple of (upload_urls_dict, s3_keys_dict)
            upload_urls_dict: Dictionary mapping filename to upload URL
            s3_keys_dict: Dictionary mapping filename to S3 key
            
        Raises:
            Exception: If API call fails
        """
        payload = {"data": image_filenames}
        
        try:
            print(f"\n{'='*60}")
            print("📤 CALLING GET-UPLOAD-URLS API")
            print(f"{'='*60}")
            print(f"Endpoint: {api_endpoint}")
            print(f"Image Filenames: {image_filenames}")
            
            response = requests.post(api_endpoint, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            print(f"\n📥 GET-UPLOAD-URLS API RESPONSE")
            print(f"Status Code: {response.status_code}")
            
            # Parse the response structure
            upload_urls = {}
            s3_keys = {}
            
            # Extract data from nested structure: uploads -> data -> [array of items]
            uploads_section = data.get("uploads", {})
            print(f"Uploads Section Keys: {uploads_section.keys()}")
            
            uploads_data = uploads_section.get("data", [])
            print(f"Number of items in uploads.data: {len(uploads_data)}")
            
            for upload_item in uploads_data:
                original_name = upload_item.get("original_name")
                upload_url = upload_item.get("upload_url")
                s3_key = upload_item.get("s3_key")
                
                print(f"\n✓ Parsing: {original_name}")
                print(f"  S3 Key: {s3_key}")
                print(f"  URL Length: {len(upload_url) if upload_url else 0}")
                
                if original_name and upload_url:
                    upload_urls[original_name] = upload_url
                    s3_keys[original_name] = s3_key
                else:
                    print(f"  ⚠ Missing URL or name!")
            
            print(f"\n📊 EXTRACTION SUMMARY")
            print(f"Total URLs extracted: {len(upload_urls)}")
            print(f"Files with URLs:")
            for filename in sorted(upload_urls.keys()):
                print(f"   ✓ {filename}")
            
            print(f"{'='*60}\n")
            
            logger.info(f"Got {len(upload_urls)} upload URLs from API")
            return upload_urls, s3_keys
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting upload URLs: {e}")
            raise Exception(f"Failed to get upload URLs: {str(e)}")

    @staticmethod
    def upload_image_to_s3(image_path: Path, upload_url: str) -> bool:
        """
        Upload a single JPEG image to S3 using the provided pre-signed URL.
        
        Args:
            image_path: Path to the JPEG image file
            upload_url: Pre-signed S3 upload URL
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\n🔄 UPLOADING TO S3: {image_path.name}")
            print(f"File size: {image_path.stat().st_size} bytes")
            
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            headers = {"Content-Type": "image/jpeg"}
            
            response = requests.put(upload_url, data=image_data, headers=headers, timeout=30)
            response.raise_for_status()
            
            print(f"✅ S3 UPLOAD SUCCESS")
            print(f"Status Code: {response.status_code}")
            print(f"File: {image_path.name}")
            
            logger.info(f"Successfully uploaded {image_path.name} to S3")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error uploading {image_path.name} to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading {image_path.name}: {e}")
            return False

    @staticmethod
    def upload_all_images(image_paths: List[Path], upload_urls: Dict[str, str], s3_keys: Dict[str, str]) -> Dict[str, str]:
        """
        Upload all images to S3.
        
        Args:
            image_paths: List of Path objects for JPEG images
            upload_urls: Dictionary mapping filename to upload URL
            s3_keys: Dictionary mapping filename to S3 key
            
        Returns:
            Dictionary mapping filename to S3 key
            
        Raises:
            Exception: If any upload fails
        """
        s3_keys_mapping = {}
        failed_uploads = []
        
        for image_path in image_paths:
            filename = image_path.name
            
            if filename not in upload_urls:
                logger.warning(f"No upload URL for {filename}")
                failed_uploads.append(filename)
                continue
            
            upload_url = upload_urls[filename]
            s3_key = s3_keys.get(filename, "")
            
            # Upload the image
            success = S3Uploader.upload_image_to_s3(image_path, upload_url)
            
            if success:
                s3_keys_mapping[filename] = s3_key
            else:
                failed_uploads.append(filename)
        
        if failed_uploads:
            raise Exception(f"Failed to upload images: {', '.join(failed_uploads)}")
        
        return s3_keys_mapping
