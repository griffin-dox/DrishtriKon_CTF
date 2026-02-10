# Automatic Database Migration on Startup

## Overview

The application now automatically runs database migrations and verification on startup. This eliminates the need for pre-deployment commands in Render or other hosting platforms.

## How It Works

### Production (Render/Gunicorn)

When the WSGI server starts, the following happens automatically:

1. **Database Connectivity Check** - Verifies the database is accessible
2. **Run Migrations** - Executes `flask db upgrade` to apply pending migrations
3. **Schema Verification** - Confirms critical tables (Users, Challenges, Competitions) are accessible

If any step fails, the application **will not start** and logs will show the error.

### Development (Local)

When running `python run.py`:

```bash
# With automatic migrations (recommended)
python run.py

# Skip migrations (if you want manual control)
python run.py --no-migrate
```

## Files Modified

### New File: `app/startup.py`

Contains the initialization logic:

- `check_database_connectivity()` - DB health check
- `run_database_migrations()` - Runs Flask-Migrate upgrade
- `verify_database_schema()` - Tests critical tables
- `initialize_application()` - Orchestrates all checks

### Updated: `wsgi.py`

Production entry point now:

- Imports `initialize_application()`
- Runs initialization before serving requests
- Exits with code 1 if initialization fails

### Updated: `run.py`

Development entry point now:

- Runs initialization by default
- Supports `--no-migrate` flag to skip
- Shows clear startup banners and logs

## Deployment Impact

### Before (Render Configuration)

```yaml
# Needed pre-deployment commands (not supported by Render)
preDeployCommand: python scripts/migrate.py && python scripts/verify_db.py
```

### After (No Pre-Deployment Needed)

```yaml
# Just start the app - migrations run automatically!
startCommand: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 4
```

## Logging Output

On successful startup, you'll see:

```
[2026-02-11 00:00:00,000] INFO: ============================================================
[2026-02-11 00:00:00,001] INFO: Starting DrishtriKon CTF Platform
[2026-02-11 00:00:00,002] INFO: ============================================================
[2026-02-11 00:00:00,003] INFO: 🚀 Initializing application (production environment)
[2026-02-11 00:00:00,004] INFO: Step 1/3: Checking database connectivity...
[2026-02-11 00:00:00,100] INFO: ✓ Database connected (15 tables found)
[2026-02-11 00:00:00,101] INFO: Step 2/3: Running database migrations...
[2026-02-11 00:00:00,102] INFO: Current DB revision: a1b2c3d4e5f6
[2026-02-11 00:00:00,103] INFO: Running database migrations...
[2026-02-11 00:00:01,000] INFO: ✓ Migrations complete. Revision: a1b2c3d4e5f6
[2026-02-11 00:00:01,001] INFO: Step 3/3: Verifying database schema...
[2026-02-11 00:00:01,050] INFO: ✓ Database schema verified
[2026-02-11 00:00:01,051] INFO:   - Users: 5
[2026-02-11 00:00:01,052] INFO:   - Challenges: 10
[2026-02-11 00:00:01,053] INFO:   - Competitions: 3
[2026-02-11 00:00:01,054] INFO: ✓ Application initialization complete. Ready to serve requests.
[2026-02-11 00:00:01,055] INFO: ============================================================
[2026-02-11 00:00:01,056] INFO: Application ready to accept connections
[2026-02-11 00:00:01,057] INFO: ============================================================
```

On failure:

```
[2026-02-11 00:00:00,000] CRITICAL: ============================================================
[2026-02-11 00:00:00,001] CRITICAL: APPLICATION STARTUP FAILED
[2026-02-11 00:00:00,002] CRITICAL: Database initialization/migration failed.
[2026-02-11 00:00:00,003] CRITICAL: Fix the errors above and restart the application.
[2026-02-11 00:00:00,004] CRITICAL: ============================================================
# App exits with code 1, preventing deployment
```

## Rollback Safety

- Migrations run in transactions (where supported by DB)
- If migration fails, app won't start (prevents serving with broken schema)
- Manual rollback still possible: `flask db downgrade`

## Benefits

✅ **No Pre-Deployment Commands** - Works on Render, Heroku, AWS, etc.  
✅ **Atomic Deployments** - App won't start if DB is broken  
✅ **Clear Error Messages** - Logs show exactly what failed  
✅ **Development Friendly** - Optional auto-migrate in dev mode  
✅ **Production Safe** - Verifies schema before accepting traffic

## Troubleshooting

### Problem: App won't start, says "Migration failed"

**Solution**: Check logs for specific error. Common causes:

- Missing `DATABASE_URL` environment variable
- Database not accessible (firewall, credentials)
- Conflicting migration heads (run `flask db heads` locally)

### Problem: Want to skip migrations temporarily

**Development**:

```bash
python run.py --no-migrate
```

**Production**: Not recommended, but you can comment out the initialization in `wsgi.py`

### Problem: Need to run migrations manually

You can still use Flask-Migrate CLI:

```bash
flask db upgrade  # Apply migrations
flask db downgrade  # Rollback
flask db current  # Show current revision
```

## Legacy Scripts

The following scripts are **still available** for manual use:

- `scripts/migrate.py` - Standalone migration runner
- `scripts/verify_db.py` - Standalone verification

But they're **no longer required** for Render deployment!
