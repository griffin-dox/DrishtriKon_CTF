""" Database health and connection management utilities
Gracefully handles database inactivity without making the app seem offline
"""

import logging
from sqlalchemy import text
from flask import jsonify, render_template
from app.extensions import db

logger = logging.getLogger(__name__)

class DatabaseUnavailableException(Exception):
    """Raised when database is unavailable"""
    pass

def check_db_connection():
    """
    Check if database connection is active
    Returns True if connected, False otherwise
    Does NOT raise an exception
    """
    try:
        db.session.execute(text('SELECT 1'))
        return True
    except Exception as e:
        logger.warning(f"Database connection check failed: {str(e)}")
        return False

def get_safe_db_result(query_func, default_value=None, timeout=5):
    """
    Safely execute a database query with error handling
    
    Args:
        query_func: Callable that returns database query result
        default_value: Value to return if database is unavailable
        timeout: Query timeout in seconds
        
    Returns:
        Query result or default_value if database is unavailable
    """
    try:
        result = query_func()
        return result if result is not None else default_value
    except Exception as e:
        logger.warning(f"Database query failed: {str(e)}")
        return default_value

def render_db_error(message=None):
    """
    Render a friendly database error message
    Used when a route requires the database but it's unavailable
    """
    if message is None:
        message = (
            "The database connection is currently unavailable. "
            "This is likely due to database inactivity on the free hosting platform. "
            "Please try again in a few moments."
        )
    
    return render_template('errors/database_unavailable.html', message=message), 503

def require_db(f):
    """
    Decorator for routes that require database access
    Catches database errors and shows friendly message instead of 500 error
    
    Usage:
        @require_db
        @main_bp.route('/some-route')
        def some_route():
            # Code that uses database
            return render_template(...)
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Database error in route {f.__name__}: {str(e)}")
            return render_db_error()
    
    return decorated_function
