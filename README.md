# DrishtriKon CTF Platform

A modern, secure, and extensible Capture The Flag (CTF) platform built with Flask and SQLAlchemy.

## Features
- User authentication with 2FA and email verification
- Admin, host, and player roles
- Challenge and competition management
- Rate limiting, honeypot, and IDS security features
- Modular logging with request/user context
- File upload security and static optimization
- Database-backed bans, IDS alerts, and rate limiting
- Session security and max session enforcement

## Project Structure
```
DrishtriKon_CTF/
├── app.py                # Main Flask app entry point
├── core/                 # Core utilities, models, logging
├── forms.py              # WTForms definitions
├── honeypot_data/        # Honeypot pattern data
├── ids_data/             # IDS state and rules
├── logs/                 # Log files and IP logs
├── migrations/           # Alembic migrations
├── requirements.txt      # Python dependencies
├── routes/               # Flask Blueprints (admin, auth, player, etc.)
├── security/             # Security modules (rate limiting, IDS, honeypot, etc.)
├── static/               # Static files (CSS, JS, images)
├── templates/            # Jinja2 templates
├── uploads/              # User-uploaded files
└── ...
```

## Setup
1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd DrishtriKon_CTF
   ```
2. **Create a virtual environment and install dependencies:**
   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Set up the database:**
   ```sh
   flask db upgrade
   ```
4. **Run the application:**
   ```sh
   flask run
   ```

## Security Notes
- All security features use module-specific loggers with request/user context.
- Bans, IDS alerts, and rate limiting are database-backed for production safety.
- Session security enforces max sessions per user.
- Password breach checks and full DB migration for honeypot/IDS patterns are recommended for production.

## API Documentation

### Authentication
- Most endpoints require authentication via session or token.
- Admin and host endpoints require elevated roles.

### Example Endpoints

#### User
- `POST /auth/login` — User login
- `POST /auth/register` — User registration
- `GET /auth/logout` — Logout
- `GET /player/profile` — Get current user profile

#### Challenges
- `GET /challenges` — List all challenges
- `GET /challenges/<id>` — Get challenge details
- `POST /challenges/submit` — Submit a flag (authenticated)

#### Admin
- `GET /admin/users` — List users (admin only)
- `POST /admin/users/edit/<user_id>` — Edit user (admin only)
- `POST /admin/challenges/create` — Create challenge (admin/host)

#### Health & Maintenance
- `GET /healthz` — Health check endpoint (returns 200 OK if running)
- `GET /maintenance` — Maintenance page (shows maintenance message)

### Response Format
All API responses are JSON unless serving HTML pages.

```
{
  "status": "success" | "error",
  "message": "...",
  "data": { ... }
}
```

### Error Handling
- 401 Unauthorized: Not logged in
- 403 Forbidden: Insufficient permissions
- 404 Not Found: Resource does not exist
- 429 Too Many Requests: Rate limited

## Contributing
Pull requests and issues are welcome! Please follow best practices for security and code style.

## License
MIT License
