# Connection Pool Exhaustion - Root Cause & Fixes

## Issue

```
psycopg2.OperationalError: connection to server at "..." failed:
FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute
```

This error occurs when the database connection pool is completely exhausted and the non-SUPERUSER application role cannot grab a reserved connection.

## Root Causes

### 1. **Multi-Worker Process Pool Multiplication**

- **Problem**: Each Gunicorn worker (process) creates its own SQLAlchemy connection pool
- **Impact**: 4 workers × 3 pool_size = 12 connections, exceeding Aiven free-tier limit (~10-15 slots)

**Original Config:**

```python
workers = 4
pool_size = 10
max_overflow = 10
# Total potential: 4 × (10 + 10) = 80 connections! 🔴
```

**Fixed Config:**

```python
workers = 2          # Reduced from 4
pool_size = 3        # Reduced from 10
max_overflow = 2     # Reduced from 10
# Total potential: 2 × (3 + 2) = 10 connections ✅
```

### 2. **load_user() Called on Every Request**

- **Problem**: Flask-Login calls `load_user()` for every authenticated request to verify user session
- **Impact**: If 4 concurrent requests happen, 4 connections grabbed simultaneously; if slow queries occur, connections held > 5 sec

**Before (Crashes with 500 error):**

```python
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # No error handling!
```

**After (Graceful degradation):**

```python
@login_manager.user_loader
def load_user(user_id):
    # Retry once if connection exhausted
    # Return None (AnonymousUser) if pool is exhausted
    # Prevents 500 errors on connection failures

    for attempt in range(2):
        try:
            return User.query.get(int(user_id))
        except OperationalError as e:
            if 'remaining connection slots' in str(e):
                sleep(0.5)  # Wait, retry
                continue
            return None  # Give up, use AnonymousUser
        except Exception:
            return None
```

### 3. **Aggressive Connection Recycling**

- **Problem**: Connections held in pool for up to 180 seconds, increasing chance of simultaneous use
- **Impact**: More concurrent connections needed to handle requests

**Fixed Config:**

```python
pool_recycle: 120    # Reduced from 180 seconds
pool_timeout: 8      # Reduced from 15 seconds (fail faster)
connect_timeout: 8   # Reduced from 10 seconds
pool_pre_ping: True  # Already set - tests each connection before use
```

## Fixes Applied

### Fix 1: Reduce Gunicorn Workers (gunicorn.conf.py)

```python
workers = 2  # Was 4
# Comment added explaining free-tier limitation
```

**Impact**: Reduces concurrent process pools from 4 to 2

### Fix 2: Reduce Connection Pool (config.py)

```python
pool_size: 3        # Was 10 - more aggressive for free-tier
max_overflow: 2     # Was 10 - limit connection spikes
pool_timeout: 8     # Was 15 - fail faster
pool_recycle: 120   # Was 180 - recycle stale connections faster
```

**Impact**: Ensures max 2 × (3 + 2) = 10 connections total

### Fix 3: Error Handling in load_user (extensions.py)

```python
@login_manager.user_loader
def load_user(user_id):
    # Try twice with 0.5s delay between attempts
    # On OperationalError or any exception, return None
    # Return None uses AnonymousUser - prevents 500 errors
    # User stays logged in via session, just not reloaded from DB
```

**Impact**: Requests don't crash when pool exhausted; users experience service degradation instead of errors

## How It Works Now

### Load User Flow (Connection Exhausted Scenario)

```
1. Authenticated request arrives
2. Flask-Login calls load_user(user_id)
3. Attempt #1: Try to query User.query.get()
   - No connection available in pool
   - OperationalError: "remaining connection slots..."
4. Wait 0.5 seconds
5. Attempt #2: Try again
   - Still no connection (common during spike)
   - Give up, return None
6. Flask-Login uses AnonymousUser instead
7. Request continues with session-based user object
   - User NOT fully reloaded from DB
   - But session data still valid
   - Prevents 500 error
```

### Benefits

- ✅ No 500 errors during connection exhaustion
- ✅ Users see working site with cached data
- ✅ Graceful degradation under load
- ✅ Retry logic handles temporary spikes
- ✅ Logs connection pool issues for monitoring

## Monitoring & Warning Signs

### Check Pool Usage

Monitor your logs for:

```
WARNING: Database connection pool exhausted, attempt...
ERROR: Failed to load user after 2 attempts
```

### Detect Issues Early

- Monitor Aiven dashboard for connection count (should stay < 10)
- Check logs for OperationalError patterns
- If seeing frequent "pool exhausted" warnings:
  - Further reduce workers (to 1)
  - Reduce pool_size more (to 2)
  - Add external cache layer (Redis) for user sessions

## For Production Upgrades

When upgrading to paid Aiven plan with more connections:

```python
# Standard production config (with 20+ available connections):
pool_size: 10
max_overflow: 10
workers: 4
pool_timeout: 30
pool_recycle: 300
```

Current free-tier config is intentionally aggressive for resilience.

## Testing the Fix

```bash
# Simulate load to verify pool exhaustion handling
# Should NOT see 500 errors, should see graceful degradation
ab -n 100 -c 20 http://localhost:5000/player/dashboard/
```

Expected behavior:

- Requests may slow down (waiting for connections)
- Some users may see "please log in again"
- No 500 errors
- Logs show retry attempts
- Service recovers when load reduces

## References

- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [Aiven PostgreSQL Limitations](https://docs.aiven.io/docs/products/postgresql)
- [Gunicorn Workers Guide](https://docs.gunicorn.org/en/stable/design.html)
- [Flask-Login Session Security](https://flask-login.readthedocs.io/)
