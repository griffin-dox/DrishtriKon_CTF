"""
Production-ready caching system for DrishtriKon CTF Platform
Supports filesystem persistence, thread safety, and memory management
"""

import os
import json
import time
import pickle
import logging
import hashlib
import threading
import functools
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

class ProductionCache:
    """
    Production-ready cache with filesystem persistence and memory management
    """
    
    def __init__(self, cache_dir: str = "cache_data", max_memory_items: int = 1000):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_memory_items = max_memory_items
        
        # Thread-safe memory cache
        self._memory_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_timeouts: Dict[str, int] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "memory_evictions": 0,
            "file_reads": 0,
            "file_writes": 0
        }
        
        logger.info(f"ProductionCache initialized with cache_dir={cache_dir}")
    
    def _get_file_path(self, key: str) -> Path:
        """Get the file path for a cache key"""
        # Use hash to avoid filesystem issues with special characters
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"
    
    def _evict_memory_if_needed(self):
        """Evict oldest items from memory cache if needed"""
        if len(self._memory_cache) <= self.max_memory_items:
            return
        
        # Sort by timestamp and remove oldest items
        sorted_items = sorted(
            self._cache_timestamps.items(), 
            key=lambda x: x[1]
        )
        
        items_to_remove = len(self._memory_cache) - self.max_memory_items + 100
        for key, _ in sorted_items[:items_to_remove]:
            self._memory_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
            self._cache_timeouts.pop(key, None)
            self._stats["memory_evictions"] += 1
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        with self._lock:
            current_time = time.time()
            
            # Check memory cache first
            if key in self._memory_cache:
                if key in self._cache_timestamps and key in self._cache_timeouts:
                    if current_time - self._cache_timestamps[key] < self._cache_timeouts[key]:
                        self._stats["hits"] += 1
                        return self._memory_cache[key]
                    else:
                        # Expired in memory
                        self._memory_cache.pop(key, None)
                        self._cache_timestamps.pop(key, None)
                        self._cache_timeouts.pop(key, None)
            
            # Check file cache
            file_path = self._get_file_path(key)
            if file_path.exists():
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    
                    # Read metadata to check timeout
                    metadata_path = file_path.with_suffix('.meta')
                    timeout = 300  # default 5 minutes
                    
                    if metadata_path.exists():
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            timeout = metadata.get('timeout', 300)
                    
                    if file_age < timeout:
                        with open(file_path, 'rb') as f:
                            value = pickle.load(f)
                        
                        # Store in memory for faster access
                        self._memory_cache[key] = value
                        self._cache_timestamps[key] = current_time
                        self._cache_timeouts[key] = timeout
                        self._evict_memory_if_needed()
                        
                        self._stats["hits"] += 1
                        self._stats["file_reads"] += 1
                        return value
                    else:
                        # Expired file, remove it
                        file_path.unlink(missing_ok=True)
                        metadata_path.unlink(missing_ok=True)
                
                except Exception as e:
                    logger.warning(f"Error reading cache file {file_path}: {e}")
                    file_path.unlink(missing_ok=True)
            
            self._stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any, timeout: int = 300):
        """Set a value in cache"""
        with self._lock:
            current_time = time.time()
            
            # Store in memory
            self._memory_cache[key] = value
            self._cache_timestamps[key] = current_time
            self._cache_timeouts[key] = timeout
            self._evict_memory_if_needed()
            
            # Store in file asynchronously (in production, use a background thread)
            try:
                file_path = self._get_file_path(key)
                metadata_path = file_path.with_suffix('.meta')
                
                # Write data
                with open(file_path, 'wb') as f:
                    pickle.dump(value, f)
                
                # Write metadata
                metadata = {
                    'timeout': timeout,
                    'created_at': current_time,
                    'key': key  # for debugging
                }
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f)
                
                self._stats["file_writes"] += 1
                
            except Exception as e:
                logger.warning(f"Failed to write cache file for key {key}: {e}")
            
            self._stats["sets"] += 1
    
    def delete(self, key: str):
        """Delete a value from cache"""
        with self._lock:
            # Remove from memory
            self._memory_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
            self._cache_timeouts.pop(key, None)
            
            # Remove from file
            file_path = self._get_file_path(key)
            metadata_path = file_path.with_suffix('.meta')
            file_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            # Clear memory
            self._memory_cache.clear()
            self._cache_timestamps.clear()
            self._cache_timeouts.clear()
            
            # Clear files
            for file_path in self.cache_dir.glob("*.cache"):
                file_path.unlink(missing_ok=True)
            for file_path in self.cache_dir.glob("*.meta"):
                file_path.unlink(missing_ok=True)
    
    def cleanup_expired(self):
        """Clean up expired cache files"""
        current_time = time.time()
        cleaned_count = 0
        
        try:
            for metadata_path in self.cache_dir.glob("*.meta"):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    file_age = current_time - metadata.get('created_at', 0)
                    timeout = metadata.get('timeout', 300)
                    
                    if file_age > timeout:
                        # Remove both data and metadata files
                        cache_path = metadata_path.with_suffix('.cache')
                        metadata_path.unlink(missing_ok=True)
                        cache_path.unlink(missing_ok=True)
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.warning(f"Error cleaning cache file {metadata_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired cache files")
        
        return cleaned_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
            
            # Count files
            cache_files = list(self.cache_dir.glob("*.cache"))
            total_size = sum(f.stat().st_size for f in cache_files if f.exists())
            
            return {
                "memory_entries": len(self._memory_cache),
                "file_entries": len(cache_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "hit_rate_percent": round(hit_rate, 2),
                "statistics": self._stats.copy(),
                "cache_dir": str(self.cache_dir),
                "max_memory_items": self.max_memory_items
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Check cache health"""
        try:
            test_key = "health_check_test"
            test_value = {"timestamp": time.time(), "status": "ok"}
            
            # Test set and get
            self.set(test_key, test_value, timeout=60)
            retrieved = self.get(test_key)
            
            if retrieved and retrieved.get("status") == "ok":
                self.delete(test_key)
                return {"status": "healthy", "type": "production_filesystem"}
            else:
                return {"status": "unhealthy", "error": "failed to retrieve test value"}
                
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

# Global cache instance
_production_cache = None

def get_cache():
    """Get the global cache instance"""
    global _production_cache
    if _production_cache is None:
        cache_dir = os.getenv('CACHE_DIR', 'cache_data')
        _production_cache = ProductionCache(cache_dir)
    return _production_cache

def production_cache(timeout: int = 300, key_prefix: str = 'cache'):
    """
    Production-ready cache decorator
    
    Args:
        timeout (int): Cache timeout in seconds
        key_prefix (str): Prefix for cache keys
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Create cache key
            key_data = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try cache first
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache HIT for {func.__name__}")
                return result
            
            # Execute function
            logger.debug(f"Cache MISS for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store result
            cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator

# Pre-configured decorators
def cache_db_query(timeout: int = 300):
    """Cache database queries"""
    return production_cache(timeout=timeout, key_prefix='db')

def cache_api_data(timeout: int = 180):
    """Cache API responses"""
    return production_cache(timeout=timeout, key_prefix='api')

def cache_template_data(timeout: int = 600):
    """Cache template data"""
    return production_cache(timeout=timeout, key_prefix='template')
