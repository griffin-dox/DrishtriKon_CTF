from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from core.app import db
from core.models import Challenge, Submission, CompetitionChallenge, Competition, User, UserCompetition, ChallengeVisibilityScope
from forms import FlagSubmissionForm
from sqlalchemy import desc
from datetime import datetime
from core.cache_utils import cached_query, invalidate_cache

challenges_bp = Blueprint('challenges', __name__, url_prefix='/challenges')

@challenges_bp.route('/')
@login_required
def list_challenges():
    # Get user's competition challenges (depends on current user so can't cache the whole function)
    challenges = get_user_competition_challenges(current_user.id)
    # Use the shared cached function for solved challenges
    solved_challenge_ids = get_solved_challenges(current_user.id)
    
    return render_template('challenges/list.html', 
                          challenges=challenges,
                          solved_challenge_ids=solved_challenge_ids,
                          title='Competition Challenges')

def get_user_competition_challenges(user_id):
    """Get challenges for competitions that the user is registered for"""
    # Get competition IDs for the user with an optimized query
    competition_ids = db.session.query(UserCompetition.competition_id).filter_by(user_id=user_id).all()
    competition_ids = [comp_id[0] for comp_id in competition_ids]
    
    if not competition_ids:
        return []
        
    # Use a JOIN to get challenges in one query with eager loading
    return (
        Challenge.query
        .join(
            CompetitionChallenge,
            Challenge.id == CompetitionChallenge.challenge_id
        )
        .options(
            db.joinedload(Challenge.creator)  # Eagerly load creator information
        )
        .filter(
            CompetitionChallenge.competition_id.in_(competition_ids),
            CompetitionChallenge.is_active == True,
            (CompetitionChallenge.release_time <= datetime.utcnow()) | (CompetitionChallenge.release_time == None),
            Challenge.visibility_scope == ChallengeVisibilityScope.COMPETITION
        )
        .order_by(Challenge.difficulty, Challenge.title)
        .all()
    )

@challenges_bp.route('/<int:challenge_id>', methods=['GET', 'POST'])
@login_required
def view_challenge(challenge_id):
    # Use optimized functions for better performance
    challenge = get_challenge_with_creator(challenge_id)
    if not challenge:
        flash('Challenge not found', 'danger')
        return redirect(url_for('challenges.list_challenges')), 404
    
    # Check if the challenge is accessible to the user
    is_accessible = False
    
    # If it's a public challenge, it's accessible to everyone
    if challenge.visibility_scope == ChallengeVisibilityScope.PUBLIC:
        is_accessible = True
    # If it's a competition challenge, check if the user is registered for that competition
    elif challenge.visibility_scope == ChallengeVisibilityScope.COMPETITION:
        # Check accessibility (using optimized query)
        is_accessible = check_challenge_accessibility(challenge_id, current_user.id)
    
    # Admin and host users can access all challenges
    if not is_accessible and not current_user.is_admin() and not current_user.is_host():
        flash('You do not have access to this challenge', 'danger')
        return redirect(url_for('challenges.list_challenges'))
    
    # Check if already solved (using cached/optimized query)
    already_solved = check_challenge_solved(challenge_id, current_user.id)
    
    form = FlagSubmissionForm()
    
    if form.validate_on_submit():
        # Check if the flag is correct
        is_correct = form.flag.data == challenge.flag
        
        # Create submission
        submission = Submission(
            user_id=current_user.id,
            challenge_id=challenge_id,
            flag_submitted=form.flag.data,
            is_correct=is_correct,
            points_awarded=challenge.points if is_correct else 0
        )
        
        # Find which competition this submission belongs to (if any) using a single query
        if is_correct:
            cc = get_competition_challenge(challenge_id, current_user.id)
            
            if cc:
                submission.competition_id = cc.competition_id
                
                # Update user's score in the competition if correct and not already solved
                if not already_solved:
                    user_competition = UserCompetition.query.filter_by(
                        user_id=current_user.id,
                        competition_id=cc.competition_id
                    ).first()
                    
                    if user_competition:
                        user_competition.score += challenge.points
        
        try:
            # Add submission
            db.session.add(submission)
            
            # Update user's overall score if correct and not already solved
            if is_correct and not already_solved:
                current_user.score += challenge.points
            
            db.session.commit()
            
            # Clear relevant caches when submissions change
            if is_correct:
                invalidate_cache(f"get_solved_challenges:{current_user.id}")
                flash('Congratulations! You solved the challenge!', 'success')
                return redirect(url_for('challenges.list_challenges'))
            else:
                flash('Incorrect flag. Try again!', 'danger')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting flag: {str(e)}', 'danger')
    
    # Get previous submissions with a limit (using optimized query)
    previous_submissions = get_previous_submissions(challenge_id, current_user.id)
    
    return render_template('challenges/detail.html', 
                          challenge=challenge,
                          form=form,
                          already_solved=already_solved,
                          previous_submissions=previous_submissions,
                          title=challenge.title)

# Helper functions with caching for better performance
@cached_query(ttl=300)  # Cache for 5 minutes
def get_challenge_with_creator(challenge_id):
    """Get a challenge with eager loading of creator"""
    return Challenge.query.options(
        db.joinedload(Challenge.creator)
    ).get(challenge_id)

def check_challenge_accessibility(challenge_id, user_id):
    """Check if a challenge is accessible to a user"""
    return db.session.query(
        db.session.query(CompetitionChallenge).filter(
            CompetitionChallenge.challenge_id == challenge_id,
            CompetitionChallenge.is_active == True,
            (CompetitionChallenge.release_time <= datetime.utcnow()) | (CompetitionChallenge.release_time == None),
            CompetitionChallenge.competition_id.in_(
                db.session.query(UserCompetition.competition_id).filter_by(user_id=user_id)
            )
        ).exists()
    ).scalar()

@cached_query(ttl=60)  # Cache for 1 minute
def check_challenge_solved(challenge_id, user_id):
    """Check if a challenge has been solved by a user"""
    return db.session.query(
        db.session.query(Submission).filter_by(
            user_id=user_id,
            challenge_id=challenge_id,
            is_correct=True
        ).exists()
    ).scalar()

def get_competition_challenge(challenge_id, user_id):
    """Get competition challenge for a given challenge and user"""
    return db.session.query(CompetitionChallenge).filter(
        CompetitionChallenge.challenge_id == challenge_id,
        CompetitionChallenge.competition_id.in_(
            db.session.query(UserCompetition.competition_id).filter_by(user_id=user_id)
        )
    ).first()

@cached_query(ttl=30)  # Cache for 30 seconds
def get_previous_submissions(challenge_id, user_id):
    """Get previous submissions for a challenge by a user"""
    return Submission.query.filter_by(
        user_id=user_id,
        challenge_id=challenge_id
    ).order_by(desc(Submission.submitted_at)).limit(10).all()

@challenges_bp.route('/labs')
@login_required
def labs():
    # Use cached queries for better performance
    challenges = get_lab_challenges()
    solved_challenge_ids = get_solved_challenges(current_user.id)
    
    return render_template('challenges/labs.html', 
                          challenges=challenges,
                          solved_challenge_ids=solved_challenge_ids,
                          title='Lab Challenges')

@cached_query(ttl=300)  # Cache for 5 minutes
def get_lab_challenges():
    """Get all public lab challenges with caching for better performance"""
    return Challenge.query.filter(
        Challenge.is_lab == True,
        Challenge.is_public == True,
        Challenge.visibility_scope == ChallengeVisibilityScope.PUBLIC
    ).options(
        db.joinedload(Challenge.creator)  # Eagerly load creator information
    ).order_by(Challenge.difficulty, Challenge.title).all()

@challenges_bp.route('/public')
@login_required
def public():
    # Use cached queries for better performance
    challenges = get_public_challenges()
    solved_challenge_ids = get_solved_challenges(current_user.id)
    
    return render_template('challenges/public.html', 
                          challenges=challenges,
                          solved_challenge_ids=solved_challenge_ids,
                          title='Public Challenges')

@cached_query(ttl=300)  # Cache for 5 minutes
def get_public_challenges():
    """Get all public non-lab challenges with caching for better performance"""
    return Challenge.query.filter(
        Challenge.is_public == True,
        Challenge.is_lab == False,  # Exclude lab challenges from public challenges view
        Challenge.visibility_scope == ChallengeVisibilityScope.PUBLIC
    ).options(
        db.joinedload(Challenge.creator)  # Eagerly load creator information
    ).order_by(Challenge.difficulty, Challenge.title).all()

@cached_query(ttl=60)  # Cache for 1 minute
def get_solved_challenges(user_id):
    """Get solved challenge IDs for a user with caching for better performance"""
    return [
        result[0] for result in db.session.query(Submission.challenge_id)
        .filter(
            Submission.user_id == user_id,
            Submission.is_correct == True
        ).distinct().all()
    ]
