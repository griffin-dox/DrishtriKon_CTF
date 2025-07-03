# Cache Storage Management Guide

## Overview

The DrishtriKon CTF platform uses a comprehensive cache management system that automatically handles cache storage optimization, cleanup, and monitoring to ensure efficient server storage usage.

## Cache Storage Location

- **Server Location**: Cache is stored in the `cache_data/` directory on the server filesystem
- **Not User Storage**: Cache files are stored on your web server, not in user browsers or local storage
- **Persistent**: Cache survives server restarts and is shared between all users

## Automatic Storage Management

### Storage Limits
- **Default Limit**: 500MB (configurable via `CACHE_MAX_STORAGE_MB` in `.env`)
- **Warning Threshold**: 80% of limit (400MB by default)
- **Critical Threshold**: 95% of limit (475MB by default)

### Automatic Cleanup
- **Scheduled Cleanup**: Runs every 6 hours automatically
- **Expired File Removal**: Removes cache files that have exceeded their TTL
- **Aggressive Cleanup**: When storage exceeds warning threshold, removes oldest files regardless of expiration
- **Emergency Cleanup**: Available for critical storage situations

### Storage Optimization
- **Directory Organization**: Cache files are organized into subdirectories by type:
  - `db/` - Database query cache
  - `api/` - API response cache
  - `template/` - Template rendering cache
  - `static/` - Static asset cache
  - `temp/` - Temporary cache files

## Cache Types and TTL (Time To Live)

| Cache Type | Default TTL | Purpose |
|------------|-------------|---------|
| Database Queries | 5 minutes (300s) | User data, leaderboards, challenge info |
| API Responses | 3 minutes (180s) | External API calls, service responses |
| Template Data | 10 minutes (600s) | Rendered page components, layouts |
| Platform Stats | 10 minutes (600s) | Homepage statistics, counters |
| Leaderboard | 3 minutes (180s) | Competition rankings |
| Challenges | 15 minutes (900s) | Challenge details, descriptions |

## Admin Controls

### Performance Dashboard (`/admin/performance/dashboard`)

#### Basic Operations
- **Clear Expired Cache**: Removes only expired cache files
- **Warm Cache**: Pre-populates frequently accessed data
- **Refresh Data**: Updates dashboard metrics

#### Advanced Operations
- **Cleanup Storage**: Force cleanup regardless of expiration if approaching storage limits
- **Optimize Structure**: Reorganizes cache files into optimized directory structure
- **Emergency Clear**: ⚠️ Removes ALL cache files (use only in emergencies)

### Monitoring Metrics
- **Cache Storage Usage**: Current size vs. limit with percentage
- **File Count**: Number of cached files
- **Disk Space**: Overall server disk usage
- **Hit Rate**: Cache effectiveness percentage
- **Cleanup Statistics**: History of maintenance operations

## Configuration

### Environment Variables (`.env`)
```env
# Cache type (filesystem recommended for production)
CACHE_TYPE=filesystem

# Cache directory location
CACHE_DIR=cache_data

# Maximum storage limit in MB
CACHE_MAX_STORAGE_MB=500
```

### Adjusting Storage Limits
To increase cache storage limit:
1. Edit `.env` file: `CACHE_MAX_STORAGE_MB=1000` (for 1GB)
2. Restart the application
3. Monitor disk space to ensure server has sufficient capacity

## Storage Optimization Best Practices

### 1. Monitor Regularly
- Check the Performance Dashboard weekly
- Watch for storage warnings
- Monitor hit rates to ensure cache effectiveness

### 2. Adjust TTL Values
For high-traffic periods, consider reducing TTL values in the code:
```python
# Reduce cache time for dynamic content during events
@cache_leaderboard(timeout=60)  # 1 minute instead of 3
def get_competition_leaderboard():
    # ...
```

### 3. Clean Up During Maintenance
- Run manual cleanup before major events
- Use "Optimize Structure" monthly
- Emergency clear only if storage critically full

### 4. Server Storage Planning
- Ensure server has at least 2GB free space beyond cache limit
- Monitor overall disk usage trends
- Consider cache limit adjustments based on user load

## Troubleshooting

### High Storage Usage
1. **Check for Expired Files**: Run "Cleanup Storage" in dashboard
2. **Reduce TTL Values**: Modify cache timeout values in code
3. **Increase Storage Limit**: Adjust `CACHE_MAX_STORAGE_MB` if server has space
4. **Emergency Clear**: Last resort - removes all cache

### Poor Cache Performance
1. **Check Hit Rates**: Should be >70% for effective caching
2. **Warm Critical Caches**: Use "Warm Cache" function
3. **Optimize Structure**: Reorganize cache files
4. **Monitor Response Times**: Use dashboard metrics

### Storage Warnings
- **Warning (80% full)**: Automatic aggressive cleanup activated
- **Critical (95% full)**: Consider manual intervention
- **Full (100%)**: Emergency cleanup required

## Automated Background Tasks

### Cleanup Schedule
- **Frequency**: Every 6 hours
- **Process**: 
  1. Remove expired cache files
  2. Check storage usage
  3. If over threshold, remove oldest files
  4. Log cleanup statistics

### Startup Tasks
- **Cache Structure Check**: Ensures proper directory organization
- **Initial Cleanup**: Removes any corrupted or orphaned cache files
- **Cache Warming**: Pre-populates critical data

## Performance Impact

### Benefits
- **Faster Load Times**: Frequently accessed data served from cache
- **Reduced Database Load**: Fewer queries to database
- **Better User Experience**: Faster page loads and responses
- **Server Efficiency**: Less CPU usage for repeated operations

### Storage Trade-offs
- **Disk Space**: Uses server storage for performance gains
- **Memory Usage**: In-memory cache layer for fastest access
- **Network**: Reduces external API calls and database queries

## Monitoring and Alerts

### Built-in Monitoring
- Real-time storage usage tracking
- Automatic cleanup when thresholds exceeded
- Performance metrics and statistics
- Health checks for cache system

### Recommended Monitoring
- Set up disk space alerts on your server
- Monitor cache hit rates weekly
- Review cleanup statistics monthly
- Check performance dashboard during high-traffic events

## Security Considerations

### Cache Security
- Cache files are server-side only (not accessible to users)
- No sensitive data should be cached without encryption
- Cache directories have appropriate file permissions
- Regular cleanup prevents data accumulation

### Data Privacy
- User-specific cache keys use hashed identifiers
- Cache expiration ensures data freshness
- Emergency cleanup available for immediate data removal
