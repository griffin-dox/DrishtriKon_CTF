"""
Gunicorn configuration file for production deployment.

This runs database migrations once at server startup, before workers are created.
Uses subprocess to run migrations to avoid flask-migrate hanging issues.
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

# Gunicorn configuration
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = 4
threads = 2
timeout = 120
worker_class = 'sync'
accesslog = '-'
errorlog = '-'
loglevel = 'info'


def on_starting(server):
    """
    Server hook: Called just before the master process is initialized.
    Runs migrations in a subprocess to avoid flask-migrate hanging issues.
    """
    import subprocess
    import sys
    
    logger.info("=" * 60)
    logger.info("Gunicorn server starting - Running initialization...")
    logger.info("=" * 60)
    
    # Create app for connectivity check only
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    # Step 1: Quick connectivity check
    logger.info("Step 1/2: Checking database connectivity...")
    from app.extensions import db
    from sqlalchemy import inspect as sa_inspect
    
    try:
        with app.app_context():
            inspector = sa_inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"✓ Database connected ({len(tables)} tables found)")
    except Exception as e:
        logger.critical(f"✗ Database connection failed: {e}")
        raise RuntimeError("Database connection failed")
    
    # Step 2: Run migrations in subprocess (handles hanging gracefully)
    logger.info("Step 2/2: Running database migrations...")
    logger.info("Running migrations via subprocess (prevents hanging)...")
    
    try:
        # Run flask db upgrade in subprocess with timeout
        process = subprocess.run(
            [sys.executable, "-m", "flask", "db", "upgrade"],
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout
            cwd=os.getcwd()
        )
        
        if process.returncode != 0:
            logger.error(f"Migration failed with exit code {process.returncode}")
            logger.error(f"STDOUT: {process.stdout}")
            logger.error(f"STDERR: {process.stderr}")
            raise RuntimeError("Migration subprocess failed")
        
        logger.info("Migration subprocess output:")
        for line in process.stdout.splitlines():
            logger.info(f"  {line}")
        
        logger.info("✓ Migrations complete")
        
    except subprocess.TimeoutExpired:
        logger.critical("✗ Migration timeout after 3 minutes - this should not happen")
        raise RuntimeError("Migration subprocess timed out")
    except Exception as e:
        logger.critical(f"✗ Migration subprocess failed: {e}")
        raise RuntimeError(f"Migration failed: {e}")
    
    logger.info("=" * 60)
    logger.info("Initialization complete - Server will now start workers")
    logger.info("=" * 60)


def when_ready(server):
    """Called just after the server is started."""
    logger.info("=" * 60)
    logger.info(f"Gunicorn server ready - Listening on {bind}")
    logger.info(f"Workers: {workers}, Threads: {threads}")
    logger.info("=" * 60)


def on_exit(server):
    """Called just before exiting Gunicorn."""
    logger.info("Gunicorn server shutting down...")
