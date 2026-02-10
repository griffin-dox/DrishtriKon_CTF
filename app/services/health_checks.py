import logging
import os
import random
import shutil
import time

from app.services.db_health import check_db_connection
from app.utils.discord_alerts import send_security_alert

logger = logging.getLogger(__name__)

_PROCESS_START = time.time()
_LAST_NOTIFY = {}

DEFAULT_SAMPLE_RATE = float(os.getenv("HEALTHCHECK_SAMPLE_RATE", "0.1"))
DEFAULT_COOLDOWN_SECONDS = int(os.getenv("HEALTHCHECK_COOLDOWN_SECONDS", "600"))
DEFAULT_HEALTHCHECK_PATH = os.getenv("HEALTHCHECK_PATH", ".")


def get_system_health():
    """Return a lightweight system health snapshot."""
    try:
        usage = shutil.disk_usage(DEFAULT_HEALTHCHECK_PATH)
        used_percent = int((usage.used / usage.total) * 100) if usage.total else 0
    except Exception as exc:
        logger.warning("Failed to check disk usage: %s", exc)
        used_percent = -1

    uptime_seconds = int(time.time() - _PROCESS_START)
    status = "ok"
    if used_percent >= 95:
        status = "degraded"

    return {
        "status": status,
        "disk_used_percent": used_percent,
        "uptime_seconds": uptime_seconds,
    }


def _should_notify(ip_address, path, sample_rate, cooldown_seconds):
    if sample_rate <= 0:
        return False

    if random.random() > sample_rate:
        return False

    key = f"{ip_address}:{path}"
    now = time.time()
    last_sent = _LAST_NOTIFY.get(key)
    if last_sent and (now - last_sent) < cooldown_seconds:
        return False

    _LAST_NOTIFY[key] = now
    return True


def notify_health_check(ip_address, path, sample_rate=None, cooldown_seconds=None):
    """Send sampled, cooldown-based health checks for login/register visits."""
    sample_rate = DEFAULT_SAMPLE_RATE if sample_rate is None else sample_rate
    cooldown_seconds = DEFAULT_COOLDOWN_SECONDS if cooldown_seconds is None else cooldown_seconds

    if not _should_notify(ip_address, path, sample_rate, cooldown_seconds):
        return False

    system_health = get_system_health()
    db_health = "ok" if check_db_connection() else "unavailable"

    extra = {
        "Path": path,
        "System health": system_health,
        "DB health": db_health,
    }

    try:
        return send_security_alert(
            event="Health check: login/register visit",
            source_ip=ip_address,
            severity="Low",
            extra=extra,
        )
    except Exception as exc:
        logger.warning("Failed to send health check alert: %s", exc)
        return False
