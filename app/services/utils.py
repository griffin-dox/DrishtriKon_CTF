# This file has been moved to utils/utils.py. Please update your imports accordingly.

from datetime import datetime, timedelta
import logging
import subprocess
import json
import os
import pyotp
import random
import string
import time
from app.extensions import db, mail
from app.models import Competition, CompetitionStatus, Challenge, CompetitionChallenge
from app.models import Badge, User, UserBadge
from werkzeug.utils import secure_filename
from flask import current_app, render_template
from flask_mail import Message
from app.services.email_service import send_otp 

logger = logging.getLogger(__name__)

# Cache variables
_last_status_update = 0
_STATUS_UPDATE_INTERVAL = 60  # Only update competition status every 60 seconds

def update_competition_statuses(force=False):
    """
    Updates the status of competitions based on their start and end times.
    Should be run periodically.
    
    Args:
        force (bool): Force update regardless of cache time
    """
    global _last_status_update
    now = datetime.utcnow()
    current_time = time.time()
    
    # Check if we need to update based on cache time
    if not force and current_time - _last_status_update < _STATUS_UPDATE_INTERVAL:
        return
    
    logger.info("Updating competition statuses")
    _last_status_update = current_time
    
    try:
        # Query competitions and update manually instead of using hybrid properties in filter
        competitions = Competition.query.all()
        upcoming_to_active = []
        active_to_ended = []
        
        for comp in competitions:
            # Use hybrid property for status check
            if comp.status == CompetitionStatus.UPCOMING and comp.start_time <= now:
                comp.manual_status_override = CompetitionStatus.ACTIVE
                upcoming_to_active.append(comp)
            elif comp.status == CompetitionStatus.ACTIVE and comp.end_time <= now:
                comp.manual_status_override = CompetitionStatus.ENDED
                active_to_ended.append(comp)
        
        # Only log if we have competitions to update
        if upcoming_to_active:
            logger.info(f"Updated {len(upcoming_to_active)} competitions to active status")
            
        if active_to_ended:
            logger.info(f"Updated {len(active_to_ended)} competitions to ended status")
        
        # Commit changes if any were made
        if upcoming_to_active or active_to_ended:
            db.session.commit()
            for comp in active_to_ended:
                make_challenges_public(comp.id)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating competition statuses: {str(e)}")
                
        # Only log if we have competitions to update
        if upcoming_to_active:
            logger.info(f"Updated {len(upcoming_to_active)} competitions to active status")
            
        if active_to_ended:
            logger.info(f"Updated {len(active_to_ended)} competitions to ended status")
        
        # Commit changes if any were made
        if upcoming_to_active or active_to_ended:
            db.session.commit()
            
            # Process ended competitions after commit to avoid issues
            for comp in active_to_ended:
                make_challenges_public(comp.id)
        
    except Exception as e:
        db.session.rollback()
        logger.error("Error updating competition statuses")

def make_challenges_public(competition_id):
    """
    Makes all challenges in a competition public when the competition ends
    """
    try:
        # Get all challenges in the competition
        cc_ids = db.session.query(CompetitionChallenge.challenge_id).filter_by(competition_id=competition_id).all()
        challenge_ids = [cc_id[0] for cc_id in cc_ids]
        
        if challenge_ids:
            logger.info(f"Making challenges public for competition {competition_id}")
            
            # Update all these challenges to be public
            Challenge.query.filter(Challenge.id.in_(challenge_ids)).update(
                {Challenge.is_public: True}, 
                synchronize_session=False
            )
            
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        logger.error("Error making challenges public")

def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    """Format a datetime object."""
    if value is None:
        return ""
    return value.strftime(format)

def calculate_time_remaining(end_time):
    """Calculate time remaining until the end time."""
    if end_time is None:
        return ""
    
    now = datetime.utcnow()
    if end_time < now:
        return "Ended"
    
    delta = end_time - now
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def save_file(file):
    """Save the file to the uploads directory and return the file path."""
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return filename, file_path, file.mimetype
    return None, None, None

def generate_otp_secret():
    """Generate a random OTP secret key"""
    return pyotp.random_base32()

def generate_otp(secret):
    """Generate a 6-digit OTP code"""
    totp = pyotp.TOTP(secret, interval=300)  # 5-minute interval
    return totp

def verify_otp(secret, otp_code):
    """Verify if the OTP code is valid"""
    if not secret or not otp_code:
        return False
    
    totp = pyotp.TOTP(secret, interval=300)  # 5-minute interval
    return totp.verify(otp_code)

def set_user_otp(user):
    """Generate and set OTP secret for a user"""
    user.otp_secret = generate_otp_secret()
    user.otp_valid_until = datetime.utcnow() + timedelta(minutes=5)
    db.session.commit()
    return generate_otp(user.otp_secret).now()

def send_otp_email(user, otp_code):
    """Send OTP code to user's email using the email_service.py"""
    
    logger.info(f"Preparing to send OTP email to {user.email} for user {user.username}")
    
    try:
        # Call the email service to send the OTP
        result = send_otp(user.email, user.username, otp_code)

        if result["success"]:
            logger.info(f"Successfully sent OTP email to {user.email}")
            return True
        else:
            logger.error(f"Failed to send OTP email to {user.email}. Error: {result['error']}")
            return False

    except Exception as e:
        logger.error(f"Error in send_otp_email: {str(e)}")
        return False

def delete_expired_unverified_users():
    """
    Delete users who have not verified their email within 10 minutes of registration.
    Should be run periodically (e.g., via cron, scheduler, or background thread).
    """
    from app.models import User
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    ten_minutes_ago = now - timedelta(minutes=10)
    try:
        expired_users = User.query.filter(
            (User.email_verified == False) &
            (User.created_at < ten_minutes_ago)
        ).all()
        count = len(expired_users)
        for user in expired_users:
            logger.info(f"Deleting unverified user: {user.username} ({user.email})")
            db.session.delete(user)
        if count > 0:
            db.session.commit()
            logger.info(f"Deleted {count} unverified users.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting unverified users: {str(e)}")

def auto_assign_badges():
    badges = Badge.query.all()
    users = User.query.all()
    for badge in badges:
        if not badge.criteria:
            continue
        for user in users:
            try:
                if eval(badge.criteria, {}, {'user': user}):
                    if not any(ub.badge_id == badge.id for ub in user.badges):
                        user_badge = UserBadge()
                        user_badge.user_id = user.id
                        user_badge.badge_id = badge.id
                        db.session.add(user_badge)
            except Exception:
                continue
    db.session.commit()