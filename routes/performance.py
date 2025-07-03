"""
Performance monitoring and optimization endpoints for admin use.
"""

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user
from core.models import UserRole
from core.performance_cache import cache_health_check, warm_critical_caches
from core.db_optimization import get_database_stats, monitor_connection_pool, analyze_query_performance
from core.cache_management import get_cache_manager, cleanup_cache, get_cache_storage_stats, emergency_clear_cache
from functools import wraps
import time
import psutil
import os

performance_bp = Blueprint('performance', __name__, url_prefix='/admin/performance')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != UserRole.OWNER:
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

@performance_bp.route('/dashboard')
@login_required
@admin_required
def performance_dashboard():
    """Performance monitoring dashboard for admins"""
    return render_template('admin/performance_dashboard.html', title='Performance Monitor')

@performance_bp.route('/api/cache-health')
@login_required
@admin_required
def cache_health():
    """Get cache system health status"""
    return jsonify(cache_health_check())

@performance_bp.route('/api/warm-cache', methods=['POST'])
@login_required
@admin_required
def warm_cache():
    """Manually warm up critical caches"""
    start_time = time.time()
    warm_critical_caches()
    end_time = time.time()
    
    return jsonify({
        "status": "success",
        "message": "Critical caches warmed up",
        "duration_seconds": round(end_time - start_time, 2)
    })

@performance_bp.route('/api/db-stats')
@login_required
@admin_required
def database_stats():
    """Get database performance statistics"""
    return jsonify(get_database_stats())

@performance_bp.route('/api/connection-pool')
@login_required
@admin_required
def connection_pool_stats():
    """Get database connection pool statistics"""
    return jsonify(monitor_connection_pool())

@performance_bp.route('/api/system-stats')
@login_required
@admin_required
def system_stats():
    """Get system resource statistics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return jsonify({
            "cpu_percent": cpu_percent,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": (disk.used / disk.total) * 100
            },
            "process": {
                "pid": os.getpid(),
                "threads": psutil.Process().num_threads()
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@performance_bp.route('/api/query-analysis')
@login_required
@admin_required
def query_analysis():
    """Analyze query performance and identify issues"""
    problematic_tables = analyze_query_performance()
    
    return jsonify({
        "problematic_tables": [
            {
                "schema": table.schemaname,
                "table": table.tablename,
                "sequential_scans": table.seq_scan,
                "index_scans": table.idx_scan,
                "ratio": round(table.seq_scan / max(table.idx_scan, 1), 2)
            } for table in problematic_tables
        ],
        "recommendations": [
            "Consider adding indexes to tables with high sequential scan ratios",
            "Review queries that frequently scan large tables",
            "Monitor connection pool usage during peak hours"
        ]
    })

@performance_bp.route('/api/optimize', methods=['POST'])
@login_required
@admin_required
def run_optimizations():
    """Run various performance optimizations"""
    optimizations_run = []
    
    try:
        # Warm up caches
        warm_critical_caches()
        optimizations_run.append("Cache warming completed")
        
        # Clear old cache entries
        from app import cache
        cache.clear()
        optimizations_run.append("Cache cleared and refreshed")
        
        # Analyze queries
        analyze_query_performance()
        optimizations_run.append("Query performance analysis completed")
        
        return jsonify({
            "status": "success",
            "optimizations": optimizations_run,
            "message": "Performance optimizations completed"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "optimizations": optimizations_run
        }), 500

@performance_bp.route('/api/metrics')
@login_required
@admin_required
def performance_metrics():
    """Get comprehensive performance metrics"""
    try:
        start_time = time.time()
        
        # Collect all metrics
        cache_health = cache_health_check()
        db_pool = monitor_connection_pool()
        system = system_stats().get_json()
        
        collection_time = time.time() - start_time
        
        return jsonify({
            "timestamp": time.time(),
            "collection_time_seconds": round(collection_time, 3),
            "cache": cache_health,
            "database_pool": db_pool,
            "system": system,
            "status": "healthy" if cache_health.get("status") == "healthy" else "degraded"
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@performance_bp.route('/api/cache-storage-stats')
@login_required
@admin_required
def cache_storage_stats():
    """Get detailed cache storage statistics"""
    try:
        cache_manager = get_cache_manager()
        storage_stats = cache_manager.get_storage_stats()
        system_info = cache_manager.get_system_storage_info()
        
        return jsonify({
            "status": "success",
            "cache_storage": storage_stats,
            "system_storage": system_info
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@performance_bp.route('/api/cleanup-cache', methods=['POST'])
@login_required
@admin_required
def cleanup_cache_endpoint():
    """Run cache cleanup"""
    try:
        force = request.json.get('force', False) if request.is_json else False
        result = cleanup_cache(force=force)
        
        return jsonify({
            "status": "success",
            "message": f"Cache cleanup completed: {result['files_removed']} files removed, {result['space_freed_mb']}MB freed",
            "cleanup_result": result
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@performance_bp.route('/api/emergency-clear-cache', methods=['POST'])
@login_required
@admin_required
def emergency_clear_cache_endpoint():
    """Emergency cache clearing"""
    try:
        result = emergency_clear_cache()
        
        return jsonify({
            "status": "success",
            "message": f"Emergency cleanup completed: {result['files_removed']} files removed, {result['space_freed_mb']}MB freed",
            "cleanup_result": result
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@performance_bp.route('/api/optimize-cache-structure', methods=['POST'])
@login_required
@admin_required
def optimize_cache_structure():
    """Optimize cache directory structure"""
    try:
        cache_manager = get_cache_manager()
        result = cache_manager.optimize_cache_structure()
        
        return jsonify({
            "status": "success",
            "message": f"Cache structure optimized: {result['moved_files']} files organized",
            "optimization_result": result
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
