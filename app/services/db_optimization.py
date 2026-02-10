"""
Database performance optimization utilities for the CTF platform.
"""

import logging
from sqlalchemy import Index, text
from sqlalchemy.orm import selectinload, joinedload
from app.extensions import db
from app.models import User, Challenge, Competition, UserRole, CompetitionStatus

logger = logging.getLogger(__name__)

def create_performance_indexes():
    """
    Create database indexes for better query performance.
    Run this during deployment or maintenance windows.
    """
    try:
        with db.engine.connect() as conn:
            # Users table indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
                CREATE INDEX IF NOT EXISTS idx_users_score ON users(score DESC);
                CREATE INDEX IF NOT EXISTS idx_users_email_verified ON users(email_verified);
                CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
            """))
            
            # Challenges table indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_challenges_type ON challenges(type);
                CREATE INDEX IF NOT EXISTS idx_challenges_visibility ON challenges(visibility_scope);
                CREATE INDEX IF NOT EXISTS idx_challenges_points ON challenges(points DESC);
                CREATE INDEX IF NOT EXISTS idx_challenges_created_at ON challenges(created_at DESC);
            """))
            
            # Competitions table indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_competitions_manual_status ON competitions(manual_status_override);
                CREATE INDEX IF NOT EXISTS idx_competitions_start_time ON competitions(start_time);
                CREATE INDEX IF NOT EXISTS idx_competitions_end_time ON competitions(end_time);
                CREATE INDEX IF NOT EXISTS idx_competitions_created_at ON competitions(created_at DESC);
            """))
            
            # Submissions table indexes (if exists)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id);
                CREATE INDEX IF NOT EXISTS idx_submissions_challenge_id ON submissions(challenge_id);
                CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON submissions(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_submissions_correct ON submissions(correct);
            """))
            
            # Teams table indexes (if exists)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_teams_created_at ON teams(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_teams_score ON teams(score DESC);
            """))
            
            # Session security indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_sessions_created_at ON user_sessions(created_at);
                CREATE INDEX IF NOT EXISTS idx_banned_ips_ip_address ON banned_ips(ip_address);
                CREATE INDEX IF NOT EXISTS idx_rate_limits_identifier ON rate_limits(identifier);
            """))
            
            conn.commit()
            logger.info("Performance indexes created successfully")
            
    except Exception as e:
        logger.error(f"Failed to create performance indexes: {e}")

def optimize_query_users_leaderboard(limit=50):
    """
    Optimized query for user leaderboard with minimal data transfer.
    """
    return (
        db.session.query(
            User.id,
            User.username,
            User.score
        )
        .filter(User.role == UserRole.PLAYER)
        .filter(User.status == 'active')
        .order_by(User.score.desc())
        .limit(limit)
        .all()
    )

def optimize_query_active_competitions():
    """
    Optimized query for active competitions with eager loading.
    """
    return (
        Competition.query
        .filter(Competition.status == CompetitionStatus.ACTIVE)
        .options(selectinload(Competition.challenges)) 
        .order_by(Competition.start_time)
        .all()
    )

def optimize_query_user_profile(user_id):
    """
    Optimized query for user profile with all related data.
    """
    return (
        User.query
        .options(
            selectinload(getattr(User, "submissions")),
            selectinload(getattr(User, "team_memberships")),
            selectinload(getattr(User, "badges"))
        )
        .filter(User.id == user_id)
        .first()
    )

def optimize_query_challenge_with_submissions(challenge_id):
    """
    Optimized query for challenge details with submission counts.
    """
    return (
        Challenge.query
        .options(selectinload(getattr(Challenge, "submissions")))
        .filter(Challenge.id == challenge_id)
        .first()
    )

def get_database_stats():
    """
    Get database performance statistics.
    """
    try:
        with db.engine.connect() as conn:
            stats = {}
            
            # Table sizes
            result = conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation
                FROM pg_stats 
                WHERE schemaname = 'public'
                ORDER BY tablename, attname;
            """))
            
            stats['table_stats'] = result.fetchall()
            
            # Index usage
            result = conn.execute(text("""
                SELECT 
                    indexrelname,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes 
                ORDER BY idx_tup_read DESC;
            """))
            
            stats['index_usage'] = result.fetchall()
            
            # Slow queries (if pg_stat_statements is enabled)
            try:
                result = conn.execute(text("""
                    SELECT 
                        query,
                        calls,
                        total_time,
                        mean_time
                    FROM pg_stat_statements 
                    ORDER BY mean_time DESC 
                    LIMIT 10;
                """))
                stats['slow_queries'] = result.fetchall()
            except:
                stats['slow_queries'] = "pg_stat_statements not available"
            
            return stats
            
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {"error": str(e)}

def analyze_query_performance():
    """
    Analyze and log query performance issues.
    """
    try:
        # Check for missing indexes
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    seq_scan,
                    seq_tup_read,
                    idx_scan,
                    idx_tup_fetch
                FROM pg_stat_user_tables 
                WHERE seq_scan > idx_scan
                ORDER BY seq_scan DESC;
            """))
            
            problematic_tables = result.fetchall()
            
            if problematic_tables:
                logger.warning(f"Tables with high sequential scans: {len(problematic_tables)}")
                for table in problematic_tables[:5]:  # Log top 5
                    logger.warning(f"Table {table.tablename}: {table.seq_scan} seq scans vs {table.idx_scan} index scans")
            
            return problematic_tables
            
    except Exception as e:
        logger.error(f"Failed to analyze query performance: {e}")
        return []

# Connection pool monitoring
def monitor_connection_pool():
    """
    Monitor database connection pool health.
    """
    try:
        pool = db.engine.pool
        # Not all pool types support all methods; use getattr with fallback
        stats = {}
        # Pool size (current pool size)
        stats["pool_size"] = getattr(pool, 'size', lambda: None)()
        # Number of connections currently checked out
        stats["checked_out"] = getattr(pool, 'checkedout', lambda: None)()
        # Number of connections currently checked in (available)
        stats["checked_in"] = getattr(pool, 'checkedin', lambda: None)()
        # Overflow (connections above pool_size)
        stats["overflow"] = getattr(pool, 'overflow', lambda: None)()
        # Invalid connections (not always available)
        stats["invalid"] = getattr(pool, 'invalid', lambda: None)()
        return stats
    except Exception as e:
        logger.error(f"Failed to monitor connection pool: {e}")
        return {"error": str(e)}
