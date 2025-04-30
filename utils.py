from datetime import datetime, timedelta
import logging
import subprocess
import json
import os
import pyotp
import random
import string
from app import db, mail
from models import Competition, CompetitionStatus, Challenge, CompetitionChallenge
import os
from werkzeug.utils import secure_filename
from flask import current_app, render_template
from flask_mail import Message
from email_service import send_otp 

def update_competition_statuses():
    """
    Updates the status of competitions based on their start and end times.
    Should be run periodically.
    """
    now = datetime.utcnow()
    logging.debug(f"Updating competition statuses at {now}")
    
    try:
        # Update upcoming competitions to active
        upcoming_to_active = Competition.query.filter(
            Competition.status == CompetitionStatus.UPCOMING,
            Competition.start_time <= now
        ).all()
        
        if upcoming_to_active:
            logging.debug(f"Found {len(upcoming_to_active)} competitions to transition from upcoming to active")
            
        for comp in upcoming_to_active:
            logging.debug(f"Changing competition '{comp.title}' (ID: {comp.id}) from UPCOMING to ACTIVE")
            logging.debug(f"  - Start time: {comp.start_time}, Current time: {now}")
            comp.status = CompetitionStatus.ACTIVE.value
        
        # Update active competitions to ended
        active_to_ended = Competition.query.filter(
            Competition.status == CompetitionStatus.ACTIVE.value,
            Competition.end_time <= now
        ).all()
        
        if active_to_ended:
            logging.debug(f"Found {len(active_to_ended)} competitions to transition from active to ended")
            
        for comp in active_to_ended:
            logging.debug(f"Changing competition '{comp.title}' (ID: {comp.id}) from ACTIVE to ENDED")
            logging.debug(f"  - End time: {comp.end_time}, Current time: {now}")
            comp.status = CompetitionStatus.ENDED
            
            # When a competition ends, make all its challenges public
            make_challenges_public(comp.id)
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating competition statuses: {str(e)}")

def make_challenges_public(competition_id):
    """
    Makes all challenges in a competition public when the competition ends
    """
    try:
        # Get all challenges in the competition
        cc_ids = db.session.query(CompetitionChallenge.challenge_id).filter_by(competition_id=competition_id).all()
        challenge_ids = [cc_id[0] for cc_id in cc_ids]
        
        if challenge_ids:
            logging.debug(f"Making {len(challenge_ids)} challenges public for ended competition ID {competition_id}")
            
            # Update all these challenges to be public
            Challenge.query.filter(Challenge.id.in_(challenge_ids)).update(
                {Challenge.is_public: True}, 
                synchronize_session=False
            )
            
            db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error making challenges public: {str(e)}")

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
    
    logging.info(f"Preparing to send OTP email to {user.email} for user {user.username}")
    
    try:
        # Call the email service to send the OTP
        result = send_otp(user.email, user.username, otp_code)

        if result["success"]:
            logging.info(f"Successfully sent OTP email to {user.email}")
            return True
        else:
            logging.error(f"Failed to send OTP email to {user.email}. Error: {result['error']}")
            return False

    except Exception as e:
        logging.error(f"Error in send_otp_email: {str(e)}")
        return False