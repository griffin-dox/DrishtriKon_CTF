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

## Security Logging Coverage (Updated July 2, 2025)

### Authentication/Authorization
- **All failed login attempts** (not just rate-limited):
  - Every failed login (wrong password, non-existent user, etc.) is now logged at WARNING level with the `security` logger, including username and IP address.
  - These events trigger Discord alerts and are visible in security logs.
- **Account lockouts/suspensions:**
  - Login attempts for locked, suspended, or banned accounts are logged at WARNING with context (username, IP).
- **Password changes:**
  - Failed password change attempts (wrong current password) are logged at WARNING with context.
  - Successful password changes are logged at INFO with context.

### User Management (Admin)
- **User creation, deletion, privilege/status changes:**
  - (If implemented in admin routes) These events should be logged at INFO/WARNING with the `security` logger for auditability.

### Logging System
- All security logs use the `security` logger, which is configured to:
  - Write to a rotating file (`security_events.log`)
  - Send WARNING and above to Discord via webhook
  - Redact sensitive data (passwords, tokens, etc.)

### Summary of Improvements
- Comprehensive logging for all authentication failures, account lockouts, and sensitive user actions.
- All logs include contextual information (user, IP, event type).
- Alerts and logs are now robust for incident response and auditing.

---

For more details, see the main `README.md` and code comments.
