"""
Google reCAPTCHA v3 utility functions for the CTF platform.
Provides verification and score checking for anti-bot protection.
"""

import requests
import logging
from flask import current_app, request
from functools import wraps

logger = logging.getLogger(__name__)

class RecaptchaError(Exception):
    """Custom exception for reCAPTCHA related errors."""
    pass

def verify_recaptcha(token, action=None, min_score=0.5):
    """
    Verify reCAPTCHA v3 token with Google's API.
    
    Args:
        token (str): The reCAPTCHA token from the client
        action (str, optional): Expected action name for verification
        min_score (float): Minimum score threshold (0.0 to 1.0)
        
    Returns:
        dict: Verification result with success, score, and details
    """
    if not token:
        return {
            'success': False,
            'score': 0.0,
            'error': 'No reCAPTCHA token provided'
        }
    
    secret_key = current_app.config.get('RECAPTCHA_SECRET_KEY')
    if not secret_key:
        logger.error("reCAPTCHA secret key not configured")
        return {
            'success': False,
            'score': 0.0,
            'error': 'reCAPTCHA not configured'
        }
    
    # Prepare verification request
    verify_url = 'https://www.google.com/recaptcha/api/siteverify'
    data = {
        'secret': secret_key,
        'response': token,
        'remoteip': request.remote_addr
    }
    
    try:
        # Make request to Google's verification API
        response = requests.post(verify_url, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        success = result.get('success', False)
        score = result.get('score', 0.0)
        
        # Check action if specified
        if action and result.get('action') != action:
            logger.warning(f"reCAPTCHA action mismatch. Expected: {action}, Got: {result.get('action')}")
            return {
                'success': False,
                'score': score,
                'error': 'Action mismatch'
            }
        
        # Check score threshold
        if success and score < min_score:
            logger.warning(f"reCAPTCHA score too low: {score} < {min_score}")
            return {
                'success': False,
                'score': score,
                'error': f'Score too low: {score}'
            }
        
        # Log the result
        if success:
            logger.info(f"reCAPTCHA verification successful. Score: {score}, Action: {result.get('action')}")
        else:
            logger.warning(f"reCAPTCHA verification failed: {result.get('error-codes', [])}")
        
        return {
            'success': success,
            'score': score,
            'error': None if success else 'Verification failed',
            'error_codes': result.get('error-codes', [])
        }
        
    except requests.RequestException as e:
        logger.error(f"reCAPTCHA verification request failed: {str(e)}")
        return {
            'success': False,
            'score': 0.0,
            'error': 'Verification service unavailable'
        }
    except Exception as e:
        logger.error(f"Unexpected error during reCAPTCHA verification: {str(e)}")
        return {
            'success': False,
            'score': 0.0,
            'error': 'Verification error'
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
            request.recaptcha_score = result['score']
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_recaptcha_score():
    """Get the reCAPTCHA score from the current request context."""
    return getattr(request, 'recaptcha_score', None)

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
    Compatibility wrapper for legacy imports. Returns True if verification passes, else False.
    """
    result = verify_recaptcha(token, action, min_score)
    return result.get('success', False)
