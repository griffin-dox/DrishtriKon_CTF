# IDrive e2 CORS Configuration Guide

## Overview

This guide provides step-by-step CORS configuration for DrishtriKon CTF buckets on IDrive e2.

## Your Configuration Details

**Domain:** `https://drishti-kon-ctf.onrender.com`  
**IP CIDRs (for reference):**

- `74.220.52.0/24`
- `74.220.60.0/24`

---

## CORS Configuration for Profile Pictures Bucket

### Bucket Name

`drishtrikon-profiles`

### CORS JSON Configuration

```json
[
  {
    "AllowedOrigins": ["https://drishti-kon-ctf.onrender.com"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag", "x-amz-version-id"],
    "MaxAgeSeconds": 3600
  }
]
```

### Configuration Explanation

| Element            | Value                                  | Purpose                                      |
| ------------------ | -------------------------------------- | -------------------------------------------- |
| **AllowedOrigins** | `https://drishti-kon-ctf.onrender.com` | Only your domain can access profile pictures |
| **AllowedMethods** | `GET`, `HEAD`                          | Only read operations (retrieving images)     |
| **AllowedHeaders** | `*`                                    | Accept any custom headers from client        |
| **ExposeHeaders**  | `ETag`, `x-amz-version-id`             | Allow browser to read response headers       |
| **MaxAgeSeconds**  | `3600`                                 | Browser caches CORS config for 1 hour        |

### Use Cases

- Loading user profile pictures on frontend
- Displaying team avatars
- Showing user profile images in leaderboards

---

## CORS Configuration for Challenge Files Bucket

### Bucket Name

`drishtrikon-challenges`

### CORS JSON Configuration

```json
[
  {
    "AllowedOrigins": ["Your Domain"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag", "Content-Length", "x-amz-version-id"],
    "MaxAgeSeconds": 3600
  }
]
```

### Configuration Explanation

| Element            | Value                                        | Purpose                                       |
| ------------------ | -------------------------------------------- | --------------------------------------------- |
| **AllowedOrigins** | `https://drishti-kon-ctf.onrender.com`       | Only your domain can download challenge files |
| **AllowedMethods** | `GET`, `HEAD`                                | Only read operations (downloading files)      |
| **AllowedHeaders** | `*`                                          | Accept range requests for large files         |
| **ExposeHeaders**  | `ETag`, `Content-Length`, `x-amz-version-id` | Expose file metadata                          |
| **MaxAgeSeconds**  | `3600`                                       | Cache CORS config for 1 hour                  |

### Use Cases

- Downloading challenge files (PDFs, ZIPs)
- Accessing challenge attachments
- Streaming large files to users

---

## Step-by-Step Setup in IDrive e2

### For Profile Pictures Bucket (`drishtrikon-profiles`)

1. **Sign in** to your IDrive e2 account
2. **Navigate** to 'Buckets'
3. **Hover** over `drishtrikon-profiles` bucket
4. **Click** the settings icon (⚙️)
5. **Go to** 'Bucket CORS' tab in the slider
6. **Click** 'Add CORS'
7. **Paste** the Profile Bucket CORS configuration (see above)
8. **Click** 'Apply'
9. **Wait** for confirmation message

### For Challenge Files Bucket (`drishtrikon-challenges`)

1. **Repeat steps 1-3** for `drishtrikon-challenges` bucket
2. **Follow steps 4-8** with Challenge Files CORS configuration

---

## Security Considerations

### ✅ What This Configuration Allows

- Only your domain (`https://drishti-kon-ctf.onrender.com`) can access assets
- Users can view/download files through your application
- Prevents direct bucket access from other domains
- Supports presigned URLs for time-limited access

### ✅ What This Configuration Prevents

- Direct bucket access from unauthorized domains
- Cross-site scripting attacks (XSS) via CORS
- Data exfiltration from other websites
- Unauthorized file uploads (GET/HEAD only)

### 🔒 Additional Security Best Practices

1. **Use Presigned URLs** - Generate short-lived URLs in your backend (see S3_FILE_STORAGE.md)
2. **Enable Bucket Versioning** - Protect against accidental deletions
3. **Enable Bucket Encryption** - Encrypt data at rest
4. **Set Bucket Policies** - Restrict IAM user permissions to minimum required
5. **Enable Access Logging** - Monitor bucket access for anomalies

---

## Testing CORS Configuration

### Test with curl

### Expected Success Response

```
Access-Control-Allow-Origin: https://drishti-kon-ctf.onrender.com
Access-Control-Allow-Methods: GET, HEAD
Access-Control-Max-Age: 3600
```

---

## Troubleshooting

### ❌ CORS Error in Browser Console

**Error:** `No 'Access-Control-Allow-Origin' header`

**Solutions:**

1. Verify domain in CORS config matches exactly (including `https://`)
2. Check bucket CORS was applied successfully
3. Wait 5 minutes for IDrive e2 to propagate changes
4. Clear browser cache and retry

### ❌ 403 Forbidden on File Access

**Cause:** IAM user permissions insufficient

**Solution:** Verify IAM policy includes:

```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject"],
  "Resource": "arn:aws:s3:::drishtrikon-*/*"
}
```

### ❌ Large Files Fail to Download

**Cause:** CORS not allowing full response

**Solution:** Ensure `ExposeHeaders` includes `Content-Length`

---

## CORS Configuration Reference

### AllowedMethods Specification

```
GET     - Read objects
PUT     - Write objects (NOT ALLOWED in our config)
POST    - Create objects (NOT ALLOWED in our config)
DELETE  - Remove objects (NOT ALLOWED in our config)
HEAD    - Check object metadata
```

### Why Only GET and HEAD?

- **GET**: Retrieve file content (images, documents)
- **HEAD**: Check if file exists and get metadata
- **Intentionally excluding** PUT/POST/DELETE for read-only access from frontend

---

## Integration with Your Application

### Presigned URLs (Recommended)

Your Flask backend generates secure, time-limited URLs:

```python
from app.services.file_upload import get_download_url

# In your route:
download_url = get_download_url(s3_key, expiration=3600)  # 1 hour
return render_template('download.html', url=download_url)
```

### Direct Bucket URLs (With Caution)

If using direct URLs, CORS ensures only your domain can load them:

```html
<!-- This works (your domain) -->
<img src="https://drishtrikon-profiles.e2.onrender.com/users/123/avatar.jpg" />

<!-- This fails (different origin) -->
<!-- Blocked by CORS from evil.com -->
```

---

## Renewal and Updates

### When to Review CORS Config

- ✓ Adding a new domain
- ✓ Changing subdomain
- ✓ Supporting new file types
- ✓ Updating security policies
- ✓ Handling CORS errors in production

### How to Update CORS

1. Repeat setup steps above
2. Click 'Edit' on existing CORS configuration
3. Update JSON and click 'Apply'
4. Wait for propagation (usually < 5 minutes)

---

## Final Checklist

- [ ] Profile bucket CORS configured with `drishtrikon-profiles`
- [ ] Challenge bucket CORS configured with `drishtrikon-challenges`
- [ ] AllowedOrigins set to `https://drishti-kon-ctf.onrender.com`
- [ ] AllowedMethods set to `GET, HEAD` only
- [ ] CORS configuration applied successfully
- [ ] Tested with curl or browser DevTools
- [ ] Presigned URLs configured in backend
- [ ] Bucket encryption enabled
- [ ] Access logging enabled
- [ ] IAM permissions verified

---

## Support Resources

**IDrive e2 Documentation:**

- [Bucket CORS Configuration](https://docs.idrive.com/e2/en/s3-compatible-buckets)
- [S3 Compatibility Guide](https://docs.idrive.com/e2/en/s3-compatible)

**Your Project Files:**

- [S3 File Storage Setup](./S3_FILE_STORAGE.md)
- [S3 Implementation Summary](./S3_IMPLEMENTATION_SUMMARY.md)
- [S3 Quick Reference](./S3_QUICK_REFERENCE.md)
