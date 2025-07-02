import os
import logging
from flask import request, session, g
from markupsafe import Markup
from functools import wraps
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security headers configuration
# Add your CDN domains below if you use others
SECURITY_HEADERS = {
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://code.jquery.com https://cdnjs.cloudflare.com "
        "https://pagead2.googlesyndication.com https://kit.fontawesome.com "
        "https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/ "
        "https://googleads.g.doubleclick.net https://ep2.adtrafficquality.google https://www.googletagmanager.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com "
        "https://use.fontawesome.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://fonts.gstatic.com https://fonts.googleapis.com https://cdnjs.cloudflare.com https://use.fontawesome.com; "
        "frame-src https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/ https://googleads.g.doubleclick.net https://ep2.adtrafficquality.google; "
        "connect-src *; "
        "report-uri /csp-violation-report-endpoint/;"
    ),
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
}

def init_security(app):
    """Initialize security settings for the application"""
    # Set secure cookie settings
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Set session settings
    app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True
    
    # Generate and set secret key if not set
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = secrets.token_hex(32)
    
    # Add security headers middleware
    @app.after_request
    def add_security_headers(response):
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

def sanitize_timestamp(timestamp):
    """Sanitize timestamp to prevent XSS"""
    if isinstance(timestamp, (int, float)):
        return timestamp
    try:
        return float(timestamp)
    except (ValueError, TypeError):
        return 0.0

def check_secure_connection():
    """Check if the connection is secure"""
    if not request.is_secure and os.getenv('FLASK_ENV') == 'production':
        logger.warning(f"Insecure connection attempt to {request.path}")
        return False
    return True

def validate_origin():
    """Validate request origin"""
    if request.method == 'POST':
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            logger.warning(f"Invalid origin: {origin}")
            return False
    return True