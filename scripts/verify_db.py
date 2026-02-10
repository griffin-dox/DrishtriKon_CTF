#!/usr/bin/env python
"""
Post-migration verification to ensure database is in good state.
"""
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app
from app.extensions import db
from app.models import User, Challenge, Competition

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create app instance
app = create_app(os.getenv('FLASK_ENV', 'development'))

def verify_schema():
    """Verify critical tables exist and are accessible."""
    with app.app_context():
        try:
            # Test query on critical tables
            user_count = User.query.count()
            challenge_count = Challenge.query.count()
            competition_count = Competition.query.count()
            
            logger.info(f"✓ Schema verification passed")
            logger.info(f"  - Users: {user_count}")
            logger.info(f"  - Challenges: {challenge_count}")
            logger.info(f"  - Competitions: {competition_count}")
            
            return True
        except Exception as e:
            logger.error(f"✗ Schema verification failed: {e}")
            return False

def main():
    logger.info("🔍 Running post-migration verification...")
    
    if not verify_schema():
        logger.error("Post-migration verification failed!")
        return 1
    
    logger.info("✓ All verifications passed. Application ready to boot!")
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
