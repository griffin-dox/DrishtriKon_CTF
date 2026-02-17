from flask import Blueprint, render_template, request
from app.models import Competition, Challenge, User, CompetitionStatus, UserRole
from sqlalchemy import func, desc
from datetime import datetime
from app.extensions import db
from app.services.cache.production import cache_db_query
from app.services.db_health import get_safe_db_result, require_db, render_db_error
import logging

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@require_db
def index():
    # Use cached queries for better performance
    # With graceful fallbacks if database is unavailable
    active_competitions = get_home_active_competitions()
    upcoming_competitions = get_home_upcoming_competitions()
    
    # Get statistics with caching
    platform_stats = get_platform_stats()
    
    # Get top players efficiently with caching
    top_players = get_top_players(10)
    
    return render_template('index.html', 
                           active_competitions=active_competitions if active_competitions else [],
                           upcoming_competitions=upcoming_competitions if upcoming_competitions else [],
                           total_users=platform_stats.get('total_users', 0) if platform_stats else 0,
                           total_challenges=platform_stats.get('total_challenges', 0) if platform_stats else 0,
                           total_competitions=platform_stats.get('total_competitions', 0) if platform_stats else 0,
                           top_players=top_players if top_players else [],
                           title='Drishti कोण - Home')

@cache_db_query(timeout=300)
def get_home_active_competitions():
    """Get active competitions for homepage with caching"""
    try:
        from datetime import datetime
        now = datetime.utcnow()
        
        # Query competitions that are currently active
        # Either manually overridden to ACTIVE, or within start/end time
        active_comps = Competition.query.filter(
            (Competition.manual_status_override == CompetitionStatus.ACTIVE) |
            ((Competition.start_time <= now) & (Competition.end_time > now))
        ).order_by(Competition.start_time).limit(5).all()
        
        return active_comps
    except Exception as e:
        logger.warning(f"Failed to fetch active competitions: {str(e)}")
        return []

@cache_db_query(timeout=300)
def get_home_upcoming_competitions():
    """Get upcoming competitions for homepage with caching"""
    try:
        from datetime import datetime
        now = datetime.utcnow()
        
        # Query competitions that are upcoming
        # Either manually overridden to UPCOMING, or start after now
        upcoming_comps = Competition.query.filter(
            (Competition.manual_status_override == CompetitionStatus.UPCOMING) |
            (Competition.start_time > now)
        ).order_by(Competition.start_time).limit(3).all()
        
        return upcoming_comps
    except Exception as e:
        logger.warning(f"Failed to fetch upcoming competitions: {str(e)}")
        return []

@cache_db_query(timeout=600)
def get_platform_stats():
    """Get platform statistics with caching"""
    try:
        total_users = db.session.query(func.count(User.id)).scalar() or 0
        total_challenges = db.session.query(func.count(Challenge.id)).scalar() or 0
        total_competitions = db.session.query(func.count(Competition.id)).scalar() or 0
        
        return {
            'total_users': total_users,
            'total_challenges': total_challenges,
            'total_competitions': total_competitions
        }
    except Exception as e:
        logger.warning(f"Failed to fetch platform stats: {str(e)}")
        return {
            'total_users': 0,
            'total_challenges': 0,
            'total_competitions': 0
        }

@cache_db_query(timeout=300)
def get_top_players(limit=10):
    """Get top players with caching"""
    try:
        return (
            User.query
            .filter_by(role=UserRole.PLAYER)
            .order_by(desc(User.score))
            .limit(limit)
            .all()
        )
    except Exception as e:
        logger.warning(f"Failed to fetch top players: {str(e)}")
        return []

@main_bp.route('/about')
def about():
    return render_template('about.html', title='About')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html', title='Contact')

@main_bp.route('/faq')
def faq():
    return render_template('faq.html', title='FAQ')

@main_bp.route('/privacy')
def privacy():
    return render_template('privacy.html', title='Privacy Policy')

@main_bp.route('/terms')
def terms():
    return render_template('terms.html', title='Terms of Service')
