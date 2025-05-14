import os
import time
import logging
from datetime import datetime, timedelta
from flask import session, request, g, redirect
from functools import wraps
from werkzeug.security import generate_password_hash

# Configure logging
session_logger = logging.getLogger('session_security')
session_logger.setLevel(logging.INFO)

# Session security constants
SESSION_TIMEOUT = 1800  # 30 minutes
SESSION_ABSOLUTE_TIMEOUT = 86400  # 24 hours
SESSION_ROTATION_INTERVAL = 300  # 5 minutes
MAX_SESSIONS_PER_USER = 3

def init_session_security(app):
    """Initialize session security settings"""
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=SESSION_TIMEOUT)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Remove all custom session security key logic
    # Optionally, you can keep a simple session timeout check if desired
    @app.before_request
    def check_session_security():
        # Exclude static files from session security
        if request.path.startswith('/static/'):
            return None
        # Exclude all requests to login, register, verify-otp, resend-otp, and logout
        if request.path in ['/login', '/register', '/verify-otp', '/resend-otp', '/logout']:
            return None
        # Optionally, implement a simple session timeout check
        # Example:
        # if 'last_active' in session and time.time() - session['last_active'] > SESSION_TIMEOUT:
        #     session.clear()
        #     return redirect('/login')
        # session['last_active'] = time.time()
        return None

def generate_session_id():
    """Generate a unique session ID"""
    return generate_password_hash(str(time.time()) + os.urandom(16).hex())

def invalidate_session():
    """Invalidate the current session"""
    session.clear()
    session_logger.info(f"Session invalidated for IP: {request.remote_addr}")

def is_sensitive_operation():
    """Check if current operation is sensitive"""
    sensitive_paths = [
        '/admin',
        '/settings',
        '/password',
        '/api/',
        '/upload',
        '/delete'
    ]
    return any(request.path.startswith(path) for path in sensitive_paths)

def require_session_security(f):
    """Decorator to enforce session security"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('_id'):
            return redirect('/login')
        
        # Check session age
        if time.time() - session['_created'] > SESSION_ABSOLUTE_TIMEOUT:
            invalidate_session()
            return redirect('/login')
        
        # Check session timeout
        if time.time() - session['_last_activity'] > SESSION_TIMEOUT:
            invalidate_session()
            return redirect('/login')
        
        # Check IP binding
        if session['_ip'] != request.remote_addr:
            invalidate_session()
            return redirect('/login')
        
        # Update last activity
        session['_last_activity'] = datetime.utcnow().timestamp()
        
        return f(*args, **kwargs)
    return decorated_function

def rotate_session():
    """Rotate session ID while maintaining session data"""
    if time.time() - session.get('_last_rotation', 0) > SESSION_ROTATION_INTERVAL:
        old_id = session['_id']
        session['_id'] = generate_session_id()
        session['_last_rotation'] = time.time()
        session_logger.info(f"Session rotated from {old_id} to {session['_id']}")

def enforce_session_limit(user_id):
    """Enforce maximum sessions per user"""
    # This would typically interact with a database to track active sessions
    # For now, we'll just log the check
    session_logger.info(f"Checking session limit for user {user_id}")
    return True  # Placeholder for actual implementation 