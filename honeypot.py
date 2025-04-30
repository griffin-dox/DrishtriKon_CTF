import os
import logging
import time
import json
import random
import string
from datetime import datetime
from flask import request, render_template, abort, redirect, url_for
from ip_logging import flag_suspicious_ip, log_ip_activity, get_client_ip

# Configure logging
honeypot_logger = logging.getLogger('honeypot')
honeypot_logger.setLevel(logging.INFO)

# Constants
HONEYPOT_DIR = "honeypot_data"
HONEYPOT_LOG = os.path.join(HONEYPOT_DIR, "honeypot_triggers.log")
HONEYPOT_BANNED_IPS = os.path.join(HONEYPOT_DIR, "banned_ips.json")

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

# Honeypot traps - paths that should never be accessed by legitimate users
# Keep a limited set for stability
HONEYPOT_PATHS = [
    '/admin/login.php',
    '/wp-admin',
    '/wp-login.php',
    '/administrator',
    '/phpmyadmin',
    '/.env',
    '/config.php',
    '/xmlrpc.php',
    '/.git/config',
    '/server-status'
]

# Simplified random path generation to avoid creating too many routes
def generate_random_honeypot_paths(count=5):
    """Generate a few random honeypot paths"""
    paths = []
    # Use a seed to get consistent paths
    random.seed(42)
    
    for i in range(count):
        path_type = random.choice([
            'admin', 'api', 'console', 'dashboard', 'login'
        ])
        
        # Generate random extensions or path components
        if i % 2 == 0:
            extension = random.choice(['php', 'aspx', 'jsp'])
            path = f"/{path_type}.{extension}"
        else:
            suffix = random.choice(['login', 'admin', 'panel'])
            path = f"/{path_type}/{suffix}"
            
        paths.append(path)
    
    # Reset the random seed
    random.seed()
    return paths

# Add a few random honeypot paths
HONEYPOT_PATHS.extend(generate_random_honeypot_paths(5))

# Honeypot input fields (hidden form fields that bots often fill out)
HONEYPOT_FIELDS = [
    'email_confirm',
    'website',
    'phone',
    'address',
    'contact_method',
    'fax',
    'company_size',
    'how_did_you_hear',
    'middle_name'
]

# Fake form tokens that appear to be CSRF tokens
def generate_fake_token():
    """Generate a fake CSRF token"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(32))

HONEYPOT_TOKENS = [generate_fake_token() for _ in range(5)]

def update_banned_ips():
    """Update banned IPs file"""
    with open(HONEYPOT_BANNED_IPS, 'w') as f:
        json.dump(BANNED_IPS, f, indent=2)

def ban_ip(ip, reason, ban_duration=3600, severity=3):
    """Ban an IP address"""
    current_time = time.time()
    
    # Add to banned IPs
    BANNED_IPS[ip] = {
        'timestamp': datetime.now().isoformat(),
        'reason': reason,
        'expires': current_time + ban_duration,
        'severity': severity
    }
    
    # Flag as suspicious with high severity
    flag_suspicious_ip(ip, f"BANNED: {reason}", severity)
    
    # Log to honeypot log
    honeypot_logger.warning(f"BANNED IP: {ip} - Reason: {reason} - Duration: {ban_duration}s")
    
    # Update banned IPs file
    update_banned_ips()

def is_ip_banned(ip):
    """Check if IP is banned"""
    if ip in BANNED_IPS:
        # Check if ban has expired
        if time.time() > BANNED_IPS[ip]['expires']:
            # Ban expired
            del BANNED_IPS[ip]
            update_banned_ips()
            return False
        return True
    return False

def log_honeypot_trigger(trap_type, trap_name, details=None):
    """Log honeypot trigger"""
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
        'details': details or {}
    }
    
    # Log to file
    with open(HONEYPOT_LOG, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    # Log to standard logger
    honeypot_logger.warning(f"HONEYPOT TRIGGERED: Type={trap_type}, Name={trap_name}, IP={ip}")
    
    # Log using IP logging
    log_ip_activity('honeypot_trigger', additional_info={
        'trap_type': trap_type,
        'trap_name': trap_name
    })
    
    return log_entry

def check_honeypot_path():
    """Check if request path is a honeypot"""
    path = request.path.rstrip('/')
    
    for honeypot_path in HONEYPOT_PATHS:
        # Check exact match or starts with (for directory paths)
        if path == honeypot_path or path.startswith(f"{honeypot_path}/"):
            log_honeypot_trigger('path', honeypot_path)
            # Ban IP for accessing a known suspicious path
            ban_ip(get_client_ip(), f"Accessed honeypot path: {path}")
            
            # Burn some time to slow down attackers (1-3 seconds)
            time.sleep(random.uniform(1, 3))
            
            # Return True to indicate honeypot was triggered
            return True
    
    return False

def check_honeypot_fields(form_data):
    """Check if request form contains honeypot fields"""
    for field in HONEYPOT_FIELDS:
        # If a honeypot field exists and is not empty, it's a bot
        if field in form_data and form_data[field]:
            log_honeypot_trigger('form_field', field, {'value': form_data[field]})
            # Flag as suspicious but don't ban immediately
            flag_suspicious_ip(get_client_ip(), f"Filled honeypot field: {field}", severity=2)
            return True
    
    return False

def check_honeypot_token(token):
    """Check if token is a honeypot token"""
    if token in HONEYPOT_TOKENS:
        log_honeypot_trigger('token', token)
        # Flag as suspicious but don't ban immediately
        flag_suspicious_ip(get_client_ip(), f"Used honeypot token", severity=2)
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
    """Create routes for honeypot paths"""
    @app.route('/honeypot-test')
    def honeypot_test():
        """Test honeypot functionality"""
        # This is a real route that's hidden from normal users
        log_ip_activity('honeypot_test')
        return "Honeypot system is active"
    
    # Create routes for each honeypot path
    for path in HONEYPOT_PATHS:
        # Skip if already registered
        if path in REGISTERED_HONEYPOT_PATHS:
            continue
            
        # Add to registered paths
        REGISTERED_HONEYPOT_PATHS.add(path)
        
        # Create a unique endpoint name for each path
        endpoint = f"honeypot_{abs(hash(path)) % 1000000}"
        
        # Use a closure to ensure each route gets its own function
        def create_route_handler(p):
            def honeypot_route():
                return handle_honeypot_trigger('path', p)
            return honeypot_route
        
        # Add the route to the app with its own handler function
        app.add_url_rule(path, endpoint, create_route_handler(path), methods=['GET', 'POST'])
        
        # For paths that are directories, add routes for common subpaths
        if not '.' in path and not path.endswith('/'):
            for subpath in ['login', 'index.php', 'admin', 'config']:
                full_path = f"{path}/{subpath}"
                
                # Skip if already registered
                if full_path in REGISTERED_HONEYPOT_PATHS:
                    continue
                    
                # Add to registered paths
                REGISTERED_HONEYPOT_PATHS.add(full_path)
                
                # Create unique endpoint
                sub_endpoint = f"honeypot_{abs(hash(full_path)) % 1000000}"
                
                # Add the route with its own handler
                app.add_url_rule(full_path, sub_endpoint, create_route_handler(full_path), methods=['GET', 'POST'])