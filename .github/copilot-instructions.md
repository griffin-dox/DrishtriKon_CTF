# DrishtriKon CTF Platform - AI Coding Agent Instructions

## Architecture Overview

**Framework**: Flask 3.1+ with SQLAlchemy 2.0 ORM
**Database**: PostgreSQL with Alembic migrations
**Key Pattern**: Modular Blueprint-based routes with layered security/caching

### Core Layers

1. **Data Layer** (`core/models.py`): 12+ SQLAlchemy models with enums (UserRole, ChallengeType, CompetitionStatus)
2. **Security Layer** (`security/`): 8 specialized modules for rate-limiting, IDS, honeypot, file upload validation, session tracking
3. **Route Layer** (`routes/`): 10 Flask Blueprints organized by feature (auth, admin, host, player, challenges, competitions, teams, badges, ads)
4. **Caching Layer** (`core/cache_management.py`): Storage-aware cache with automatic cleanup, threshold monitoring, and multi-tier invalidation
5. **Utility Layer** (`core/`, `utils/`): Email, OTP, logging, performance optimization

## Critical Design Patterns

### User Authentication & Sessions
- **2FA Flow**: Email OTP → Session tracking → Max 1800s (30min) session lifetime
- **Session Security** (`security/session_security.py`): Generates session IDs, tracks IP/User-Agent, enforces activity timeouts
- **Key Pattern**: Store user context in Flask `g` object during requests (`g.user_id`, `g.username`, `g.request_id`)

### Role-Based Access Control
- Three roles: `OWNER` (admin), `HOST` (competition creators), `PLAYER` (participants)
- Check roles with `user.is_admin()`, `user.is_host()` methods
- Admin routes are **protected by login_required** decorator + security checks

### Multi-Tenant Security Enforcement
- Request enters `before_request_all()` hook which:
  - Assigns UUID `request_id` for distributed logging
  - **Skips heavy checks** for `/static/` and `/auth/` routes (performance critical)
  - Runs honeypot path/field checks → IDS analysis → security checks only for sensitive routes
  - Logs IP activity (honeypot, IDS, bans stored in DB via `BannedIP`, `IDSAlert`, `RateLimit` models)

### Cache Management Strategy
- **Three-tier caching**: In-memory (simple), filesystem (with metadata), production (Redis-ready structure)
- Cache keys use prefixes: `db:`, `api:`, `template:`, `static:` for automatic categorization
- **Critical Pattern**: `CacheStorageManager` monitors 500MB limit (configurable), auto-cleans at 80% threshold, moves oldest files on overflow
- **Warm-up on startup**: `warm_critical_caches()` pre-populates frequently accessed data (challenges, leaderboards)
- Do not use cache for: user sessions, rate limit state, real-time scores

## Development Workflows

### Setup & Running
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
flask db upgrade  # Apply Alembic migrations
flask run  # Runs on http://localhost:5000
```

### Database Migrations
```bash
flask db init              # First time only
flask db migrate -m "description"  # Create migration from model changes
flask db upgrade           # Apply migrations
flask db downgrade         # Rollback
```

### Environment Variables (Required)
```
DATABASE_URL=postgresql://user:pass@localhost/drishtrikon
SESSION_SECRET=<random-32-char-hex>
SECRET_KEY=<random-32-char-hex>
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=<app-password>
RECAPTCHA_SITE_KEY=<from-google>
RECAPTCHA_SECRET_KEY=<from-google>
FLASK_ENV=development|production
CACHE_TYPE=simple|filesystem
CACHE_DIR=cache_data
```

## Code Organization & Patterns

### Adding Routes
1. Create Blueprint in `routes/module_name.py`
2. Use `@module_bp.route()` decorator (never bare Flask.route)
3. Import and register in `app.py` within `app.app_context()`
4. Apply decorators in order: `@login_required`, `@role_check()`, then `@csrf.exempt` only if needed

### Database Operations
```python
from app import db
from core.models import User

# Create/Update
user = User(username='test')
user.set_password('securepass')
db.session.add(user)
db.session.commit()  # Always commit explicitly

# Query with logging
user = User.query.filter_by(username='test').first()
if not user:
    current_app.logger.warning(f"User not found: test")

# Delete with cascade
db.session.delete(user)
db.session.commit()
```

### Security Checks & Logging
- **Use module-specific loggers**: `logging.getLogger(__name__)`
- **Attach request context**: Always pass `extra={"user": username, "ip": ip, "event": "type"}`
- **Never log passwords**: Use placeholder patterns, strip sensitive fields
- **Rate limiting**: Check `is_rate_limited(ip_address)` before sensitive operations
- **Honeypot triggers**: Log with level WARNING, don't leak details to response

### Caching in Routes
```python
from core.cache_management import get_cache_manager
from flask_caching import Cache

# For simple caching
@app.cached(timeout=300, key_prefix='challenges:')
def get_challenges():
    return Challenge.query.all()

# For storage-aware caching with manual invalidation
cache_mgr = get_cache_manager()
stats = cache_mgr.get_storage_stats()  # Monitor usage
cache_mgr.cleanup_expired_cache(force=True)  # Force cleanup if needed
```

## Key Files to Know

| File | Purpose |
|------|---------|
| `app.py` | Flask initialization, blueprint registration, middleware config |
| `core/models.py` | All DB models (User, Challenge, Competition, Team, Badge, IDS states) |
| `core/config.py` | Configuration defaults (env-dependent) |
| `security/security.py` | Rate limiting, HTML sanitization, TLS/referrer checks |
| `security/ids.py` | Intrusion detection system with attack pattern matching |
| `security/honeypot.py` | Fake login routes that log attacker behavior |
| `routes/auth.py` | Login/register/2FA with OTP verification |
| `routes/admin.py` | Admin dashboard, user bans, IDS alerts, rate limits management |
| `core/cache_management.py` | Storage monitoring, automatic cleanup, emergency clearing |
| `forms.py` | WTForms validation with CSRF protection |

## Common Gotchas & Patterns

### Session Handling
- **Don't call `session.clear()`** on every request—it resets CSRF tokens. Use selective pops:
  ```python
  for key in list(session.keys()):
      if key not in ('_fresh', 'csrf_token', 'last_active'):
          session.pop(key)
  ```
- Session updates require `session.modified = True` before redirects

### Response JSON Format
All API endpoints return:
```json
{ "status": "success|error", "message": "...", "data": { ... } }
```

### Performance Optimization
- Static files (CSS, JS, images) **bypass all security checks** via `request.path.startswith('/static/')`
- Sensitive routes are: `/admin`, `/host`, `/player`, `/challenges`, `/competitions`
- GET requests never require referrer checks
- Database pool configured for 20 connections + 30 overflow (adjust `SQLALCHEMY_ENGINE_OPTIONS` if needed)

### Email & OTP
- OTP expires in **10 minutes** (set at registration/2FA trigger)
- Email uses Gmail SMTP (configurable via MAIL_* env vars)
- `send_otp_email()` and `send_otp()` are utility functions, not auto-sent

### Testing
Run tests with:
```bash
pytest tests/
pytest --cov=. --cov-report=html  # Coverage report
```

## Debugging Tips

1. **Check logs**: `logs/app.log` has request_id and user context
2. **Enable SQL logging**: Set `echo: true` in `SQLALCHEMY_ENGINE_OPTIONS`
3. **Cache issues**: Run `cache_mgr.emergency_cleanup()` to clear all cache
4. **IDS false positives**: Check `IDSAlert` table, tune patterns in `security/ids.py`
5. **Rate limit debugging**: Inspect `RateLimit` table, use `is_rate_limited()` helper
