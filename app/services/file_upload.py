"""
File upload helper functions that integrate S3 service with routes.

This module provides high-level functions for uploading different types
of files (profile pictures, challenge files, etc.) with automatic
validation and S3 storage.
"""

import logging
from typing import Tuple, Optional, Dict, Any
from werkzeug.datastructures import FileStorage
from flask import current_app

logger = logging.getLogger(__name__)


def upload_profile_picture(
    file: FileStorage,
    user_id: int,
    username: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Upload a profile picture to S3.
    
    Args:
        file: File upload object from request.files
        user_id: User ID
        username: Username
        
    Returns:
        Tuple of (success, message, s3_url)
    """
    if not file:
        return False, "No file provided", None
    
    # Check if S3 is enabled
    if not current_app.config.get('S3_ENABLED'):
        return False, "File upload service not configured", None
    
    try:
        from app.services.s3_service import get_s3_service, FileType
        
        # Get S3 service for profile bucket
        s3_service = get_s3_service('profiles')
        if not s3_service:
            return False, "Profile upload service not available", None
        
        # Upload file with validation
        success, message, file_info = s3_service.upload_file(
            file=file,
            folder=f"users/{user_id}",
            file_type_config=FileType.PROFILE_IMAGE,
            metadata={
                'user_id': str(user_id),
                'username': username
            }
        )
        
        if not success or file_info is None:
            return False, message, None
        
        # Return the S3 URL
        return True, "Profile picture uploaded successfully", file_info['url']
        
    except Exception as e:
        logger.error(f"Error uploading profile picture: {str(e)}")
        return False, "Failed to upload profile picture", None


def upload_team_avatar(
    file: FileStorage,
    team_id: int,
    team_name: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Upload a team avatar to S3.
    
    Args:
        file: File upload object from request.files
        team_id: Team ID
        team_name: Team name
        
    Returns:
        Tuple of (success, message, s3_url)
    """
    if not file:
        return False, "No file provided", None
    
    # Check if S3 is enabled
    if not current_app.config.get('S3_ENABLED'):
        return False, "File upload service not configured", None
    
    try:
        from app.services.s3_service import get_s3_service, FileType
        
        # Get S3 service for profile bucket
        s3_service = get_s3_service('profiles')
        if not s3_service:
            return False, "Team avatar upload service not available", None
        
        # Upload file with validation
        success, message, file_info = s3_service.upload_file(
            file=file,
            folder=f"teams/{team_id}",
            file_type_config=FileType.PROFILE_IMAGE,
            metadata={
                'team_id': str(team_id),
                'team_name': team_name
            }
        )
        
        if not success or file_info is None:
            return False, message, None
        
        # Return the S3 URL
        return True, "Team avatar uploaded successfully", file_info['url']
        
    except Exception as e:
        logger.error(f"Error uploading team avatar: {str(e)}")
        return False, "Failed to upload team avatar", None


def upload_challenge_file(
    file: FileStorage,
    challenge_id: int,
    challenge_title: str,
    host_id: int
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Upload a challenge file to S3.
    
    Args:
        file: File upload object from request.files
        challenge_id: Challenge ID
        challenge_title: Challenge title
        host_id: ID of the host uploading the file
        
    Returns:
        Tuple of (success, message, file_info_dict)
    """
    if not file:
        return False, "No file provided", None
    
    # Check if S3 is enabled
    if not current_app.config.get('S3_ENABLED'):
        return False, "File upload service not configured", None
    
    try:
        from app.services.s3_service import get_s3_service, FileType
        
        # Get S3 service for challenge bucket
        s3_service = get_s3_service('challenges')
        if not s3_service:
            return False, "Challenge file upload service not available", None
        
        # Upload file with validation
        success, message, file_info = s3_service.upload_file(
            file=file,
            folder=f"challenges/{challenge_id}",
            file_type_config=FileType.CHALLENGE_FILE,
            metadata={
                'challenge_id': str(challenge_id),
                'challenge_title': challenge_title,
                'host_id': str(host_id)
            }
        )
        
        if not success:
            return False, message, None
        
        # Return full file info for database storage
        return True, "Challenge file uploaded successfully", file_info
        
    except Exception as e:
        logger.error(f"Error uploading challenge file: {str(e)}")
        return False, "Failed to upload challenge file", None


def upload_badge_image(
    file: FileStorage,
    badge_name: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Upload a badge image to S3.
    
    Args:
        file: File upload object from request.files
        badge_name: Badge name
        
    Returns:
        Tuple of (success, message, s3_url)
    """
    if not file:
        return False, "No file provided", None
    
    # Check if S3 is enabled
    if not current_app.config.get('S3_ENABLED'):
        return False, "File upload service not configured", None
    
    try:
        from app.services.s3_service import get_s3_service, FileType
        
        # Get S3 service for profile bucket (badges go in profile bucket)
        s3_service = get_s3_service('profiles')
        if not s3_service:
            return False, "Badge image upload service not available", None
        
        # Upload file with validation
        success, message, file_info = s3_service.upload_file(
            file=file,
            folder="badges",
            file_type_config=FileType.PROFILE_IMAGE,
            metadata={
                'badge_name': badge_name
            }
        )
        
        if not success or file_info is None:
            return False, message, None
        
        # Return the S3 URL
        return True, "Badge image uploaded successfully", file_info['url']
        
    except Exception as e:
        logger.error(f"Error uploading badge image: {str(e)}")
        return False, "Failed to upload badge image", None


def upload_ad_image(
    file: FileStorage,
    ad_title: str
) -> Tuple[bool, str, Optional[str]]:
    """
    Upload an ad image to S3.
    
    Args:
        file: File upload object from request.files
        ad_title: Ad title
        
    Returns:
        Tuple of (success, message, s3_url)
    """
    if not file:
        return False, "No file provided", None
    
    # Check if S3 is enabled
    if not current_app.config.get('S3_ENABLED'):
        return False, "File upload service not configured", None
    
    try:
        from app.services.s3_service import get_s3_service, FileType
        
        # Get S3 service for profile bucket (ads go in profile bucket)
        s3_service = get_s3_service('profiles')
        if not s3_service:
            return False, "Ad image upload service not available", None
        
        # Upload file with validation
        success, message, file_info = s3_service.upload_file(
            file=file,
            folder="ads",
            file_type_config=FileType.PROFILE_IMAGE,
            metadata={
                'ad_title': ad_title
            }
        )
        
        if not success or file_info is None:
            return False, message, None
        
        # Return the S3 URL
        return True, "Ad image uploaded successfully", file_info['url']
        
    except Exception as e:
        logger.error(f"Error uploading ad image: {str(e)}")
        return False, "Failed to upload ad image", None


def delete_file_from_s3(s3_key: str, bucket_type: str = 'profiles') -> Tuple[bool, str]:
    """
    Delete a file from S3.
    
    Args:
        s3_key: S3 object key
        bucket_type: Type of bucket ('profiles' or 'challenges')
        
    Returns:
        Tuple of (success, message)
    """
    try:
        from app.services.s3_service import get_s3_service
        from flask import current_app
        
        if not current_app.config.get('S3_ENABLED'):
            return False, "File storage service not configured"
        
        s3_service = get_s3_service(bucket_type)
        if not s3_service:
            return False, "File storage service not available"
        
        return s3_service.delete_file(s3_key)
        
    except Exception as e:
        logger.error(f"Error deleting file from S3: {str(e)}")
        return False, f"Failed to delete file: {str(e)}"


def get_download_url(s3_key: str, bucket_type: str = 'challenges', expiration: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for downloading a file.
    
    Args:
        s3_key: S3 object key
        bucket_type: Type of bucket ('profiles' or 'challenges')
        expiration: URL expiration in seconds (default: 1 hour)
        
    Returns:
        Presigned URL or None if error
    """
    try:
        from app.services.s3_service import get_s3_service
        from flask import current_app
        
        if not current_app.config.get('S3_ENABLED'):
            logger.warning("S3 not enabled, cannot generate download URL")
            return None
        
        s3_service = get_s3_service(bucket_type)
        if not s3_service:
            logger.warning(f"S3 service not available for bucket type: {bucket_type}")
            return None
        
        return s3_service.generate_presigned_url(s3_key, expiration, download=True)
        
    except Exception as e:
        logger.error(f"Error generating download URL: {str(e)}")
        return None
