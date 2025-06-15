import re
import logging
import json
import time
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from flask import request, session, g
from core.ip_logging import get_client_ip, flag_suspicious_ip, log_ip_activity

# Initialize logging
ids_logger = logging.getLogger('ids')
ids_logger.setLevel(logging.WARNING)

# Constants
IDS_DIR = "ids_data"
IDS_ALERTS_FILE = os.path.join(IDS_DIR, "ids_alerts.log")
IDS_RULES_FILE = os.path.join(IDS_DIR, "ids_rules.json")
IDS_STATE_FILE = os.path.join(IDS_DIR, "ids_state.json")

# Ensure IDS directory exists
if not os.path.exists(IDS_DIR):
    os.makedirs(IDS_DIR)

# IDS State
IDS_STATE = {
    'last_analysis': datetime.now().isoformat(),
    'attack_counters': {},
    'ip_request_stats': {},
    'known_user_agents': {},
    'endpoint_access_patterns': {},
    'anomaly_scores': {}
}

# Load IDS state if it exists
if os.path.exists(IDS_STATE_FILE):
    try:
        with open(IDS_STATE_FILE, 'r') as f:
            IDS_STATE = json.load(f)
    except json.JSONDecodeError:
        pass

# Rules for pattern-based detection
# Basic rule format: {'id': '', 'pattern': '', 'location': '', 'severity': 0, 'description': ''}
IDS_RULES = [
    {
        'id': 'SQL_INJECTION_1',
        'pattern': r'(\b(select|union|insert|update|delete|drop|alter)\b.*\b(from|table|column|database|where)\b)|(-{2,}|/\*|\*/)',
        'location': 'params',
        'severity': 3,
        'description': 'Potential SQL injection attempt'
    },
    {
        'id': 'XSS_1',
        'pattern': r'<script.*?>|javascript:|on\w+\s*=|<iframe|<img[^>]+onerror|alert\s*\(|document\.cookie',
        'location': 'params',
        'severity': 3,
        'description': 'Potential Cross-Site Scripting (XSS) attempt'
    },
    {
        'id': 'TRAVERSAL_1',
        'pattern': r'\.\.\/|\.\.\\|~\/|~\\|\/etc\/passwd|\/etc\/shadow|\/bin\/bash|cmd\.exe|command\.com',
        'location': 'path',
        'severity': 3,
        'description': 'Potential path traversal or command injection attempt'
    },
    {
        'id': 'SCANNING_1',
        'pattern': r'\.git\/|\.env|wp-config|config\.php|phpinfo|composer\.json|web\.config|elasticsearch|jenkins|solr',
        'location': 'path',
        'severity': 2,
        'description': 'Web application fingerprinting or scanning attempt'
    },
    {
        'id': 'USER_AGENT_1',
        'pattern': r'(nmap|nikto|sqlmap|dirbuster|hydra|gobuster|wpscan|w3af|acunetix|nessus|openvas|metasploit|burpsuite|zap|massscan)',
        'location': 'user_agent',
        'severity': 3,
        'description': 'Known penetration testing or hacking tool in User-Agent'
    },
    {
        'id': 'COMMAND_INJECTION_1',
        'pattern': r'`.*`|\$\(.*\)|;.*\b(ping|wget|curl|bash|sh|nc|ncat|python|perl|ruby|php)\b|\|.*\b(cat|ls|dir|pwd|id|whoami|ifconfig|ipconfig)\b',
        'location': 'params',
        'severity': 3,
        'description': 'Potential command injection attempt'
    },
    {
        'id': 'LOGIN_SPAM_1',
        'pattern': r'',  # Special rule handled in code
        'location': 'behavior',
        'severity': 2,
        'description': 'Excessive failed login attempts'
    },
    {
        'id': 'RAPID_REQUESTS_1',
        'pattern': r'',  # Special rule handled in code
        'location': 'behavior',
        'severity': 2,
        'description': 'Abnormally high request rate'
    }
]

# User-agent patterns for common browsers (to establish baseline)
COMMON_BROWSER_PATTERNS = [
    r'Chrome/\d+', 
    r'Firefox/\d+', 
    r'Safari/\d+', 
    r'Edge/\d+', 
    r'MSIE \d+', 
    r'OPR/\d+', 
    r'Opera/\d+'
]

# Track request stats for behavioral analysis
REQUEST_STATS = defaultdict(list)
FAILED_LOGINS = defaultdict(int)

def save_ids_state():
    """Save the IDS state to file"""
    with open(IDS_STATE_FILE, 'w') as f:
        json.dump(IDS_STATE, f, indent=2)

def log_ids_alert(rule_id, details):
    """Log an IDS alert"""
    ip = get_client_ip()
    timestamp = datetime.now().isoformat()
    
    # Get rule details
    rule = next((r for r in IDS_RULES if r['id'] == rule_id), {'severity': 1, 'description': 'Unknown rule'})
    
    alert = {
        'timestamp': timestamp,
        'ip': ip,
        'rule_id': rule_id,
        'severity': rule['severity'],
        'description': rule['description'],
        'user_id': getattr(g, 'user_id', None),
        'username': getattr(g, 'username', 'anonymous'),
        'path': request.path,
        'method': request.method,
        'user_agent': request.headers.get('User-Agent', ''),
        'details': details
    }
    
    # Log to file
    with open(IDS_ALERTS_FILE, 'a') as f:
        f.write(json.dumps(alert) + '\n')
    
    # Log to standard logger
    ids_logger.warning(f"IDS ALERT: Rule={rule_id}, Severity={rule['severity']}, IP={ip}, Path={request.path}")
    
    # Flag IP as suspicious based on severity
    flag_suspicious_ip(ip, f"IDS Alert: {rule['description']}", rule['severity'])
    
    # Update attack counters in IDS state
    if not rule_id in IDS_STATE['attack_counters']:
        IDS_STATE['attack_counters'][rule_id] = 0
    IDS_STATE['attack_counters'][rule_id] += 1
    
    # Log using IP logging
    log_ip_activity('ids_alert', additional_info={
        'rule_id': rule_id,
        'severity': rule['severity'],
        'description': rule['description']
    })
    
    # Save updated state
    save_ids_state()
    
    return alert

def analyze_request():
    """Analyze the current request for intrusion attempts"""
    # Check pattern-based rules
    alerts = []
    
    # Get request data
    ip = get_client_ip()
    path = request.path
    user_agent = request.headers.get('User-Agent', '')
    params = dict(request.values)  # Combines form and query parameters
    
    # Clean sensitive data
    clean_params = {}
    for key, value in params.items():
        if 'password' in key.lower() or 'token' in key.lower() or 'key' in key.lower():
            clean_params[key] = '[REDACTED]'
        else:
            clean_params[key] = value
    
    # Add request to stats
    REQUEST_STATS[ip].append({
        'timestamp': time.time(),
        'path': path,
        'method': request.method
    })
    
    # Clean old requests (older than 5 minutes)
    REQUEST_STATS[ip] = [r for r in REQUEST_STATS[ip] if r['timestamp'] > time.time() - 300]
    
    # Check each rule
    for rule in IDS_RULES:
        # Skip behavioral rules
        if rule['location'] == 'behavior':
            continue
            
        # Get the content to check based on rule location
        if rule['location'] == 'path':
            content = path
        elif rule['location'] == 'user_agent':
            content = user_agent
        elif rule['location'] == 'params':
            # Check all parameters
            content = json.dumps(clean_params)
        else:
            continue
            
        # Check pattern
        if rule['pattern'] and re.search(rule['pattern'], content, re.IGNORECASE):
            alert = log_ids_alert(rule['id'], {
                'matched_content': content,
                'clean_params': clean_params
            })
            alerts.append(alert)
    
    # Behavioral analysis
    run_behavioral_analysis(ip)
    
    return alerts

def track_failed_login(username, ip=None):
    """Track failed login attempt"""
    if ip is None:
        ip = get_client_ip()
    
    # Increment counter
    FAILED_LOGINS[ip] += 1
    
    # Check threshold (5 failed attempts in 15 minutes)
    if FAILED_LOGINS[ip] >= 5:
        log_ids_alert('LOGIN_SPAM_1', {
            'username': username,
            'failed_count': FAILED_LOGINS[ip]
        })
        
        # Reset counter
        FAILED_LOGINS[ip] = 0
        
        return True
    
    return False

def run_behavioral_analysis(ip):
    """Run behavioral analysis on the client IP"""
    # Check request rate
    requests = REQUEST_STATS[ip]
    
    # Skip if not enough data
    if len(requests) < 10:
        return
    
    # Calculate requests per minute
    now = time.time()
    one_min_ago = now - 60
    
    recent_requests = [r for r in requests if r['timestamp'] > one_min_ago]
    request_rate = len(recent_requests)
    
    # Check if request rate is high (threshold: 30 requests per minute)
    if request_rate > 30:
        log_ids_alert('RAPID_REQUESTS_1', {
            'request_rate': request_rate,
            'threshold': 30,
            'time_period': '60 seconds'
        })
    
    # Check for unusual endpoint diversity
    endpoints = [r['path'] for r in recent_requests]
    unique_endpoints = len(set(endpoints))
    
    # If client hit many different endpoints in a short time, could be scanning
    if unique_endpoints > 15:
        log_ids_alert('SCANNING_1', {
            'unique_endpoints': unique_endpoints,
            'threshold': 15,
            'time_period': '60 seconds'
        })
    
    # Update anomaly score
    anomaly_score = calculate_anomaly_score(ip, request_rate, unique_endpoints)
    
    # Save anomaly score in state
    IDS_STATE['anomaly_scores'][ip] = anomaly_score
    save_ids_state()
    
    return anomaly_score

def calculate_anomaly_score(ip, request_rate, unique_endpoints):
    """Calculate an anomaly score based on request patterns"""
    score = 0
    
    # Request rate factor
    if request_rate > 60:
        score += 50
    elif request_rate > 40:
        score += 30
    elif request_rate > 20:
        score += 10
    
    # Endpoint diversity factor
    if unique_endpoints > 20:
        score += 50
    elif unique_endpoints > 10:
        score += 30
    elif unique_endpoints > 5:
        score += 10
    
    # Previous anomaly score factor (persistence)
    previous_score = IDS_STATE['anomaly_scores'].get(ip, 0)
    score += previous_score * 0.5  # Decay previous score by half
    
    # Cap score at 100
    return min(score, 100)