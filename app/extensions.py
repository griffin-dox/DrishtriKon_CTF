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
        from app.models import User
        return User.query.get(int(user_id))
