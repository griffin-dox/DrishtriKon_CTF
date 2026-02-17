"""
Application configuration classes.
Supports development, production, and testing environments.
"""

import os
import secrets
from datetime import timedelta


class Config:
    """Base configuration with common settings."""
    
    # Flask core
    SECRET_KEY = os.getenv('SECRET_KEY')
    SESSION_SECRET = os.getenv('SESSION_SECRET')
    
    # Environment
    ENV = os.getenv('FLASK_ENV', 'production')
    
    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=1800)  # 30 minutes
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 180,  # Reduced from 300 to recycle connections faster
        "pool_pre_ping": True,  # Test connection before using
        "pool_size": 10,  # Reduced from 20 to use fewer connections
        "max_overflow": 10,  # Reduced from 30 to limit connection spikes
        "pool_timeout": 15,  # Reduced from 30 to fail faster if no conn available
        "echo": False,
        "connect_args": {
            "connect_timeout": 10,  # Connection timeout in seconds
            "application_name": "drishtrikon_ctf",  # Identify connection in DB logs
        },
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email (Gmail SMTP)
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
    MAIL_MAX_EMAILS = 5
    MAIL_ASCII_ATTACHMENTS = False
    
    # reCAPTCHA
    RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
    RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
    RECAPTCHA_ENABLED = bool(RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY)
    
    # Cache
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Paths (relative to instance root)
    UPLOAD_FOLDER = os.path.join(os.getcwd(), "var", "uploads")
    LOG_DIR = os.path.join(os.getcwd(), "var", "logs")
    CACHE_DIR = os.path.join(os.getcwd(), "var", "cache")
    
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_PROFILE_BUCKET = os.getenv("AWS_PROFILE_BUCKET")  # For user/team profile pictures
    AWS_CHALLENGE_BUCKET = os.getenv("AWS_CHALLENGE_BUCKET")  # For challenge files
    S3_ENABLED = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and 
                     (AWS_PROFILE_BUCKET or AWS_CHALLENGE_BUCKET))
    
    # External services
    FORMCARRY_ENDPOINT = os.getenv("FORMCARRY_ENDPOINT")
    
    @staticmethod
    def validate():
        """Validate required configuration."""
        required = ['SECRET_KEY', 'SESSION_SECRET', 'SQLALCHEMY_DATABASE_URI']
        missing = [key for key in required if not getattr(Config, key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


class DevelopmentConfig(Config):
    """Development environment configuration."""
    
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    
    # Cache
    CACHE_TYPE = 'simple'
    
    # Email debug
    MAIL_DEBUG = True
    
    # Logging
    LOG_LEVEL = 'DEBUG'
    
    @staticmethod
    def validate():
        """In development, generate secrets if missing."""
        if not Config.SECRET_KEY:
            Config.SECRET_KEY = secrets.token_hex(32)
            print("⚠️  Generated SECRET_KEY for development")
        
        if not Config.SESSION_SECRET:
            Config.SESSION_SECRET = secrets.token_hex(32)
            print("⚠️  Generated SESSION_SECRET for development")
        
        if not Config.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URL must be set even in development")


class ProductionConfig(Config):
    """Production environment configuration."""
    
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    
    # Cache
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'filesystem')
    CACHE_THRESHOLD = 1000
    
    # Email
    MAIL_DEBUG = False
    
    # Logging
    LOG_LEVEL = 'INFO'
    
    @staticmethod
    def validate():
        """Strict validation for production."""
        Config.validate()
        
        # Ensure secrets are strong
        if len(Config.SECRET_KEY or '') < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        
        if len(Config.SESSION_SECRET or '') < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters in production")


class TestConfig(Config):
    """Testing environment configuration."""
    
    DEBUG = False
    TESTING = True
    SESSION_COOKIE_SECURE = False
    
    # Use in-memory SQLite for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # SQLite doesn't support pooling, override with empty options
    SQLALCHEMY_ENGINE_OPTIONS = {
        'echo': False,
    }
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Cache
    CACHE_TYPE = 'simple'
    
    # Email (don't send real emails in tests)
    MAIL_SUPPRESS_SEND = True
    
    @staticmethod
    def validate():
        """Minimal validation for tests."""
        if not Config.SECRET_KEY:
            Config.SECRET_KEY = 'test-secret-key'
        if not Config.SESSION_SECRET:
            Config.SESSION_SECRET = 'test-session-secret'


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': ProductionConfig
}


def get_config(env=None):
    """Get configuration class for environment."""
    if env is None:
        env = os.getenv('FLASK_ENV', 'production')
    
    config_class = config.get(env, config['default'])
    config_class.validate()
    return config_class
