from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from app import db
from models import User, UserRole, Challenge, Competition, Badge, UserStatus, CompetitionHost
from forms import UserCreateForm, UserEditForm, ChallengeForm, CompetitionForm, BadgeForm, CompetitionHostForm, UserSearchForm
from sqlalchemy import desc
from utils import save_file

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin role required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    # Get counts for dashboard
    total_users = User.query.count()
    total_challenges = Challenge.query.count()
    total_competitions = Competition.query.count()
    
    # Get recent users
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    
    # Get recent competitions
    recent_competitions = Competition.query.order_by(desc(Competition.created_at)).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           total_users=total_users,
                           total_challenges=total_challenges,
                           total_competitions=total_competitions,
                           recent_users=recent_users,
                           recent_competitions=recent_competitions,
                           title='Admin Dashboard')

@admin_bp.route('/stats')
@login_required
@admin_required
def global_stats():
    from sqlalchemy import func
    from models import Submission, Badge

    # User breakdown
    total_users = User.query.count()
    total_players = User.query.filter_by(role=UserRole.PLAYER).count()
    total_hosts = User.query.filter_by(role=UserRole.HOST).count()
    total_admins = User.query.filter_by(role=UserRole.OWNER).count()

    # Challenge and Submission breakdown
    total_challenges = Challenge.query.count()
    public_challenges = Challenge.query.filter_by(is_public=True).count()
    lab_challenges = Challenge.query.filter_by(is_lab=True).count()

    total_submissions = Submission.query.count()
    correct_submissions = Submission.query.filter_by(is_correct=True).count()
    incorrect_submissions = total_submissions - correct_submissions

    # Badges and Competitions
    total_badges = Badge.query.count()
    total_competitions = Competition.query.count()

    return render_template('admin/global_stats.html',
                           total_users=total_users,
                           total_players=total_players,
                           total_hosts=total_hosts,
                           total_admins=total_admins,
                           total_challenges=total_challenges,
                           public_challenges=public_challenges,
                           lab_challenges=lab_challenges,
                           total_submissions=total_submissions,
                           correct_submissions=correct_submissions,
                           incorrect_submissions=incorrect_submissions,
                           total_badges=total_badges,
                           total_competitions=total_competitions,
                           title='Platform Stats')

# User Management
@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users():
    search_form = UserSearchForm()
    query = User.query
    
    if search_form.validate_on_submit():
        search_term = f"%{search_form.search.data}%"
        query = query.filter(User.username.ilike(search_term))
        flash(f'Showing results for "{search_form.search.data}"', 'info')
    
    users = query.order_by(User.username).all()
    return render_template('admin/users.html', users=users, search_form=search_form, title='User Management')

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = UserCreateForm()
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=UserRole[form.role.data]
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('User has been created successfully', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
    
    return render_template('admin/create_user.html', form=form, title='Create User')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role = UserRole[form.role.data]
        user.status = UserStatus[form.status.data]
        
        try:
            db.session.commit()
            flash('User has been updated successfully', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
    
    return render_template('admin/edit_user.html', form=form, user=user, title='Edit User')

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('admin.users'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User has been deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('admin.users'))

# Challenge Management
@admin_bp.route('/challenges')
@login_required
@admin_required
def challenges():
    challenges = Challenge.query.order_by(Challenge.title).all()
    return render_template('admin/challenges.html', challenges=challenges, title='Challenge Management')

@admin_bp.route('/challenges/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_challenge():
    form = ChallengeForm()
    
    if form.validate_on_submit():
        file = form.file.data
        filename, file_path, mimetype = save_file(file)

        challenge = Challenge(
            title=form.title.data,
            description=form.description.data,
            file_name=filename,
            file_path=file_path,
            file_mimetype=mimetype,
            flag=form.flag.data,
            points=form.points.data,
            type=form.type.data,
            difficulty=int(form.difficulty.data),
            hint=form.hint.data,
            is_lab=form.is_lab.data,
            is_public=form.is_public.data,
            creator_id=current_user.id
        )
        
        try:
            db.session.add(challenge)
            db.session.commit()
            flash('Challenge has been created successfully', 'success')
            return redirect(url_for('admin.challenges'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating challenge: {str(e)}', 'danger')
    
    return render_template('admin/create_challenge.html', form=form, title='Create Challenge')

@admin_bp.route('/challenges/edit/<int:challenge_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    form = ChallengeForm(obj=challenge)
    
    if form.validate_on_submit():
        challenge.title = form.title.data
        challenge.description = form.description.data
        challenge.flag = form.flag.data
        challenge.points = form.points.data
        challenge.type = form.type.data
        challenge.difficulty = int(form.difficulty.data)
        challenge.hint = form.hint.data
        challenge.is_lab = form.is_lab.data
        challenge.is_public = form.is_public.data
        challenge.file_name = form.file_name.data
        challenge.file_path = form.file_path.data
        challenge.file_mimetype = form.file_mimetype.data

        try:
            db.session.commit()
            flash('Challenge has been updated successfully', 'success')
            return redirect(url_for('admin.challenges'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating challenge: {str(e)}', 'danger')
    
    return render_template('admin/edit_challenge.html', form=form, challenge=challenge, title='Edit Challenge')

@admin_bp.route('/challenges/delete/<int:challenge_id>', methods=['POST'])
@login_required
@admin_required
def delete_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    
    try:
        db.session.delete(challenge)
        db.session.commit()
        flash('Challenge has been deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting challenge: {str(e)}', 'danger')
    
    return redirect(url_for('admin.challenges'))

# Competition Management
@admin_bp.route('/competitions')
@login_required
@admin_required
def competitions():
    competitions = Competition.query.order_by(Competition.start_time.desc()).all()
    return render_template('admin/competitions.html', competitions=competitions, title='Competition Management')

@admin_bp.route('/competitions/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_competition():
    form = CompetitionForm()
    
    if form.validate_on_submit():
        competition = Competition(
            title=form.title.data,
            description=form.description.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            max_participants=form.max_participants.data,
            is_public=form.is_public.data,
            host_id=current_user.id
        )
        
        try:
            db.session.add(competition)
            db.session.commit()
            flash('Competition has been created successfully', 'success')
            return redirect(url_for('admin.competitions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating competition: {str(e)}', 'danger')
    
    return render_template('admin/create_competition.html', form=form, title='Create Competition')

@admin_bp.route('/competitions/edit/<int:competition_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_competition(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    form = CompetitionForm(obj=competition)
    
    if form.validate_on_submit():
        competition.title = form.title.data
        competition.description = form.description.data
        competition.start_time = form.start_time.data
        competition.end_time = form.end_time.data
        competition.max_participants = form.max_participants.data
        competition.is_public = form.is_public.data
        
        try:
            db.session.commit()
            flash('Competition has been updated successfully', 'success')
            return redirect(url_for('admin.competitions'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating competition: {str(e)}', 'danger')
    
    return render_template('admin/edit_competition.html', form=form, competition=competition, title='Edit Competition')

@admin_bp.route('/competitions/delete/<int:competition_id>', methods=['POST'])
@login_required
@admin_required
def delete_competition(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    action = request.form.get('challenge_action')  # 'delete' or 'make_public'

    try:
        # Handle challenges
        for comp_challenge in competition.challenges:
            challenge = comp_challenge.challenge  # Access actual Challenge model
            
            if action == 'delete':
                db.session.delete(challenge)
            elif action == 'make_public':
                challenge.competition_id = None
                challenge.is_public = True
                db.session.delete(comp_challenge)  # Remove link from junction table
            else:
                raise ValueError("Invalid challenge action selected.")
        
        # Optional: Remove host assignment (not necessary if it's just a foreign key)
        # If host is 1-to-1 enforced, remove reverse link:
        competition.host_id = None

        # Finally, delete the competition
        db.session.delete(competition)
        db.session.commit()
        flash('Competition and associated data handled successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting competition: {str(e)}', 'danger')

    return redirect(url_for('admin.competitions'))


# Competition Host Management
@admin_bp.route('/competitions/<int:competition_id>/hosts', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_competition_hosts(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    
    # Get current hosts
    current_hosts = [ch.host for ch in CompetitionHost.query.filter_by(competition_id=competition.id).all()]
    
    # Get potential hosts (users with host or owner role)
    potential_hosts = User.query.filter(
        User.role.in_([UserRole.HOST, UserRole.OWNER]),
        User.id != competition.host_id,  # Exclude the primary host
        ~User.id.in_([h.id for h in current_hosts])  # Exclude current additional hosts
    ).all()
    
    # Create the host assignment form
    form = CompetitionHostForm()
    form.host_id.choices = [(host.id, host.username) for host in potential_hosts]
    
    if not potential_hosts:
        form.host_id.choices = [(-1, 'No available hosts')]
    
    if form.validate_on_submit() and potential_hosts:
        host_id = form.host_id.data
        
        # Check if this user is already a host for this competition
        existing = CompetitionHost.query.filter_by(
            competition_id=competition.id,
            host_id=host_id
        ).first()
        
        if not existing:
            host_assignment = CompetitionHost(
                competition_id=competition.id,
                host_id=host_id
            )
            
            try:
                db.session.add(host_assignment)
                db.session.commit()
                flash('Host assigned to competition successfully', 'success')
                return redirect(url_for('admin.manage_competition_hosts', competition_id=competition.id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error assigning host: {str(e)}', 'danger')
        else:
            flash('This user is already assigned as a host for this competition', 'warning')
    
    return render_template('admin/manage_competition_hosts.html', 
                          competition=competition,
                          current_hosts=current_hosts,
                          form=form,
                          title=f'Manage Hosts - {competition.title}')

@admin_bp.route('/competitions/<int:competition_id>/hosts/<int:host_id>/remove', methods=['POST'])
@login_required
@admin_required
def remove_competition_host(competition_id, host_id):
    host_assignment = CompetitionHost.query.filter_by(
        competition_id=competition_id,
        host_id=host_id
    ).first_or_404()
    
    try:
        db.session.delete(host_assignment)
        db.session.commit()
        flash('Host removed from competition successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing host: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_competition_hosts', competition_id=competition_id))

# Badge Management
@admin_bp.route('/badges')
@login_required
@admin_required
def badges():
    badges = Badge.query.order_by(Badge.name).all()
    return render_template('admin/badges.html', badges=badges, title='Badge Management')

@admin_bp.route('/badges/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_badge():
    form = BadgeForm()
    
    if form.validate_on_submit():
        badge = Badge(
            name=form.name.data,
            description=form.description.data,
            icon=form.icon.data,
            criteria=form.criteria.data
        )
        
        try:
            db.session.add(badge)
            db.session.commit()
            flash('Badge has been created successfully', 'success')
            return redirect(url_for('admin.badges'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating badge: {str(e)}', 'danger')
    
    return render_template('admin/create_badge.html', form=form, title='Create Badge')

@admin_bp.route('/badges/edit/<int:badge_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_badge(badge_id):
    badge = Badge.query.get_or_404(badge_id)
    form = BadgeForm(obj=badge)
    
    if form.validate_on_submit():
        badge.name = form.name.data
        badge.description = form.description.data
        badge.icon = form.icon.data
        badge.criteria = form.criteria.data
        
        try:
            db.session.commit()
            flash('Badge has been updated successfully', 'success')
            return redirect(url_for('admin.badges'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating badge: {str(e)}', 'danger')
    
    return render_template('admin/edit_badge.html', form=form, badge=badge, title='Edit Badge')

@admin_bp.route('/badges/delete/<int:badge_id>', methods=['POST'])
@login_required
@admin_required
def delete_badge(badge_id):
    badge = Badge.query.get_or_404(badge_id)
    
    try:
        db.session.delete(badge)
        db.session.commit()
        flash('Badge has been deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting badge: {str(e)}', 'danger')
    
    return redirect(url_for('admin.badges'))
