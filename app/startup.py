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
        from app.extensions import db
        from alembic.script import ScriptDirectory
        from alembic.config import Config
        
        with app.app_context():
            # Get migration config
            migrations_dir = Path(__file__).parent.parent / 'migrations'
            alembic_cfg = Config(str(migrations_dir / 'alembic.ini'))
            alembic_cfg.set_main_option('script_location', str(migrations_dir))
            
            # Get current revision from database
            script = ScriptDirectory.from_config(alembic_cfg)
            
            # Run migrations
            logger.info("Running database migrations...")
            upgrade()
            
            logger.info(f"✓ Migrations complete")
            return True
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}", exc_info=True)
        logger.error("This is a critical error - app startup halted")
        return False


def verify_database_schema(app: Flask) -> bool:
    """Verify critical tables are accessible."""
    try:
        from app.models import User, Challenge, Competition
        
        with app.app_context():
            # Test queries on critical tables
            user_count = User.query.count()
            challenge_count = Challenge.query.count()
            competition_count = Competition.query.count()
            
            logger.info(f"✓ Database schema verified")
            logger.info(f"  - Users: {user_count}")
            logger.info(f"  - Challenges: {challenge_count}")
            logger.info(f"  - Competitions: {competition_count}")
            return True
    except Exception as e:
        logger.error(f"✗ Schema verification failed: {e}")
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
    
    # Step 2: Run migrations
    logger.info("Step 2/3: Running database migrations...")
    if not run_database_migrations(app):
        logger.error("Database migration failed. App cannot start safely.")
        return False
    
    # Step 3: Verify schema
    logger.info("Step 3/3: Verifying database schema...")
    if not verify_database_schema(app):
        logger.error("Database schema verification failed. Check migrations.")
        return False
    
    logger.info("✓ Application initialization complete. Ready to serve requests.")
    return True
