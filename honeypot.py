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
from core.ip_logging import flag_suspicious_ip, log_ip_activity, get_client_ip

# Configure logging
honeypot_logger = logging.getLogger('honeypot')
honeypot_logger.setLevel(logging.INFO)

# Constants
HONEYPOT_DIR = "honeypot_data"
HONEYPOT_LOG = os.path.join(HONEYPOT_DIR, "honeypot_triggers.log")
HONEYPOT_BANNED_IPS = os.path.join(HONEYPOT_DIR, "banned_ips.json")
HONEYPOT_PATTERNS = os.path.join(HONEYPOT_DIR, "patterns.json")

# Ensure honeypot directory exists
if not os.path.exists(HONEYPOT_DIR):
    os.makedirs(HONEYPOT_DIR)

# Initialize banned IPs
BANNED_IPS = {}
if os.path.exists(HONEYPOT_BANNED_IPS):
    try:
        with open(HONEYPOT_BANNED_IPS, 'r') as f:
            BANNED_IPS = json.load(f)
    except json.JSONDecodeError:
        # If file is corrupted, start fresh
        BANNED_IPS = {}

# Load or initialize patterns
PATTERNS = {
    'paths': [],
    'fields': [],
    'tokens': [],
    'last_rotation': datetime.now().isoformat()
}

if os.path.exists(HONEYPOT_PATTERNS):
    try:
        with open(HONEYPOT_PATTERNS, 'r') as f:
            PATTERNS = json.load(f)
    except json.JSONDecodeError:
        pass

def generate_dynamic_paths(count=10):
    """Generate dynamic honeypot paths"""
    paths = []
    components = [
        'admin', 'api', 'console', 'dashboard', 'login', 'auth',
        'wp', 'cms', 'backend', 'system', 'config', 'setup',
        'install', 'update', 'maintenance', 'debug', 'test'
    ]
    
    extensions = ['php', 'aspx', 'jsp', 'asp', 'html', 'xml', 'json']
    
    for _ in range(count):
        # Generate path with 2-4 components
        num_components = random.randint(2, 4)
        path_components = random.sample(components, num_components)
        
        # Add random extension
        if random.random() < 0.3:  # 30% chance of extension
            path_components[-1] += f".{random.choice(extensions)}"
            
        path = '/' + '/'.join(path_components)
        paths.append(path)
    
    return paths

def generate_dynamic_fields(count=10):
    """Generate dynamic honeypot form fields"""
    fields = []
    prefixes = ['user', 'admin', 'system', 'config', 'setup', 'test']
    suffixes = ['name', 'email', 'id', 'key', 'token', 'auth', 'verify']
    
    for _ in range(count):
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        field = f"{prefix}_{suffix}"
        fields.append(field)
    
    return fields

def rotate_honeypot_patterns():
    """Rotate honeypot patterns periodically"""
    now = datetime.now()
    last_rotation = datetime.fromisoformat(PATTERNS['last_rotation'])
    
    # Rotate every 6 hours
    if (now - last_rotation) > timedelta(hours=6):
        PATTERNS['paths'] = generate_dynamic_paths(20)
        PATTERNS['fields'] = generate_dynamic_fields(15)
        PATTERNS['tokens'] = [generate_fake_token() for _ in range(10)]
        PATTERNS['last_rotation'] = now.isoformat()
        
        # Save patterns
        with open(HONEYPOT_PATTERNS, 'w') as f:
            json.dump(PATTERNS, f, indent=2)
        
        honeypot_logger.info("Rotated honeypot patterns")

def generate_fake_token():
    """Generate a fake CSRF token"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(32))

def update_banned_ips():
    """Update banned IPs file"""
    with open(HONEYPOT_BANNED_IPS, 'w') as f:
        json.dump(BANNED_IPS, f, indent=2)

def ban_ip(ip, reason, ban_duration=3600, severity=3):
    """Ban an IP address with improved tracking"""
    current_time = time.time()
    
    # Add to banned IPs with more details
    BANNED_IPS[ip] = {
        'timestamp': datetime.now().isoformat(),
        'reason': reason,
        'expires': current_time + ban_duration,
        'severity': severity,
        'user_agent': request.headers.get('User-Agent', ''),
        'path': request.path,
        'method': request.method,
        'headers': dict(request.headers),
        'ban_count': BANNED_IPS.get(ip, {}).get('ban_count', 0) + 1
    }
    
    # Increase ban duration for repeat offenders
    if BANNED_IPS[ip]['ban_count'] > 1:
        BANNED_IPS[ip]['expires'] = current_time + (ban_duration * BANNED_IPS[ip]['ban_count'])
    
    # Flag as suspicious with high severity
    flag_suspicious_ip(ip, f"BANNED: {reason}", severity)
    
    # Log to honeypot log
    honeypot_logger.warning(
        f"BANNED IP: {ip} - Reason: {reason} - "
        f"Duration: {ban_duration}s - Count: {BANNED_IPS[ip]['ban_count']}"
    )
    
    # Update banned IPs file
    update_banned_ips()

def is_ip_banned(ip):
    """Check if IP is banned with improved detection"""
    if ip in BANNED_IPS:
        # Check if ban has expired
        if time.time() > BANNED_IPS[ip]['expires']:
            # Ban expired
            del BANNED_IPS[ip]
            update_banned_ips()
            return False
            
        # Check for suspicious patterns even if not banned
        if detect_suspicious_patterns(ip):
            ban_ip(ip, "Suspicious behavior pattern detected", 7200, 2)
            return True
            
        return True
    return False

def detect_suspicious_patterns(ip):
    """Detect suspicious behavior patterns"""
    # Check request rate
    if is_high_request_rate(ip):
        return True
        
    # Check for common attack patterns
    if has_attack_patterns():
        return True
        
    # Check for suspicious headers
    if has_suspicious_headers():
        return True
        
    return False

def is_high_request_rate(ip):
    """Check if IP has high request rate"""
    # This would typically use Redis or similar for tracking
    # For now, we'll use a simple in-memory check
    return False  # Placeholder

def has_attack_patterns():
    """Check for common attack patterns in request"""
    attack_patterns = [
        r'\.\.\/',  # Path traversal
        r'<script.*?>',  # XSS
        r'UNION.*?SELECT',  # SQL injection
        r'exec\s*\(',  # Command injection
        r'eval\s*\(',  # Code execution
    ]
    
    # Check URL
    for pattern in attack_patterns:
        if re.search(pattern, request.url, re.I):
            return True
            
    # Check headers
    for header in request.headers.values():
        if re.search(pattern, header, re.I):
            return True
            
    return False

def has_suspicious_headers():
    """Check for suspicious headers"""
    suspicious_headers = {
        'X-Forwarded-For': r'^(\d{1,3}\.){3}\d{1,3}$',
        'User-Agent': r'(nmap|nikto|sqlmap|dirbuster|hydra|gobuster|wpscan)',
        'Accept': r'\*/\*',
    }
    
    for header, pattern in suspicious_headers.items():
        value = request.headers.get(header, '')
        if re.search(pattern, value, re.I):
            return True
            
    return False

def log_honeypot_trigger(trap_type, trap_name, details=None):
    """Log honeypot trigger with enhanced details"""
    ip = get_client_ip()
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        'timestamp': timestamp,
        'ip': ip,
        'trap_type': trap_type,
        'trap_name': trap_name,
        'user_agent': request.headers.get('User-Agent', ''),
        'path': request.path,
        'method': request.method,
        'headers': dict(request.headers),
        'cookies': dict(request.cookies),
        'query_params': dict(request.args),
        'form_data': dict(request.form),
        'details': details or {}
    }
    
    # Log to file
    with open(HONEYPOT_LOG, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    # Log to standard logger
    honeypot_logger.warning(
        f"HONEYPOT TRIGGERED: Type={trap_type}, Name={trap_name}, "
        f"IP={ip}, Path={request.path}"
    )
    
    # Log using IP logging
    log_ip_activity('honeypot_trigger', additional_info={
        'trap_type': trap_type,
        'trap_name': trap_name,
        'details': details
    })
    
    return log_entry

def check_honeypot_path():
    """Check if request path is a honeypot with improved detection"""
    # Rotate patterns if needed
    rotate_honeypot_patterns()
    
    path = request.path.rstrip('/')
    
    # Check against dynamic patterns
    for honeypot_path in PATTERNS['paths']:
        if path == honeypot_path or path.startswith(f"{honeypot_path}/"):
            log_honeypot_trigger('path', honeypot_path)
            ban_ip(get_client_ip(), f"Accessed honeypot path: {path}")
            
            # Add random delay
            time.sleep(random.uniform(1, 3))
            
            return True
    
    return False

def check_honeypot_fields(form_data):
    """Check if request form contains honeypot fields with improved detection"""
    # Rotate patterns if needed
    rotate_honeypot_patterns()
    
    for field in PATTERNS['fields']:
        if field in form_data and form_data[field]:
            log_honeypot_trigger('form_field', field, {'value': form_data[field]})
            flag_suspicious_ip(get_client_ip(), f"Filled honeypot field: {field}", 2)
            return True
    
    return False

def check_honeypot_token(token):
    """Check if token is a honeypot token with improved detection"""
    # Rotate patterns if needed
    rotate_honeypot_patterns()
    
    if token in PATTERNS['tokens']:
        log_honeypot_trigger('token', token)
        flag_suspicious_ip(get_client_ip(), "Used honeypot token", 2)
        return True
    
    return False

def handle_honeypot_trigger(trap_type, trap_name, details=None):
    """Handle a honeypot trigger"""
    log_honeypot_trigger(trap_type, trap_name, details)
    
    # Different responses based on trap type
    if trap_type == 'path':
        if random.random() < 0.5:
            # Sometimes return a fake login page that collects more info about the attacker
            return render_template('honeypot/fake_login.html')
        else:
            # Sometimes return a fake error to make it look like the site is broken
            return render_template('errors/500.html'), 500
    
    elif trap_type == 'form_field':
        # Pretend the form submission succeeded
        return redirect(url_for('main.index'))
    
    elif trap_type == 'token':
        # Pretend the token was accepted but expired
        return render_template('errors/403.html'), 403
    
    # Default: just abort with forbidden error
    return abort(403)

# Dictionary to track registered honeypot paths
REGISTERED_HONEYPOT_PATHS = set()

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
            f"honeypot_{hashlib.md5(p.encode()).hexdigest()}",
            create_route_handler(path)
        )