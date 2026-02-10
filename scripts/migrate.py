#!/usr/bin/env python
"""
Production-safe database migration runner for Render deployment.
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from flask_migrate import upgrade, current
from sqlalchemy import inspect as sa_inspect

# Create app instance
app = create_app(os.getenv('FLASK_ENV', 'production'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def check_database_health():
    """Verify database connectivity before running migrations."""
    try:
        with app.app_context():
            inspector = sa_inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"✓ Database connectivity check passed ({len(tables)} existing tables)")
            return True
    except Exception as e:
        logger.error(f"✗ Database health check failed: {e}")
        return False

def verify_migration_safety():
    """Check for unstaged migrations that could cause issues."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        alembic_cfg = Config(str(migrations_dir / 'alembic.ini'))
        script = ScriptDirectory.from_config(alembic_cfg)
        
        # Check if there are any head revisions
        heads = script.get_heads()
        if len(heads) > 1:
            logger.warning(f"⚠ Multiple migration heads detected: {heads}")
            logger.warning("This indicates branched migrations. Resolve before deploying.")
            return False
        
        logger.info("✓ Migration safety check passed")
        return True
    except Exception as e:
        logger.error(f"✗ Migration safety check failed: {e}")
        return False

def run_migrations(env):
    """Run pending migrations."""
    with app.app_context():
        try:
            current_rev = current()
            logger.info(f"Current database revision: {current_rev or 'None (fresh DB)'}")
            
            logger.info("Running migrations...")
            upgrade()
            
            new_rev = current()
            logger.info(f"✓ Migrations complete. New revision: {new_rev}")
            return True
        except Exception as e:
            logger.error(f"✗ Migration failed: {e}")
            logger.error("Deployment will be halted to prevent data corruption")
            return False

def main():
    env = os.getenv('FLASK_ENV', 'development')
    is_production = env == 'production'
    
    logger.info(f"🚀 Starting database migration process ({env} environment)")
    
    # Step 1: Health check
    if not check_database_health():
        logger.error("Database is not healthy. Aborting migrations.")
        return 1
    
    # Step 2: Verify migration safety
    if not verify_migration_safety():
        return 1
    
    # Step 3: Run migrations
    if not run_migrations(env):
        return 1
    
    logger.info(f"✓ Database migration process completed successfully")
    logger.info(f"Application is ready to start")
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
