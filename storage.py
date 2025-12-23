import boto3
from botocore.client import Config
from config import settings
import logging
from typing import BinaryIO
import uuid
from datetime import datetime
from io import BytesIO

logger = logging.getLogger(__name__)

class B2Storage:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.B2_ENDPOINT,
            aws_access_key_id=settings.B2_KEY_ID,
            aws_secret_access_key=settings.B2_APPLICATION_KEY,
            config=Config(signature_version='s3v4')
        )
        self.bucket_name = settings.B2_BUCKET_NAME
        self.endpoint_url = settings.B2_ENDPOINT
        logger.info("B2 Storage client initialized")
    
    def upload_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Upload file to B2 and return public URL"""
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            
            # Upload to B2 using S3 client
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=unique_filename,
                Body=file_content,
                ContentType=content_type
            )
            
            # Return public URL
            file_url = f"{self.endpoint_url}/file/{self.bucket_name}/{unique_filename}"
            logger.info(f"File uploaded successfully: {unique_filename}")
            return file_url
        except Exception as e:
            logger.error(f"Failed to upload to B2: {e}")
            raise Exception(f"Storage upload failed: {str(e)}")
    
    def delete_file(self, file_url: str):
        """Delete file from B2"""
        try:
            # Extract filename from URL
            filename = file_url.split('/')[-1]
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=filename)
            logger.info(f"File deleted successfully: {filename}")
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            raise
    
    def get_file(self, file_url: str) -> bytes:
        """Download file from B2"""
        try:
            filename = file_url.split('/')[-1]
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=filename)
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise

def download_file(self, file_url: str) -> bytes:
    """Download a file from Supabase storage"""
    try:
        # Extract bucket and path from file_url
        # Example URL: https://[project].supabase.co/storage/v1/object/public/documents/uuid-filename.pdf
        
        # Parse the URL to get bucket and file path
        parts = file_url.split('/storage/v1/object/public/')
        if len(parts) != 2:
            raise ValueError(f"Invalid file URL format: {file_url}")
        
        path_parts = parts[1].split('/', 1)
        if len(path_parts) != 2:
            raise ValueError(f"Could not extract bucket and path from URL: {file_url}")
        
        bucket_name = path_parts[0]
        file_path = path_parts[1]
        
        # Download from Supabase storage
        response = self.client.storage.from_(bucket_name).download(file_path)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to download file from {file_url}: {e}")
        raise Exception(f"Failed to download file: {str(e)}")

# Singleton instance
b2_storage = B2Storage()

def get_storage():
    return b2_storage
