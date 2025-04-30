import os
import logging
import json
import ipaddress
import time
from datetime import datetime
from functools import wraps
from flask import request, session, g

# Configure logging for IP activity
logging.basicConfig(level=logging.INFO)
ip_logger = logging.getLogger('ip_logger')
ip_logger.setLevel(logging.INFO)

# Constants
IP_LOG_DIR = "logs"
IP_LOG_FILE = os.path.join(IP_LOG_DIR, "ip_activity.log")
SUSPICIOUS_ACTIVITIES_FILE = os.path.join(IP_LOG_DIR, "suspicious_ips.json")
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILES = 10

# Ensure log directory exists
if not os.path.exists(IP_LOG_DIR):
    os.makedirs(IP_LOG_DIR)

# IP tracking
SUSPICIOUS_IPS = {}
KNOWN_PROXIES = set()  # Known legitimate proxies

def is_valid_ip(ip):
    """Check if string is a valid IP address"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def get_client_ip():
    """Get client IP address from request, handling proxies"""
    # Check X-Forwarded-For header first (when behind proxy)
    if 'X-Forwarded-For' in request.headers:
        # X-Forwarded-For can contain multiple IPs, first one is the client
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        if is_valid_ip(ip):
            return ip
            
    # Fallback to remote_addr
    return request.remote_addr

def is_suspicious_ip(ip):
    """Check if IP is already flagged as suspicious"""
    if ip in SUSPICIOUS_IPS:
        # Check if IP has been suspicious recently
        return (time.time() - SUSPICIOUS_IPS[ip]['last_activity']) < 3600  # 1 hour
    return False

def is_known_attack_source(ip):
    """Check if IP is a known attack source (could integrate with external threat intel)"""
    # This is a placeholder - in production, this would use a real threat intelligence source
    return False

def update_suspicious_ips():
    """Update suspicious IPs file"""
    with open(SUSPICIOUS_ACTIVITIES_FILE, 'w') as f:
        json.dump(SUSPICIOUS_IPS, f, indent=2)

def flag_suspicious_ip(ip, reason, severity=1):
    """Flag an IP as suspicious"""
    current_time = time.time()
    
    if ip in SUSPICIOUS_IPS:
        # Update existing entry
        SUSPICIOUS_IPS[ip]['incidents'].append({
            'timestamp': datetime.now().isoformat(),
            'reason': reason,
            'severity': severity
        })
        SUSPICIOUS_IPS[ip]['count'] += 1
        SUSPICIOUS_IPS[ip]['last_activity'] = current_time
    else:
        # Create new entry
        SUSPICIOUS_IPS[ip] = {
            'first_seen': datetime.now().isoformat(),
            'last_activity': current_time,
            'count': 1,
            'incidents': [{
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'severity': severity
            }]
        }
    
    # Log to file
    ip_logger.warning(f"SUSPICIOUS ACTIVITY: IP {ip} - {reason} (Severity: {severity})")
    
    # Update suspicious IPs file
    update_suspicious_ips()
    
    return SUSPICIOUS_IPS[ip]

def rotate_logs():
    """Rotate log files if they get too large"""
    if os.path.exists(IP_LOG_FILE) and os.path.getsize(IP_LOG_FILE) > MAX_LOG_SIZE:
        # Rotate log files
        for i in range(MAX_LOG_FILES - 1, 0, -1):
            src = f"{IP_LOG_FILE}.{i}" if i > 0 else IP_LOG_FILE
            dst = f"{IP_LOG_FILE}.{i+1}"
            
            if os.path.exists(src):
                if os.path.exists(dst):
                    os.remove(dst)
                os.rename(src, dst)
        
        # Create new log file
        open(IP_LOG_FILE, 'w').close()

def log_ip_activity(activity_type, endpoint=None, additional_info=None):
    """Log IP activity"""
    ip = get_client_ip()
    timestamp = datetime.now().isoformat()
    user_id = getattr(g, 'user_id', None)
    username = getattr(g, 'username', 'anonymous')
    
    log_entry = {
        'timestamp': timestamp,
        'ip': ip,
        'user_id': user_id,
        'username': username,
        'activity_type': activity_type,
        'endpoint': endpoint or request.path,
        'user_agent': request.headers.get('User-Agent', ''),
        'referrer': request.referrer,
        'session_id': session.get('_id', 'no-session')
    }
    
    if additional_info:
        log_entry.update(additional_info)
    
    # Rotate logs if needed
    rotate_logs()
    
    # Log to file
    with open(IP_LOG_FILE, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')
    
    # Also log to standard logger for server logs
    ip_logger.info(f"IP: {ip} - User: {username} - Activity: {activity_type} - Endpoint: {endpoint or request.path}")
    
    return log_entry

# Decorator for logging access to specific endpoints
def log_access(activity_type=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log before executing view function
            log_ip_activity(activity_type or f.__name__)
            return f(*args, **kwargs)
        return decorated_function
    return decorator