import logging
from functools import wraps

from flask import jsonify, request, flash, redirect, url_for, session
from flask_login import current_user

from app.security.rate_limiter import is_rate_limited, get_reset_time

rate_limit_logger = logging.getLogger(__name__)


def _default_identifier():
    return request.remote_addr or "unknown"


def user_or_ip_identifier():
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return f"ip:{request.remote_addr or 'unknown'}"


def otp_session_identifier():
    otp_user_id = session.get("otp_user_id")
    if otp_user_id:
        return f"otp_user:{otp_user_id}"
    return f"ip:{request.remote_addr or 'unknown'}"


def rate_limit_route(
    key_type,
    max_requests,
    window,
    identifier_func=None,
    message=None,
    methods=None,
):
    """
    Rate limit decorator with HTML/JSON-aware responses.

    Args:
        key_type: Rate limit bucket key stored in DB (e.g., 'flag_submit')
        max_requests: Maximum requests allowed within window
        window: Window in seconds
        identifier_func: Optional function to create a stable identifier
        message: Optional custom message
        methods: Optional set of HTTP methods to apply limit to
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if methods and request.method not in methods:
                return f(*args, **kwargs)

            identifier = identifier_func() if identifier_func else _default_identifier()

            if is_rate_limited(key_type, identifier, max_requests, window):
                reset_time = get_reset_time(key_type, identifier, window)
                retry_after = max(1, int(reset_time))
                base_message = message or "Too many requests. Please try again later."

                rate_limit_logger.warning(
                    "Rate limit hit: %s:%s on %s",
                    key_type,
                    identifier,
                    request.path,
                    extra={
                        "event": "rate_limit",
                        "identifier": identifier,
                        "key_type": key_type,
                        "path": request.path,
                        "method": request.method,
                        "retry_after": retry_after,
                    },
                )

                if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
                    response = jsonify({
                        "status": "error",
                        "message": base_message,
                        "data": {"retry_after": retry_after},
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    return response

                flash(f"{base_message} Retry after {retry_after}s.", "danger")
                response = redirect(request.referrer or url_for("main.index"))
                response.headers["Retry-After"] = str(retry_after)
                return response

            return f(*args, **kwargs)

        return wrapped

    return decorator
