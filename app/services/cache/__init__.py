"""
Cache subsystem initialization.

Provides centralized cache management with storage monitoring,
automatic cleanup, and performance optimization.
"""

try:
    from app.services.cache.management import (
        get_cache_manager,
        schedule_cache_maintenance,
        CacheStorageManager
    )
except ImportError:
    pass

try:
    from app.services.cache.performance import warm_critical_caches
except ImportError:
    def warm_critical_caches():
        pass

__all__ = [
    'get_cache_manager',
    'schedule_cache_maintenance',
    'CacheStorageManager',
    'warm_critical_caches',
]
