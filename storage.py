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
    
    def upload_file(self, file_obj: BinaryIO, filename: str, content_type: str) -> str:
        """Upload file to B2 and return URL"""
        # Generate unique filename
        file_extension = filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                unique_filename,
                ExtraArgs={
                    'ContentType': content_type,
                    'Metadata': {
                        'original_filename': filename
                    }
                }
            )
            
            # Generate URL
            file_url = f"{settings.B2_ENDPOINT}/{self.bucket_name}/{unique_filename}"
            logger.info(f"File uploaded successfully: {unique_filename}")
            return file_url
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
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
