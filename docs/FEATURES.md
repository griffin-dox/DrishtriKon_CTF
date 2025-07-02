# Features Overview

This document provides a comprehensive list of features in the DrishtriKon CTF Platform.

## Core Features
- User authentication (login, registration, logout)
- Two-factor authentication (2FA) and email verification
- Role-based access: Admin, Host, Player
- Challenge and competition management (CRUD, visibility, scheduling)
- Team management (create, join, leave, manage teams)
- Leaderboards (global, competition, team, player)
- File upload and download (with security checks)
- Modular logging (per request, per user, per module)
- Customizable static asset optimization
- API endpoints for all major actions (RESTful design)

## Security Features
- Google reCAPTCHA v3 (login, register, contact)
- Content Security Policy (CSP) enforcement and reporting
- Rate limiting (per user/IP)
- Honeypot fields and IDS for suspicious activity
- Session security (max sessions, secure cookies)
- File upload restrictions and static optimization
- Password breach checks
- Database-backed bans, IDS alerts, and rate limiting

## Admin/Host Features
- Admin dashboard (stats, user management, challenge/competition management)
- Host dashboard (manage own competitions/challenges)
- Badge management (create, assign, view badges)
- Global stats and reporting

## User Experience
- Responsive, modern UI (Bootstrap, custom CSS)
- Accessible navigation and forms
- Flash messages and error handling
- Community/social links (GitHub, Twitter, Discord, LinkedIn)

## Extensibility
- Modular codebase for easy feature addition
- Blueprint-based Flask app structure
- Alembic migrations for database changes

---

For API details, see the main `README.md`.
For security details, see `SECURITY.md`.
