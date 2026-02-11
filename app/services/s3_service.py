"""
AWS S3 File Upload Service with Enhanced Security.

This module provides secure file upload functionality to AWS S3 with:
- Strict MIME type validation
- Magic byte verification
- File size limits
- Virus scanning integration points
- Secure filename generation
- Signed URL generation for secure access
"""

import os
import logging
import hashlib
import mimetypes
import magic
import re
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any, TYPE_CHECKING, cast
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

# Runtime imports with error handling
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore
    logger.warning("boto3 not installed. S3 functionality will be disabled.")

# For Pylance: Declare actual types used at runtime
if TYPE_CHECKING:
    assert BOTO3_AVAILABLE is True
    # Pylance sees boto3 and ClientError as their real types here
    assert boto3 is not None
    assert ClientError is not Exception


class FileType:
    """File type definitions with MIME types and allowed extensions."""
    
    PROFILE_IMAGE = {
        'extensions': ['.jpg', '.jpeg'],
        'mime_types': ['image/jpeg'],
        'magic_bytes': [b'\xFF\xD8\xFF'],  # JPEG magic bytes
        'max_size': 5 * 1024 * 1024,  # 5MB
        'description': 'JPEG images only'
    }
    
    CHALLENGE_FILE = {
        'extensions': ['.jpg', '.jpeg', '.pdf', '.zip'],
        'mime_types': [
            'image/jpeg',
            'application/pdf',
            'application/zip',
            'application/x-zip-compressed'
        ],
        'magic_bytes': [
            b'\xFF\xD8\xFF',  # JPEG
            b'%PDF',          # PDF
            b'PK\x03\x04',    # ZIP
            b'PK\x05\x06',    # Empty ZIP
            b'PK\x07\x08'     # Spanned ZIP
        ],
        'max_size': 50 * 1024 * 1024,  # 50MB
        'description': 'JPEG, PDF, or ZIP files'
    }


class S3FileUploadService:
    """Service for securely uploading files to AWS S3."""
    
    def __init__(self, bucket_name: str, region_name: str = 'us-east-1'):
        """
        Initialize S3 service.
        
        Args:
            bucket_name: Name of the S3 bucket
            region_name: AWS region name
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required for S3 uploads. Install with: pip install boto3")
        
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.s3_client: Optional[Any] = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the S3 client with error handling."""
        # Type guard: Assert boto3 is available (Pylance type narrowing)
        assert BOTO3_AVAILABLE, "boto3 is not available"
        assert boto3 is not None, "boto3 module is None"
        
        try:
            self.s3_client = boto3.client('s3', region_name=self.region_name)
            # Test connectivity
            if self.s3_client is not None:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            raise
        except ClientError as e:
            # Type guard: Cast to actual ClientError type for Pylance
            error_response = cast(Dict[str, Any], getattr(e, 'response', {}))
            error_code = error_response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404':
                logger.error(f"S3 bucket '{self.bucket_name}' not found")
            elif error_code == '403':
                logger.error(f"Access denied to S3 bucket '{self.bucket_name}'")
            else:
                logger.error(f"Error connecting to S3: {str(e)}")
            raise
    
    def _validate_file_size(self, file: FileStorage, max_size: int) -> Tuple[bool, str]:
        """
        Validate file size.
        
        Args:
            file: File to validate
            max_size: Maximum allowed size in bytes
            
        Returns:
            Tuple of (is_valid, message)
        """
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size > max_size:
            max_mb = max_size / (1024 * 1024)
            current_mb = size / (1024 * 1024)
            return False, f"File size ({current_mb:.2f}MB) exceeds maximum allowed size ({max_mb:.2f}MB)"
        
        if size == 0:
            return False, "File is empty"
        
        return True, "File size is acceptable"
    
    def _validate_extension(self, filename: str, allowed_extensions: list) -> Tuple[bool, str]:
        """
        Validate file extension.
        
        Args:
            filename: Original filename
            allowed_extensions: List of allowed extensions (with dots)
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not filename or '.' not in filename:
            return False, "Invalid filename"
        
        ext = os.path.splitext(filename.lower())[1]
        
        if ext not in allowed_extensions:
            return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(allowed_extensions)}"
        
        return True, "File extension is valid"
    
    def _validate_mime_type(self, file_path: str, allowed_mime_types: list) -> Tuple[bool, str]:
        """
        Validate MIME type using python-magic.
        
        Args:
            file_path: Path to the file
            allowed_mime_types: List of allowed MIME types
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(file_path)
            
            if detected_mime not in allowed_mime_types:
                return False, f"File type '{detected_mime}' not allowed. Allowed: {', '.join(allowed_mime_types)}"
            
            return True, f"MIME type validated: {detected_mime}"
        except Exception as e:
            logger.error(f"Error validating MIME type: {str(e)}")
            return False, "Unable to validate file type"
    
    def _validate_magic_bytes(self, file_path: str, allowed_magic_bytes: list) -> Tuple[bool, str]:
        """
        Validate file magic bytes (file signature).
        
        Args:
            file_path: Path to the file
            allowed_magic_bytes: List of allowed magic byte sequences
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)  # Read first 16 bytes
            
            # Check if file starts with any allowed magic bytes
            for magic_sequence in allowed_magic_bytes:
                if header.startswith(magic_sequence):
                    return True, "Magic bytes validated"
            
            return False, "File signature does not match expected format"
        except Exception as e:
            logger.error(f"Error validating magic bytes: {str(e)}")
            return False, "Unable to validate file signature"
    
    def _check_for_embedded_threats(self, file_path: str, file_type_config: dict) -> Tuple[bool, str]:
        """
        Check for embedded threats like scripts in images or executables in archives.
        
        Args:
            file_path: Path to the file
            file_type_config: File type configuration
            
        Returns:
            Tuple of (is_safe, message)
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read(8192)  # Read first 8KB
            
            # Check for HTML/JavaScript in image files
            if 'image/' in str(file_type_config.get('mime_types', [])):
                dangerous_patterns = [
                    b'<script',
                    b'<html',
                    b'javascript:',
                    b'onerror=',
                    b'onload=',
                ]
                
                for pattern in dangerous_patterns:
                    if pattern.lower() in content.lower():
                        return False, "Potentially malicious content detected in image file"
            
            # Check for executable signatures in non-executable files
            executable_signatures = [
                b'MZ',  # Windows PE
                b'\x7fELF',  # Linux ELF
                b'\xfe\xed\xfa',  # Mach-O
            ]
            
            for sig in executable_signatures:
                if content.startswith(sig):
                    return False, "Executable file detected"
            
            return True, "No embedded threats detected"
        except Exception as e:
            logger.error(f"Error checking for embedded threats: {str(e)}")
            return False, "Unable to scan file for threats"
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Generate a secure, unique filename.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized unique filename
        """
        # Get safe filename
        safe_name = secure_filename(filename)
        name, ext = os.path.splitext(safe_name)
        
        # Remove any remaining special characters
        name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
        
        # Truncate long names
        if len(name) > 50:
            name = name[:50]
        
        # Generate unique identifier
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        random_hash = hashlib.sha256(os.urandom(16)).hexdigest()[:8]
        
        # Construct final filename
        unique_filename = f"{name}_{timestamp}_{random_hash}{ext}"
        
        return unique_filename
    
    def _generate_s3_key(self, folder: str, filename: str) -> str:
        """
        Generate S3 object key with folder structure.
        
        Args:
            folder: Folder path in S3
            filename: Filename
            
        Returns:
            S3 object key
        """
        # Ensure folder doesn't start with /
        folder = folder.lstrip('/')
        
        # Add date-based subfolder for organization
        date_folder = datetime.utcnow().strftime('%Y/%m')
        
        return f"{folder}/{date_folder}/{filename}"
    
    def upload_file(
        self,
        file: FileStorage,
        folder: str,
        file_type_config: dict,
        metadata: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Upload a file to S3 with comprehensive validation.
        
        Args:
            file: File to upload
            folder: S3 folder path
            file_type_config: File type configuration (from FileType class)
            metadata: Optional metadata to attach to the file
            
        Returns:
            Tuple of (success, message, file_info_dict)
        """
        temp_file_path = None
        
        try:
            # 1. Validate file is provided
            if not file or not file.filename:
                return False, "No file provided", None
            
            # 2. Validate file size
            valid, msg = self._validate_file_size(file, file_type_config['max_size'])
            if not valid:
                return False, msg, None
            
            # 3. Validate file extension
            valid, msg = self._validate_extension(file.filename, file_type_config['extensions'])
            if not valid:
                return False, msg, None
            
            # 4. Save to temporary location for validation
            temp_filename = f"temp_{hashlib.md5(os.urandom(8)).hexdigest()}"
            temp_file_path = f"/tmp/{temp_filename}" if os.name != 'nt' else os.path.join(os.environ.get('TEMP', 'C:\\Temp'), temp_filename)
            file.save(temp_file_path)
            
            # 5. Validate MIME type
            valid, msg = self._validate_mime_type(temp_file_path, file_type_config['mime_types'])
            if not valid:
                return False, msg, None
            
            # 6. Validate magic bytes
            valid, msg = self._validate_magic_bytes(temp_file_path, file_type_config['magic_bytes'])
            if not valid:
                return False, msg, None
            
            # 7. Check for embedded threats
            valid, msg = self._check_for_embedded_threats(temp_file_path, file_type_config)
            if not valid:
                return False, msg, None
            
            # 8. Generate secure filename
            secure_name = self._sanitize_filename(file.filename)
            s3_key = self._generate_s3_key(folder, secure_name)
            
            # 9. Prepare metadata
            upload_metadata = {
                'original-filename': file.filename,
                'upload-timestamp': datetime.utcnow().isoformat(),
                'file-type': file_type_config['description']
            }
            if metadata:
                upload_metadata.update(metadata)
            
            # 10. Determine content type
            ext = os.path.splitext(file.filename)[1].lower()
            content_type = mimetypes.types_map.get(ext, 'application/octet-stream')
            
            # 11. Upload to S3
            if self.s3_client is None:
                return False, "S3 client not properly initialized", None
            
            with open(temp_file_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=f,
                    ContentType=content_type,
                    Metadata=upload_metadata,
                    ServerSideEncryption='AES256'  # Enable encryption at rest
                )
            
            # 12. Generate file info
            file_info = {
                's3_key': s3_key,
                'bucket': self.bucket_name,
                'filename': secure_name,
                'original_filename': file.filename,
                'content_type': content_type,
                'url': f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{s3_key}"
            }
            
            logger.info(f"Successfully uploaded file to S3: {s3_key}")
            return True, "File uploaded successfully", file_info
            
        except ClientError as e:
            logger.error(f"S3 upload error: {str(e)}")
            return False, f"Failed to upload file to storage: {str(e)}", None
        except Exception as e:
            logger.error(f"Unexpected error during file upload: {str(e)}")
            return False, f"Error processing file: {str(e)}", None
        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file: {str(e)}")
    
    def delete_file(self, s3_key: str) -> Tuple[bool, str]:
        """
        Delete a file from S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if self.s3_client is None:
                return False, "S3 client not properly initialized"
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted file from S3: {s3_key}")
            return True, "File deleted successfully"
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            return False, f"Failed to delete file: {str(e)}"
    
    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
        download: bool = False
    ) -> Optional[str]:
        """
        Generate a presigned URL for secure file access.
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            download: If True, force download instead of inline display
            
        Returns:
            Presigned URL or None if error
        """
        try:
            if self.s3_client is None:
                logger.error("S3 client not properly initialized")
                return None
            
            params = {
                'Bucket': self.bucket_name,
                'Key': s3_key
            }
            
            if download:
                # Force download with original filename
                params['ResponseContentDisposition'] = f'attachment; filename="{os.path.basename(s3_key)}"'
            
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expiration
            )
            
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return None
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            if self.s3_client is None:
                logger.warning("S3 client not properly initialized")
                return False
            
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False


def get_s3_service(bucket_type: str) -> Optional[S3FileUploadService]:
    """
    Get S3 service instance for a specific bucket type.
    
    Args:
        bucket_type: Type of bucket ('profiles', 'challenges')
        
    Returns:
        S3FileUploadService instance or None if not configured
    """
    from flask import current_app
    
    if bucket_type == 'profiles':
        bucket_name = current_app.config.get('AWS_PROFILE_BUCKET')
    elif bucket_type == 'challenges':
        bucket_name = current_app.config.get('AWS_CHALLENGE_BUCKET')
    else:
        logger.error(f"Unknown bucket type: {bucket_type}")
        return None
    
    if not bucket_name:
        logger.warning(f"S3 bucket not configured for type: {bucket_type}")
        return None
    
    region = current_app.config.get('AWS_REGION', 'us-east-1')
    
    try:
        return S3FileUploadService(bucket_name, region)
    except Exception as e:
        logger.error(f"Failed to initialize S3 service: {str(e)}")
        return None
