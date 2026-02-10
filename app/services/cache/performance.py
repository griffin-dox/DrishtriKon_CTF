import time
import logging
import functools
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)

def cached_db_query(timeout=300, key_prefix='db'):
    """
    Advanced decorator for caching expensive database queries with Flask-Cache.
    
    Args:
        timeout (int): Cache timeout in seconds (default: 5 minutes)
        key_prefix (str): Prefix for cache keys
        
    Returns:
        Decorated function with caching
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Import cache here to avoid circular imports
            from app.extensions import cache
            
            # Create a cache key based on function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            try:
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
                
            except Exception as e:
                logger.warning(f"Cache error for {cache_key}: {e}, falling back to direct execution")
                return func(*args, **kwargs)
                
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern):
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern (str): Pattern to match cache keys
    """
    try:
        from app.extensions import cache
        # For filesystem/simple cache, clear all cache
        cache.clear()
        logger.debug(f"Cleared all cache entries (pattern: '{pattern}')")
    except Exception as e:
        logger.warning(f"Failed to invalidate cache pattern '{pattern}': {e}")

def cache_key_for_user(user_id, key_suffix):
    """
    Generate a cache key for user-specific data.
    
    Args:
        user_id (int): User ID
        key_suffix (str): Additional key identifier
        
    Returns:
        str: Cache key
    """
    return f"user:{user_id}:{key_suffix}"

def cache_key_for_competition(comp_id, key_suffix):
    """
    Generate a cache key for competition-specific data.
    
    Args:
        comp_id (int): Competition ID
        key_suffix (str): Additional key identifier
        
    Returns:
        str: Cache key
    """
    return f"comp:{comp_id}:{key_suffix}"

# Pre-configured cache decorators for common use cases
@cached_db_query(timeout=600, key_prefix='stats')
def cache_platform_stats(func):
    """Cache platform statistics for 10 minutes"""
    return func

@cached_db_query(timeout=300, key_prefix='competitions')
def cache_competitions(func):
    """Cache competition data for 5 minutes"""
    return func

@cached_db_query(timeout=180, key_prefix='leaderboard')
def cache_leaderboard(func):
    """Cache leaderboard data for 3 minutes"""
    return func

@cached_db_query(timeout=900, key_prefix='challenges')
def cache_challenges(func):
    """Cache challenge data for 15 minutes"""
    return func

# Function to warm up critical caches
def warm_critical_caches():
    """
    Pre-populate critical caches with frequently accessed data.
    Should be called during application startup or periodically.
    """
    try:
        from app.routes.main import (
            get_platform_stats, 
            get_top_players,
            get_home_active_competitions, 
            get_home_upcoming_competitions
        )
        
        # Warm up homepage data
        get_platform_stats()
        get_top_players(10)
        get_home_active_competitions()
        get_home_upcoming_competitions()
        
        logger.info("Critical caches warmed up successfully")
        
    except Exception as e:
        logger.warning(f"Failed to warm up caches: {e}")

# Cache health check
def cache_health_check():
    """
    Check if caching system is working properly.
    
    Returns:
        dict: Cache health status
    """
    try:
        from app.extensions import cache
        test_key = "health_check_test"
        test_value = {"timestamp": time.time(), "status": "ok"}
        
        # Set and get test value
        cache.set(test_key, test_value, timeout=60)
        retrieved = cache.get(test_key)
        
        if retrieved and retrieved.get("status") == "ok":
            cache.delete(test_key)
            return {"status": "healthy", "type": current_app.config.get('CACHE_TYPE', 'unknown')}
        else:
            return {"status": "unhealthy", "error": "failed to retrieve test value"}
            
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
