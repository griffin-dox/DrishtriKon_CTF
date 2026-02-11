import enum
from datetime import datetime
from app.extensions import db
from flask_login import UserMixin
from sqlalchemy import case, func, cast
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB


# User Roles Enum
class UserRole(enum.Enum):
    OWNER = "owner"
    HOST = "host"
    PLAYER = "player"

# User Status Enum
class UserStatus(enum.Enum):
    ACTIVE = "active"
    RESTRICTED = "restricted"
    SUSPENDED = "suspended"
    BANNED = "banned"

# Challenge Types Enum
class ChallengeType(enum.Enum):
    WEB = "web"
    CRYPTO = "crypto"
    FORENSICS = "forensics"
    REVERSE = "reverse"
    PWNABLE = "pwnable"
    MISC = "misc"
    OSINT = "osint"
    LAB = "lab"

# Challenge Visibility Scope Enum
class ChallengeVisibilityScope(enum.Enum):
    PUBLIC = "PUBLIC"                # Visible to all users on public pages
    COMPETITION = "COMPETITION"      # Only visible within competitions
    PRIVATE = "PRIVATE"              # Only visible to admins and creators

# Competition Status Enum
class CompetitionStatus(enum.Enum):
    UPCOMING = "UPCOMING"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"

# Competition Hosting Type Enum
class CompetitionHostingType(enum.Enum):
    IN_PLATFORM = "IN_PLATFORM"
    THIRD_PARTY = "THIRD_PARTY"

# User Model
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.PLAYER, nullable=False)
    status = db.Column(
        db.Enum(UserStatus, name="userstatus", native_enum=False), 
        default=UserStatus.ACTIVE
    )
    score = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.String(255), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    otp_secret = db.Column(db.String(32), nullable=True)
    otp_valid_until = db.Column(db.DateTime, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    two_factor_enabled = db.Column(db.Boolean, default=False)  # New field for 2FA toggle
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    hosted_competitions = db.relationship('Competition', back_populates='host', lazy=True)
    submissions = db.relationship('Submission', back_populates='user', lazy=True, cascade="all, delete-orphan")
    badges = db.relationship('UserBadge', back_populates='user', lazy=True, cascade="all, delete-orphan")
    competitions = db.relationship('UserCompetition', back_populates='user', lazy=True, cascade="all, delete-orphan")
    team_memberships = db.relationship('TeamMember', 
                                   foreign_keys="TeamMember.user_id",
                                   primaryjoin="User.id == TeamMember.user_id",
                                   backref=db.backref('user_account', lazy=True),
                                   lazy=True, 
                                   cascade="all, delete-orphan")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == UserRole.OWNER
        
    def is_host(self):
        return self.role == UserRole.HOST or self.role == UserRole.OWNER
    
    def is_active_user(self):
        return self.status == UserStatus.ACTIVE
    
    def get_otp_expiry(self):
        """Returns OTP expiry time in minutes"""
        if not self.otp_valid_until:
            return 0
        
        now = datetime.utcnow()
        if now > self.otp_valid_until:
            return 0
            
        delta = self.otp_valid_until - now
        return int(delta.total_seconds() // 60) + 1  # Return remaining minutes, rounded up

# Competition Model
class Competition(db.Model):
    __tablename__ = 'competitions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    manual_status_override = db.Column(db.Enum(CompetitionStatus), nullable=True)
    max_participants = db.Column(db.Integer, nullable=True)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    show_leaderboard = db.Column(db.Boolean, default=True)
    
    # New fields for competition hosting
    hosting_type = db.Column(db.Enum(CompetitionHostingType), default=CompetitionHostingType.IN_PLATFORM, nullable=False)
    subdomain = db.Column(db.String(63), nullable=True)  # For third-party hosting

    # Define the 'host' relationship
    host = db.relationship('User', back_populates='hosted_competitions')

    # Other relationships
    participants = db.relationship('UserCompetition', back_populates='competition', lazy=True)
    challenges = db.relationship('CompetitionChallenge', back_populates='competition', lazy=True)

    @hybrid_property
    def status(self):
        if self.manual_status_override is not None:
            return self.manual_status_override
        now = datetime.utcnow()
        if self.start_time > now:
            return CompetitionStatus.UPCOMING
        elif self.end_time < now:
            return CompetitionStatus.ENDED
        return CompetitionStatus.ACTIVE

    @status.expression
    def _status_expression(cls):
        return case(
            (cls.manual_status_override != None, cls.manual_status_override),
            (cls.start_time > func.now(), cast('UPCOMING', PGEnum(CompetitionStatus))),
            (cls.end_time < func.now(), cast('ENDED', PGEnum(CompetitionStatus))),
            else_=cast('ACTIVE', PGEnum(CompetitionStatus))
        )

# Challenge Model
class Challenge(db.Model):
    __tablename__ = 'challenges'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.String(512))  # relative path
    file_mimetype = db.Column(db.String(128))
    flag = db.Column(db.String(255), nullable=False)
    points = db.Column(db.Integer, nullable=False)
    type = db.Column(db.Enum(ChallengeType), nullable=False)
    difficulty = db.Column(db.Integer, nullable=False)  # 1-5 scale
    hint = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_lab = db.Column(db.Boolean, default=False)
    is_public = db.Column(db.Boolean, default=False)  # Public challenges accessible to all users
    
    # New field for challenge visibility scope
    visibility_scope = db.Column(db.Enum(ChallengeVisibilityScope), 
                               default=ChallengeVisibilityScope.PRIVATE, 
                               nullable=False)
    
    # Store competition attribution for challenges that were previously in a competition
    competition_attribution = db.Column(db.String(255), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    

    # Relationships
    creator = db.relationship('User')
    submissions = db.relationship('Submission', back_populates='challenge', lazy=True)
    competitions = db.relationship('CompetitionChallenge', back_populates='challenge', lazy=True)
    
    def is_in_competition(self):
        """Returns True if this challenge is associated with any competition"""
        return self.competitions is not None and len(self.competitions.all()) > 0
        
    def is_public_challenge(self):
        """Returns True if this challenge should be visible on public challenges page"""
        return self.is_public and not self.is_lab and self.visibility_scope == ChallengeVisibilityScope.PUBLIC and not self.is_in_competition()
        
    def is_public_lab(self):
        """Returns True if this challenge should be visible on public labs page"""
        return self.is_public and self.is_lab and self.visibility_scope == ChallengeVisibilityScope.PUBLIC and not self.is_in_competition()
        
    def competition_name(self):
        """Returns the name of the competition this challenge is associated with, if any"""
        if not self.is_in_competition():
            return None
        competition_challenge = self.competitions.first() if hasattr(self.competitions, 'first') else None
        if competition_challenge:
            return competition_challenge.competition.title
        return None

    def competition_host_name(self):
        """Returns the name of the host of the competition this challenge is associated with"""
        if not self.is_in_competition():
            return None
        competition_challenge = self.competitions.first() if hasattr(self.competitions, 'first') else None
        if competition_challenge and competition_challenge.competition:
            return competition_challenge.competition.host.username
        return None

# Submission Model
class Submission(db.Model):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=True)
    flag_submitted = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    points_awarded = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='submissions')
    challenge = db.relationship('Challenge', back_populates='submissions')
    competition = db.relationship('Competition')

# Badge Model
class Badge(db.Model):
    __tablename__ = 'badges'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(255), nullable=True)
    criteria = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)  # Path to custom badge image in static/badges/
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('UserBadge', back_populates='badge', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'image_url': self.image_url,
            'criteria': self.criteria,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# User-Badge Association Model
class UserBadge(db.Model):
    __tablename__ = 'user_badges'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badges.id'), nullable=False)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='badges')
    badge = db.relationship('Badge', back_populates='users')

# Competition-Challenge Association Model
class CompetitionChallenge(db.Model):
    __tablename__ = 'competition_challenges'
    
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    release_time = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    competition = db.relationship('Competition', back_populates='challenges')
    challenge = db.relationship('Challenge', back_populates='competitions')

# Competition-Host Association Model
class CompetitionHost(db.Model):
    __tablename__ = 'competition_hosts'
    
    id = db.Column(db.Integer, primary_key=True)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    competition = db.relationship('Competition', backref=db.backref('additional_hosts', lazy=True))
    host = db.relationship('User', backref=db.backref('assigned_competitions', lazy=True))

# User-Competition Association Model
class UserCompetition(db.Model):
    __tablename__ = 'user_competitions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='competitions')
    competition = db.relationship('Competition', back_populates='participants')


# Team Status Enum
class TeamStatus(enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    
class TeamRole(enum.Enum):
    CAPTAIN = "captain"
    MEMBER = "member"
    
# Team Model
class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    avatar = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    members = db.relationship('TeamMember', back_populates='team', lazy=True)
    competitions = db.relationship('TeamCompetition', back_populates='team', lazy=True)
    
    # Get the team captain
    def get_captain(self):
        captain = TeamMember.query.filter_by(
            team_id=self.id, 
            role='captain'
        ).first()
        return captain
    
    # Get all team members including the captain
    def get_all_members(self):
        return TeamMember.query.filter_by(team_id=self.id).all()
    
    # Count total members
    def member_count(self):
        return TeamMember.query.filter_by(team_id=self.id).count()
    
    # Check if the team is full (maximum 5 members)
    def is_full(self):
        return self.member_count() >= 5
    
    # Check if the team has minimum required members (2)
    def has_minimum_members(self):
        return self.member_count() >= 2
        
# Team Member Model
class TeamMember(db.Model):
    __tablename__ = 'team_members'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    role = db.Column(db.String(20), default='member', nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with proper overlaps
    user = db.relationship('User', overlaps="team_memberships,user_account")
    team = db.relationship('Team', back_populates='members')
    
    # Ensure uniqueness of user-team combination
    __table_args__ = (
        db.UniqueConstraint('user_id', 'team_id', name='_user_team_uc'),
    )
    
# Team Competition Model - tracks team participation in competitions
class TeamCompetition(db.Model):
    __tablename__ = 'team_competitions'
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    competition_id = db.Column(db.Integer, db.ForeignKey('competitions.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    team = db.relationship('Team', back_populates='competitions')
    competition = db.relationship('Competition')
    
    # Ensure uniqueness of team-competition combination
    __table_args__ = (
        db.UniqueConstraint('team_id', 'competition_id', name='_team_competition_uc'),
    )

class AdLocation(enum.Enum):
    LEFT_SIDEBAR = "left_sidebar"
    RIGHT_SIDEBAR = "right_sidebar"
    HORIZONTAL_TOP = "horizontal_top"
    HORIZONTAL_BOTTOM = "horizontal_bottom"
    HOME_HORIZONTAL = "home_horizontal"


class AdConfiguration(db.Model):
    __tablename__ = 'ad_configuration'
    
    id = db.Column(db.Integer, primary_key=True)
    use_google_ads = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdImage(db.Model):
    __tablename__ = 'ad_images'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(512), nullable=False)
    link_url = db.Column(db.String(512), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    placements = db.relationship('AdPlacement', back_populates='ad_image', lazy=True)
    

class AdPlacement(db.Model):
    __tablename__ = 'ad_placements'
    
    id = db.Column(db.Integer, primary_key=True)
    ad_image_id = db.Column(db.Integer, db.ForeignKey('ad_images.id'), nullable=False)
    location = db.Column(db.Enum(AdLocation), nullable=False)
    is_exclusive = db.Column(db.Boolean, default=False)  # If True, only this ad shows in this location
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ad_image = db.relationship('AdImage', back_populates='placements')

# Add classes for promotional system
class PromotionalContainer(db.Model):
    __tablename__ = 'promotional_containers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    location = db.Column(db.String(255), nullable=False)  # Location in UI
    is_active = db.Column(db.Boolean, default=True)
    rotation_speed = db.Column(db.Integer, default=5000)  # Milliseconds between rotations
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    promotional_items = db.relationship('PromotionalItem', back_populates='container', lazy=True)
    
class PromotionalItem(db.Model):
    __tablename__ = 'promotional_items'
    
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.Integer, db.ForeignKey('promotional_containers.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(512), nullable=False)
    link_url = db.Column(db.String(512), nullable=True)
    display_order = db.Column(db.Integer, default=0)  # Order in the rotation
    is_active = db.Column(db.Boolean, default=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    container = db.relationship('PromotionalContainer', back_populates='promotional_items')

class UserSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(128), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BannedIP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), unique=True, nullable=False)
    reason = db.Column(db.String(256))
    banned_at = db.Column(db.DateTime, default=datetime.utcnow)

class IDSAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), nullable=False)
    endpoint = db.Column(db.String(256))
    alert_type = db.Column(db.String(128))
    details = db.Column(db.Text)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)

class RateLimit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), nullable=False)
    endpoint = db.Column(db.String(256))
    count = db.Column(db.Integer, default=1)
    window_start = db.Column(db.DateTime, default=datetime.utcnow)

class IDSState(db.Model):
    __tablename__ = 'ids_state'
    id = db.Column(db.Integer, primary_key=True)
    attack_counters = db.Column(db.JSON, default=dict)
    ip_request_stats = db.Column(db.JSON, default=dict)
    failed_logins = db.Column(db.JSON, default=dict)
    anomaly_scores = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)