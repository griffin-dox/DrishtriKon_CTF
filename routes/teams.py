from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from core.models import User, Team, TeamMember, TeamRole, TeamStatus, TeamCompetition, Competition, CompetitionStatus, UserCompetition
from forms import TeamCreateForm, TeamEditForm, TeamInviteMemberForm, TeamJoinForm, TeamLeaveForm, TeamKickMemberForm, TeamCompetitionRegisterForm
import secrets
import string
from sqlalchemy import func, desc
from datetime import datetime, timedelta

teams_bp = Blueprint('teams', __name__, url_prefix='/teams')

# Helper function to generate a random team code
def generate_team_code(length=8):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Helper function to check if user is team captain
def is_team_captain(team_id):
    if not current_user.is_authenticated:
        return False
    member = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id,
        role='captain'
    ).first()
    return member is not None

# Helper function to get user's team
def get_user_team():
    if not current_user.is_authenticated:
        return None
    member = TeamMember.query.filter_by(user_id=current_user.id).first()
    if not member:
        return None
    return member.team

@teams_bp.route('/')
def list_teams():
    # List all active teams
    teams = Team.query.filter_by(status='active').order_by(Team.name).all()
    
    # Get user's team if they have one
    user_team = None
    if current_user.is_authenticated:
        user_team = get_user_team()
    
    return render_template('teams/list.html', 
                          teams=teams,
                          user_team=user_team,
                          title='Teams')

@teams_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_team():
    # Check if user already belongs to a team
    existing_membership = TeamMember.query.filter_by(user_id=current_user.id).first()
    if existing_membership:
        flash('You already belong to a team. You must leave your current team before creating a new one.', 'warning')
        return redirect(url_for('teams.view_team', team_id=existing_membership.team_id))
    
    form = TeamCreateForm()
    if form.validate_on_submit():
        # Create the team
        team = Team(
            name=form.name.data,
            description=form.description.data,
            avatar=form.avatar.data,
            status='active'
        )
        
        try:
            db.session.add(team)
            db.session.flush()  # Flush to get the team ID
            
            # Add the creator as captain
            member = TeamMember(
                user_id=current_user.id,
                team_id=team.id,
                role='captain'
            )
            
            db.session.add(member)
            db.session.commit()
            
            flash(f'Team "{team.name}" has been created! You are the team captain.', 'success')
            return redirect(url_for('teams.view_team', team_id=team.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating team: {str(e)}', 'danger')
    
    return render_template('teams/create.html', form=form, title='Create Team')

@teams_bp.route('/<int:team_id>')
def view_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Get team members with user info
    members = db.session.query(TeamMember, User).join(
        User, TeamMember.user_id == User.id
    ).filter(TeamMember.team_id == team_id).all()
    
    # Get team competitions
    team_competitions = TeamCompetition.query.filter_by(team_id=team_id).all()
    competition_ids = [tc.competition_id for tc in team_competitions]
    competitions = Competition.query.filter(Competition.id.in_(competition_ids)).all() if competition_ids else []
    
    # Check if current user is a member of this team
    is_member = False
    is_captain = False
    if current_user.is_authenticated:
        member = TeamMember.query.filter_by(
            team_id=team_id,
            user_id=current_user.id
        ).first()
        is_member = member is not None
        is_captain = member.role == 'captain' if is_member else False
    
    return render_template('teams/detail.html',
                          team=team,
                          members=members,
                          competitions=competitions,
                          is_member=is_member,
                          is_captain=is_captain,
                          title=f'Team: {team.name}')

@teams_bp.route('/<int:team_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Check if user is captain
    if not is_team_captain(team_id) and not current_user.is_admin():
        flash('Only team captains can edit team details.', 'danger')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    form = TeamEditForm()
    
    if request.method == 'GET':
        form.name.data = team.name
        form.description.data = team.description
        form.avatar.data = team.avatar
        form.status.data = team.status.name
        form.id.data = team.id
    
    if form.validate_on_submit():
        team.name = form.name.data
        team.description = form.description.data
        team.avatar = form.avatar.data
        team.status = form.status.data.lower()
        
        try:
            db.session.commit()
            flash('Team details updated successfully.', 'success')
            return redirect(url_for('teams.view_team', team_id=team_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating team: {str(e)}', 'danger')
    
    return render_template('teams/edit.html', form=form, team=team, title='Edit Team')

@teams_bp.route('/<int:team_id>/invite', methods=['GET', 'POST'])
@login_required
def invite_member(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Check if user is captain
    if not is_team_captain(team_id) and not current_user.is_admin():
        flash('Only team captains can invite members.', 'danger')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Check if team is full (max 5 members)
    if team.member_count() >= 5:
        flash('Your team has reached the maximum number of members (5).', 'warning')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    form = TeamInviteMemberForm()
    
    if form.validate_on_submit():
        # Get user by username
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if user already belongs to a team
        existing_membership = TeamMember.query.filter_by(user_id=user.id).first()
        if existing_membership:
            flash(f'User {user.username} already belongs to another team.', 'warning')
            return redirect(url_for('teams.invite_member', team_id=team_id))
        
        # Add user to team
        member = TeamMember(
            user_id=user.id,
            team_id=team.id,
            role='member'
        )
        
        try:
            db.session.add(member)
            db.session.commit()
            flash(f'User {user.username} has been added to your team.', 'success')
            return redirect(url_for('teams.view_team', team_id=team_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding member: {str(e)}', 'danger')
    
    return render_template('teams/invite.html', form=form, team=team, title='Invite Team Member')

@teams_bp.route('/<int:team_id>/join', methods=['POST'])
@login_required
def join_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Check if user already belongs to a team
    existing_membership = TeamMember.query.filter_by(user_id=current_user.id).first()
    if existing_membership:
        flash('You already belong to a team. You must leave your current team before joining a new one.', 'warning')
        return redirect(url_for('teams.view_team', team_id=existing_membership.team_id))
    
    # Check if team is full (max 5 members)
    if team.member_count() >= 5:
        flash('This team has reached the maximum number of members (5).', 'warning')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Add user to team
    member = TeamMember(
        user_id=current_user.id,
        team_id=team.id,
        role='member'
    )
    
    try:
        db.session.add(member)
        db.session.commit()
        flash(f'You have joined the team {team.name}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error joining team: {str(e)}', 'danger')
    
    return redirect(url_for('teams.view_team', team_id=team_id))

@teams_bp.route('/<int:team_id>/leave', methods=['GET', 'POST'])
@login_required
def leave_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Check if user is a member of this team
    member = TeamMember.query.filter_by(
        team_id=team_id,
        user_id=current_user.id
    ).first()
    
    if not member:
        flash('You are not a member of this team.', 'warning')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    form = TeamLeaveForm()
    
    if form.validate_on_submit():
        # Check if user is the captain and not the only member
        if member.role == 'captain' and team.member_count() > 1:
            # Find another member to promote to captain
            new_captain = TeamMember.query.filter(
                TeamMember.team_id == team_id,
                TeamMember.user_id != current_user.id
            ).first()
            
            if new_captain:
                new_captain.role = 'captain'
                flash(f'User {new_captain.user.username} has been promoted to team captain.', 'info')
        
        # Remove user from team
        try:
            db.session.delete(member)
            
            # If this was the last member, delete the team
            if team.member_count() <= 1:
                db.session.delete(team)
                flash(f'Team {team.name} has been disbanded as it has no more members.', 'info')
                db.session.commit()
                return redirect(url_for('teams.list_teams'))
            
            db.session.commit()
            flash(f'You have left team {team.name}.', 'success')
            return redirect(url_for('teams.list_teams'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error leaving team: {str(e)}', 'danger')
    
    return render_template('teams/leave.html', form=form, team=team, title='Leave Team')

@teams_bp.route('/<int:team_id>/kick/<int:member_id>', methods=['POST'])
@login_required
def kick_member(team_id, member_id):
    team = Team.query.get_or_404(team_id)
    
    # Check if user is captain
    if not is_team_captain(team_id) and not current_user.is_admin():
        flash('Only team captains can remove members.', 'danger')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Get the member to kick
    member = TeamMember.query.filter_by(
        id=member_id,
        team_id=team_id
    ).first_or_404()
    
    # Cannot kick yourself as captain
    if member.user_id == current_user.id:
        flash('You cannot remove yourself as captain. Use the leave team option instead.', 'warning')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Get user info for the flash message
    user = User.query.get(member.user_id)
    
    # Remove member
    try:
        db.session.delete(member)
        db.session.commit()
        flash(f'User {user.username} has been removed from the team.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing member: {str(e)}', 'danger')
    
    return redirect(url_for('teams.view_team', team_id=team_id))

@teams_bp.route('/<int:team_id>/register/<int:competition_id>', methods=['POST'])
@login_required
def register_for_competition(team_id, competition_id):
    team = Team.query.get_or_404(team_id)
    competition = Competition.query.get_or_404(competition_id)
    
    # Check if user is captain
    if not is_team_captain(team_id) and not current_user.is_admin():
        flash('Only team captains can register for competitions.', 'danger')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Check if team has minimum required members (2)
    if not team.has_minimum_members():
        flash('Your team needs at least 2 members to register for competitions.', 'warning')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Check if registration is allowed
    if competition.status == 'ENDED':
        flash('Registration is closed for this competition', 'danger')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Check if the competition has a maximum participant limit
    if competition.max_participants:
        current_participants = (
            UserCompetition.query.filter_by(competition_id=competition_id).count() +
            TeamCompetition.query.filter_by(competition_id=competition_id).count()
        )
        if current_participants >= competition.max_participants:
            flash('This competition has reached its maximum number of participants', 'danger')
            return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Check if already registered
    existing_registration = TeamCompetition.query.filter_by(
        team_id=team_id,
        competition_id=competition_id
    ).first()
    
    if existing_registration:
        flash('Your team is already registered for this competition', 'info')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Create registration
    team_competition = TeamCompetition(
        team_id=team_id,
        competition_id=competition_id,
        score=0
    )
    
    try:
        db.session.add(team_competition)
        db.session.commit()
        flash('Your team has successfully registered for this competition', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error registering for competition: {str(e)}', 'danger')
    
    return redirect(url_for('competitions.view_competition', competition_id=competition_id))

@teams_bp.route('/<int:team_id>/unregister/<int:competition_id>', methods=['POST'])
@login_required
def unregister_from_competition(team_id, competition_id):
    team = Team.query.get_or_404(team_id)
    competition = Competition.query.get_or_404(competition_id)
    
    # Check if user is captain
    if not is_team_captain(team_id) and not current_user.is_admin():
        flash('Only team captains can unregister from competitions.', 'danger')
        return redirect(url_for('teams.view_team', team_id=team_id))
    
    # Check if the competition has already started
    if competition.status != 'UPCOMING':
        flash('You cannot unregister from a competition that has already started', 'danger')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    # Find registration
    team_competition = TeamCompetition.query.filter_by(
        team_id=team_id,
        competition_id=competition_id
    ).first()
    
    if not team_competition:
        flash('Your team is not registered for this competition', 'info')
        return redirect(url_for('competitions.view_competition', competition_id=competition_id))
    
    try:
        db.session.delete(team_competition)
        db.session.commit()
        flash('Your team has successfully unregistered from this competition', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error unregistering from competition: {str(e)}', 'danger')
    
    return redirect(url_for('competitions.view_competition', competition_id=competition_id))