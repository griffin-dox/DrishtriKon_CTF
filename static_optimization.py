import os
import re
import logging
import hashlib
import time
from flask import request, url_for

# Cache variables for optimized static URLs
_static_file_cache = {}
_static_file_version_cache = {}
_last_static_file_check = 0
_STATIC_CHECK_INTERVAL = 3600  # Check static files once per hour

def get_static_url(filename):
    """
    Generate a URL for a static file with cache-busting version parameter.
    
    Args:
        filename (str): The path to the static file relative to the static folder
        
    Returns:
        str: URL with cache-busting version parameter
    """
    # Add version parameter for cache busting
    version = get_file_version(filename)
    return url_for('static', filename=filename, v=version)

def get_file_version(filename):
    """
    Get a version identifier for a static file based on its modification time or content hash.
    
    Args:
        filename (str): The path to the static file relative to the static folder
        
    Returns:
        str: Version identifier for the file
    """
    global _last_static_file_check, _static_file_version_cache
    
    current_time = time.time()
    
    # Periodically check if static files have changed
    if current_time - _last_static_file_check > _STATIC_CHECK_INTERVAL:
        _static_file_version_cache = {}
        _last_static_file_check = current_time
    
    # Return cached version if available
    if filename in _static_file_version_cache:
        return _static_file_version_cache[filename]
    
    # Generate a version based on file modification time or content hash
    full_path = os.path.join('static', filename)
    
    if os.path.exists(full_path):
        try:
            # Use modified time for quick version generation
            version = str(int(os.path.getmtime(full_path)))
            
            # For CSS and JS files, use content hash for more precise versioning
            if filename.endswith(('.css', '.js')):
                with open(full_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()[:8]
                    version = file_hash
            
            _static_file_version_cache[filename] = version
            return version
        except Exception as e:
            logging.error(f"Error generating version for {filename}: {str(e)}")
    
    # Default version if file not found or error occurred
    return 'dev'

def add_static_url_processor(app):
    """
    Add a template context processor for static URL generation.
    
    Args:
        app: Flask application instance
    """
    @app.context_processor
    def static_processor():
        return {
            'static_url': get_static_url
        }