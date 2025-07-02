import logging
from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta
from core.models import RateLimit, db

rate_logger = logging.getLogger('security')
rate_logger.setLevel(logging.INFO)

def is_rate_limited(key_type, identifier, max_requests, window):
    """Check if request should be rate limited using the database"""
    now = datetime.utcnow()
    rl = RateLimit.query.filter_by(ip=identifier, endpoint=key_type).first()
    if rl:
        if now - rl.window_start > timedelta(seconds=window):
            rl.count = 1
            rl.window_start = now
        else:
            rl.count += 1
        db.session.commit()
        return rl.count > max_requests
    else:
        new_rl = RateLimit(ip=identifier, endpoint=key_type, count=1, window_start=now)
        db.session.add(new_rl)
        db.session.commit()
        return False

def get_reset_time(key_type, identifier, window):
    rl = RateLimit.query.filter_by(ip=identifier, endpoint=key_type).first()
    if rl:
        now = datetime.utcnow()
        elapsed = (now - rl.window_start).total_seconds()
        return max(0, window - elapsed)
    return 0

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
            if is_rate_limited(key_type, identifier, max_requests, window):
                # Get remaining time
                reset_time = get_reset_time(key_type, identifier, window)

                # Log rate limit hit as a security event
                rate_logger.warning(
                    f"Rate limit exceeded: {key_type}:{identifier} on {request.path} from {request.remote_addr}",
                    extra={
                        'event': 'RateLimitExceeded',
                        'source_ip': request.remote_addr,
                        'user': getattr(request, 'user', None),
                        'endpoint': request.path,
                        'key_type': key_type,
                        'identifier': identifier
                    }
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
