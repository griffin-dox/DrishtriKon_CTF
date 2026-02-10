from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, BooleanField, SubmitField
from wtforms.validators import Optional
from functools import wraps
from app.extensions import db
from app.models import Badge, UserBadge, ChallengeVisibilityScope, CompetitionChallenge
from app.models import User, UserRole, Challenge, Competition,  UserStatus, CompetitionHost
from app.forms import UserCreateForm, UserEditForm, ChallengeForm, CompetitionForm, BadgeForm, CompetitionHostForm, UserSearchForm
from sqlalchemy import desc
from app.services.utils import save_file
from werkzeug.utils import secure_filename
from app.services.cache.utils import cached_query
from app.models import Submission
import os
import logging
from pytz import timezone
from app.security.rate_limit_policies import rate_limit_route, user_or_ip_identifier

# Define a module logger
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')

# Use a set for efficient lookup
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip'}  # Added zip

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    # Get dashboard data with caching
    dashboard_data = get_admin_dashboard_data()
    
    return render_template('admin/dashboard.html', 
                           total_users=dashboard_data['total_users'],
                           total_challenges=dashboard_data['total_challenges'],
                           total_competitions=dashboard_data['total_competitions'],
                           total_badges=dashboard_data['total_badges'],
                           recent_users=dashboard_data['recent_users'],
                           recent_competitions=dashboard_data['recent_competitions'],
                           recent_badges=dashboard_data['recent_badges'],
                           title='Admin Dashboard')

@cached_query(ttl=300)  # Cache for 5 minutes
def get_admin_dashboard_data():
    """Get admin dashboard data with caching"""
    # Get counts for dashboard
    total_users = User.query.count()
    total_challenges = Challenge.query.count()
    total_competitions = Competition.query.count()
    total_badges = Badge.query.count()
    
    # Get recent users
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    
    # Get recent competitions
    recent_competitions = Competition.query.order_by(desc(Competition.created_at)).limit(5).all()
    
    # Get recent badges
    recent_badges = Badge.query.order_by(desc(Badge.created_at)).limit(5).all()
    recent_badge_activity = UserBadge.query.order_by(desc(UserBadge.awarded_at)).limit(10).all()
    
    return {
        'total_users': total_users,
        'total_challenges': total_challenges,
        'total_competitions': total_competitions,
        'total_badges': total_badges,
        'recent_users': recent_users,
        'recent_competitions': recent_competitions,
        'recent_badges': recent_badges,
        'recent_badge_activity': recent_badge_activity
    }

@admin_bp.route('/stats')
@login_required
@admin_required
def global_stats():
    # Get all stats with caching to avoid repetitive database queries
    stats = get_admin_global_stats()
    
    return render_template('admin/global_stats_enhanced.html',
                           total_users=stats['total_users'],
                           total_players=stats['total_players'],
                           total_hosts=stats['total_hosts'],
                           total_admins=stats['total_admins'],
                           total_challenges=stats['total_challenges'],
                           public_challenges=stats['public_challenges'],
                           lab_challenges=stats['lab_challenges'],
                           total_submissions=stats['total_submissions'],
                           correct_submissions=stats['correct_submissions'],
                           incorrect_submissions=stats['incorrect_submissions'],
                           total_badges=stats['total_badges'],
                           total_competitions=stats['total_competitions'],
                           title='Platform Analytics')

@cached_query(ttl=600)  # Cache for 10 minutes
def get_admin_global_stats():
    """Get global platform statistics with caching for admin dashboard"""
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
    
    return {
        'total_users': total_users,
        'total_players': total_players,
        'total_hosts': total_hosts,
        'total_admins': total_admins,
        'total_challenges': total_challenges,
        'public_challenges': public_challenges,
        'lab_challenges': lab_challenges,
        'total_submissions': total_submissions,
        'correct_submissions': correct_submissions,
        'incorrect_submissions': incorrect_submissions,
        'total_badges': total_badges,
        'total_competitions': total_competitions
    }

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
@rate_limit_route(
    "admin_user_create",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many user creation attempts.",
    methods={"POST"},
)
def create_user():
    form = UserCreateForm()
    
    if form.validate_on_submit():
        user = User()
        user.username = form.username.data
        user.email = form.email.data
        user.role = UserRole[form.role.data]
        user.set_password(form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
            flash('User has been created successfully', 'success')
            # Log user creation
            security_logger.info(
                f"User created: {user.username} ({user.email}), role: {user.role.name}, by admin: {current_user.username}",
                extra={"user": user.username, "email": user.email, "event": "user_created", "role": user.role.name, "by": current_user.username, "by_ip": request.remote_addr}
            )
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
    
    return render_template('admin/create_user.html', form=form, title='Create User')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
@rate_limit_route(
    "admin_user_edit",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many user update attempts.",
    methods={"POST"},
)
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == "POST":
        form = UserEditForm(request.form, obj=user)
    else:
        form = UserEditForm(obj=user)
        
    if form.validate_on_submit():
        old_role = user.role.name
        old_status = user.status.name
        user.username = form.username.data
        user.email = form.email.data
        user.role = UserRole[form.role.data]
        user.status = UserStatus[form.status.data]
        try:
            db.session.commit()
            flash('User has been updated successfully', 'success')
            # Log privilege/status changes
            if old_role != user.role.name:
                security_logger.warning(
                    f"User role changed for {user.username}: {old_role} -> {user.role.name} by admin: {current_user.username}",
                    extra={"user": user.username, "event": "role_changed", "old_role": old_role, "new_role": user.role.name, "by": current_user.username, "by_ip": request.remote_addr}
                )
            if old_status != user.status.name:
                security_logger.warning(
                    f"User status changed for {user.username}: {old_status} -> {user.status.name} by admin: {current_user.username}",
                    extra={"user": user.username, "event": "status_changed", "old_status": old_status, "new_status": user.status.name, "by": current_user.username, "by_ip": request.remote_addr}
                )
                from app.services.email_service import send_status_change_email, send_status_restored_email
                # Send email if status is restricted, suspended, or banned
                if user.status.name in ["RESTRICTED", "SUSPENDED", "BANNED"]:
                    send_status_change_email(user.email, user.username, user.status.name)
                # Send restored email if status is changed from restricted/suspended/banned to ACTIVE
                if old_status in ["RESTRICTED", "SUSPENDED", "BANNED"] and user.status.name == "ACTIVE":
                    send_status_restored_email(user.email, user.username)
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
    print("form:", form)
    print("form.csrf_token:", getattr(form, 'csrf_token', None))
    print("form.hidden_tag:", getattr(form, 'hidden_tag', None))
    
    return render_template('admin/edit_user.html', form=form, user=user, title='Edit User')

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "admin_user_delete",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many user delete attempts.",
    methods={"POST"},
)
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # Prevent deletion of protected email
    if user.email == 'codeitishant@gmail.com':
        flash('This user cannot be deleted.', 'danger')
        return redirect(url_for('admin.users'))
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('admin.users'))
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User has been deleted successfully', 'success')
        # Log user deletion
        security_logger.warning(
            f"User deleted: {user.username} ({user.email}) by admin: {current_user.username}",
            extra={"user": user.username, "email": user.email, "event": "user_deleted", "by": current_user.username, "by_ip": request.remote_addr}
        )
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
@rate_limit_route(
    "admin_challenge_create",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many challenge creation attempts.",
    methods={"POST"},
)
def create_challenge():
    form = ChallengeForm()
    
    if form.validate_on_submit():
        file = form.file.data
        filename, file_path, mimetype = save_file(file)

        # Determine visibility scope based on is_public flag
        visibility_scope = ChallengeVisibilityScope.PRIVATE
        if form.is_public.data:
            visibility_scope = ChallengeVisibilityScope.PUBLIC
            
        challenge = Challenge()
        challenge.title = form.title.data
        challenge.description = form.description.data
        challenge.file_name = filename
        challenge.file_path = file_path
        challenge.file_mimetype = mimetype
        challenge.flag = form.flag.data
        challenge.points = form.points.data
        challenge.type = form.type.data
        challenge.difficulty = int(form.difficulty.data)
        challenge.hint = form.hint.data
        challenge.is_lab = form.is_lab.data
        challenge.is_public = form.is_public.data
        challenge.visibility_scope = visibility_scope
        challenge.creator_id = current_user.id
        
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
@rate_limit_route(
    "admin_challenge_edit",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many challenge update attempts.",
    methods={"POST"},
)
def edit_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    form = ChallengeForm(obj=challenge)
    
    if form.validate_on_submit():
        # Update non-file attributes
        challenge.title = form.title.data
        challenge.description = form.description.data
        challenge.flag = form.flag.data
        challenge.points = form.points.data
        challenge.type = form.type.data
        challenge.difficulty = int(form.difficulty.data)
        challenge.hint = form.hint.data
        challenge.is_lab = form.is_lab.data
        challenge.is_public = form.is_public.data
        
        # Update visibility scope based on challenge status
        if challenge.is_public:
            challenge.visibility_scope = ChallengeVisibilityScope.PUBLIC
        else:
            challenge.visibility_scope = ChallengeVisibilityScope.PRIVATE
            
        # Handle file upload if a new file is selected
        file = form.file.data
        if file and file.filename:  # Check if a file was actually uploaded
            if allowed_file(file.filename):
                # Store the old file path for potential cleanup
                old_file_path = challenge.file_path if challenge.file_path else None
                
                # Use the utility function to save the file consistently
                filename, file_path, mimetype = save_file(file)
                
                # Update the challenge with the new file information
                if filename and file_path and mimetype:
                    challenge.file_name = filename
                    challenge.file_path = file_path
                    challenge.file_mimetype = mimetype
                    
                    # Clean up the old file if it exists and is different
                    if old_file_path and old_file_path != file_path and os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                            logger.info(f"Removed old challenge file: {old_file_path}")
                        except Exception as e:
                            logger.error(f"Error removing old file {old_file_path}: {str(e)}")
            else:
                flash('Invalid file type selected.', 'danger')
                return redirect(url_for('admin.edit_challenge', challenge_id=challenge_id))

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
@rate_limit_route(
    "admin_challenge_delete",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many challenge delete attempts.",
    methods={"POST"},
)
def delete_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    try:
        # Delete related submissions
        related_submissions = Submission.query.filter_by(challenge_id=challenge_id).all()
        for submission in related_submissions:
            db.session.delete(submission)

        db.session.delete(challenge)
        db.session.commit()
        flash('Challenge and related submissions deleted successfully', 'success')
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
@rate_limit_route(
    "admin_competition_create",
    20,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many competition creation attempts.",
    methods={"POST"},
)
def create_competition():
    form = CompetitionForm()
    
    if form.validate_on_submit():
        competition = Competition()
        competition.title = form.title.data
        competition.description = form.description.data
        competition.start_time = form.start_time.data
        competition.end_time = form.end_time.data
        competition.max_participants = form.max_participants.data
        competition.is_public = form.is_public.data
        competition.host_id = current_user.id
        
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
@rate_limit_route(
    "admin_competition_edit",
    40,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many competition update attempts.",
    methods={"POST"},
)
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
@rate_limit_route(
    "admin_competition_delete",
    20,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many competition delete attempts.",
    methods={"POST"},
)
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
                # Set the competition attribution
                attribution = f"From Competition: {competition.title} by {competition.host.username}"
                challenge.competition_attribution = attribution
                
                # Update visibility scope
                challenge.visibility_scope = ChallengeVisibilityScope.PUBLIC
                challenge.is_public = True
                
                # Remove the competition association
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
@rate_limit_route(
    "admin_competition_host_assign",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many host assignment attempts.",
    methods={"POST"},
)
def manage_competition_hosts(competition_id):
    competition = Competition.query.get_or_404(competition_id)
    
    # Convert UTC times to IST
    IST = timezone('Asia/Kolkata')
    competition.start_time = competition.start_time.astimezone(IST)
    competition.end_time = competition.end_time.astimezone(IST)

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
            host_assignment = CompetitionHost()
            host_assignment.competition_id = competition.id
            host_assignment.host_id = host_id
            try:
                db.session.add(host_assignment)
                db.session.commit()
                flash('Host assigned to competition successfully', 'success')
                # Log host assignment
                security_logger.info(
                    f"Host assigned: user_id={host_id} to competition_id={competition.id} by admin: {current_user.username}",
                    extra={"host_id": host_id, "competition_id": competition.id, "event": "host_assigned", "by": current_user.username, "by_ip": request.remote_addr}
                )
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
@rate_limit_route(
    "admin_competition_host_remove",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many host removal attempts.",
    methods={"POST"},
)
def remove_competition_host(competition_id, host_id):
    host_assignment = CompetitionHost.query.filter_by(
        competition_id=competition_id,
        host_id=host_id
    ).first_or_404()
    
    try:
        db.session.delete(host_assignment)
        db.session.commit()
        flash('Host removed from competition successfully', 'success')
        # Log host removal
        security_logger.warning(
            f"Host removed: user_id={host_id} from competition_id={competition_id} by admin: {current_user.username}",
            extra={"host_id": host_id, "competition_id": competition_id, "event": "host_removed", "by": current_user.username, "by_ip": request.remote_addr}
        )
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
    form = FlaskForm() 
    return render_template('admin/badges.html', badges=badges, form=form, title='Badge Management')

@admin_bp.route('/badges/create', methods=['GET', 'POST'])
@login_required
@admin_required
@rate_limit_route(
    "admin_badge_create",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many badge creation attempts.",
    methods={"POST"},
)
def create_badge():
    form = BadgeForm()
    if form.validate_on_submit():
        image_url = None
        if form.image.data:
            file = form.image.data
            filename = secure_filename(file.filename)
            image_path = os.path.join('static', 'badges', filename)
            file.save(os.path.join(current_app.root_path, image_path))
            image_url = f'/static/badges/{filename}'
        badge = Badge()
        badge.name = form.name.data
        badge.description = form.description.data
        badge.icon = form.icon.data
        badge.criteria = form.criteria.data
        badge.image_url = image_url
        
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
@rate_limit_route(
    "admin_badge_edit",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many badge update attempts.",
    methods={"POST"},
)
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
@rate_limit_route(
    "admin_badge_delete",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many badge delete attempts.",
    methods={"POST"},
)
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

# Challenge Competition Management
@admin_bp.route('/challenges/<int:challenge_id>/move', methods=['GET', 'POST'])
@login_required
@admin_required
@rate_limit_route(
    "admin_challenge_move",
    40,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many challenge move attempts.",
    methods={"POST"},
)
def move_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)
    
    # Create dynamic form with competition choices
    class MoveChallengeForm(FlaskForm):
        competition = SelectField('Target Competition', choices=[], coerce=int, validators=[Optional()])
        make_public = BooleanField('Make Public')
        submit = SubmitField('Move Challenge')
    
    # Load all competitions
    competitions = Competition.query.all()
    form = MoveChallengeForm()
    
    # Add empty choice for "No Competition" (making it public)
    form.competition.choices = [(-1, 'None (Make Public)')] + [(c.id, c.title) for c in competitions]  
    
    # Get current competition info if any
    current_competition = None
    competition_challenge = None
    if challenge.competitions:
        competition_challenge = challenge.competitions[0]  # Get the first (should be only) competition
        current_competition = competition_challenge.competition
    
    if form.validate_on_submit():
        try:
            # Remove from current competition if it exists
            if competition_challenge:
                db.session.delete(competition_challenge)
            
            target_competition_id = form.competition.data
            
            if target_competition_id == -1 or form.make_public.data:
                # Make public with attribution if coming from a competition
                if current_competition:
                    attribution = f"From Competition: {current_competition.title} by {current_competition.host.username}"
                    challenge.competition_attribution = attribution
                
                # Update visibility settings
                challenge.is_public = True
                challenge.visibility_scope = ChallengeVisibilityScope.PUBLIC
            else:
                # Add to the new competition
                new_competition = Competition.query.get(target_competition_id)
                if new_competition:
                    # Create new competition challenge association
                    new_comp_challenge = CompetitionChallenge()
                    new_comp_challenge.competition_id = new_competition.id
                    new_comp_challenge.challenge_id = challenge.id
                    db.session.add(new_comp_challenge)
                    
                    # Update visibility settings for competition
                    challenge.is_public = False
                    challenge.visibility_scope = ChallengeVisibilityScope.COMPETITION
            
            db.session.commit()
            flash(f'Challenge "{challenge.title}" has been moved successfully', 'success')
            return redirect(url_for('admin.challenges'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error moving challenge: {str(e)}', 'danger')
    
    # Pass competitions to the template for dropdown
    return render_template('admin/move_challenge.html', 
                          challenge=challenge,
                          current_competition=current_competition,
                          competitions=competitions,
                          form=form,
                          title='Move Challenge')

@admin_bp.route('/assign_badge', methods=['GET', 'POST'])
@login_required
@admin_required
@rate_limit_route(
    "admin_badge_assign",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many badge assignments.",
    methods={"POST"},
)
def assign_badge():
    from forms import AssignBadgeForm
    form = AssignBadgeForm()
    # Populate user and badge choices
    form.user_id.choices = [(u.id, f"{u.username} (ID: {u.id})") for u in User.query.order_by(User.username).all()]
    form.badge_id.choices = [(b.id, b.name) for b in Badge.query.order_by(Badge.name).all()]
    if form.validate_on_submit():
        user_id = form.user_id.data
        badge_id = form.badge_id.data
        # Prevent duplicate assignment
        from app.models import UserBadge
        if UserBadge.query.filter_by(user_id=user_id, badge_id=badge_id).first():
            flash('User already has this badge.', 'warning')
        else:
            user_badge = UserBadge()
            user_badge.user_id = user_id
            user_badge.badge_id = badge_id
            db.session.add(user_badge)
            db.session.commit()
            flash('Badge assigned successfully!', 'success')
        return redirect(url_for('admin.assign_badge'))
    return render_template('admin/assign_badge.html', form=form, title='Assign Badge')

@admin_bp.route('/badges/evaluate', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "admin_badge_evaluate",
    5,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many badge evaluations.",
    methods={"POST"},
)
def evaluate_badges():
    from app.models import User, Badge, UserBadge
    assigned = 0
    users = User.query.all()
    badges = Badge.query.all()
    for user in users:
        user_context = {
            'user': user,
            'points': getattr(user, 'points', 0),
            'challenges_solved': getattr(user, 'challenges_solved', 0),
            # Add more user stats as needed
        }
        for badge in badges:
            if badge.criteria:
                try:
                    if eval(badge.criteria, {}, user_context):
                        if not UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first():
                            user_badge = UserBadge()
                            user_badge.user_id = user.id
                            user_badge.badge_id = badge.id
                            db.session.add(user_badge)
                            assigned += 1
                except Exception as e:
                    logger.warning(f"Error evaluating badge {badge.id} for user {user.id}: {e}")
    db.session.commit()
    flash(f'Automatic badge assignment complete. {assigned} badges assigned.', 'success')
    return redirect(url_for('admin.badges'))
