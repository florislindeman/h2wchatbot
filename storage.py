import boto3
from botocore.client import Config
from config import settings
import logging
from typing import BinaryIO
import uuid

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
        logger.info("B2 Storage client initialized")
    
    def upload_file(self, file_content: bytes, filename: str, content_type: str) -> str:
    """Upload file to B2 and return public URL"""
    try:
        # Create a file-like object from bytes
        from io import BytesIO
        file_obj = BytesIO(file_content)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        # Upload to B2
        file_info = self.bucket.upload_bytes(
            file_content,
            unique_filename,
            content_type=content_type
        )
        
        # Return public URL
        return f"{self.endpoint_url}/file/{self.bucket_name}/{unique_filename}"
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

# Singleton instance
b2_storage = B2Storage()

def get_storage():
    return b2_storage
