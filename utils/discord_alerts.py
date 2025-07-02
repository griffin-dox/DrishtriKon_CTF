import os
import requests
from datetime import datetime
from dotenv import load_dotenv
import logging
import json
from logging.handlers import RotatingFileHandler

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_SECURITY_WEBHOOK_URL")
LOG_FILE_PATH = os.getenv("SECURITY_LOG_FILE", "security_events.log")
MAX_LOG_BYTES = int(os.getenv("SECURITY_LOG_MAX_BYTES", 5 * 1024 * 1024))  # 5MB
BACKUP_COUNT = int(os.getenv("SECURITY_LOG_BACKUP_COUNT", 3))


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from logs."""
    SENSITIVE_KEYS = {"password", "token", "secret", "key"}

    def filter(self, record):
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            for k in self.SENSITIVE_KEYS:
                if k in record.extra:
                    record.extra[k] = "[REDACTED]"
        return True


def format_security_alert(event, source_ip=None, user=None, severity="Medium", extra=None, timestamp=None):
    """
    Format a concise security alert message for Discord.
    Returns a markdown string.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    ts_str = timestamp.strftime('%Y-%m-%d %H:%M UTC')
    msg_lines = [
        "🚨 **Security Alert**",
        f"**Event:** {event}",
    ]
    if source_ip:
        msg_lines.append(f"**Source IP:** {source_ip}")
    if user:
        msg_lines.append(f"**User:** {user}")
    msg_lines.append(f"**Severity:** {severity}")
    msg_lines.append(f"**Timestamp:** {ts_str}")
    if extra:
        for k, v in extra.items():
            msg_lines.append(f"**{k}:** {v}")
    return "  \n".join(msg_lines)


def send_security_alert(event, source_ip=None, user=None, severity="Medium", extra=None, timestamp=None):
    """
    Send a concise security alert to Discord via webhook.
    """
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("DISCORD_SECURITY_WEBHOOK_URL is not set in environment.")
    message = format_security_alert(event, source_ip, user, severity, extra, timestamp)
    data = {"content": message}
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Discord Alert Error] {e}")
        return False


def test_send_security_alert():
    """Send a test alert to Discord (for manual testing)."""
    return send_security_alert(
        event="Failed SSH Login",
        source_ip="192.168.1.5",
        user="root",
        severity="High",
        extra={"Reason": "Invalid password", "Attempt": 3}
    )


class DiscordSecurityLogHandler(logging.Handler):
    """Custom logging handler to send security warnings/errors to Discord."""

    def emit(self, record):
        try:
            # Only send warnings/errors/critical
            if record.levelno < logging.WARNING:
                return
            event = record.getMessage()
            # Try to extract extra info if present
            extra = {}
            if hasattr(record, 'ip'):
                extra['Source IP'] = record.ip
            if hasattr(record, 'user'):
                extra['User'] = record.user
            # Severity mapping
            severity = 'Critical' if record.levelno >= logging.CRITICAL else (
                'High' if record.levelno >= logging.ERROR else 'Medium')
            send_security_alert(
                event=event,
                source_ip=extra.get('Source IP'),
                user=extra.get('User'),
                severity=severity,
                extra=getattr(record, 'extra', None)
            )
        except Exception as e:
            print(f"[Discord Log Handler Error] {e}")


class JSONFormatter(logging.Formatter):
    """Format logs as JSON for SIEM and log aggregation."""
    def format(self, record):
        log_record = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        # Add extra fields if present
        if hasattr(record, 'extra') and isinstance(record.extra, dict):
            log_record.update(record.extra)
        if hasattr(record, 'ip'):
            log_record['ip'] = record.ip
        if hasattr(record, 'user'):
            log_record['user'] = record.user
        return json.dumps(log_record)


# --- Logging System Setup ---
def setup_logging():
    """Set up robust, scalable, and secure logging."""
    json_formatter = JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = RotatingFileHandler(LOG_FILE_PATH, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT)
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)
    file_handler.addFilter(SensitiveDataFilter())

    discord_handler = DiscordSecurityLogHandler()
    discord_handler.setLevel(logging.WARNING)
    discord_handler.addFilter(SensitiveDataFilter())

    for logger_name in [
        'security', 'ids', 'ip_logger', 'session_security', __name__
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
            logger.addHandler(file_handler)
        if not any(isinstance(h, DiscordSecurityLogHandler) for h in logger.handlers):
            logger.addHandler(discord_handler)
        logger.propagate = False


setup_logging()

if __name__ == "__main__":
    test_send_security_alert()
