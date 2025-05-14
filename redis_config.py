import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'db': int(os.getenv('REDIS_DB', 0)),
    'password': os.getenv('REDIS_PASSWORD', None),
    'decode_responses': True  # Automatically decode responses to strings
}

# Redis URL for connection
# Format: redis://username:password@host:port
REDIS_URL = os.getenv('REDIS_URL')

def get_redis_config():
    """Get Redis configuration dictionary"""
    return REDIS_CONFIG

def get_redis_url():
    """Get Redis URL for connection"""
    if REDIS_URL:
        return REDIS_URL
    return f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/{REDIS_CONFIG['db']}"

def get_redis_client():
    """Get a configured Redis client"""
    import redis
    if REDIS_URL:
        return redis.from_url(REDIS_URL, decode_responses=True)
    return redis.Redis(**REDIS_CONFIG) 