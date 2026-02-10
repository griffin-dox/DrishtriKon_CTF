# S3 File Storage Integration Guide

## Overview

This document describes the secure S3 file storage implementation for the DrishtriKon CTF platform. The system uses AWS S3 for storing user-uploaded files with comprehensive security validation.

## Features

### Security Measures

1. **Strict File Type Validation**
   - MIME type verification using python-magic
   - Magic byte verification (file signature)
   - Extension validation
   - Dual validation approach prevents file type spoofing

2. **File Size Limits**
   - Profile pictures: 5MB maximum
   - Challenge files: 50MB maximum
   - Server-side and client-side validation

3. **Malicious Content Detection**
   - Embedded script detection in images
   - Polyglot file detection
   - Executable signature detection
   - Content scanning for known attack patterns

4. **Secure File Handling**
   - Filename sanitization
   - Unique filename generation with timestamps and hashes
   - Temporary file processing with cleanup
   - Automatic encryption at rest (AES-256)

5. **Access Control**
   - Presigned URLs for secure file access
   - Time-limited download links
   - Separate buckets for different file types
   - Metadata tracking for audit trails

### Allowed File Types

#### Profile Pictures (Users & Teams)

- **Extensions**: `.jpg`, `.jpeg` only
- **MIME Types**: `image/jpeg`
- **Max Size**: 5MB
- **Storage**: `AWS_PROFILE_BUCKET`

#### Challenge Files

- **Extensions**: `.jpg`, `.jpeg`, `.pdf`, `.zip`
- **MIME Types**:
  - `image/jpeg`
  - `application/pdf`
  - `application/zip`
  - `application/x-zip-compressed`
- **Max Size**: 50MB
- **Storage**: `AWS_CHALLENGE_BUCKET`

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# AWS Credentials
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# S3 Buckets
AWS_PROFILE_BUCKET=drishtrikon-profiles
AWS_CHALLENGE_BUCKET=drishtrikon-challenges
```

### AWS IAM Permissions

Create an IAM user with the following policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:PutObjectAcl"
      ],
      "Resource": [
        "arn:aws:s3:::your-profile-bucket/*",
        "arn:aws:s3:::your-challenge-bucket/*",
        "arn:aws:s3:::your-profile-bucket",
        "arn:aws:s3:::your-challenge-bucket"
      ]
    }
  ]
}
```

### S3 Bucket Setup

#### 1. Create Buckets

```bash
# Using AWS CLI
aws s3 mb s3://drishtrikon-profiles --region us-east-1
aws s3 mb s3://drishtrikon-challenges --region us-east-1
```

#### 2. Enable Encryption

```bash
aws s3api put-bucket-encryption \
  --bucket drishtrikon-profiles \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

#### 3. Configure Bucket Policy

For profile bucket (public read for avatars):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::drishtrikon-profiles/*"
    }
  ]
}
```

For challenge bucket (private, use presigned URLs):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyPublicAccess",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::drishtrikon-challenges/*",
      "Condition": {
        "StringNotEquals": {
          "aws:PrincipalAccount": "YOUR_AWS_ACCOUNT_ID"
        }
      }
    }
  ]
}
```

#### 4. Enable CORS (for web uploads)

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
    "AllowedOrigins": ["https://yourdomain.com"],
    "ExposeHeaders": ["ETag"]
  }
]
```

#### 5. Enable Versioning (Recommended)

```bash
aws s3api put-bucket-versioning \
  --bucket drishtrikon-profiles \
  --versioning-configuration Status=Enabled
```

## Usage Examples

### Upload Profile Picture

```python
from app.services.file_upload import upload_profile_picture

# In your route handler
if form.avatar.data:
    success, message, avatar_url = upload_profile_picture(
        file=form.avatar.data,
        user_id=current_user.id,
        username=current_user.username
    )

    if success:
        current_user.avatar = avatar_url
        db.session.commit()
    else:
        flash(f'Upload failed: {message}', 'danger')
```

### Upload Challenge File

```python
from app.services.file_upload import upload_challenge_file

# In challenge creation/edit route
if form.file.data:
    success, message, file_info = upload_challenge_file(
        file=form.file.data,
        challenge_id=challenge.id,
        challenge_title=challenge.title,
        host_id=current_user.id
    )

    if success:
        challenge.file_name = file_info['filename']
        challenge.file_path = file_info['s3_key']
        challenge.file_mimetype = file_info['content_type']
        db.session.commit()
```

### Generate Download URL

```python
from app.services.file_upload import get_download_url

# Generate a presigned URL for downloading
download_url = get_download_url(
    s3_key=challenge.file_path,
    bucket_type='challenges',
    expiration=3600  # 1 hour
)
```

### Delete File

```python
from app.services.file_upload import delete_file_from_s3

# Delete old file before uploading new one
if old_avatar_url and 's3.amazonaws.com' in old_avatar_url:
    s3_key = old_avatar_url.split('.com/')[-1]
    success, message = delete_file_from_s3(s3_key, 'profiles')
```

## File Organization Structure

Files are organized in S3 with the following structure:

```
Profile Bucket:
  users/
    {user_id}/
      {year}/
        {month}/
          {filename}_{timestamp}_{hash}.jpg
  teams/
    {team_id}/
      {year}/
        {month}/
          {filename}_{timestamp}_{hash}.jpg
  badges/
    {year}/
      {month}/
        {filename}_{timestamp}_{hash}.jpg

Challenge Bucket:
  challenges/
    {challenge_id}/
      {year}/
        {month}/
          {filename}_{timestamp}_{hash}.{ext}
```

## Security Best Practices

### 1. Validation Layers

The system implements multiple validation layers:

1. **Client-side**: Form validators check file type and size
2. **Server-side form validation**: WTForms validates before processing
3. **Extension check**: Verifies file has allowed extension
4. **MIME type check**: Uses python-magic to detect actual file type
5. **Magic byte check**: Verifies file signature matches expected type
6. **Content scanning**: Checks for embedded malicious content

### 2. Preventing Common Attacks

#### Path Traversal

- All filenames are sanitized using `secure_filename()`
- Path separators and special characters are removed
- Files are stored with generated names, not user-provided names

#### File Upload Attacks

- Magic byte verification prevents mime type spoofing
- Polyglot file detection prevents dual-purpose files
- Executable detection blocks malware uploads
- Size limits prevent DoS attacks

#### XSS via Images

- Image files are scanned for HTML/JavaScript tags
- Event handlers (`onerror`, `onload`) are detected
- Files with suspicious content are rejected

### 3. Access Control

#### Public Files (Profile Pictures)

- Stored in profile bucket with public read access
- No sensitive information in metadata
- URL-based access (no authentication needed)

#### Private Files (Challenges)

- Stored in challenge bucket (private)
- Access via presigned URLs only
- Time-limited access (default 1 hour)
- Download forced (Content-Disposition: attachment)

### 4. Monitoring & Logging

The system logs:

- All upload attempts (success/failure)
- Validation failures with reasons
- File deletions
- S3 errors

Example log entry:

```
[2026-02-10 10:30:15] INFO app.services.s3_service: Successfully uploaded file to S3: challenges/42/2026/02/ctf_challenge_20260210_103015_a1b2c3d4.zip
```

## Error Handling

### Common Errors

1. **"File type not allowed"**
   - Solution: Ensure file matches allowed extensions
   - Check: Verify file isn't renamed from different type

2. **"File signature does not match expected format"**
   - Solution: File may be corrupted or renamed
   - Check: Verify file is actually the type claimed

3. **"Potentially malicious content detected"**
   - Solution: File contains suspicious patterns
   - Check: Remove any embedded scripts or code

4. **"S3 bucket not configured"**
   - Solution: Set AWS environment variables
   - Check: Verify bucket names and region are correct

5. **"Access denied to S3 bucket"**
   - Solution: Check IAM permissions
   - Check: Verify AWS credentials are correct

## Migration from Local Storage

If you have existing local files, migrate them to S3:

```python
# Migration script
from app.models import User, Challenge
from app.services.s3_service import S3FileUploadService, FileType
import os

def migrate_profile_pictures():
    s3_service = S3FileUploadService(os.getenv('AWS_PROFILE_BUCKET'))

    users = User.query.filter(User.avatar.isnot(None)).all()

    for user in users:
        if 's3.amazonaws.com' not in user.avatar:
            # Local file, migrate to S3
            local_path = os.path.join('var/uploads', user.avatar)

            if os.path.exists(local_path):
                with open(local_path, 'rb') as f:
                    success, msg, file_info = s3_service.upload_file(
                        f,
                        f"users/{user.id}",
                        FileType.PROFILE_IMAGE,
                        {'user_id': str(user.id)}
                    )

                    if success:
                        user.avatar = file_info['url']
                        print(f"Migrated avatar for user {user.username}")

    db.session.commit()
```

## Cost Optimization

### S3 Lifecycle Policies

Configure lifecycle rules to move old files to cheaper storage:

```json
{
  "Rules": [
    {
      "Id": "MoveOldChallengesToIA",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 365,
          "StorageClass": "GLACIER"
        }
      ],
      "Prefix": "challenges/"
    }
  ]
}
```

### Cost Estimates

Based on typical usage:

- Profile pictures: ~500KB average, 1000 users = ~500MB = $0.01/month
- Challenge files: ~10MB average, 100 challenges = ~1GB = $0.02/month
- Data transfer: ~100GB/month = ~$9/month
- **Total estimated cost**: ~$10/month for typical CTF platform

## Troubleshooting

### Enable Debug Logging

```python
import logging
logging.getLogger('app.services.s3_service').setLevel(logging.DEBUG)
```

### Test S3 Connectivity

```python
from app.services.s3_service import get_s3_service

s3 = get_s3_service('profiles')
if s3:
    print("✓ S3 service initialized successfully")
else:
    print("✗ S3 service initialization failed")
```

### Verify File Upload

```python
# Test upload
from werkzeug.datastructures import FileStorage
from io import BytesIO

test_file = FileStorage(
    stream=BytesIO(b'test content'),
    filename='test.jpg',
    content_type='image/jpeg'
)

success, message, file_info = s3_service.upload_file(
    test_file,
    'test',
    FileType.PROFILE_IMAGE
)

print(f"Upload {'succeeded' if success else 'failed'}: {message}")
```

## Support

For issues or questions:

1. Check application logs in `var/logs/app.log`
2. Verify S3 configuration in AWS console
3. Test IAM permissions with AWS CLI
4. Review CloudWatch logs for S3 API calls
