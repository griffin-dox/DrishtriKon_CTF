"""
Comprehensive cache management and storage optimization for DrishtriKon CTF Platform
Handles cache cleanup, storage monitoring, and automated maintenance
"""

import os
import time
import shutil
import logging
import threading
import schedule
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import psutil

from core.production_cache import get_cache

logger = logging.getLogger(__name__)

class CacheStorageManager:
    """
    Manages cache storage, cleanup, and optimization
    """
    
    def __init__(self, 
                 cache_dir: str = "cache_data",
                 max_storage_mb: int = 500,  # 500MB default limit
                 cleanup_interval_hours: int = 6,  # Cleanup every 6 hours
                 storage_warning_threshold: float = 0.8):  # Warn at 80% capacity
        
        self.cache_dir = Path(cache_dir)
        self.max_storage_mb = max_storage_mb
        self.cleanup_interval_hours = cleanup_interval_hours
        self.storage_warning_threshold = storage_warning_threshold
        
        # Statistics
        self.cleanup_stats = {
            "last_cleanup": None,
            "total_cleanups": 0,
            "files_removed": 0,
            "space_freed_mb": 0.0,
            "avg_cleanup_time": 0.0
        }
        
        # Schedule automatic cleanup
        self._schedule_cleanup()
        
        logger.info(f"CacheStorageManager initialized: max_storage={max_storage_mb}MB, cleanup_interval={cleanup_interval_hours}h")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get current cache storage statistics"""
        try:
            if not self.cache_dir.exists():
                return {
                    "current_size_mb": 0,
                    "file_count": 0,
                    "usage_percent": 0,
                    "status": "healthy"
                }
            
            # Calculate total size
            total_size = 0
            file_count = 0
            
            for file_path in self.cache_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            current_size_mb = total_size / (1024 * 1024)
            usage_percent = (current_size_mb / self.max_storage_mb) * 100
            
            # Determine status
            if usage_percent >= 95:
                status = "critical"
            elif usage_percent >= self.storage_warning_threshold * 100:
                status = "warning"
            else:
                status = "healthy"
            
            return {
                "current_size_mb": round(current_size_mb, 2),
                "max_size_mb": self.max_storage_mb,
                "file_count": file_count,
                "usage_percent": round(usage_percent, 2),
                "status": status,
                "cache_dir": str(self.cache_dir),
                "cleanup_stats": self.cleanup_stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {"error": str(e)}
    
    def cleanup_expired_cache(self, force: bool = False) -> Dict[str, Any]:
        """
        Clean up expired cache files and manage storage limits
        
        Args:
            force (bool): Force cleanup even if under storage limits
            
        Returns:
            Dict with cleanup results
        """
        start_time = time.time()
        
        try:
            cache = get_cache()
            
            # First, run the cache's built-in cleanup for expired files
            expired_cleaned = cache.cleanup_expired()
            
            # Get current storage stats
            stats = self.get_storage_stats()
            
            files_removed = expired_cleaned
            space_freed = 0.0
            
            # If storage is still over limit or force cleanup, do additional cleanup
            if force or stats.get("usage_percent", 0) > self.storage_warning_threshold * 100:
                additional_removed, additional_freed = self._aggressive_cleanup()
                files_removed += additional_removed
                space_freed += additional_freed
            
            # Update cleanup statistics
            cleanup_time = time.time() - start_time
            self.cleanup_stats["last_cleanup"] = datetime.now().isoformat()
            self.cleanup_stats["total_cleanups"] += 1
            self.cleanup_stats["files_removed"] += files_removed
            self.cleanup_stats["space_freed_mb"] += space_freed
            
            # Update average cleanup time
            total_time = self.cleanup_stats["avg_cleanup_time"] * (self.cleanup_stats["total_cleanups"] - 1) + cleanup_time
            self.cleanup_stats["avg_cleanup_time"] = total_time / self.cleanup_stats["total_cleanups"]
            
            result = {
                "status": "success",
                "files_removed": files_removed,
                "space_freed_mb": round(space_freed, 2),
                "cleanup_time_seconds": round(cleanup_time, 2),
                "storage_after_cleanup": self.get_storage_stats()
            }
            
            logger.info(f"Cache cleanup completed: {files_removed} files removed, {space_freed:.2f}MB freed")
            return result
            
        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")
            return {"status": "error", "error": str(e)}
    
    def _aggressive_cleanup(self) -> tuple:
        """
        Perform aggressive cleanup when storage is over limit
        Removes oldest cache files regardless of expiration
        
        Returns:
            tuple: (files_removed, space_freed_mb)
        """
        files_removed = 0
        space_freed = 0.0
        
        try:
            # Get all cache files sorted by modification time (oldest first)
            cache_files = []
            for file_path in self.cache_dir.glob("*.cache"):
                if file_path.exists():
                    stat = file_path.stat()
                    cache_files.append((file_path, stat.st_mtime, stat.st_size))
            
            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[1])
            
            # Remove oldest files until we're under the threshold
            target_size = self.max_storage_mb * self.storage_warning_threshold * 0.7  # Clean to 70% of warning threshold
            current_stats = self.get_storage_stats()
            current_size_mb = current_stats.get("current_size_mb", 0)
            
            for file_path, mod_time, file_size in cache_files:
                if current_size_mb <= target_size:
                    break
                
                try:
                    # Remove both cache and metadata files
                    metadata_path = file_path.with_suffix('.meta')
                    
                    if file_path.exists():
                        file_path.unlink()
                        space_freed += file_size / (1024 * 1024)
                        files_removed += 1
                    
                    if metadata_path.exists():
                        metadata_path.unlink()
                    
                    current_size_mb -= file_size / (1024 * 1024)
                    
                except Exception as e:
                    logger.warning(f"Error removing cache file {file_path}: {e}")
            
            if files_removed > 0:
                logger.warning(f"Aggressive cleanup: removed {files_removed} cache files ({space_freed:.2f}MB) to manage storage")
            
        except Exception as e:
            logger.error(f"Error during aggressive cleanup: {e}")
        
        return files_removed, space_freed
    
    def _schedule_cleanup(self):
        """Schedule automatic cache cleanup"""
        def run_scheduled_cleanup():
            logger.info("Running scheduled cache cleanup")
            self.cleanup_expired_cache()
        
        # Schedule cleanup every N hours
        schedule.every(self.cleanup_interval_hours).hours.do(run_scheduled_cleanup)
        
        # Run scheduler in background thread
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        logger.info(f"Scheduled cache cleanup every {self.cleanup_interval_hours} hours")
    
    def optimize_cache_structure(self) -> Dict[str, Any]:
        """
        Optimize cache directory structure and file organization
        """
        try:
            # Create subdirectories for better organization
            subdirs = ["db", "api", "template", "static", "temp"]
            for subdir in subdirs:
                subdir_path = self.cache_dir / subdir
                subdir_path.mkdir(exist_ok=True)
            
            # Move existing cache files to appropriate subdirectories based on prefix
            moved_files = 0
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    # Read metadata to determine category
                    metadata_file = cache_file.with_suffix('.meta')
                    if metadata_file.exists():
                        with open(metadata_file, 'r') as f:
                            import json
                            metadata = json.load(f)
                            key = metadata.get('key', '')
                            
                            # Determine subdirectory based on key prefix
                            target_subdir = "temp"  # default
                            if key.startswith('db:'):
                                target_subdir = "db"
                            elif key.startswith('api:'):
                                target_subdir = "api"
                            elif key.startswith('template:'):
                                target_subdir = "template"
                            elif key.startswith('static:'):
                                target_subdir = "static"
                            
                            # Move files if not already in subdirectory
                            if cache_file.parent.name != target_subdir:
                                target_dir = self.cache_dir / target_subdir
                                target_cache = target_dir / cache_file.name
                                target_meta = target_dir / metadata_file.name
                                
                                if not target_cache.exists():
                                    shutil.move(str(cache_file), str(target_cache))
                                    shutil.move(str(metadata_file), str(target_meta))
                                    moved_files += 1
                                
                except Exception as e:
                    logger.warning(f"Error organizing cache file {cache_file}: {e}")
            
            return {
                "status": "success",
                "moved_files": moved_files,
                "subdirectories_created": len(subdirs)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing cache structure: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_system_storage_info(self) -> Dict[str, Any]:
        """Get overall system storage information"""
        try:
            # Get disk usage for the cache directory
            cache_disk_usage = shutil.disk_usage(self.cache_dir.parent)
            
            # Get system memory info
            memory = psutil.virtual_memory()
            
            return {
                "disk": {
                    "total_gb": round(cache_disk_usage.total / (1024**3), 2),
                    "used_gb": round(cache_disk_usage.used / (1024**3), 2),
                    "free_gb": round(cache_disk_usage.free / (1024**3), 2),
                    "usage_percent": round((cache_disk_usage.used / cache_disk_usage.total) * 100, 2)
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "usage_percent": memory.percent
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting system storage info: {e}")
            return {"error": str(e)}
    
    def emergency_cleanup(self) -> Dict[str, Any]:
        """
        Emergency cleanup when storage is critically full
        Removes all cache files regardless of expiration
        """
        try:
            removed_files = 0
            space_freed = 0.0
            
            # Remove all cache files
            for file_path in self.cache_dir.rglob("*"):
                if file_path.is_file() and file_path.suffix in ['.cache', '.meta']:
                    try:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        space_freed += file_size / (1024 * 1024)
                        removed_files += 1
                    except Exception as e:
                        logger.warning(f"Error removing file {file_path}: {e}")
            
            # Clear in-memory cache as well
            cache = get_cache()
            cache.clear()
            
            logger.warning(f"Emergency cleanup completed: {removed_files} files removed, {space_freed:.2f}MB freed")
            
            return {
                "status": "success",
                "files_removed": removed_files,
                "space_freed_mb": round(space_freed, 2),
                "message": "Emergency cleanup completed - all cache cleared"
            }
            
        except Exception as e:
            logger.error(f"Error during emergency cleanup: {e}")
            return {"status": "error", "error": str(e)}

# Global cache manager instance
_cache_manager = None

def get_cache_manager() -> CacheStorageManager:
    """Get the global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        cache_dir = os.getenv('CACHE_DIR', 'cache_data')
        max_storage = int(os.getenv('CACHE_MAX_STORAGE_MB', '500'))
        _cache_manager = CacheStorageManager(cache_dir, max_storage)
    return _cache_manager

def schedule_cache_maintenance():
    """Schedule regular cache maintenance tasks"""
    cache_manager = get_cache_manager()
    
    # Run initial cleanup
    logger.info("Running initial cache cleanup...")
    cache_manager.cleanup_expired_cache()
    
    # Optimize cache structure
    logger.info("Optimizing cache structure...")
    cache_manager.optimize_cache_structure()
    
    logger.info("Cache maintenance scheduling completed")

# Utility functions for easy access
def cleanup_cache(force: bool = False) -> Dict[str, Any]:
    """Clean up cache files - wrapper function"""
    return get_cache_manager().cleanup_expired_cache(force)

def get_cache_storage_stats() -> Dict[str, Any]:
    """Get cache storage statistics - wrapper function"""
    return get_cache_manager().get_storage_stats()

def emergency_clear_cache() -> Dict[str, Any]:
    """Emergency cache clearing - wrapper function"""
    return get_cache_manager().emergency_cleanup()
