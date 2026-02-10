# Database Resilience & Graceful Error Handling

## Overview

This document explains how the DrishtriKon CTF platform gracefully handles database inactivity on free hosting services. Instead of showing a generic 500 error and making the platform appear completely offline, users can continue browsing public pages while database-dependent features show friendly error messages.

---

## Problem Statement

On free database hosting services (like those on Render, Supabase free tier, etc.), databases often go into "sleep mode" after periods of inactivity. When users visit the application:

**Before Fix:**

- Homepage tried to query database
- Database was inactive/sleeping
- Query failed with generic 500 error
- **Entire application appeared offline**
- Users saw no way to understand what happened

**After Fix:**

- Homepage attempts database queries with error handling
- If database is inactive, queries fail gracefully
- **Homepage still renders** with empty data
- Users can still browse: About, FAQ, Terms, Contact, Privacy
- Database-dependent features (login, challenges, competitions) show friendly error messages explaining the situation
- Auto-retry encourages users to try again after database wakes up

---

## Architecture

### Core Components

#### 1. Database Health Module (`core/db_health.py`)

Provides utilities for safe database operations:

```python
from core.db_health import (
    check_db_connection,      # Returns True/False
    get_safe_db_result,       # Safely execute queries with fallbacks
    render_db_error,          # Render friendly error page
    require_db                # Decorator for DB-dependent routes
)
```

**Key Functions:**

- `check_db_connection()`: Checks if DB is alive (returns bool, no exceptions)
- `get_safe_db_result(query_func, default)`: Execute query with default fallback
- `render_db_error(message)`: Renders 503 error page with explanation
- `@require_db`: Decorator that wraps routes with try-catch for DB errors

#### 2. Error Template (`templates/errors/database_unavailable.html`)

User-friendly 503 error page that:

- Explains the situation (free hosting DB goes to sleep)
- Shows estimated recovery time
- Provides options to retry or go home
- Auto-retries every 5 seconds
- Uses professional styling with helpful icons

#### 3. Route-Level Error Handling

All database-dependent routes use `@require_db` decorator:

```python
from core.db_health import require_db

@main_bp.route('/some-route')
@require_db
def some_route():
    # Code that uses database
    # If any exception occurs, returns friendly error page
    return render_template(...)
```

#### 4. Query-Level Error Handling

Queries wrapped with try-catch and default returns:

```python
@cache_db_query(timeout=300)
def get_home_active_competitions():
    try:
        return Competition.query.filter_by(...).all()
    except Exception as e:
        logger.warning(f"Failed to fetch: {str(e)}")
        return []  # Return empty list on error
```

#### 5. Global Error Handler

The 500 error handler detects database-specific errors:

```python
@app.errorhandler(500)
def internal_server_error(error):
    error_str = str(error).lower()
    if 'database' in error_str or 'connection' in error_str:
        return render_db_error()  # Show friendly message
    return render_template('errors/500.html')  # Generic 500 error
```

#### 6. Robust Before-Request Hook

The `before_request` hook is wrapped in try-catch:

```python
@app.before_request
def before_request_all():
    try:
        # All middleware logic here
        ...
    except Exception as e:
        # Log but don't crash
        logger.warning(f"Error in before_request: {str(e)}")
        pass  # Allow request to proceed
```

---

## User Experience Flow

### Scenario 1: Database is Active

1. User visits homepage
2. Queries execute normally
3. Statistics, competitions, top players displayed
4. All features work as expected

### Scenario 2: Database is Inactive (Free Hosting Sleep)

**Homepage:**

1. User visits `/`
2. `@require_db` decorator catches database error
3. Route returns friendly error message with explanation
4. User sees: "Database temporarily unavailable"
5. "Auto-retry in 5 seconds..." countdown starts
6. User can click "Try Again" button
7. Database wakes up and page refreshes successfully

**Other Pages (No DB Required):**

1. User visits `/about`, `/faq`, `/terms`, `/contact`, `/privacy`
2. These routes don't have `@require_db` decorator
3. Pages render normally (no database queries)
4. User can continue browsing

**Database-Dependent Pages (Auth, Challenges, Competitions):**

1. User tries to log in
2. Route has `@require_db` decorator (via try-catch wrapper)
3. Database query fails during User lookup
4. Friendly error page rendered
5. User understands the issue and knows to wait/retry

---

## Implementation Details

### Routes by Database Requirement

**No Database Required (Always Available):**

- `/` (homepage - with graceful empty state)
- `/about`
- `/contact`
- `/faq`
- `/privacy`
- `/terms`
- `/static/*` (all static assets)
- `/healthz` (health check)

**Requires Database (Show Error If Down):**

- `/auth/login` - `@require_db` via try-catch
- `/auth/register` - try-catch wrapper
- `/challenges/*` - `@require_db`
- `/competitions/*` - `@require_db`
- `/admin/*` - `@require_db`
- `/host/*` - `@require_db`
- `/player/*` - `@require_db`

### Query Handling

**Before (Would Crash):**

```python
def index():
    total_users = db.session.query(func.count(User.id)).scalar()
    # If DB down: crashes with 500
```

**After (Graceful):**

```python
def get_platform_stats():
    try:
        total_users = db.session.query(func.count(User.id)).scalar() or 0
        return {'total_users': total_users, ...}
    except Exception as e:
        logger.warning(f"DB error: {e}")
        return {'total_users': 0, ...}  # Return defaults

def index():
    stats = get_platform_stats()  # Returns dict, never crashes
    return render_template('index.html',
        total_users=stats.get('total_users', 0) or 0)  # Safe access
```

---

## Configuration

No additional configuration needed. The system works automatically:

1. **Check Database Connection:**

   ```python
   from core.db_health import check_db_connection
   is_active = check_db_connection()  # True or False
   ```

2. **Custom Error Messages:**

   ```python
   from core.db_health import render_db_error
   return render_db_error("Custom message about what failed")
   ```

3. **Add to Routes:**

   ```python
   from core.db_health import require_db

   @my_bp.route('/endpoint')
   @require_db
   def my_endpoint():
       # Code here is wrapped with error handling
       return render_template(...)
   ```

---

## Logging

Database errors are logged with context:

```
[2026-02-02 10:15:33] WARNING [uuid-1234] [user:5|alice] core.db_health: Database query failed: (psycopg2.OperationalError) lost connection to server
```

Log files:

- `logs/app.log` - All logs including DB errors
- `logs/security.log` - Security-specific events

---

## Monitoring & Debugging

### Check Database Health

```python
# In Flask shell or script
from core.db_health import check_db_connection

if check_db_connection():
    print("✓ Database is active")
else:
    print("✗ Database is inactive")
```

### Force Test Error State

```python
# Temporarily disable database connection for testing
# Edit app.py DATABASE_URL to invalid value
# Visit /
# Should see friendly error message
# Restore DATABASE_URL when done
```

### View Error Logs

```bash
tail -f logs/app.log | grep -i database
```

---

## Best Practices for Route Implementation

### ✓ DO: Wrap Database Queries

```python
@my_bp.route('/data')
def get_data():
    try:
        return db.session.query(Model).all()
    except Exception as e:
        logger.error(f"DB error: {e}")
        return render_db_error()
```

### ✓ DO: Provide Safe Defaults

```python
def get_stats():
    try:
        count = db.session.query(func.count(Model.id)).scalar()
        return count if count is not None else 0
    except:
        return 0
```

### ✓ DO: Use @require_db Decorator

```python
from core.db_health import require_db

@my_bp.route('/endpoint')
@require_db
def endpoint():
    # Errors here are automatically caught
    return db.session.query(...).all()
```

### ✗ DON'T: Crash on Database Errors

```python
# BAD: Will show 500 error if DB is down
def get_data():
    return db.session.query(Model).all()  # No error handling
```

### ✗ DON'T: Ignore Errors Silently

```python
# BAD: User won't know what happened
def get_data():
    try:
        return db.session.query(Model).all()
    except:
        pass  # Silent failure
```

### ✗ DON'T: Return Incomplete Data

```python
# BAD: Mixing None with real data
def get_stats():
    users = db.session.query(User).all()  # Could be None
    return {'users': users}  # Template can't handle None
```

---

## Recovery Time Expectations

| Hosting Service   | Wake-Up Time  | Notes                              |
| ----------------- | ------------- | ---------------------------------- |
| Render.com        | 15-30 seconds | Auto-sleep after 30 min inactivity |
| Supabase Free     | 5-15 seconds  | Boots up quickly                   |
| Vercel PostgreSQL | Instant       | Always on, rarely sleeps           |
| Railway.app       | 10-20 seconds | Lightweight sleep mode             |

The auto-retry every 5 seconds means most users will see success after 1-2 attempts.

---

## Testing the Feature

### Test 1: Simulate Database Inactive

1. Edit `.env` and set `DATABASE_URL` to invalid value:

   ```
   DATABASE_URL=postgresql://invalid:pass@localhost/fake
   ```

2. Restart Flask: `flask run`

3. Visit pages:
   - `/about` - ✓ Works (no DB)
   - `/` - Shows database error page
   - `/login` - Shows database error page
   - Check for auto-retry countdown

4. Restore correct `DATABASE_URL` and restart

5. Refresh page - Should succeed after auto-retry

### Test 2: Verify Logging

1. With broken DB, visit homepage
2. Check `logs/app.log`:
   ```bash
   grep -i "database" logs/app.log
   ```
3. Should see warning about failed queries

### Test 3: Public Pages Work

1. With broken DB, verify these pages work:
   - `/` (shows empty stats, still displays layout)
   - `/about` (works perfectly)
   - `/faq` (works perfectly)
   - `/terms` (works perfectly)
   - `/contact` (works perfectly)
   - `/privacy` (works perfectly)

---

## Future Enhancements

1. **Database Health Widget**
   - Small status indicator on navbar
   - Shows "Database: Active" or "Reconnecting..."

2. **Progressive Load**
   - Homepage loads public content first
   - Database stats load asynchronously
   - Shows loading spinner for stats

3. **Scheduled Wake-Up**
   - Cron job that pings database every 20 minutes
   - Prevents sleep mode on production

4. **Connection Pooling Optimization**
   - Increase pool recycling for longer idle times
   - Add connection validation on checkout

5. **API Health Endpoint**
   - `/api/health` returns detailed status
   - Client-side monitoring script uses it

---

## Troubleshooting

### Q: Homepage still shows 500 error

**A:** Check that routes/main.py has `@require_db` decorator on index route and all query functions have try-catch blocks.

### Q: Database error message not appearing

**A:** Verify templates/errors/database_unavailable.html exists and error handler in app.py includes database keyword checking.

### Q: Auto-retry not working

**A:** Check that JavaScript in database_unavailable.html template runs (check browser console for errors).

### Q: Some queries still crash

**A:** Ensure all database queries have try-catch wrappers. Search for direct `.query()` calls without error handling.

### Q: Users seeing different errors

**A:** Some routes may still need @require_db decorator. Add it systematically to all DB-dependent routes.

---

## Summary

The database resilience system ensures:

✓ **Partial Availability**: Public pages always work  
✓ **Clear Communication**: Users understand what happened  
✓ **Automatic Recovery**: Auto-retry without user action  
✓ **Graceful Degradation**: App doesn't appear completely offline  
✓ **Better Experience**: Professional error messages instead of 500 errors

This approach is common in modern web apps and significantly improves perceived reliability on free hosting platforms.
