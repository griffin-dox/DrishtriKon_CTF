"""
Development server entry point.

This file replaces main.py and provides a clean entry point
for local development with auto-reload and debugging.

Usage:
    python run.py                    # Run with auto-migrations
    python run.py --no-migrate       # Skip migrations
    flask run                        # Flask CLI (manual migration required)
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

# Create application instance for development
app = create_app('development')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    
    # Check if migrations should be skipped
    skip_migrate = '--no-migrate' in sys.argv or '--skip-migrate' in sys.argv
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║         DrishtriKon CTF Platform - Development          ║
╠══════════════════════════════════════════════════════════╣
║  Server: http://localhost:{port}                            ║
║  Debug:  {'Enabled' if debug else 'Disabled'}                                        ║
║  Env:    Development                                    ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Run startup initialization unless --no-migrate is specified
    if not skip_migrate:
        logger.info("Running startup initialization...")
        if not initialize_application(app):
            logger.error("=" * 60)
            logger.error("Startup initialization failed!")
            logger.error("Fix the errors above or run with --no-migrate")
            logger.error("=" * 60)
            sys.exit(1)
        logger.info("Startup initialization complete.\n")
    else:
        logger.warning("Skipping migrations (--no-migrate flag set)")
        logger.warning("Make sure to run 'flask db upgrade' manually!\n")
    
    app.run(host="0.0.0.0", port=port, debug=debug)
