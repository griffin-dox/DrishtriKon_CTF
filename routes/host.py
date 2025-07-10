from flask import Blueprint, render_template, redirect, url_for, flash, request, render_template
from flask_login import login_required, current_user
from functools import wraps
from app import db
import os
from core.models import Competition, Challenge, CompetitionChallenge, User, UserCompetition, CompetitionHost, Submission, CompetitionStatus, ChallengeVisibilityScope
from forms import CompetitionForm, ChallengeForm, CompetitionManualStatusForm
from sqlalchemy import desc
from sqlalchemy.sql import func
from utils.utils import save_file
from werkzeug.utils import secure_filename
from core.models import Badge, UserBadge
from core.models import User
from utils.utils import auto_assign_badges
from forms import BadgeForm

# Define the upload folder
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'zip', 'txt', 'pdf', 'png', 'jpg', 'jpeg'}

host_bp = Blueprint('host', __name__, url_prefix='/host')

# Host role required decorator
def host_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_host():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def is_host_of_competition(competition_id):
    return (
        Competition.query.filter_by(id=competition_id, host_id=current_user.id).first() or
        CompetitionHost.query.filter_by(competition_id=competition_id, host_id=current_user.id).first()
    )

@host_bp.route('/')
@login_required
@host_required
def dashboard():
    primary_hosted = Competition.query.filter_by(host_id=current_user.id).order_by(desc(Competition.created_at)).all()
    additional_hosted_ids = db.session.query(CompetitionHost.competition_id).filter_by(host_id=current_user.id).all()
    additional_hosted_ids = [ch[0] for ch in additional_hosted_ids]
    additional_hosted = Competition.query.filter(Competition.id.in_(additional_hosted_ids)).order_by(desc(Competition.created_at)).all()
    total_hosted = len(primary_hosted)
    total_additional = len(additional_hosted)
    total_participants = db.session.query(db.func.count(UserCompetition.id)).\
        join(Competition, UserCompetition.competition_id == Competition.id).\
        filter(Competition.host_id == current_user.id).scalar() or 0

    return render_template('host/dashboard.html', 
                          primary_hosted=primary_hosted,
                          additional_hosted=additional_hosted,
                          total_hosted=total_hosted,
                          total_additional=total_additional,
                          total_participants=total_participants,
                          title='Host Dashboard')

@host_bp.route('/competitions')
@login_required
@host_required
def competitions():
    primary_hosted = Competition.query.filter_by(host_id=current_user.id).all()
    additional_hosted_ids = db.session.query(CompetitionHost.competition_id).filter_by(host_id=current_user.id).all()
    additional_hosted_ids = [ch[0] for ch in additional_hosted_ids]
    additional_hosted = Competition.query.filter(Competition.id.in_(additional_hosted_ids)).all()
    all_competitions = {c.id: c for c in primary_hosted + additional_hosted}
    competitions = sorted(all_competitions.values(), key=lambda c: c.start_time, reverse=True)
    return render_template('host/competitions.html', 
                          competitions=competitions, 
                          primary_hosted_ids=[c.id for c in primary_hosted],
                          title='My Competitions')

@host_bp.route('/competitions/edit/<int:competition_id>', methods=['GET', 'POST'])
@login_required
@host_required
def edit_competition(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if not is_host_of_competition(competition_id) and not current_user.is_admin():
        flash('You do not have permission to edit this competition', 'danger')
        return redirect(url_for('host.competitions'))

    form = CompetitionForm(obj=competition)
    if form.validate_on_submit():
        competition.title = form.title.data
        competition.description = form.description.data
        competition.start_time = form.start_time.data
        competition.end_time = form.end_time.data
        competition.max_participants = form.max_participants.data
        competition.show_leaderboard = form.show_leaderboard.data
        competition.is_public = form.is_public.data
        try:
            db.session.commit()
            flash('Competition updated successfully', 'success')
            return redirect(url_for('host.competitions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating competition: {str(e)}', 'danger')
    return render_template('host/edit_competition.html', form=form, competition=competition, title='Edit Competition')

@host_bp.route('/competitions/manage/<int:competition_id>', methods=['GET', 'POST'])
@login_required
@host_required
def manage_competition(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if not is_host_of_competition(competition_id) and not current_user.is_admin():
        flash('You do not have permission to manage this competition', 'danger')
        return redirect(url_for('host.competitions'))

    status_form = CompetitionManualStatusForm(obj=competition)

    if request.method == 'POST':
        if 'submit' in request.form:  # manual status update form
            if status_form.validate_on_submit():
                competition.manual_status_override = CompetitionStatus[status_form.status.data]
                try:
                    db.session.commit()
                    flash("Competition status manually updated.", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error updating status: {str(e)}", "danger")
            return redirect(url_for('host.manage_competition', competition_id=competition_id))
        
        elif 'show_leaderboard' in request.form:  # leaderboard visibility toggle form
            competition.show_leaderboard = 'show_leaderboard' in request.form
            try:
                db.session.commit()
                flash("Leaderboard visibility updated.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating leaderboard: {str(e)}", "danger")
            return redirect(url_for('host.manage_competition', competition_id=competition_id))

    competition_challenges = CompetitionChallenge.query.filter_by(competition_id=competition_id).all()
    participants = UserCompetition.query.filter_by(competition_id=competition_id).all()

    # ✅ Host Stats
    total_participants = len(participants)
    total_submissions = db.session.query(func.count()).select_from(Submission).filter_by(competition_id=competition_id).scalar()
    correct_submissions = db.session.query(func.count()).select_from(Submission).filter_by(competition_id=competition_id, is_correct=True).scalar()
    avg_score = db.session.query(func.avg(UserCompetition.score)).filter_by(competition_id=competition_id).scalar() or 0
    challenge_solve_distribution = db.session.query(
        Challenge.title, func.count(Submission.id)
    ).join(CompetitionChallenge, CompetitionChallenge.challenge_id == Challenge.id)\
     .join(Submission, Submission.challenge_id == Challenge.id)\
     .filter(CompetitionChallenge.competition_id == competition_id, Submission.is_correct == True)\
     .group_by(Challenge.title).all()

    return render_template(
        'host/competition_management.html',
        competition=competition,
        competition_challenges=competition_challenges,
        participants=participants,
        total_participants=total_participants,
        total_submissions=total_submissions,
        correct_submissions=correct_submissions,
        avg_score=round(avg_score, 2),
        challenge_solve_distribution=challenge_solve_distribution,
        status_form=status_form, 
        title=f'Manage {competition.title}'
    )

@host_bp.route('/challenges')
@login_required
@host_required
def challenges():
    primary_hosted_ids = db.session.query(Competition.id).filter_by(host_id=current_user.id).all()
    primary_hosted_ids = [c[0] for c in primary_hosted_ids]
    additional_hosted_ids = db.session.query(CompetitionHost.competition_id).filter_by(host_id=current_user.id).all()
    additional_hosted_ids = [ch[0] for ch in additional_hosted_ids]
    hosted_competition_ids = set(primary_hosted_ids + additional_hosted_ids)
    competition_challenge_ids = db.session.query(CompetitionChallenge.challenge_id).\
        filter(CompetitionChallenge.competition_id.in_(hosted_competition_ids)).all()
    competition_challenge_ids = [cc[0] for cc in competition_challenge_ids]
    challenges = Challenge.query.filter(
        (Challenge.creator_id == current_user.id) | 
        (Challenge.id.in_(competition_challenge_ids))
    ).order_by(Challenge.title).all()
    competitions = Competition.query.filter(Competition.id.in_(hosted_competition_ids)).order_by(Competition.title).all()
    return render_template('host/challenges.html', 
                          challenges=challenges, 
                          competitions=competitions,
                          title='Challenges')

@host_bp.route('/create_challenge/<int:competition_id>', methods=['GET', 'POST'])
@login_required
@host_required
def create_challenge(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if not is_host_of_competition(competition_id) and not current_user.is_admin():
        flash('You do not have permission to create challenges for this competition', 'danger')
        return redirect(url_for('host.competitions'))

    form = ChallengeForm()
    if form.validate_on_submit():
        file = form.file.data
        filename, file_path, mimetype = save_file(file)

        # For challenges created within competitions, set visibility accordingly
        visibility_scope = ChallengeVisibilityScope.COMPETITION
        
        # If the host wants this challenge to be public too, allow it
        if form.is_public.data:
            visibility_scope = ChallengeVisibilityScope.PUBLIC
            
        # Create the challenge object
        challenge = Challenge(
            title=form.title.data,
            description=form.description.data,
            flag=form.flag.data,
            points=form.points.data,
            type=form.type.data,
            difficulty=int(form.difficulty.data),
            hint=form.hint.data,
            is_lab=form.is_lab.data,
            is_public=form.is_public.data,
            visibility_scope=visibility_scope,
            creator_id=current_user.id,
            file_name=filename,
            file_path=file_path,
            file_mimetype=mimetype
        )
        db.session.add(challenge)
        db.session.commit()

        competition_challenge = CompetitionChallenge(
            competition_id=competition.id,
            challenge_id=challenge.id,
            is_active=True
        )
        db.session.add(competition_challenge)
        db.session.commit()

        flash('Challenge created and added to competition.', 'success')
        return redirect(url_for('host.manage_competition', competition_id=competition.id))

    return render_template('host/create_challenge.html', form=form, competition=competition, edit_mode=False, title='Create Challenge')

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@host_bp.route('/challenge/edit/<int:challenge_id>', methods=['GET', 'POST'])
@login_required
@host_required
def edit_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    competitions = db.session.query(Competition).join(CompetitionChallenge).filter(
        CompetitionChallenge.challenge_id == challenge_id
    ).all()

    allowed = any(
        comp.host_id == current_user.id or
        CompetitionHost.query.filter_by(competition_id=comp.id, host_id=current_user.id).first()
        for comp in competitions
    )

    if not allowed and not current_user.is_admin():
        flash("You don't have permission to edit this challenge.", "danger")
        return redirect(url_for('host.challenges'))

    form = ChallengeForm(obj=challenge)
    if form.validate_on_submit():
        # Update the challenge attributes
        challenge.title = form.title.data
        challenge.description = form.description.data
        challenge.flag = form.flag.data
        challenge.points = form.points.data
        challenge.type = form.type.data
        challenge.difficulty = int(form.difficulty.data)
        challenge.hint = form.hint.data
        challenge.is_lab = form.is_lab.data
        challenge.is_public = form.is_public.data
        
        # Update the visibility scope based on public flag
        if form.is_public.data:
            challenge.visibility_scope = ChallengeVisibilityScope.PUBLIC
        else:
            # If it's part of a competition, it should be COMPETITION scope
            challenge.visibility_scope = ChallengeVisibilityScope.COMPETITION if challenge.is_in_competition() else ChallengeVisibilityScope.PRIVATE
        
        # Handle file upload
        if form.file.data:
            file = form.file.data
            if allowed_file(file.filename):  # Check if file type is allowed
                filename = secure_filename(file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)

                # Update file metadata in the database
                challenge.file_name = filename
                challenge.file_path = file_path
                challenge.file_mimetype = file.mimetype
            else:
                flash('Invalid file format.', 'danger')
                return redirect(url_for('host.edit_challenge', challenge_id=challenge_id))

        # Commit changes to the database
        db.session.commit()
        flash("Challenge updated.", "success")
        return redirect(url_for('host.challenges'))

    return render_template('host/create_challenge.html', form=form, challenge=challenge, edit_mode=True, title='Edit Challenge')

@host_bp.route('/challenge/delete/<int:challenge_id>', methods=['POST'])
@login_required
@host_required
def delete_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    competition_links = CompetitionChallenge.query.filter_by(challenge_id=challenge_id).all()

    allowed_links = [cc for cc in competition_links if is_host_of_competition(cc.competition_id) or current_user.is_admin()]

    if not allowed_links:
        flash("You don't have permission to delete this challenge.", "danger")
        return redirect(url_for('host.challenges'))

    for cc in allowed_links:
        db.session.delete(cc)

    # Only delete the challenge if it's not linked to any other competition
    still_linked = CompetitionChallenge.query.filter_by(challenge_id=challenge_id).count()
    if still_linked == 0:
        db.session.delete(challenge)

    db.session.commit()
    flash("Challenge deleted or unlinked from your competitions.", "success")
    return redirect(url_for('host.challenges'))

@host_bp.route('/competitions/<int:competition_id>/stats')
@login_required
@host_required
def competition_stats(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    if not is_host_of_competition(competition_id):
        flash("You are not authorized to view these stats", "danger")
        return redirect(url_for('host.dashboard'))

    submissions = db.session.query(UserCompetition).filter_by(competition_id=competition_id).all()
    top_scores = sorted(submissions, key=lambda x: x.score, reverse=True)[:10]

    return render_template('host/competition_stats.html',
                           competition=competition,
                           top_scores=top_scores,
                           total_participants=len(submissions),
                           title=f"{competition.title} - Stats")

@host_bp.route('/badges')
@login_required
@host_required
def badges():
    badges = Badge.query.order_by(Badge.created_at.desc()).all()
    return render_template('host/badges.html', badges=badges, title='Manage Badges')

@host_bp.route('/badges/create', methods=['GET', 'POST'])
@login_required
@host_required
def create_badge():
    form = BadgeForm()
    if form.validate_on_submit():
        badge = Badge(
            name=form.name.data,
            description=form.description.data,
            icon=form.icon.data,
            criteria=form.criteria.data,
            image_url=form.image_url.data
        )
        db.session.add(badge)
        db.session.commit()
        flash('Badge created successfully!', 'success')
        return redirect(url_for('host.badges'))
    return render_template('host/create_badge.html', form=form, title='Create Badge')

@host_bp.route('/badges/assign', methods=['GET', 'POST'])
@login_required
@host_required
def assign_badge():
    users = User.query.all()
    badges = Badge.query.all()
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        badge_id = request.form.get('badge_id')
        if not user_id or not badge_id:
            flash('Please select both user and badge.', 'danger')
            return redirect(url_for('host.assign_badge'))
        user = User.query.get(user_id)
        badge = Badge.query.get(badge_id)
        if not user or not badge:
            flash('Invalid user or badge.', 'danger')
            return redirect(url_for('host.assign_badge'))
        if any(ub.badge_id == badge.id for ub in user.badges):
            flash('User already has this badge.', 'info')
            return redirect(url_for('host.assign_badge'))
        user_badge = UserBadge(user_id=user.id, badge_id=badge.id)
        db.session.add(user_badge)
        db.session.commit()
        flash('Badge assigned successfully!', 'success')
        return redirect(url_for('host.assign_badge'))
    return render_template('host/assign_badge.html', users=users, badges=badges, title='Assign Badge')

@host_bp.route('/badges/auto_assign', methods=['POST'])
@login_required
@host_required
def auto_assign_badges_route():
    auto_assign_badges()
    flash('Auto-assignment of badges completed!', 'success')
    return redirect(url_for('host.badges'))