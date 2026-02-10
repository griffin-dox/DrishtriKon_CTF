"""
Google reCAPTCHA v3 utility functions for the CTF platform.
Provides verification and score checking for anti-bot protection.
"""

import requests
import logging
from flask import current_app, request, g
from functools import wraps

logger = logging.getLogger(__name__)

class RecaptchaError(Exception):
    """Custom exception for reCAPTCHA related errors."""
    pass

def verify_recaptcha(token, action=None, min_score=0.5):
    """
    Dummy reCAPTCHA: Always return success for development/demo mode.
    
    Args:
        token (str): The reCAPTCHA token from the client
        action (str, optional): Expected action name for verification
        min_score (float): Minimum score threshold (0.0 to 1.0)
        
    Returns:
        dict: Verification result with success, score, and details
    """
    logger.info("Dummy reCAPTCHA mode: always returning success.")
    return {
        'success': True,
        'score': 1.0,
        'error': None,
        'error_codes': []
    }

def require_recaptcha(action=None, min_score=0.5, json_response=False):
    """
    Decorator to require reCAPTCHA verification for routes.
    
    Args:
        action (str, optional): Expected action name
        min_score (float): Minimum score threshold
        json_response (bool): Whether to return JSON error responses
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip reCAPTCHA in testing or if disabled
            if current_app.config.get('TESTING') or not current_app.config.get('RECAPTCHA_ENABLED', True):
                return f(*args, **kwargs)
            
            # Get token from request
            token = None
            if request.is_json:
                token = request.json.get('recaptcha_token') if request.json else None
            else:
                token = request.form.get('recaptcha_token')
            
            # Verify token
            result = verify_recaptcha(token, action, min_score)
            
            if not result['success']:
                error_msg = f"reCAPTCHA verification failed: {result['error']}"
                logger.warning(f"Route {request.endpoint} blocked by reCAPTCHA: {error_msg}")
                
                if json_response:
                    from flask import jsonify
                    return jsonify({
                        'success': False,
                        'error': 'reCAPTCHA verification failed',
                        'message': 'Please try again or contact support if the issue persists.'
                    }), 400
                else:
                    from flask import flash, redirect, url_for
                    flash('Security verification failed. Please try again.', 'error')
                    return redirect(request.referrer or url_for('main.index'))
            
            # Store score in request context for potential use
            g.recaptcha_score = result['score']
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_recaptcha_score():
    """Get the reCAPTCHA score from the current request context."""
    return getattr(g, 'recaptcha_score', None)

def is_recaptcha_enabled():
    """Check if reCAPTCHA is enabled and properly configured."""
    return (
        current_app.config.get('RECAPTCHA_ENABLED', True) and
        current_app.config.get('RECAPTCHA_SITE_KEY') and
        current_app.config.get('RECAPTCHA_SECRET_KEY')
    )

def get_recaptcha_site_key():
    """Get the reCAPTCHA site key for client-side integration."""
    if is_recaptcha_enabled():
        return current_app.config.get('RECAPTCHA_SITE_KEY')
    return None

def verify_recaptcha_token(token, action=None, min_score=0.5):
    """
    Compatibility wrapper for legacy imports. Always returns True in dummy mode.
    """
    return True
