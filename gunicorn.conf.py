"""
Gunicorn configuration file for production deployment.

This runs database migrations once at server startup, before workers are created.
Uses subprocess to run migrations to avoid flask-migrate hanging issues.

Render-optimized: Binds to PORT environment variable (default 10000 on Render)
"""
import os
import logging
from app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# Port Configuration for Render
# ============================================================
# Render sets PORT environment variable (default: 10000)
# Must bind to 0.0.0.0 for Render to route traffic correctly
PORT = os.getenv('PORT', '10000')  # Changed default to 10000 for Render
bind = f"0.0.0.0:{PORT}"

# ============================================================
# Gunicorn worker configuration
# ============================================================
workers = 4
threads = 2
timeout = 120
worker_class = 'sync'
accesslog = '-'
errorlog = '-'
loglevel = 'info'
keepalive = 5  # Close idle connections after 5s to free resources


def on_starting(server):
    """
    Server hook: Called just before the master process is initialized.
    Runs migrations in a subprocess to avoid flask-migrate hanging issues.
    Critical for Render deployment success.
    """
    import subprocess
    import sys
    
    logger.info("=" * 70)
    logger.info("🚀 GUNICORN INITIALIZATION - Render Compatible Mode")
    logger.info("=" * 70)
    logger.info(f"  Environment: {os.getenv('FLASK_ENV', 'production').upper()}")
    logger.info(f"  Port: {PORT} (from PORT env var)")
    logger.info(f"  Bind Address: {bind}")
    logger.info(f"  Workers: {workers} | Threads: {threads}")
    logger.info("=" * 70)
    
    # Create app for connectivity check only
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    # Step 1: Database connectivity check (CRITICAL)
    logger.info("📋 Step 1/3: Checking database connectivity...")
    from app.extensions import db
    from sqlalchemy import inspect as sa_inspect
    
    try:
        with app.app_context():
            inspector = sa_inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"   ✓ Database connected ({len(tables)} tables)")
    except Exception as e:
        logger.critical(f"   ✗ Database connection FAILED: {e}")
        logger.critical("   Deployment will be halted.")
        raise RuntimeError("Database connection failed")
    
    # Step 2: Database migrations (CRITICAL)
    logger.info("📋 Step 2/3: Running database migrations...")
    logger.info("   Executing: python -m flask db upgrade")
    
    try:
        process = subprocess.run(
            [sys.executable, "-m", "flask", "db", "upgrade"],
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout
            cwd=os.getcwd()
        )
        
        if process.returncode != 0:
            logger.error(f"   ✗ Migration failed with exit code {process.returncode}")
            if process.stdout:
                logger.error("   STDOUT:")
                for line in process.stdout.splitlines():
                    logger.error(f"     {line}")
            if process.stderr:
                logger.error("   STDERR:")
                for line in process.stderr.splitlines():
                    logger.error(f"     {line}")
            raise RuntimeError("Migration subprocess failed")
        
        if process.stdout:
            for line in process.stdout.splitlines():
                if line.strip():
                    logger.info(f"   {line}")
        
        logger.info("   ✓ Migrations completed successfully")
        
    except subprocess.TimeoutExpired:
        logger.critical("   ✗ Migration timeout (exceeded 3 minutes)")
        logger.critical("   This suggests database locks or connectivity issues.")
        raise RuntimeError("Migration subprocess timed out")
    except Exception as e:
        logger.critical(f"   ✗ Migration subprocess failed: {e}")
        raise RuntimeError(f"Migration failed: {e}")
    
    # Step 3: Warmup check
    logger.info("📋 Step 3/3: Warmup check...")
    try:
        with app.app_context():
            # Quick application boot to ensure factories work
            logger.info("   ✓ Application boot successful")
    except Exception as e:
        logger.critical(f"   ✗ Application boot failed: {e}")
        raise RuntimeError("Application boot failed")
    
    logger.info("=" * 70)
    logger.info("✅ Initialization complete - Server will now start workers")
    logger.info(f"   → Gunicorn will listen on 0.0.0.0:{PORT}")
    logger.info(f"   → Render will route traffic to this port")
    logger.info("=" * 70)


def when_ready(server):
    """
    Called just after the server is started and ready to accept requests.
    This is the signal for Render to consider deployment successful.
    """
    logger.info("=" * 70)
    logger.info("✅ GUNICORN SERVER READY")
    logger.info("=" * 70)
    logger.info(f"  Listening on: 0.0.0.0:{PORT}")
    logger.info(f"  Workers: {workers} | Threads: {threads} | Timeout: {timeout}s")
    logger.info(f"  Ready to accept requests")
    logger.info("=" * 70)


def on_exit(server):
    """Called just before exiting Gunicorn."""
    logger.info("🛑 Gunicorn server shutting down...")
