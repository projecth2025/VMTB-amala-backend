"""
Temporary storage utilities for managing uploaded files and converted images.
"""
import os
import shutil
from pathlib import Path
from typing import List
import uuid


class TempStorage:
    """Manages temporary file storage for document processing"""

    def __init__(self, base_path: str = "/tmp/uploads"):
        """
        Initialize temporary storage manager.
        
        Args:
            base_path: Base directory for temporary files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def create_request_directory(self) -> str:
        """
        Create a new directory for a processing request.
        
        Returns:
            request_id: Unique identifier for this request
        """
        request_id = str(uuid.uuid4())
        request_dir = self.base_path / request_id
        request_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (request_dir / "raw").mkdir(exist_ok=True)
        (request_dir / "converted").mkdir(exist_ok=True)
        
        return request_id

    def get_request_path(self, request_id: str, subdir: str = "") -> Path:
        """
        Get the path for a request directory.
        
        Args:
            request_id: The request ID
            subdir: Subdirectory (e.g., 'raw', 'converted')
            
        Returns:
            Path object for the directory
        """
        path = self.base_path / request_id
        if subdir:
            path = path / subdir
        return path

    def save_uploaded_file(self, request_id: str, file_content: bytes, filename: str) -> Path:
        """
        Save an uploaded file to the raw subdirectory.
        
        Args:
            request_id: The request ID
            file_content: Binary content of the file
            filename: Original filename
            
        Returns:
            Path to the saved file
        """
        raw_dir = self.get_request_path(request_id, "raw")
        file_path = raw_dir / filename
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        return file_path

    def get_raw_files(self, request_id: str) -> List[Path]:
        """
        Get all raw files for a request.
        
        Args:
            request_id: The request ID
            
        Returns:
            List of Path objects
        """
        raw_dir = self.get_request_path(request_id, "raw")
        if not raw_dir.exists():
            return []
        return sorted(raw_dir.glob("*"))

    def get_converted_images(self, request_id: str) -> List[Path]:
        """
        Get all converted JPEG images for a request.
        
        Args:
            request_id: The request ID
            
        Returns:
            List of Path objects, sorted for consistent ordering
        """
        converted_dir = self.get_request_path(request_id, "converted")
        if not converted_dir.exists():
            return []
        
        # Get all JPEG files and sort them
        # Sorting ensures consistent ordering even after conversion
        jpegs = sorted(converted_dir.glob("*.jpeg"))
        return jpegs

    def cleanup_request(self, request_id: str) -> bool:
        """
        Delete all temporary files for a request.
        
        Args:
            request_id: The request ID
            
        Returns:
            True if successful, False otherwise
        """
        request_dir = self.get_request_path(request_id)
        if request_dir.exists():
            try:
                shutil.rmtree(request_dir)
                return True
            except Exception as e:
                print(f"Error cleaning up request {request_id}: {e}")
                return False
        return True

    def get_converted_dir(self, request_id: str) -> Path:
        """
        Get the path to the converted images directory.
        
        Args:
            request_id: The request ID
            
        Returns:
            Path to converted directory
        """
        return self.get_request_path(request_id, "converted")
