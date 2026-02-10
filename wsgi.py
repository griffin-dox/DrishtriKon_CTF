"""
WSGI entry point for production deployment.

This file is used by WSGI servers like Gunicorn, uWSGI, or mod_wsgi.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 4
    uwsgi --http :8000 --wsgi-file wsgi.py --callable app
"""

import os
import sys
import logging
from app import create_app
from app.startup import initialize_application

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Create application instance
app = create_app(os.getenv('FLASK_ENV', 'production'))

# Only run initialization if NOT using Flask CLI development server
# Flask CLI sets FLASK_RUN_FROM_CLI or we check if we're the main module
is_flask_cli = os.getenv('FLASK_RUN_FROM_CLI') or os.getenv('WERKZEUG_RUN_MAIN')
is_production = not is_flask_cli

if is_production:
    # Run startup initialization (migrations + verification)
    # This happens once when the WSGI server loads the module
    logger.info("=" * 60)
    logger.info("Starting DrishtriKon CTF Platform")
    logger.info("=" * 60)

    if not initialize_application(app):
        logger.critical("=" * 60)
        logger.critical("APPLICATION STARTUP FAILED")
        logger.critical("Database initialization/migration failed.")
        logger.critical("Fix the errors above and restart the application.")
        logger.critical("=" * 60)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Application ready to accept connections")
    logger.info("=" * 60)
else:
    logger.info("Flask CLI detected - skipping automatic migrations")
    logger.info("Run 'python run.py' for automatic migrations, or 'flask db upgrade' manually")

if __name__ == "__main__":
    # This is only for debugging; use a proper WSGI server in production
    app.run()
