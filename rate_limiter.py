import logging
from threading import Lock
from functools import wraps
from flask import request, jsonify, current_app
import time

# Configure logging
rate_logger = logging.getLogger('rate_limiter')
rate_logger.setLevel(logging.INFO)

class InMemoryRateLimiter:
    def __init__(self):
        self.data = {}
        self.lock = Lock()

    def _get_key(self, key_type, identifier):
        """Generate key for rate limiting"""
        return f"rate_limit:{key_type}:{identifier}"

    def is_rate_limited(self, key_type, identifier, max_requests, window):
        """Check if request should be rate limited"""
        key = self._get_key(key_type, identifier)
        now = int(time.time())
        with self.lock:
            record = self.data.get(key)
            if not record or now >= record['reset']:
                # New window
                self.data[key] = {'count': 1, 'reset': now + window}
                return False
            if record['count'] >= max_requests:
                return True
            self.data[key]['count'] += 1
            return False

    def get_remaining_requests(self, key_type, identifier, max_requests):
        """Get remaining requests in current window"""
        key = self._get_key(key_type, identifier)
        now = int(time.time())
        with self.lock:
            record = self.data.get(key)
            if not record or now >= record['reset']:
                return max_requests
            return max(0, max_requests - record['count'])

    def get_reset_time(self, key_type, identifier):
        """Get time until rate limit resets"""
        key = self._get_key(key_type, identifier)
        now = int(time.time())
        with self.lock:
            record = self.data.get(key)
            if not record or now >= record['reset']:
                return 0
            return max(0, record['reset'] - now)

# Initialize rate limiter
rate_limiter = InMemoryRateLimiter()

def rate_limit(key_type, max_requests, window, identifier_func=None):
    """
    Rate limit decorator

    Args:
        key_type: Type of rate limit (e.g., 'ip', 'user', 'endpoint')
        max_requests: Maximum number of requests allowed in window
        window: Time window in seconds
        identifier_func: Function to get identifier (defaults to IP address)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get identifier
            if identifier_func:
                identifier = identifier_func()
            else:
                identifier = request.remote_addr

            # Check rate limit
            if rate_limiter.is_rate_limited(key_type, identifier, max_requests, window):
                # Get remaining time
                reset_time = rate_limiter.get_reset_time(key_type, identifier)

                # Log rate limit hit
                rate_logger.warning(
                    f"Rate limit exceeded: {key_type}:{identifier} "
                    f"on {request.path} from {request.remote_addr}"
                )

                # Return rate limit response
                response = jsonify({
                    'error': 'Too many requests',
                    'retry_after': reset_time
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(reset_time)
                return response

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Common rate limiters
def ip_rate_limit(max_requests, window):
    """Rate limit by IP address"""
    return rate_limit('ip', max_requests, window)

def user_rate_limit(max_requests, window):
    """Rate limit by user ID"""
    def get_user_id():
        from flask_login import current_user
        return str(current_user.id) if current_user.is_authenticated else request.remote_addr
    return rate_limit('user', max_requests, window, get_user_id)

def endpoint_rate_limit(max_requests, window):
    """Rate limit by endpoint"""
    def get_endpoint():
        return request.path
    return rate_limit('endpoint', max_requests, window, get_endpoint)

# Example usage:
# @app.route('/api/endpoint')
# @ip_rate_limit(100, 60)  # 100 requests per minute per IP
# @user_rate_limit(1000, 3600)  # 1000 requests per hour per user
# def api_endpoint():
#     return jsonify({'status': 'success'})
