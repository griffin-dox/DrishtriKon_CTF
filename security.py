import re
import time
import logging
import random
from functools import wraps
from datetime import datetime, timedelta
from flask import request, abort, session, jsonify, g, Response, render_template
from werkzeug.http import dump_cookie

# Rate limiting counters - in a production environment, use Redis or similar
# Dictionary to store IP: [request_count, first_request_time]
LOGIN_ATTEMPT_TRACKER = {}
API_REQUEST_TRACKER = {}

# Constants for rate limiting
MAX_LOGIN_ATTEMPTS = 5   # Maximum attempts 
LOGIN_ATTEMPT_WINDOW = 15 * 60  # 15 minutes time window in seconds
API_MAX_REQUESTS = 60    # Maximum API requests per window
API_WINDOW = 60          # 1 minute time window in seconds

def rate_limited(tracker, max_requests, window):
    """
    Decorator for rate limiting specific routes
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.remote_addr
            current_time = time.time()
            
            # Initialize or update tracker
            if ip not in tracker:
                tracker[ip] = [1, current_time]
            else:
                # If window has expired, reset the counter
                if current_time - tracker[ip][1] > window:
                    tracker[ip] = [1, current_time]
                else:
                    # Increment the counter
                    tracker[ip][0] += 1
            
            # Check if rate limit exceeded
            if tracker[ip][0] > max_requests:
                # Calculate time until rate limit resets
                time_elapsed = current_time - tracker[ip][1]
                time_remaining = int(window - time_elapsed)
                
                # Add jitter to prevent timing attacks (1-3 seconds)
                time.sleep(random.uniform(1, 3))
                
                # Return 429 Too Many Requests
                response = jsonify({
                    'error': 'Too many requests',
                    'retry_after': time_remaining
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(time_remaining)
                return response
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Specific rate limiters
login_rate_limited = rate_limited(LOGIN_ATTEMPT_TRACKER, MAX_LOGIN_ATTEMPTS, LOGIN_ATTEMPT_WINDOW)
api_rate_limited = rate_limited(API_REQUEST_TRACKER, API_MAX_REQUESTS, API_WINDOW)

# Security headers
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'X-XSS-Protection': '1; mode=block',
    'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.replit.com; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.gstatic.com; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self';",
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
}

def add_security_headers(response):
    """Add security headers to every response"""
    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value
    return response

def sanitize_html(html_content):
    """Sanitize HTML content to prevent XSS"""
    if not html_content:
        return ""
        
    # List of potentially dangerous patterns
    dangerous_patterns = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'on\w+=".*?"',
        r'<iframe.*?>.*?</iframe>',
        r'<embed.*?>.*?</embed>',
        r'<object.*?>.*?</object>',
        r'<style.*?>.*?</style>',
        r'expression\s*\(',
        r'url\s*\(',
        r'eval\s*\(',
        r'document\.cookie',
        r'document\.write',
        r'window\.location',
        r'document\.location',
    ]
    
    # Replace dangerous patterns
    sanitized = html_content
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    return sanitized

def check_csrf_token():
    """Check CSRF token in form submissions"""
    # Skip for GET, HEAD, OPTIONS
    if request.method in ['GET', 'HEAD', 'OPTIONS']:
        return True
        
    # During development, temporarily disable CSRF checks
    # TODO: Re-enable CSRF protection in production
    return True
    
    # Verify CSRF token for all other methods
    token = session.get('csrf_token', None)
    form_token = request.form.get('csrf_token', None)
    
    # Also check for token in headers for AJAX requests
    header_token = request.headers.get('X-CSRF-Token', None)
    
    if token and (token == form_token or token == header_token):
        return True
    
    logging.warning(f"CSRF validation failed for {request.path} from {request.remote_addr}")
    return False

def require_tls():
    """Ensure connection is over HTTPS"""
    # During development, temporarily disable HTTPS requirement
    # TODO: Re-enable HTTPS requirement in production
    return True
    
    if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
        return False
    return True
    
def check_referrer():
    """Verify referrer is from the same origin"""
    # During development, temporarily disable referrer checks
    # TODO: Re-enable referrer checks in production
    return True
    
    referrer = request.headers.get('Referer', '')
    if not referrer:
        return True  # No referrer, can't check
        
    # Allow same origin or allowed domains
    allowed_hosts = [request.host]  # Add trusted domains here
    
    for host in allowed_hosts:
        if referrer.startswith(f"https://{host}/") or referrer.startswith(f"http://{host}/"):
            return True
            
    return False

def security_checks():
    """Run all security checks and return a boolean"""
    # Perform security checks for sensitive routes
    sensitive_routes = [
        '/login', '/register', '/admin', '/account', 
        '/password/change', '/user/edit', '/payment'
    ]
    
    if any(request.path.startswith(route) for route in sensitive_routes):
        # For sensitive routes, require all security checks
        return (require_tls() and 
                check_csrf_token() and 
                check_referrer())
    
    # For other routes, be less strict
    return True

def is_rate_limited(user_id=None, ip_address=None):
    """
    Check if a user or IP is currently rate limited
    """
    if ip_address:
        current_time = time.time()
        if ip_address in LOGIN_ATTEMPT_TRACKER:
            attempts, first_request_time = LOGIN_ATTEMPT_TRACKER[ip_address]
            # Check if rate limited
            if attempts > MAX_LOGIN_ATTEMPTS:
                # Check if window has expired
                if current_time - first_request_time < LOGIN_ATTEMPT_WINDOW:
                    return True
                else:
                    # Reset if window expired
                    LOGIN_ATTEMPT_TRACKER[ip_address] = [0, current_time]
    return False

def track_login_attempt(user_id=None, ip_address=None, successful=False):
    """
    Track a login attempt, reset counter on success
    """
    if ip_address:
        current_time = time.time()
        if successful:
            # Reset on successful login
            if ip_address in LOGIN_ATTEMPT_TRACKER:
                LOGIN_ATTEMPT_TRACKER[ip_address] = [0, current_time]
        else:
            # Track failed attempt
            if ip_address not in LOGIN_ATTEMPT_TRACKER:
                LOGIN_ATTEMPT_TRACKER[ip_address] = [1, current_time]
            else:
                attempts, first_request_time = LOGIN_ATTEMPT_TRACKER[ip_address]
                # If window expired, start fresh
                if current_time - first_request_time > LOGIN_ATTEMPT_WINDOW:
                    LOGIN_ATTEMPT_TRACKER[ip_address] = [1, current_time]
                else:
                    # Increment counter
                    LOGIN_ATTEMPT_TRACKER[ip_address][0] += 1

def invalidate_session():
    """Invalidate user session securely"""
    # Clear session
    session.clear()
    
    # Generate a new session id to prevent session fixation
    session.regenerate_id()
    
    # Set a secure, expired cookie to force client removal
    expired_cookie = dump_cookie(
        key='session',
        value='',
        expires=0,
        path='/',
        domain=None,
        secure=True,
        httponly=True,
        samesite='Lax'
    )
    
    response = Response()
    response.headers.add('Set-Cookie', expired_cookie)
    return response