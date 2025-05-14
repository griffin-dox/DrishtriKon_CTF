import time
import logging
import redis
from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime, timedelta

# Configure logging
rate_logger = logging.getLogger('rate_limiter')
rate_logger.setLevel(logging.INFO)

class RedisRateLimiter:
    def __init__(self, redis_url=None):
        self.redis = redis.from_url(redis_url or 'redis://localhost:6379/0')
        
    def _get_key(self, key_type, identifier):
        """Generate Redis key for rate limiting"""
        return f"rate_limit:{key_type}:{identifier}"
        
    def _get_window_key(self, key_type, identifier, window):
        """Generate Redis key for rate limit window"""
        return f"rate_limit:{key_type}:{identifier}:{window}"
        
    def is_rate_limited(self, key_type, identifier, max_requests, window):
        """Check if request should be rate limited"""
        key = self._get_key(key_type, identifier)
        window_key = self._get_window_key(key_type, identifier, window)
        
        # Get current count
        current = self.redis.get(key)
        if current is None:
            # First request in window
            self.redis.setex(key, window, 1)
            return False
            
        current = int(current)
        if current >= max_requests:
            # Rate limit exceeded
            return True
            
        # Increment counter
        self.redis.incr(key)
        return False
        
    def get_remaining_requests(self, key_type, identifier, max_requests):
        """Get remaining requests in current window"""
        key = self._get_key(key_type, identifier)
        current = self.redis.get(key)
        if current is None:
            return max_requests
        return max(0, max_requests - int(current))
        
    def get_reset_time(self, key_type, identifier):
        """Get time until rate limit resets"""
        key = self._get_key(key_type, identifier)
        ttl = self.redis.ttl(key)
        return max(0, ttl)

# Initialize rate limiter
rate_limiter = RedisRateLimiter()

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