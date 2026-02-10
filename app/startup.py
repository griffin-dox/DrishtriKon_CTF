"""
Application startup initialization.

Handles database migrations and verification before app starts.
"""
import os
import sys
import logging
from pathlib import Path
from flask import Flask
from flask_migrate import upgrade, current
from sqlalchemy import inspect as sa_inspect

logger = logging.getLogger(__name__)


def check_database_connectivity(app: Flask) -> bool:
    """Verify database is accessible."""
    try:
        from app.extensions import db
        with app.app_context():
            inspector = sa_inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"✓ Database connected ({len(tables)} tables found)")
            return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False


def run_database_migrations(app: Flask) -> bool:
    """Run pending database migrations."""
    try:
        logger.info("Entering run_database_migrations...")
        with app.app_context():
            logger.info("Inside app context, about to run upgrade()...")
            
            # Run migrations using Flask-Migrate
            # This automatically configures Alembic and runs upgrade
            upgrade()
            
            logger.info("upgrade() completed successfully")
            logger.info("✓ Migrations complete")
            return True
            
    except Exception as e:
        logger.error(f"✗ Migration failed with exception: {e}", exc_info=True)
        logger.error("This is a critical error - app startup halted")
        return False
    finally:
        logger.info("Exiting run_database_migrations...")


def verify_database_schema(app: Flask) -> bool:
    """Verify critical tables are accessible using raw SQL to avoid ORM issues."""
    try:
        from app.extensions import db
        from sqlalchemy import text
        
        with app.app_context():
            # Use raw SQL queries to avoid triggering hybrid properties or ORM issues
            user_count = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar()
            challenge_count = db.session.execute(text("SELECT COUNT(*) FROM challenges")).scalar()
            competition_count = db.session.execute(text("SELECT COUNT(*) FROM competitions")).scalar()
            
            logger.info("✓ Database schema verified")
            logger.info(f"  - Users: {user_count}")
            logger.info(f"  - Challenges: {challenge_count}")
            logger.info(f"  - Competitions: {competition_count}")
            return True
            
    except Exception as e:
        logger.error(f"✗ Schema verification failed: {e}", exc_info=True)
        return False


def initialize_application(app: Flask) -> bool:
    """
    Run all startup checks and initialization tasks.
    
    Returns:
        bool: True if initialization succeeded, False otherwise
    """
    env = os.getenv('FLASK_ENV', 'production')
    logger.info(f"🚀 Initializing application ({env} environment)")
    
    # Step 1: Check database connectivity
    logger.info("Step 1/3: Checking database connectivity...")
    if not check_database_connectivity(app):
        logger.error("Cannot connect to database. Check DATABASE_URL configuration.")
        return False
    logger.info("Step 1/3: ✓ Database connectivity check passed")
    
    # Step 2: Run migrations
    logger.info("Step 2/3: Running database migrations...")
    if not run_database_migrations(app):
        logger.error("Database migration failed. App cannot start safely.")
        return False
    logger.info("Step 2/3: ✓ Database migrations completed")
    
    # Step 3: Verify schema
    logger.info("Step 3/3: Verifying database schema...")
    if not verify_database_schema(app):
        logger.error("Database schema verification failed. Check migrations.")
        return False
    logger.info("Step 3/3: ✓ Database schema verified")
    
    logger.info("=" * 60)
    logger.info("✓ Application initialization complete. Ready to serve requests.")
    logger.info("=" * 60)
    return True
    return True
