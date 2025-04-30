from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models import Challenge, Submission, CompetitionChallenge, Competition, User, UserCompetition, ChallengeVisibilityScope
from forms import FlagSubmissionForm
from sqlalchemy import desc
from datetime import datetime

challenges_bp = Blueprint('challenges', __name__, url_prefix='/challenges')

@challenges_bp.route('/')
@login_required
def list_challenges():
    # Get challenges from competitions the user is registered in
    user_competitions = UserCompetition.query.filter_by(user_id=current_user.id).all()
    competition_ids = [uc.competition_id for uc in user_competitions]
    
    if competition_ids:
        # Get competition challenges that are active and released
        competition_challenges = CompetitionChallenge.query.filter(
            CompetitionChallenge.competition_id.in_(competition_ids),
            CompetitionChallenge.is_active == True,
            (CompetitionChallenge.release_time <= datetime.utcnow()) | (CompetitionChallenge.release_time == None)
        ).all()
        
        challenge_ids = [cc.challenge_id for cc in competition_challenges]
        # Only get competition-type challenges
        challenges = Challenge.query.filter(
            Challenge.id.in_(challenge_ids),
            Challenge.visibility_scope == ChallengeVisibilityScope.COMPETITION
        ).all()
    else:
        challenges = []
    
    # Get solved challenges
    solved_challenges = db.session.query(Submission.challenge_id).\
        filter(Submission.user_id == current_user.id, Submission.is_correct == True).all()
    
    solved_challenge_ids = [sc[0] for sc in solved_challenges]
    
    return render_template('challenges/list.html', 
                          challenges=challenges,
                          solved_challenge_ids=solved_challenge_ids,
                          title='Competition Challenges')

@challenges_bp.route('/<int:challenge_id>', methods=['GET', 'POST'])
@login_required
def view_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if the challenge is accessible to the user
    is_accessible = False
    
    # If it's a public challenge, it's accessible to everyone
    if challenge.visibility_scope == ChallengeVisibilityScope.PUBLIC:
        is_accessible = True
    # If it's a competition challenge, check if the user is registered for that competition
    elif challenge.visibility_scope == ChallengeVisibilityScope.COMPETITION:
        # Check if the user is registered for a competition that has this challenge
        user_competitions = UserCompetition.query.filter_by(user_id=current_user.id).all()
        competition_ids = [uc.competition_id for uc in user_competitions]
        
        if competition_ids:
            cc = CompetitionChallenge.query.filter(
                CompetitionChallenge.competition_id.in_(competition_ids),
                CompetitionChallenge.challenge_id == challenge_id,
                CompetitionChallenge.is_active == True,
                (CompetitionChallenge.release_time <= datetime.utcnow()) | (CompetitionChallenge.release_time == None)
            ).first()
            
            if cc:
                is_accessible = True
    
    if not is_accessible and not current_user.is_admin() and not current_user.is_host():
        flash('You do not have access to this challenge', 'danger')
        return redirect(url_for('challenges.list_challenges'))
    
    # Check if the user has already solved this challenge
    already_solved = Submission.query.filter_by(
        user_id=current_user.id,
        challenge_id=challenge_id,
        is_correct=True
    ).first() is not None
    
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
        
        # Find which competition this submission belongs to (if any)
        user_competitions = UserCompetition.query.filter_by(user_id=current_user.id).all()
        competition_ids = [uc.competition_id for uc in user_competitions]
        
        if competition_ids:
            cc = CompetitionChallenge.query.filter(
                CompetitionChallenge.competition_id.in_(competition_ids),
                CompetitionChallenge.challenge_id == challenge_id
            ).first()
            
            if cc:
                submission.competition_id = cc.competition_id
                
                # Update user's score in the competition if correct
                if is_correct:
                    user_competition = UserCompetition.query.filter_by(
                        user_id=current_user.id,
                        competition_id=cc.competition_id
                    ).first()
                    
                    if user_competition and not already_solved:
                        user_competition.score += challenge.points
        
        try:
            db.session.add(submission)
            
            # Update user's overall score if correct and not already solved
            if is_correct and not already_solved:
                current_user.score += challenge.points
            
            db.session.commit()
            
            if is_correct:
                flash('Congratulations! You solved the challenge!', 'success')
                return redirect(url_for('challenges.list_challenges'))
            else:
                flash('Incorrect flag. Try again!', 'danger')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting flag: {str(e)}', 'danger')
    
    # Get previous submissions
    previous_submissions = Submission.query.filter_by(
        user_id=current_user.id,
        challenge_id=challenge_id
    ).order_by(desc(Submission.submitted_at)).all()
    
    return render_template('challenges/detail.html', 
                          challenge=challenge,
                          form=form,
                          already_solved=already_solved,
                          previous_submissions=previous_submissions,
                          title=challenge.title)

@challenges_bp.route('/labs')
@login_required
def labs():
    # Get all public challenges (both labs and regular public challenges)
    challenges = Challenge.query.filter(
        Challenge.visibility_scope == ChallengeVisibilityScope.PUBLIC
    ).all()
    
    # Get solved challenges
    solved_challenges = db.session.query(Submission.challenge_id).\
        filter(Submission.user_id == current_user.id, Submission.is_correct == True).all()
    
    solved_challenge_ids = [sc[0] for sc in solved_challenges]
    
    return render_template('challenges/labs.html', 
                          challenges=challenges,
                          solved_challenge_ids=solved_challenge_ids,
                          title='Public Challenges')
