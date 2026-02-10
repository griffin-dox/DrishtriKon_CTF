import time
import logging
import functools
from datetime import datetime, timedelta

# Global in-memory cache for simple caching
_simple_cache = {}
_cache_timestamps = {}

logger = logging.getLogger(__name__)

class SimpleCache:
    """Simple in-memory cache implementation optimized for performance"""
    
    def get(self, key):
        if key in _simple_cache:
            # Check if expired
            if key in _cache_timestamps:
                if time.time() - _cache_timestamps[key]['time'] > _cache_timestamps[key]['timeout']:
                    self.delete(key)
                    return None
            return _simple_cache[key]
        return None
    
    def set(self, key, value, timeout=300):
        _simple_cache[key] = value
        _cache_timestamps[key] = {'time': time.time(), 'timeout': timeout}
        # Clean expired entries occasionally to prevent memory bloat
        if len(_simple_cache) % 50 == 0:
            self._cleanup_expired()
    
    def delete(self, key):
        _simple_cache.pop(key, None)
        _cache_timestamps.pop(key, None)
    
    def clear(self):
        _simple_cache.clear()
        _cache_timestamps.clear()
    
    def _cleanup_expired(self):
        current_time = time.time()
        expired_keys = []
        for key, data in _cache_timestamps.items():
            if current_time - data['time'] > data['timeout']:
                expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

# Initialize cache instance
cache = SimpleCache()

def fast_cache(timeout=300, key_prefix='cache'):
    """
    Fast in-memory cache decorator for database queries and expensive operations.
    
    Args:
        timeout (int): Cache timeout in seconds (default: 5 minutes)
        key_prefix (str): Prefix for cache keys
        
    Returns:
        Decorated function with caching
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get from cache first
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache HIT for {cache_key}")
                return result
            
            # Cache miss, execute the function
            logger.debug(f"Cache MISS for {cache_key}")
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, timeout=timeout)
            
            return result
                
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern):
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern (str): Pattern to match cache keys
    """
    try:
        keys_to_remove = [key for key in _simple_cache.keys() if pattern in key]
        for key in keys_to_remove:
            cache.delete(key)
        logger.debug(f"Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache pattern '{pattern}': {e}")

def cache_key_for_user(user_id, key_suffix):
    """Generate a cache key for user-specific data."""
    return f"user:{user_id}:{key_suffix}"

def cache_key_for_competition(comp_id, key_suffix):
    """Generate a cache key for competition-specific data."""
    return f"comp:{comp_id}:{key_suffix}"

# Pre-configured cache decorators for common use cases
def cache_platform_stats(func):
    """Cache platform statistics for 10 minutes"""
    return fast_cache(timeout=600, key_prefix='stats')(func)

def cache_competitions(func):
    """Cache competition data for 5 minutes"""
    return fast_cache(timeout=300, key_prefix='competitions')(func)

def cache_leaderboard(func):
    """Cache leaderboard data for 3 minutes"""
    return fast_cache(timeout=180, key_prefix='leaderboard')(func)

def cache_challenges(func):
    """Cache challenge data for 15 minutes"""
    return fast_cache(timeout=900, key_prefix='challenges')(func)

# Cache health check
def cache_health_check():
    """
    Check if caching system is working properly.
    
    Returns:
        dict: Cache health status
    """
    try:
        test_key = "health_check_test"
        test_value = {"timestamp": time.time(), "status": "ok"}
        
        # Set and get test value
        cache.set(test_key, test_value, timeout=60)
        retrieved = cache.get(test_key)
        
        if retrieved and retrieved.get("status") == "ok":
            cache.delete(test_key)
            return {
                "status": "healthy", 
                "type": "simple_memory",
                "entries": len(_simple_cache),
                "memory_usage": f"{len(str(_simple_cache))} bytes (approx)"
            }
        else:
            return {"status": "unhealthy", "error": "failed to retrieve test value"}
            
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# Function to get cache statistics
def get_cache_stats():
    """Get cache usage statistics"""
    return {
        "total_entries": len(_simple_cache),
        "memory_usage_approx": f"{len(str(_simple_cache))} bytes",
        "oldest_entry": min(_cache_timestamps.values(), key=lambda x: x['time'])['time'] if _cache_timestamps else None,
        "newest_entry": max(_cache_timestamps.values(), key=lambda x: x['time'])['time'] if _cache_timestamps else None
    }
