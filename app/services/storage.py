"""
Supabase Storage Service for handling file uploads and management.
This is the ONLY service that should use Supabase for data operations (storage).
"""
import os
import uuid
from typing import Optional, Dict, Any, List
from fastapi import UploadFile, HTTPException
from app.core.auth import get_supabase_auth_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

class StorageService:
    """Service for managing file storage using Supabase Storage"""
    
    def __init__(self):
        self.supabase = get_supabase_auth_client()
        self.bucket_name = settings.SUPABASE_STORAGE_BUCKET
        self.documents_bucket_name = settings.SUPABASE_DOCUMENTS_BUCKET

        self._valid_image_types = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
        self._valid_video_types = {
            "video/mp4",
            "video/webm",
            "video/quicktime",
            "video/x-matroska",
            "video/ogg",
        }
        self._valid_document_types = {
            "application/pdf",
            # Office formats (optional; safe defaults)
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    
    async def upload_property_image(self, file: UploadFile, property_id: int) -> Dict[str, Any]:
        """Upload property image to Supabase Storage"""
        return await self._upload_file(file, f"properties/{property_id}", "property_image")
    
    async def upload_user_avatar(self, file: UploadFile, user_id: int) -> Dict[str, Any]:
        """Upload user avatar to Supabase Storage"""
        return await self._upload_file(file, f"users/{user_id}", "avatar")
    
    async def upload_agent_avatar(self, file: UploadFile, agent_id: int) -> Dict[str, Any]:
        """Upload agent avatar to Supabase Storage"""
        return await self._upload_file(file, f"agents/{agent_id}", "avatar")
    
    async def upload_generic(self, file: UploadFile, folder: str = "uploads") -> Dict[str, Any]:
        """Generic upload for dashboard and misc files"""
        return await self._upload_file(file, folder, "generic")

    async def upload_document(self, file: UploadFile, folder: str = "documents") -> Dict[str, Any]:
        """Upload a document (PDF, etc.) to the documents bucket."""
        return await self._upload_file(
            file,
            folder,
            "document",
            bucket_name=self.documents_bucket_name,
            allow_documents=True,
        )
    
    async def _upload_file(
        self,
        file: UploadFile,
        folder: str,
        file_type: str,
        *,
        bucket_name: Optional[str] = None,
        allow_documents: bool = False,
    ) -> Dict[str, Any]:
        """Generic file upload method"""
        try:
            # Validate file type
            if not self._is_valid_upload(file, allow_documents=allow_documents):
                raise HTTPException(status_code=400, detail="Invalid file type")
            
            # Generate unique filename
            file_extension = self._get_file_extension(file.filename, content_type=file.content_type)
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"{folder}/{unique_filename}"
            
            # Read file content
            file_content = await file.read()
            
            # Upload to Supabase Storage
            target_bucket = bucket_name or self.bucket_name
            response = self.supabase.storage.from_(target_bucket).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": file.content_type,
                    "cache-control": "3600",
                    "upsert": False
                }
            )
            
            if hasattr(response, 'error') and response.error:
                logger.error(f"Storage upload error: {response.error}")
                raise HTTPException(status_code=500, detail="File upload failed")
            
            # Get public URL
            public_url = self.supabase.storage.from_(target_bucket).get_public_url(file_path)
            
            return {
                "file_path": file_path,
                "public_url": public_url,
                "file_type": file_type,
                "file_size": len(file_content),
                "content_type": file.content_type,
                "original_filename": file.filename
            }
            
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    
    def delete_file(self, file_path: str) -> bool:
        """Delete file from Supabase Storage"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).remove([file_path])
            return not (hasattr(response, 'error') and response.error)
        except Exception as e:
            logger.error(f"File deletion error: {str(e)}")
            return False
    
    def get_file_url(self, file_path: str) -> str:
        """Get public URL for file"""
        return self.supabase.storage.from_(self.bucket_name).get_public_url(file_path)
    
    def list_files(self, folder: str) -> List[Dict[str, Any]]:
        """List files in a folder"""
        try:
            response = self.supabase.storage.from_(self.bucket_name).list(folder)
            if hasattr(response, 'error') and response.error:
                logger.error(f"Storage list error: {response.error}")
                return []
            return response or []
        except Exception as e:
            logger.error(f"File listing error: {str(e)}")
            return []
    
    def _is_valid_upload(self, file: UploadFile, *, allow_documents: bool = False) -> bool:
        """Validate upload content types.

        By default we accept images/videos (property media). For the property
        management document vault, we also allow PDFs (and optional office docs).
        """
        valid = set(self._valid_image_types) | set(self._valid_video_types)
        if allow_documents:
            valid |= set(self._valid_document_types)
        return file.content_type in valid
    
    def _get_file_extension(self, filename: str, *, content_type: Optional[str] = None) -> str:
        """Get file extension from filename, with a safe fallback by content-type."""
        if filename:
            ext = os.path.splitext(filename)[1]
            if ext:
                return ext

        if content_type == "application/pdf":
            return ".pdf"
        if content_type in self._valid_video_types:
            return ".mp4"
        return ".jpg"

# Global storage service instance
storage_service = StorageService()
