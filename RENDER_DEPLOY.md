# Render Deployment Configuration

## IMPORTANT: Update Your Render Service Settings

After pushing these changes, update your Render service configuration:

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
gunicorn wsgi:app -c gunicorn.conf.py
```

## What Changed

**Problem:**

- `flask-migrate upgrade()` hangs indefinitely when called from Gunicorn hooks
- Database migrations never complete, causing deployment timeouts
- Worker processes killed after port scan timeout (5-10 minutes)

**Solution:**

- Run migrations in a **subprocess** with timeout protection
- Uses `subprocess.run()` to execute `flask db upgrade` independently
- 3-minute timeout prevents infinite hanging
- Clean error reporting if migrations fail

## How It Works

### gunicorn.conf.py

The Gunicorn config file defines server hooks:

1. **`on_starting(server)`** - Runs ONCE when master process initializes
   - Step 1: Quick database connectivity check
   - Step 2: Run migrations via subprocess
     - Executes: `python -m flask db upgrade`
     - 180 second timeout (3 minutes)
     - Captures stdout/stderr for debugging
     - Raises RuntimeError if fails
   - Prevents bad deployments if migrations fail

2. **`when_ready(server)`** - Called after workers start
   - Logs server is ready to accept requests

3. **`on_exit(server)`** - Called on shutdown
   - Clean logging

### Initialization Flow

```
Gunicorn starts
  ↓
on_starting() hook runs
  ↓
Step 1: Check DB connectivity (quick SQLAlchemy inspector check)
  ↓
Step 2: Run migrations in subprocess
  - subprocess.run(["python", "-m", "flask", "db", "upgrade"])
  - 180 second timeout
  - Captures output
  ↓
Success? → Fork workers → Bind to port → Accept requests
Failure? → Raise RuntimeError → Exit code 1 → Render shows error
```

## Gunicorn Settings

Defined in `gunicorn.conf.py`:

- **Workers**: 4 (adjust based on Render plan)
- **Threads**: 2 per worker
- **Timeout**: 120s (for long requests)
- **Worker class**: sync (simple, reliable)
- **Bind**: `0.0.0.0:$PORT` (reads from Render env)
- **Logging**: stdout for access + error logs

## Testing Locally

### Option 1: Gunicorn with config (production-like)

```bash
# Set environment variables first
export DATABASE_URL="postgresql://..."
export SECRET_KEY="..."

# Run with Gunicorn config
gunicorn wsgi:app -c gunicorn.conf.py
```

### Option 2: Development server

```bash
python run.py  # Auto-runs migrations
```

### Option 3: Flask CLI (manual migrations)

```bash
flask db upgrade  # Run migrations
flask run         # Start dev server
```

## Migration Rollback

If you need to rollback a migration:

```bash
flask db downgrade
```

Then redeploy to apply the downgrade in production.

## Monitoring Deployment

### Successful Deployment Logs

```
[INFO] ============================================================
[INFO] Gunicorn server starting - Running initialization...
[INFO] ============================================================
[INFO] Step 1/2: Checking database connectivity...
[INFO] ✓ Database connected (23 tables found)
[INFO] Step 2/2: Running database migrations...
[INFO] Running migrations via subprocess (prevents hanging)...
[INFO] Migration subprocess output:
[INFO]   INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
[INFO]   INFO  [alembic.runtime.migration] Will assume transactional DDL.
[INFO] ✓ Migrations complete
[INFO] ============================================================
[INFO] Initialization complete - Server will now start workers
[INFO] ============================================================
[INFO] Starting gunicorn 25.0.3
[INFO] Listening at: http://0.0.0.0:21048
[INFO] Using worker: sync
[INFO] Booting worker with pid: 40
[INFO] ============================================================
[INFO] Gunicorn server ready - Listening on 0.0.0.0:21048
[INFO] Workers: 4, Threads: 2
[INFO] ============================================================
```

### Failed Deployment Logs

If database connection fails:

```
[CRITICAL] ✗ Database connection failed: ...
RuntimeError: Database connection failed
==> Exited with status 1
```

If migrations fail:

```
[ERROR] Migration failed with exit code 1
[ERROR] STDOUT: ...
[ERROR] STDERR: ...
RuntimeError: Migration subprocess failed
==> Exited with status 1
```

If migrations timeout (>3 minutes):

```
[CRITICAL] ✗ Migration timeout after 3 minutes - this should not happen
RuntimeError: Migration subprocess timed out
==> Exited with status 1
```

## Environment Variables (Required)

Ensure these are set in Render environment:

- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Flask secret key
- `SESSION_SECRET` - Session encryption key
- `FLASK_ENV=production`
- `MAIL_USERNAME`, `MAIL_PASSWORD` - Email credentials
- `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY` - reCAPTCHA keys
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - S3 credentials
- `S3_BUCKET_NAME`, `S3_ENDPOINT_URL` - S3 config

## Advantages of This Approach

✅ **Pure Python** - No bash scripts, works on any platform  
✅ **Runs Once** - Migrations happen in master process, not per-worker  
✅ **No Timeouts** - Server hook runs before workers start  
✅ **Safe Failures** - Bad migrations prevent deployment  
✅ **Clean Logging** - Detailed step-by-step initialization logs  
✅ **Gunicorn Native** - Uses built-in server hooks (standard pattern)
