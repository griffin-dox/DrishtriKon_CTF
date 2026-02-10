# Quick Reference: S3 File Uploads

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install boto3>=1.35.0
```

### 2. Configure Environment

```bash
# Add to .env
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
AWS_PROFILE_BUCKET=bucket-name
AWS_CHALLENGE_BUCKET=bucket-name
```

### 3. Import and Use

```python
from app.services.file_upload import (
    upload_profile_picture,
    upload_challenge_file,
    upload_team_avatar,
    delete_file_from_s3,
    get_download_url
)
```

---

## 📋 File Type Rules

| Type        | Extensions                      | Max Size | Storage    |
| ----------- | ------------------------------- | -------- | ---------- |
| Profile     | `.jpg`, `.jpeg`                 | 5MB      | profiles   |
| Team Avatar | `.jpg`, `.jpeg`                 | 5MB      | profiles   |
| Challenge   | `.jpg`, `.jpeg`, `.pdf`, `.zip` | 50MB     | challenges |
| Badge       | `.jpg`, `.jpeg`                 | 5MB      | profiles   |
| Ad          | `.jpg`, `.jpeg`                 | 5MB      | profiles   |

---

## 💻 Code Snippets

### Upload Profile Picture

```python
if form.avatar.data:
    success, message, avatar_url = upload_profile_picture(
        form.avatar.data,
        current_user.id,
        current_user.username
    )
    if success:
        # Delete old avatar
        if current_user.avatar and 's3.amazonaws.com' in current_user.avatar:
            old_key = current_user.avatar.split('.com/')[-1]
            delete_file_from_s3(old_key, 'profiles')

        current_user.avatar = avatar_url
        db.session.commit()
        flash('Profile picture updated', 'success')
    else:
        flash(f'Upload failed: {message}', 'danger')
```

### Upload Challenge File

```python
if form.file.data:
    success, message, file_info = upload_challenge_file(
        form.file.data,
        challenge.id,
        challenge.title,
        current_user.id
    )
    if success:
        challenge.file_name = file_info['filename']
        challenge.file_path = file_info['s3_key']
        challenge.file_mimetype = file_info['content_type']
        db.session.commit()
```

### Generate Download Link

```python
# In route that serves challenge file
if challenge.file_path:
    if 's3.amazonaws.com' in challenge.file_path:
        # S3 file - generate presigned URL
        download_url = get_download_url(
            challenge.file_path,
            'challenges',
            expiration=3600
        )
        return redirect(download_url)
    else:
        # Legacy local file
        return send_from_directory('uploads', challenge.file_path)
```

---

## 🔒 Form Validators

### In forms.py

```python
from app.validators import SecureFileAllowed, FileSize, SafeFilename

class ProfileForm(FlaskForm):
    avatar = FileField('Profile Picture', validators=[
        Optional(),
        SecureFileAllowed(['.jpg', '.jpeg'],
                         mime_types=['image/jpeg'],
                         message='Only JPEG images allowed'),
        FileSize(5 * 1024 * 1024),  # 5MB
        SafeFilename()
    ])

class ChallengeForm(FlaskForm):
    file = FileField('Challenge File', validators=[
        Optional(),
        SecureFileAllowed(['.jpg', '.jpeg', '.pdf', '.zip'],
                         mime_types=['image/jpeg', 'application/pdf',
                                    'application/zip'],
                         message='Only JPEG, PDF, or ZIP files'),
        FileSize(50 * 1024 * 1024),  # 50MB
        SafeFilename()
    ])
```

---

## 🔍 Error Handling

```python
# Check if S3 is configured
from flask import current_app

if current_app.config.get('S3_ENABLED'):
    # S3 is available
    success, message, url = upload_profile_picture(...)
else:
    # S3 not configured
    flash('File upload not available', 'warning')
```

### Common Errors

```python
# "File type not allowed"
# → Check file extension matches MIME type

# "File size exceeds maximum"
# → Check file is within size limits

# "S3 bucket not configured"
# → Set AWS env variables

# "Access denied to S3"
# → Check IAM permissions
```

---

## 🧹 Cleanup Old Files

```python
from app.services.file_upload import delete_file_from_s3

# Before uploading new file
if old_url and 's3.amazonaws.com' in old_url:
    try:
        # Extract S3 key from URL
        s3_key = old_url.split('.com/')[-1]
        delete_file_from_s3(s3_key, bucket_type='profiles')
    except Exception as e:
        current_app.logger.warning(f"Failed to delete old file: {e}")
```

---

## 📦 S3 Key Patterns

```
Profile: users/{user_id}/{year}/{month}/filename_timestamp_hash.jpg
Team: teams/{team_id}/{year}/{month}/filename_timestamp_hash.jpg
Challenge: challenges/{challenge_id}/{year}/{month}/filename_timestamp_hash.ext
Badge: badges/{year}/{month}/filename_timestamp_hash.jpg
```

---

## ⚡ Testing

```python
# Test S3 connection
from app.services.s3_service import get_s3_service

s3 = get_s3_service('profiles')
if s3:
    print("✓ S3 ready")
else:
    print("✗ S3 not configured")

# Test file upload
from werkzeug.datastructures import FileStorage
from io import BytesIO

test_file = FileStorage(
    stream=BytesIO(b'\xFF\xD8\xFF'),  # JPEG magic bytes
    filename='test.jpg',
    content_type='image/jpeg'
)

success, msg, info = upload_profile_picture(test_file, 1, 'testuser')
print(f"Upload: {success} - {msg}")
```

---

## 🔐 Security Checklist

- ✅ File extension validation
- ✅ MIME type verification
- ✅ Magic byte checking
- ✅ Size limits enforced
- ✅ Filename sanitization
- ✅ Malicious content scanning
- ✅ Encryption at rest
- ✅ Access control
- ✅ Audit logging

---

## 📊 Monitoring

```python
import logging
logger = logging.getLogger(__name__)

# Logs automatically include:
logger.info(f"Successfully uploaded file to S3: {s3_key}")
logger.error(f"S3 upload error: {error}")
logger.warning(f"File validation failed: {reason}")
```

---

## 💡 Pro Tips

1. **Always delete old files** before uploading new ones
2. **Check S3_ENABLED** before attempting uploads
3. **Use presigned URLs** for challenge file downloads
4. **Handle both S3 and legacy local files** during migration
5. **Log upload failures** for debugging
6. **Test with various file types** including malicious ones
7. **Monitor S3 costs** with CloudWatch
8. **Set lifecycle rules** to archive old files

---

## 📞 Need Help?

1. Check logs: `var/logs/app.log`
2. Review docs: `docs/S3_FILE_STORAGE.md`
3. Test connectivity: Use `get_s3_service()` helper
4. Verify AWS credentials in `.env`
5. Check IAM permissions in AWS Console

---

## 🎯 Remember

- **JPEG only** for profile pictures and team avatars
- **JPEG/PDF/ZIP** for challenge files
- **5MB limit** for images
- **50MB limit** for challenges
- **Always validate** on both client and server
- **Clean up** old files before uploading new ones
