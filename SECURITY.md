# Security Overview

This document details the security features and best practices implemented in the DrishtriKon CTF Platform.

## Security Features
- **Google reCAPTCHA v3**: Integrated for login, registration, and contact forms. Scripts and badge are loaded only on those pages.
- **Content Security Policy (CSP)**: Strict CSP allows only trusted domains for scripts, styles, fonts, frames, and images. CSP violations are logged and reported.
- **Session Security**: Enforces secure, HTTP-only, and SameSite cookies. Max sessions per user are enforced.
- **Rate Limiting**: Per-user and per-IP rate limiting to prevent brute force and abuse.
- **Honeypot & IDS**: Hidden honeypot fields and intrusion detection system for suspicious activity.
- **File Upload Security**: Strict file type and size checks, with static optimization for uploads.
- **Password Security**: Password breach checks and strong password requirements.
- **Logging**: All security modules use contextual logging with user/session/request info.
- **Admin/Host Separation**: Role-based access control for admin, host, and player.
- **Database-backed Bans & Alerts**: All bans, IDS alerts, and rate limits are stored in the database for auditability.

## Best Practices
- Always use HTTPS in production.
- Set strong, unique `SECRET_KEY` and reCAPTCHA keys in environment variables.
- Regularly review CSP violation logs and update allowed domains only as needed.
- Keep dependencies up to date and monitor for vulnerabilities.

## Reporting Security Issues
If you discover a security vulnerability, please report it privately to the maintainers.

---

For more details, see the main `README.md` and code comments.
