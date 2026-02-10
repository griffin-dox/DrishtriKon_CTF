"""
WSGI entry point for production deployment.

This file is used by WSGI servers like Gunicorn, uWSGI, or mod_wsgi.

Usage:
    gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 4
    uwsgi --http :8000 --wsgi-file wsgi.py --callable app
"""

"""
WSGI entry point for production deployment.

When using Gunicorn with gunicorn.conf.py:
  - Migrations run once in on_starting() hook (before workers fork)
  - This file just exports the app object

When using Flask CLI directly:
  - Use 'python run.py' for auto-migrations
  - Or 'flask db upgrade' manually then 'flask run'
"""
import os
import logging

# Configure logging for Flask CLI mode
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

from app import create_app

# Create application instance
app = create_app(os.getenv('FLASK_ENV', 'production'))

# Note for Flask CLI users
if os.getenv('FLASK_RUN_FROM_CLI') or os.getenv('WERKZEUG_RUN_MAIN'):
    logger.info("Flask CLI detected - use 'python run.py' for auto-migrations")

if __name__ == "__main__":
    # This is only for debugging; use a proper WSGI server in production
    app.run()
