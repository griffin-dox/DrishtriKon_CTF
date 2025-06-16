from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, IntegerField, BooleanField, DateTimeField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional, URL, NumberRange
from core.models import User, UserRole, ChallengeType, CompetitionStatus, TeamStatus, TeamRole
from flask_wtf.file import FileField, FileAllowed, FileRequired
from security.user_security import validate_password_strength, PasswordBreachDetector

# Custom validator for secure passwords
class SecurePassword:
    def __init__(self, message=None):
        self.message = message
        
    def __call__(self, form, field):
        # Check password strength
        is_valid, error_message = validate_password_strength(field.data)
        if not is_valid:
            message = self.message or error_message
            raise ValidationError(message)
            
        # Check for breached passwords
        breach_level = PasswordBreachDetector.check_password_leak(field.data)
        if breach_level > 0:
            raise ValidationError("This password appears in data breaches and is not secure. Please choose a different one.")

class SecureForm(FlaskForm):
    class Meta:
        csrf = True

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class OTPForm(FlaskForm):
    otp_code = StringField('OTP Code', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('Verify')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8),
        SecurePassword()
    ])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    avatar = StringField('Avatar URL', validators=[Optional(), Length(max=255)])
    two_factor_enabled = BooleanField('Enable Two-Factor Authentication (2FA)')
    submit = SubmitField('Update Profile')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(), 
        Length(min=8),
        SecurePassword()
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')

class UserCreateForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8),
        SecurePassword()
    ])
    role = SelectField('Role', choices=[(role.name, role.value) for role in UserRole])
    submit = SubmitField('Create User')

class UserEditForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    # Set dropdown order: player, host, owner
    role = SelectField('Role', choices=[('PLAYER', 'player'), ('HOST', 'host'), ('OWNER', 'owner')])
    status = SelectField('Status', choices=[('ACTIVE', 'Active'), ('RESTRICTED', 'Restricted'), 
                                           ('SUSPENDED', 'Suspended'), ('BANNED', 'Banned')])
    submit = SubmitField('Update User')

class ChallengeForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField('Description', validators=[DataRequired()])
    file = FileField('Attach File', validators=[
        FileAllowed(['zip', 'txt', 'pdf', 'png', 'jpg', 'jpeg'], 'Invalid file type!')
    ])
    flag = StringField('Flag', validators=[DataRequired(), Length(max=255)])
    points = IntegerField('Points', validators=[DataRequired()])
    type = SelectField('Type', choices=[(t.name, t.value) for t in ChallengeType])
    difficulty = SelectField('Difficulty', choices=[(str(i), str(i)) for i in range(1, 6)])
    hint = TextAreaField('Hint', validators=[Optional()])
    is_lab = BooleanField('Mark as Lab Challenge (educational/tutorial challenges)', 
                 default=False, 
                 description="Lab challenges are educational in nature and appear in the Labs section")
    is_public = BooleanField('Make Publicly Visible (outside competitions)', 
                  default=False, 
                  description="Public challenges appear on public pages for all users. Competition-specific challenges are only visible within that competition.")
    submit = SubmitField('Save Challenge')

class CompetitionForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField('Description', validators=[Optional()])
    start_time = DateTimeField('Start Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    end_time = DateTimeField('End Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    max_participants = IntegerField('Max Participants', validators=[Optional()])
    is_public = BooleanField('Public Competition', default=True)
    submit = SubmitField('Save Competition')
    show_leaderboard = BooleanField('Show Leaderboard')


class BadgeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    icon = StringField('Icon Class', validators=[Optional()])
    criteria = TextAreaField('Award Criteria', validators=[Optional()])
    image = FileField('Badge Image', validators=[Optional()])
    submit = SubmitField('Save Badge')

class CompetitionChallengeForm(FlaskForm):
    challenge_id = SelectField('Challenge', coerce=int, validators=[DataRequired()])
    release_time = DateTimeField('Release Time', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Add Challenge')

class FlagSubmissionForm(FlaskForm):
    flag = StringField('Flag', validators=[DataRequired()])
    submit = SubmitField('Submit Flag')

class CompetitionHostForm(FlaskForm):
    host_id = SelectField('Host', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Assign Host')
    
class UserSearchForm(FlaskForm):
    search = StringField('Search Username', validators=[DataRequired()])
    submit = SubmitField('Search')

class CompetitionManualStatusForm(FlaskForm):
    status = SelectField(
        'Competition Status',
        choices=[(status.name, status.value.capitalize()) for status in CompetitionStatus],
        validators=[DataRequired()]
    )
    submit = SubmitField('Update Status')


class AdConfigurationForm(FlaskForm):
    use_google_ads = BooleanField('Use Google Ads')
    submit = SubmitField('Update Ad Configuration')


class AdImageForm(FlaskForm):
    title = StringField('Ad Title', validators=[DataRequired(), Length(max=255)])
    description = TextAreaField('Ad Description', validators=[Optional(), Length(max=1000)])
    image = FileField('Ad Image', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    link_url = StringField('Ad Link URL', validators=[Optional(), URL()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Ad Image')


class AdPlacementForm(FlaskForm):
    ad_image_id = SelectField('Ad Image', coerce=int, validators=[DataRequired()])
    location = SelectField('Ad Location', validators=[DataRequired()])
    is_exclusive = BooleanField('Exclusive Placement (Only this ad will show in this location)', default=False)
    start_date = DateTimeField('Start Date (Optional)', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    end_date = DateTimeField('End Date (Optional)', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    submit = SubmitField('Save Placement')
    
    def __init__(self, *args, **kwargs):
        super(AdPlacementForm, self).__init__(*args, **kwargs)
        from core.models import AdLocation
        self.location.choices = [(loc.name, loc.value.replace('_', ' ').title()) for loc in AdLocation]


# Team Forms
class TeamCreateForm(FlaskForm):
    name = StringField('Team Name', validators=[DataRequired(), Length(min=3, max=64)])
    description = TextAreaField('Team Description', validators=[Optional(), Length(max=500)])
    avatar = StringField('Team Avatar URL', validators=[Optional()])
    submit = SubmitField('Create Team')
    
    def validate_name(self, name):
        from core.models import Team
        team = Team.query.filter_by(name=name.data).first()
        if team:
            raise ValidationError('Team name already exists. Please choose a different one.')

class TeamEditForm(FlaskForm):
    name = StringField('Team Name', validators=[DataRequired(), Length(min=3, max=64)])
    description = TextAreaField('Team Description', validators=[Optional(), Length(max=500)])
    avatar = StringField('Team Avatar URL', validators=[Optional()])
    status = SelectField('Status', choices=[
        (status.name, status.value.capitalize()) for status in TeamStatus
    ])
    submit = SubmitField('Update Team')
    
    def validate_name(self, name):
        from core.models import Team
        team = Team.query.filter_by(name=name.data).first()
        if team and team.id != self.id.data:
            raise ValidationError('Team name already exists. Please choose a different one.')
    
    def __init__(self, *args, **kwargs):
        super(TeamEditForm, self).__init__(*args, **kwargs)
        self.id = IntegerField('Team ID', validators=[Optional()])

class TeamInviteMemberForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    submit = SubmitField('Invite Member')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if not user:
            raise ValidationError('User not found.')
        if user.role != UserRole.PLAYER:
            raise ValidationError('Only players can join teams.')

class TeamJoinForm(FlaskForm):
    team_code = StringField('Team Code', validators=[DataRequired(), Length(min=6, max=16)])
    submit = SubmitField('Join Team')

class TeamLeaveForm(FlaskForm):
    confirmation = BooleanField('I understand that leaving the team may affect my competition eligibility', validators=[DataRequired()])
    submit = SubmitField('Leave Team')

class TeamKickMemberForm(FlaskForm):
    member_id = IntegerField('Member ID', validators=[DataRequired()])
    submit = SubmitField('Remove Member')

class TeamCompetitionRegisterForm(FlaskForm):
    team_id = SelectField('Team', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Register Team')

class AssignBadgeForm(FlaskForm):
    user_id = SelectField('User', coerce=int, validators=[DataRequired()])
    badge_id = SelectField('Badge', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Assign Badge')