import os
import logging
import json
import ipaddress
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import request, session, g
from collections import defaultdict
from user_agents import parse

# Configure logging for IP activity
logging.basicConfig(level=logging.INFO)
ip_logger = logging.getLogger('ip_logger')
ip_logger.setLevel(logging.INFO)

# Constants
IP_LOG_DIR = "logs/ip_logs"
IP_LOG_FILE = os.path.join(IP_LOG_DIR, "ip_activity.json")
SUSPICIOUS_IPS_FILE = os.path.join(IP_LOG_DIR, "suspicious_ips.json")
MAX_REQUESTS_PER_MINUTE = 60
SUSPICIOUS_THRESHOLD = 5
BAN_DURATION = 3600  # 1 hour in seconds
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
MAX_LOG_FILES = 10

# Ensure log directory exists
if not os.path.exists(IP_LOG_DIR):
    os.makedirs(IP_LOG_DIR)

class IPActivityTracker:
    def __init__(self):
        self.suspicious_ips = self._load_suspicious_ips()
        self.ip_activity = self._load_ip_activity()
    
    def _load_suspicious_ips(self):
        """Load suspicious IPs from file"""
        if os.path.exists(SUSPICIOUS_IPS_FILE):
            try:
                with open(SUSPICIOUS_IPS_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _load_ip_activity(self):
        """Load IP activity from file"""
        if os.path.exists(IP_LOG_FILE):
            try:
                with open(IP_LOG_FILE, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def _save_suspicious_ips(self):
        """Save suspicious IPs to file"""
        with open(SUSPICIOUS_IPS_FILE, 'w') as f:
            json.dump(self.suspicious_ips, f, indent=2)
    
    def _save_ip_activity(self):
        """Save IP activity to file"""
        with open(IP_LOG_FILE, 'w') as f:
            json.dump(self.ip_activity, f, indent=2)
    
    def get_client_ip(self):
        """Get client IP address with proxy support"""
        if request.headers.getlist("X-Forwarded-For"):
            return request.headers.getlist("X-Forwarded-For")[0]
        return request.remote_addr
    
    def get_ip_info(self, ip):
        """Get IP information"""
        info = {
            'ip': ip,
            'timestamp': datetime.utcnow().isoformat(),
            'user_agent': request.headers.get('User-Agent', ''),
            'path': request.path,
            'method': request.method,
            'referrer': request.headers.get('Referer', ''),
            'session_id': session.get('_id', 'no-session'),
            'user_id': getattr(g, 'user_id', None),
            'username': getattr(g, 'username', 'anonymous')
        }
        
        # Parse user agent for basic info
        try:
            user_agent = parse(request.headers.get('User-Agent', ''))
            info.update({
                'browser': f"{user_agent.browser.family} {user_agent.browser.version_string}",
                'os': f"{user_agent.os.family} {user_agent.os.version_string}",
                'device': user_agent.device.family
            })
        except Exception as e:
            ip_logger.warning(f"Error parsing user agent: {str(e)}")
        
        return info
    
    def is_rate_limited(self, ip):
        """Check if IP is rate limited using in-memory dictionary"""
        if not hasattr(self, '_rate_limit_cache'):
            self._rate_limit_cache = {}
        
        now = int(time.time())
        window = now // 60  # current minute window
        key = (ip, window)
        
        # Clean up old entries
        keys_to_delete = [k for k in self._rate_limit_cache if k[1] < window]
        for k in keys_to_delete:
            del self._rate_limit_cache[k]
        
        count = self._rate_limit_cache.get(key, 0) + 1
        self._rate_limit_cache[key] = count
        
        if count > MAX_REQUESTS_PER_MINUTE:
            return True
        return False
    
    def log_ip_activity(self, activity_type, additional_info=None):
        """Log IP activity with enhanced information"""
        ip = self.get_client_ip()
        
        # Skip logging for localhost in development
        if ip in ('127.0.0.1', 'localhost') and os.getenv('FLASK_ENV') == 'development':
            return
        
        # Check rate limiting
        if self.is_rate_limited(ip):
            self.flag_suspicious_ip(ip, "Rate limit exceeded", severity=2)
            return
        
        # Get IP information
        ip_info = self.get_ip_info(ip)
        ip_info['activity_type'] = activity_type
        
        if additional_info:
            ip_info.update(additional_info)
        
        # Log to file
        log_entry = json.dumps(ip_info) + '\n'
        with open(os.path.join(IP_LOG_DIR, f"{datetime.utcnow().strftime('%Y-%m-%d')}.log"), 'a') as f:
            f.write(log_entry)
        
        # Update activity tracking
        if ip not in self.ip_activity:
            self.ip_activity[ip] = []
        
        self.ip_activity[ip].append(ip_info)
        self._save_ip_activity()
        
        # Check for suspicious patterns
        self._check_suspicious_patterns(ip, ip_info)
    
    def _check_suspicious_patterns(self, ip, ip_info):
        """Check for suspicious patterns in IP activity"""
        if ip not in self.ip_activity:
            return

        recent_activity = [a for a in self.ip_activity[ip] 
                         if datetime.fromisoformat(a['timestamp']) > 
                         datetime.utcnow() - timedelta(minutes=5)]
        
        # Check for rapid requests
        if len(recent_activity) > 30:  # More than 30 requests in 5 minutes
            self.flag_suspicious_ip(ip, "Rapid request pattern", severity=2)
        
        # Check for suspicious user agents
        suspicious_agents = ['nmap', 'sqlmap', 'nikto', 'dirbuster', 'hydra']
        if any(agent in ip_info['user_agent'].lower() for agent in suspicious_agents):
            self.flag_suspicious_ip(ip, "Suspicious user agent", severity=3)
        
        # Check for suspicious paths (admin, sensitive endpoints)
        suspicious_paths = ['/admin', '/wp-admin', '/phpmyadmin', '/.env', '/config']
        if any(path in ip_info['path'].lower() for path in suspicious_paths):
            # Check if user is authorized (basic check: user_id or username not anonymous)
            user_id = ip_info.get('user_id')
            username = ip_info.get('username', 'anonymous')
            if not user_id or username == 'anonymous':
                # Unauthorized attempt: raise security alert/warning
                self.flag_suspicious_ip(ip, f"Unauthorized access attempt to {ip_info['path']}", severity=2)
            else:
                # Authorized access: log as info only
                ip_logger.info(f"Authorized access to {ip_info['path']} by user: {username} (IP: {ip})")
    
    def flag_suspicious_ip(self, ip, reason, severity=1):
        """Flag an IP as suspicious"""
        if ip not in self.suspicious_ips:
            self.suspicious_ips[ip] = {
                'first_seen': datetime.utcnow().isoformat(),
                'last_seen': datetime.utcnow().isoformat(),
                'reasons': [],
                'severity': 0,
                'ban_count': 0
            }
        
        self.suspicious_ips[ip]['last_seen'] = datetime.utcnow().isoformat()
        self.suspicious_ips[ip]['reasons'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'reason': reason,
            'severity': severity
        })
        self.suspicious_ips[ip]['severity'] = max(self.suspicious_ips[ip]['severity'], severity)
        
        # Increment ban count if severity is high
        if severity >= 3:
            self.suspicious_ips[ip]['ban_count'] += 1
        
        self._save_suspicious_ips()
        
        # Log suspicious activity with username if available
        username = (
            self.ip_activity[ip][-1].get('username', 'anonymous')
            if ip in self.ip_activity and self.ip_activity[ip] else 'anonymous'
        )
        ip_logger.warning(f"Suspicious IP flagged: {ip} (user: {username}) - Reason: {reason} - Severity: {severity}")
    
    def is_ip_suspicious(self, ip):
        """Check if an IP is suspicious"""
        if ip in self.suspicious_ips:
            # Check if IP is banned
            if self.suspicious_ips[ip]['severity'] >= SUSPICIOUS_THRESHOLD:
                return True
            
            # Check if ban has expired
            last_seen = datetime.fromisoformat(self.suspicious_ips[ip]['last_seen'])
            if datetime.utcnow() - last_seen > timedelta(seconds=BAN_DURATION):
                del self.suspicious_ips[ip]
                self._save_suspicious_ips()
                return False
            
            return True
        return False
    
    def get_ip_stats(self, ip):
        """Get statistics for an IP address"""
        if ip not in self.ip_activity:
            return None
        
        activity = self.ip_activity[ip]
        return {
            'total_requests': len(activity),
            'first_seen': activity[0]['timestamp'],
            'last_seen': activity[-1]['timestamp'],
            'user_agents': list(set(a.get('user_agent') for a in activity if a.get('user_agent'))),
            'suspicious': self.is_ip_suspicious(ip),
            'suspicious_details': self.suspicious_ips.get(ip)
        }

# Initialize IP activity tracker
ip_tracker = IPActivityTracker()

# Export functions for use in other modules
def get_client_ip():
    return ip_tracker.get_client_ip()

def log_ip_activity(activity_type, additional_info=None):
    return ip_tracker.log_ip_activity(activity_type, additional_info)

def flag_suspicious_ip(ip, reason, severity=1):
    return ip_tracker.flag_suspicious_ip(ip, reason, severity)

def is_ip_suspicious(ip):
    return ip_tracker.is_ip_suspicious(ip)

def get_ip_stats(ip):
    return ip_tracker.get_ip_stats(ip)

def is_valid_ip(ip):
    """Check if string is a valid IP address"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def log_access(activity_type=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log before executing view function
            log_ip_activity(activity_type or f.__name__)
            return f(*args, **kwargs)
        return decorated_function
    return decorator