import os
import logging
import time
import json
import random
import string
import hashlib
import re
from datetime import datetime, timedelta
from flask import request, render_template, abort, redirect, url_for, jsonify
from app.services.ip_logging import flag_suspicious_ip, log_ip_activity, get_client_ip
from app.models import BannedIP
from app.extensions import db

# Configure logging
honeypot_logger = logging.getLogger('honeypot')
honeypot_logger.setLevel(logging.INFO)

# Dictionary to track registered honeypot paths
REGISTERED_HONEYPOT_PATHS = set()

# Restore only the dynamic honeypot patterns logic (PATTERNS), not file-based bans
PATTERNS = {
    'paths': [],
    'fields': [],
    'tokens': [],
    'last_rotation': datetime.now().isoformat()
}

def generate_dynamic_paths(count=10):
    """Generate dynamic honeypot paths"""
    # ...existing code...
    pass

def generate_dynamic_fields(count=10):
    """Generate dynamic honeypot fields"""
    # ...existing code...
    pass

def rotate_honeypot_patterns():
    """Rotate honeypot patterns"""
    # ...existing code...
    pass

# Ensure log_honeypot_trigger and ban_ip are defined before use in create_honeypot_routes
# Move their definitions above create_honeypot_routes
def log_honeypot_trigger(trigger_type, trigger_value):
    """Log honeypot triggers"""
    # ...existing code...
    pass

def ban_ip(ip_address, reason):
    """Ban an IP address"""
    # ...existing code...
    pass

def check_honeypot_path(request_path=None):
    """Return True if the request path matches a honeypot path."""
    if request_path is None:
        from flask import request
        request_path = request.path
    return any(request_path == p for p in PATTERNS['paths'])

def check_honeypot_fields(form):
    """Return True if any honeypot field is present and non-empty in the form."""
    for field in PATTERNS['fields']:
        if field in form and form[field]:
            return True
    return False

# Create honeypot routes
def create_honeypot_routes(app):
    """Create honeypot routes with improved detection"""
    @app.route('/honeypot-test')
    def honeypot_test():
        """Test endpoint for honeypot functionality"""
        return jsonify({'status': 'honeypot system active'})
    
    # Create dynamic honeypot routes
    for path in PATTERNS['paths']:
        def create_route_handler(p):
            def honeypot_route():
                log_honeypot_trigger('route', p)
                ban_ip(get_client_ip(), f"Accessed honeypot route: {p}")
                return render_template('honeypot/fake_login.html')
            return honeypot_route
        
        app.add_url_rule(
            path,
            f"honeypot_{hashlib.md5(path.encode()).hexdigest()}",
            create_route_handler(path)
        )