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

**Old Approach** (Broken):

- Migrations ran inside `wsgi.py` during module import
- Gunicorn worker timeout (30s) killed long-running migrations
- App would exit with status 1 after migrations started

**New Approach** (Fixed):

- Migrations run in Gunicorn's `on_starting()` server hook
- Runs once before workers fork (not per-worker)
- No worker timeout interference
- Uses `app/startup.py` initialization logic
- Pure Python, no bash scripts needed

## How It Works

### gunicorn.conf.py

The Gunicorn config file defines server hooks:

1. **`on_starting(server)`** - Runs ONCE when master process initializes
   - Creates Flask app
   - Runs `initialize_application()` (migrations + verification)
   - Raises error if initialization fails (prevents bad deployment)

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
Create Flask app (production mode)
  ↓
initialize_application(app):
  Step 1: Check DB connectivity
  Step 2: Run migrations (flask-migrate upgrade)
  Step 3: Verify schema (raw SQL queries)
  ↓
Success? → Fork workers → Accept requests
Failure? → Raise RuntimeError → Exit with error
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
[INFO] Gunicorn server starting - Running initialization...
[INFO] 🚀 Initializing application (Production environment)
[INFO] Step 1/3: Checking database connectivity...
[INFO] ✓ Database connected (23 tables found)
[INFO] Step 1/3: ✓ Database connectivity check passed
[INFO] Step 2/3: Running database migrations...
[INFO] Entering run_database_migrations...
[INFO] Inside app context, about to run upgrade()...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
[INFO] upgrade() completed successfully
[INFO] ✓ Migrations complete
[INFO] Exiting run_database_migrations...
[INFO] Step 2/3: ✓ Database migrations completed
[INFO] Step 3/3: Verifying database schema...
[INFO] ✓ Database schema verified
[INFO]   - Users: X
[INFO]   - Challenges: Y
[INFO]   - Competitions: Z
[INFO] Step 3/3: ✓ Database schema verified
[INFO] ✓ Application initialization complete. Ready to serve requests.
[INFO] Initialization complete - Server will now start workers
[INFO] Starting gunicorn 25.0.3
[INFO] Listening at: http://0.0.0.0:XXXXX
[INFO] Gunicorn server ready - Listening on 0.0.0.0:XXXXX
```

### Failed Deployment Logs

If initialization fails:

```
[ERROR] ✗ Migration failed with exception: ...
[CRITICAL] INITIALIZATION FAILED - Cannot start server
RuntimeError: Application initialization failed
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
