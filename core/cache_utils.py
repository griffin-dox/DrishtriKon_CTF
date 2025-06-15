import time
import logging
import functools
from datetime import datetime, timedelta

# Dictionary to store cached results
_query_cache = {}

def cached_query(ttl=60):
    """
    Decorator to cache function results, particularly useful for expensive database queries.
    
    Args:
        ttl (int): Time to live for cache in seconds
        
    Returns:
        Decorated function with caching
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Check if we have a valid cached result
            current_time = time.time()
            if cache_key in _query_cache:
                result, timestamp = _query_cache[cache_key]
                if current_time - timestamp < ttl:
                    # Return cached result if still valid
                    return result
            
            # No valid cache found, call the function
            result = func(*args, **kwargs)
            
            # Cache the result
            _query_cache[cache_key] = (result, current_time)
            
            # Clean up expired cache entries periodically (1% chance each call)
            if hash(cache_key) % 100 == 0:
                clean_expired_cache(ttl)
                
            return result
        return wrapper
    return decorator

def clean_expired_cache(ttl):
    """
    Remove expired entries from the cache
    
    Args:
        ttl (int): Time to live in seconds
    """
    current_time = time.time()
    expired_keys = [
        key for key, (_, timestamp) in _query_cache.items() 
        if current_time - timestamp > ttl
    ]
    
    # Delete expired items
    for key in expired_keys:
        del _query_cache[key]
    
    if expired_keys:
        logging.debug(f"Cleaned {len(expired_keys)} expired cache entries")

def invalidate_cache(key_prefix=None):
    """
    Invalidate cache entries. If key_prefix is provided, only invalidate
    entries starting with that prefix.
    
    Args:
        key_prefix (str, optional): Prefix of keys to invalidate
    """
    global _query_cache
    
    if key_prefix:
        keys_to_remove = [k for k in _query_cache if k.startswith(key_prefix)]
        for key in keys_to_remove:
            del _query_cache[key]
        logging.debug(f"Invalidated {len(keys_to_remove)} cache entries with prefix '{key_prefix}'")
    else:
        count = len(_query_cache)
        _query_cache = {}
        logging.debug(f"Invalidated all {count} cache entries")