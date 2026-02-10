from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort, current_app
import os
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User, Competition, Submission, Badge, UserBadge, UserCompetition, Challenge
from app.forms import ProfileForm
from sqlalchemy import desc

player_bp = Blueprint('player', __name__, url_prefix='/player')

@player_bp.route('/dashboard')
@login_required
def dashboard():
    # Get registered competitions
    user_competitions = UserCompetition.query.filter_by(user_id=current_user.id).all()
    competition_ids = [uc.competition_id for uc in user_competitions]
    
    registered_competitions = Competition.query.filter(Competition.id.in_(competition_ids)).all() if competition_ids else []
    
    # Get recent submissions
    recent_submissions = Submission.query.filter_by(user_id=current_user.id).\
        order_by(desc(Submission.submitted_at)).limit(5).all()
    
    # Get user badges
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()
    
    return render_template('player/dashboard.html', 
                          registered_competitions=registered_competitions,
                          recent_submissions=recent_submissions,
                          user_badges=user_badges,
                          title='Player Dashboard')

@player_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        # Check if username is already taken by another user
        if form.username.data != current_user.username:
            user = User.query.filter_by(username=form.username.data).first()
            if user:
                flash('Username already exists. Please choose a different one.', 'danger')
                return redirect(url_for('player.profile'))
        
        # Check if email is already taken by another user
        if form.email.data != current_user.email:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                flash('Email already registered. Please use a different one.', 'danger')
                return redirect(url_for('player.profile'))
        
        # Update basic info
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        current_user.two_factor_enabled = form.two_factor_enabled.data
        
        # Handle profile picture upload
        if form.avatar.data:
            from app.services.file_upload import upload_profile_picture, delete_file_from_s3
            
            # Delete old avatar if exists and is from S3
            if current_user.avatar and 's3.amazonaws.com' in current_user.avatar:
                try:
                    # Extract S3 key from URL
                    old_key = current_user.avatar.split('.com/')[-1]
                    delete_file_from_s3(old_key, 'profiles')
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete old avatar: {str(e)}")
            
            # Upload new avatar
            success, message, avatar_url = upload_profile_picture(
                form.avatar.data,
                current_user.id,
                current_user.username
            )
            
            if success:
                current_user.avatar = avatar_url
            else:
                flash(f'Profile picture upload failed: {message}', 'warning')
        
        try:
            db.session.commit()
            flash('Your profile has been updated', 'success')
            return redirect(url_for('player.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
    
    # Get user stats
    total_points = current_user.score
    total_competitions = UserCompetition.query.filter_by(user_id=current_user.id).count()
    total_submissions = Submission.query.filter_by(user_id=current_user.id).count()
    correct_submissions = Submission.query.filter_by(user_id=current_user.id, is_correct=True).count()
    
    # Get badges
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()
    
    return render_template('player/profile.html', 
                          form=form,
                          total_points=total_points,
                          total_competitions=total_competitions,
                          total_submissions=total_submissions,
                          correct_submissions=correct_submissions,
                          user_badges=user_badges,
                          title='My Profile')

@player_bp.route('/settings')
@login_required
def settings():
    return render_template('player/settings.html', title='Settings')

@player_bp.route('/competitions')
@login_required
def my_competitions():
    # Get registered competitions
    user_competitions = UserCompetition.query.filter_by(user_id=current_user.id).all()
    competition_ids = [uc.competition_id for uc in user_competitions]
    
    registered_competitions = Competition.query.filter(Competition.id.in_(competition_ids)).all() if competition_ids else []
    
    return render_template('player/competitions.html', 
                          competitions=registered_competitions,
                          title='My Competitions')

@player_bp.route('/submissions')
@login_required
def my_submissions():
    # Get all submissions by the user
    submissions = Submission.query.filter_by(user_id=current_user.id).\
        order_by(desc(Submission.submitted_at)).all()
    
    return render_template('player/submissions.html', 
                          submissions=submissions,
                          title='My Submissions')

@player_bp.route('/badges')
@login_required
def my_badges():
    # Get all badges earned by the user
    user_badges = UserBadge.query.filter_by(user_id=current_user.id).all()
    
    return render_template('player/badges.html', 
                          user_badges=user_badges,
                          title='My Badges')

@player_bp.route('/challenges/<int:challenge_id>/download')
@login_required
def download_file(challenge_id):
    # Get the challenge from the database
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Check if the challenge is public or if the user is an admin/host
    if not challenge.is_public and current_user.role not in ['admin', 'host']:
        flash('You do not have permission to download this file', 'danger')
        return redirect(url_for('player.challenges'))  # Redirect to the challenges list page

    # Set the file path to the 'uploads/' directory
    file_path = os.path.join('uploads', challenge.file_name)
    
    # Ensure the file exists and serve it
    if os.path.exists(file_path):
        return send_from_directory('uploads', challenge.file_name, as_attachment=True)
    else:
        flash('File not found', 'danger')
        return redirect(url_for('player.challenges'))  # Redirect to the challenges list page