from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from core.app import db
from core.models import Competition, CompetitionStatus, User, UserCompetition, UserRole
from sqlalchemy import desc
from datetime import datetime
from forms import TeamCompetitionRegisterForm
from core.cache_utils import cached_query, invalidate_cache

competitions_bp = Blueprint('competitions', __name__, url_prefix='/competitions')

@competitions_bp.route('/')
def list_competitions():
    # Use cached queries for better performance
    active_competitions = get_active_competitions()
    upcoming_competitions = get_upcoming_competitions()
    past_competitions = get_past_competitions()
    
    # Check which competitions the user is registered for
    registered_competition_ids = []
    if current_user.is_authenticated:
        registered_competition_ids = get_user_registered_competitions(current_user.id)
    
    return render_template('competitions/list.html', 
                          active_competitions=active_competitions,
                          upcoming_competitions=upcoming_competitions,
                          past_competitions=past_competitions,
                          registered_competition_ids=registered_competition_ids,
                          title='Competitions')

@cached_query(ttl=300)  # Cache for 5 minutes
def get_active_competitions():
    """Get active public competitions with caching"""
    return Competition.query.filter_by(
        status=CompetitionStatus.ACTIVE,
        is_public=True
    ).order_by(Competition.start_time).all()

@cached_query(ttl=300)  # Cache for 5 minutes
def get_upcoming_competitions():
    """Get upcoming public competitions with caching"""
    return Competition.query.filter_by(
        status=CompetitionStatus.UPCOMING,
        is_public=True
    ).order_by(Competition.start_time).all()

@cached_query(ttl=300)  # Cache for 5 minutes
def get_past_competitions():
    """Get past public competitions with caching"""
    return Competition.query.filter_by(
        status=CompetitionStatus.ENDED,
        is_public=True
    ).order_by(desc(Competition.end_time)).all()

@cached_query(ttl=60)  # Cache for 1 minute
def get_user_registered_competitions(user_id):
    """Get competition IDs the user is registered for"""
    user_competitions = UserCompetition.query.filter_by(user_id=user_id).all()
    return [uc.competition_id for uc in user_competitions]

@competitions_bp.route('/<int:competition_id>')
def view_competition(competition_id):
    # Get the competition with efficient query
    competition = get_competition_by_id(competition_id)
    if not competition:
        flash('Competition not found', 'danger')
        return redirect(url_for('competitions.list_competitions')), 404
    
    # Check if the competition is public or if the user is the host
    is_host = current_user.is_authenticated and (
        competition.host_id == current_user.id or current_user.is_admin()
    )
    
    if not competition.is_public and not is_host:
        flash('This competition is private', 'danger')
        return redirect(url_for('competitions.list_competitions'))
    
    # Check if the user is registered
    is_registered = False
    if current_user.is_authenticated:
        is_registered = check_user_registered(current_user.id, competition_id)
    
    # Get competition leaderboard with caching
    leaderboard = []
    if competition.show_leaderboard or is_host:
        leaderboard = get_competition_leaderboard(competition_id)

    form = TeamCompetitionRegisterForm()

    return render_template('competitions/detail.html', 
                          competition=competition,
                          is_registered=is_registered,
                          is_host=is_host,
                          leaderboard=leaderboard,
                          title=competition.title,
                          form=form)

@cached_query(ttl=300)  # Cache for 5 minutes
def get_competition_by_id(competition_id):
    """Get competition by ID with caching"""
    return Competition.query.get(competition_id)

@cached_query(ttl=60)  # Cache for 1 minute
def check_user_registered(user_id, competition_id):
    """Check if user is registered for a competition"""
    user_competition = UserCompetition.query.filter_by(
        user_id=user_id,
        competition_id=competition_id
    ).first()
    return user_competition is not None

@cached_query(ttl=60)  # Cache for 1 minute
def get_competition_leaderboard(competition_id):
    """Get competition leaderboard with caching"""
    participants = db.session.query(UserCompetition, User)\
        .join(User, UserCompetition.user_id == User.id)\
        .filter(UserCompetition.competition_id == competition_id)\
        .filter(User.role == UserRole.PLAYER)\
        .order_by(desc(UserCompetition.score)).all()
    
    leaderboard = []
    for idx, (participant, user) in enumerate(participants):
        leaderboard.append({
            'rank': idx + 1,
            'username': user.username,
            'score': participant.score
        })
    
    return leaderboard

@competitions_bp.route('/<int:competition_id>/register', methods=['POST'])
@login_required
def register(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    
    # Check if registration is allowed
    if competition.status == CompetitionStatus.ENDED:
        flash('Registration is closed for this competition', 'danger')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Check if the competition has a maximum participant limit
    if competition.max_participants:
        current_participants = UserCompetition.query.filter_by(competition_id=competition_id).count()
        if current_participants >= competition.max_participants:
            flash('This competition has reached its maximum number of participants', 'danger')
            return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Check if already registered
    existing_registration = UserCompetition.query.filter_by(
        user_id=current_user.id,
        competition_id=competition_id
    ).first()
    
    if existing_registration:
        flash('You are already registered for this competition', 'info')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Create registration
    user_competition = UserCompetition(
        user_id=current_user.id,
        competition_id=competition_id,
        score=0
    )
    
    try:
        db.session.add(user_competition)
        db.session.commit()
        
        # Invalidate caches after successful registration
        invalidate_cache(f"check_user_registered:{current_user.id}:{competition_id}")
        invalidate_cache(f"get_user_registered_competitions:{current_user.id}")
        invalidate_cache(f"get_competition_leaderboard:{competition_id}")
        
        flash('You have successfully registered for this competition', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering for competition: {str(e)}', 'danger')
    
    return redirect(url_for('competitions.view_competition', competition_id=competition_id))

@competitions_bp.route('/<int:competition_id>/unregister', methods=['POST'])
@login_required
def unregister(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    
    # Check if the competition has already started
    if competition.status != CompetitionStatus.UPCOMING:
        flash('You cannot unregister from a competition that has already started', 'danger')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Find registration
    user_competition = UserCompetition.query.filter_by(
        user_id=current_user.id,
        competition_id=competition_id
    ).first()
    
    if not user_competition:
        flash('You are not registered for this competition', 'info')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    try:
        db.session.delete(user_competition)
        db.session.commit()
        flash('You have successfully unregistered from this competition', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error unregistering from competition: {str(e)}', 'danger')
    
    return redirect(url_for('competitions.view_competition', competition_id=competition_id))

@competitions_bp.route('/leaderboard')
def global_leaderboard():
    # Get top users with caching
    leaderboard = get_global_leaderboard()
    
    return render_template('competitions/global_leaderboard.html', 
                          leaderboard=leaderboard,
                          title='Global Leaderboard')

@cached_query(ttl=300)  # Cache for 5 minutes
def get_global_leaderboard():
    """Get global leaderboard with caching"""
    top_users = User.query.filter_by(role=UserRole.PLAYER).order_by(desc(User.score)).limit(100).all()
    
    leaderboard = []
    for idx, user in enumerate(top_users):
        leaderboard.append({
            'rank': idx + 1,
            'username': user.username,
            'score': user.score
        })
    
    return leaderboard
