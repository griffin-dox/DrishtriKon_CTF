from flask import Blueprint, render_template, request
from core.models import Competition, Challenge, User, CompetitionStatus, UserRole
from sqlalchemy import func, desc
from datetime import datetime
from app import db
from core.cache_utils import cached_query, invalidate_cache

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Use cached queries for better performance
    active_competitions = get_home_active_competitions()
    upcoming_competitions = get_home_upcoming_competitions()
    
    # Get statistics with caching
    platform_stats = get_platform_stats()
    
    # Get top players efficiently with caching
    top_players = get_top_players(10)
    
    return render_template('index.html', 
                           active_competitions=active_competitions,
                           upcoming_competitions=upcoming_competitions,
                           total_users=platform_stats['total_users'],
                           total_challenges=platform_stats['total_challenges'],
                           total_competitions=platform_stats['total_competitions'],
                           top_players=top_players,
                           title='Drishti कोण - Home')

@cached_query(ttl=300)  # Cache for 5 minutes
def get_home_active_competitions():
    """Get active competitions for homepage with caching"""
    return Competition.query.filter_by(
        status=CompetitionStatus.ACTIVE
    ).order_by(Competition.start_time).limit(5).all()

@cached_query(ttl=300)  # Cache for 5 minutes
def get_home_upcoming_competitions():
    """Get upcoming competitions for homepage with caching"""
    return Competition.query.filter_by(
        status=CompetitionStatus.UPCOMING
    ).order_by(Competition.start_time).limit(3).all()

@cached_query(ttl=600)  # Cache for 10 minutes
def get_platform_stats():
    """Get platform statistics with caching"""
    total_users = db.session.query(func.count(User.id)).scalar()
    total_challenges = db.session.query(func.count(Challenge.id)).scalar()
    total_competitions = db.session.query(func.count(Competition.id)).scalar()
    
    return {
        'total_users': total_users,
        'total_challenges': total_challenges,
        'total_competitions': total_competitions
    }

@cached_query(ttl=300)  # Cache for 5 minutes
def get_top_players(limit=10):
    """Get top players with caching"""
    return (
        User.query
        .filter_by(role=UserRole.PLAYER)
        .order_by(desc(User.score))
        .limit(limit)
        .all()
    )

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
