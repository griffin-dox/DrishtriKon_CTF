"""
Gunicorn configuration file for production deployment.

This runs database migrations once at server startup, before workers are created.
"""
import os
import logging
from app import create_app
from app.startup import initialize_application

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
    Perfect for running migrations - happens once, not per worker.
    """
    logger.info("=" * 60)
    logger.info("Gunicorn server starting - Running initialization...")
    logger.info("=" * 60)
    
    # Create app and run migrations
    app = create_app(os.getenv('FLASK_ENV', 'production'))
    
    if not initialize_application(app):
        logger.critical("=" * 60)
        logger.critical("INITIALIZATION FAILED - Cannot start server")
        logger.critical("=" * 60)
        raise RuntimeError("Application initialization failed - check logs above")
    
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
