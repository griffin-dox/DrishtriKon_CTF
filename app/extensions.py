"""
Flask extensions initialization.
Extensions are initialized here to avoid circular imports.
They are attached to the app in the application factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_mail import Mail
from flask_caching import Cache

# Initialize extensions (without app binding)
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()
mail = Mail()
cache = Cache()


def init_extensions(app):
    """Initialize Flask extensions with app instance."""
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    cache.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    login_manager.session_protection = "strong"
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user with connection error handling.
        
        If database is temporarily unavailable (connection pool exhausted),
        return None to use AnonymousUser instead of crashing with 500 error.
        """
        from app.models import User
        import logging
        from sqlalchemy.exc import OperationalError
        from time import sleep
        
        logger = logging.getLogger(__name__)
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                return User.query.get(int(user_id))
            except OperationalError as e:
                # Connection pool exhausted or database unavailable
                if 'remaining connection slots are reserved' in str(e) or 'too many connections' in str(e):
                    logger.warning(f"Database connection pool exhausted, attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        sleep(0.5)  # Brief wait before retry
                        continue
                    else:
                        # Last attempt failed - log and return None (AnonymousUser)
                        logger.error(f"Failed to load user {user_id} after {max_retries} attempts")
                        return None
                else:
                    # Other operational error
                    logger.error(f"Operational error loading user {user_id}: {e}")
                    return None
            except Exception as e:
                # Any other error - return None to use AnonymousUser
                logger.error(f"Unexpected error loading user {user_id}: {e}")
                return None
