from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models import Competition, CompetitionStatus, User, UserCompetition, UserRole
from sqlalchemy import desc
from datetime import datetime
from forms import TeamCompetitionRegisterForm

competitions_bp = Blueprint('competitions', __name__, url_prefix='/competitions')

@competitions_bp.route('/')
def list_competitions():
    # Get active and upcoming public competitions
    active_competitions = Competition.query.filter_by(
        status=CompetitionStatus.ACTIVE,
        is_public=True
    ).order_by(Competition.start_time).all()
    
    upcoming_competitions = Competition.query.filter_by(
        status=CompetitionStatus.UPCOMING,
        is_public=True
    ).order_by(Competition.start_time).all()
    
    past_competitions = Competition.query.filter_by(
        status=CompetitionStatus.ENDED,
        is_public=True
    ).order_by(desc(Competition.end_time)).all()
    
    # Check which competitions the user is registered for
    registered_competition_ids = []
    if current_user.is_authenticated:
        user_competitions = UserCompetition.query.filter_by(user_id=current_user.id).all()
        registered_competition_ids = [uc.competition_id for uc in user_competitions]
    
    return render_template('competitions/list.html', 
                          active_competitions=active_competitions,
                          upcoming_competitions=upcoming_competitions,
                          past_competitions=past_competitions,
                          registered_competition_ids=registered_competition_ids,
                          title='Competitions')

@competitions_bp.route('/<int:competition_id>')
def view_competition(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    
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
        user_competition = UserCompetition.query.filter_by(
            user_id=current_user.id,
            competition_id=competition_id
        ).first()
        is_registered = user_competition is not None
    
    # Get participants for the leaderboard - join with users to filter out admin and host users
    participants = db.session.query(UserCompetition, User)\
        .join(User, UserCompetition.user_id == User.id)\
        .filter(UserCompetition.competition_id == competition_id)\
        .filter(User.role == UserRole.PLAYER)\
        .order_by(desc(UserCompetition.score)).all()
    
        # Prepare leaderboard data
    leaderboard = []
    if competition.show_leaderboard or is_host:
        participants = db.session.query(UserCompetition, User)\
            .join(User, UserCompetition.user_id == User.id)\
            .filter(UserCompetition.competition_id == competition_id)\
            .filter(User.role == UserRole.PLAYER)\
            .order_by(desc(UserCompetition.score)).all()

        for idx, (participant, user) in enumerate(participants):
            leaderboard.append({
                'rank': idx + 1,
                'username': user.username,
                'score': participant.score
            })

    form = TeamCompetitionRegisterForm()

    return render_template('competitions/detail.html', 
                          competition=competition,
                          is_registered=is_registered,
                          is_host=is_host,
                          leaderboard=leaderboard,
                          title=competition.title,
                          form=form,)

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
    # Get top users by score, excluding admin and host roles (only show players)
    top_users = User.query.filter_by(role=UserRole.PLAYER).order_by(desc(User.score)).limit(100).all()
    
    leaderboard = []
    for idx, user in enumerate(top_users):
        leaderboard.append({
            'rank': idx + 1,
            'username': user.username,
            'score': user.score
        })
    
    return render_template('competitions/global_leaderboard.html', 
                          leaderboard=leaderboard,
                          title='Global Leaderboard')
