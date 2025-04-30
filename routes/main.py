from flask import Blueprint, render_template, request
from models import Competition, Challenge, User, CompetitionStatus, UserRole
from sqlalchemy import func, desc
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Get active and upcoming competitions
    active_competitions = Competition.query.filter_by(
        status=CompetitionStatus.ACTIVE
    ).order_by(Competition.start_time).limit(5).all()
    
    upcoming_competitions = Competition.query.filter_by(
        status=CompetitionStatus.UPCOMING
    ).order_by(Competition.start_time).limit(3).all()
    
    # Get statistics for the platform
    total_users = User.query.count()
    total_challenges = Challenge.query.count()
    total_competitions = Competition.query.count()
    
    # Get top players by score (exclude admin and host users)
    top_players = User.query.filter_by(role=UserRole.PLAYER).order_by(desc(User.score)).limit(10).all()
    
    return render_template('index.html', 
                           active_competitions=active_competitions,
                           upcoming_competitions=upcoming_competitions,
                           total_users=total_users,
                           total_challenges=total_challenges,
                           total_competitions=total_competitions,
                           top_players=top_players,
                           title='Drishti कोण - Home')

@main_bp.route('/about')
def about():
    return render_template('about.html', title='About')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html', title='Contact')

@main_bp.route('/faq')
def faq():
    return render_template('faq.html', title='FAQ')
