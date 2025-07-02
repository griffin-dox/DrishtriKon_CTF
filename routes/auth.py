from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse
from datetime import datetime, timedelta
from app import db, login_manager
from core.models import User
from forms import LoginForm, RegistrationForm, ChangePasswordForm, OTPForm
from core.utils import set_user_otp, send_otp_email, verify_otp as verify_otp_code
from core.recaptcha import verify_recaptcha_token
from security.session_security import generate_session_id
from flask_wtf.csrf import generate_csrf
import random

auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    # Get client IP for rate limiting
    ip_address = request.remote_addr
    
    # Import rate limiting and tracking functions
    from security.security import is_rate_limited, track_login_attempt
    
    # Check if the IP is rate limited
    if is_rate_limited(None, ip_address):
        flash('Too many failed login attempts. Please try again later.', 'danger')
        return render_template('auth/login.html', form=LoginForm(), title='Login', rate_limited=True)
    
    form = LoginForm()
    if form.validate_on_submit():
        # Verify reCAPTCHA if enabled
        recaptcha_token = request.form.get('recaptcha_token')
        if not verify_recaptcha_token(recaptcha_token, 'login'):
            flash('reCAPTCHA verification failed. Please try again.', 'danger')
            return render_template('auth/login.html', form=form, title='Login')
        
        username = form.username.data
        
        # Check if this username is rate limited
        if is_rate_limited(username, None):
            flash('Too many failed login attempts for this account. Please try again later.', 'danger')
            return render_template('auth/login.html', form=form, title='Login', rate_limited=True)
        
        user = User.query.filter_by(username=username).first()
        
        login_successful = False
        
        if user is None or not user.check_password(form.password.data):
            # Track failed login attempt
            track_login_attempt(username, ip_address, False)
            
            # Use a generic error message to avoid leaking valid usernames
            flash('Invalid credentials', 'danger')
            
            # Add a small delay to mitigate timing attacks
            import time
            time.sleep(0.5 + (hash(username + ip_address) % 10) / 10)
            
            return redirect(url_for('auth.login'))
        
        if not user.is_active_user():
            flash('Your account has been suspended or banned. Please contact an administrator.', 'danger')
            track_login_attempt(username, ip_address, False)
            return redirect(url_for('auth.login'))
        
        if not user.email_verified:
            flash('Please verify your email before logging in.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Track successful attempt
        track_login_attempt(username, ip_address, True)
        if user.two_factor_enabled:
            # Generate and send OTP for 2FA
            otp_code = set_user_otp(user)
            send_otp_email(user, otp_code)
            
            # Instead of session.clear(), selectively clear only what you need
            for key in list(session.keys()):
                if key not in ('_fresh', 'csrf_token', 'last_active'):
                    session.pop(key)
            
            # Store user ID in session for the OTP verification
            session['otp_user_id'] = user.id
            session['login_time'] = datetime.utcnow().isoformat()
            
            # Store next page in session if it exists and it's a relative path
            next_page = request.args.get('next')
            if next_page and urlparse(next_page).netloc == '':
                session['next_page'] = next_page
            
            flash('A verification code has been sent to your email.', 'info')
            return redirect(url_for('auth.verify_otp'))
        else:
            # Log in directly if 2FA is not enabled
            login_user(user)
            next_page = session.pop('next_page', None)
            return redirect(next_page or url_for('main.index'))
    
    return render_template('auth/login.html', form=form, title='Login')

@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        # Verify reCAPTCHA if enabled
        recaptcha_token = request.form.get('recaptcha_token')
        if not verify_recaptcha_token(recaptcha_token, 'register'):
            flash('reCAPTCHA verification failed. Please try again.', 'danger')
            return render_template('auth/register.html', form=form, title='Register')
        
        user = User(
            username=form.username.data,
            email=form.email.data
        )
        user.set_password(form.password.data)
        user.email_verified = False
        user.otp_secret = str(random.randint(100000, 999999))
        user.otp_valid_until = datetime.utcnow() + timedelta(minutes=10)
        try:
            db.session.add(user)
            db.session.commit()
            # Send OTP to email
            from core.email_service import send_otp
            send_otp(user.email, user.username, user.otp_secret)
            session['verify_email_user_id'] = user.id
            flash('A verification code has been sent to your email. Please verify to complete registration.', 'info')
            return redirect(url_for('auth.verify_email'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
    return render_template('auth/register.html', form=form, title='Register')

@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if 'verify_email_user_id' not in session:
        flash('No verification in progress. Please register.', 'warning')
        return redirect(url_for('auth.register'))
    user = User.query.get(session['verify_email_user_id'])
    if not user:
        flash('User not found. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    # Check if OTP expired
    if not user.otp_valid_until or user.otp_valid_until < datetime.utcnow():
        db.session.delete(user)
        db.session.commit()
        session.pop('verify_email_user_id', None)
        flash('Verification code expired. Please register again.', 'warning')
        return redirect(url_for('auth.register'))
    form = OTPForm()
    if form.validate_on_submit():
        if user.otp_secret == form.otp_code.data:
            user.email_verified = True
            user.otp_secret = None
            user.otp_valid_until = None
            db.session.commit()
            session.pop('verify_email_user_id', None)
            flash('Email verified! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid verification code.', 'danger')
    return render_template('auth/verify_email.html', form=form, title='Verify Email')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    # Check if we have the user ID in session
    if 'otp_user_id' not in session:
        flash('Please log in first', 'warning')
        return redirect(url_for('auth.login'))
    
    user_id = session['otp_user_id']
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('auth.login'))
    
    # Check if OTP has expired
    if not user.otp_valid_until or user.otp_valid_until < datetime.utcnow():
        flash('Verification code has expired. Please log in again.', 'warning')
        return redirect(url_for('auth.login'))
    
    form = OTPForm()
    
    if form.validate_on_submit():
        otp_code = form.otp_code.data
        
        # Only verify with the actual OTP code from email
        if verify_otp_code(user.otp_secret, otp_code):
            # Clear OTP verification data
            user.otp_secret = None
            user.otp_valid_until = None
            user.email_verified = True
            db.session.commit()
            
            # Log user in
            login_user(user)

            # Set session security keys after login
            session['_id'] = generate_session_id()
            session['_created'] = datetime.utcnow().timestamp()
            session['_last_activity'] = datetime.utcnow().timestamp()
            session['_ip'] = request.remote_addr
            session['_user_agent'] = request.headers.get('User-Agent', '')

            session.modified = True  # Force session to be saved before redirect

            # Clear only OTP-related session data
            next_page = session.pop('next_page', None)
            session.pop('otp_user_id', None)
            
            # Redirect to appropriate page
            if next_page and urlparse(next_page).netloc == '':
                return redirect(next_page)
            else:
                if user.is_admin():
                    return redirect(url_for('admin.dashboard'))
                elif user.is_host():
                    return redirect(url_for('host.dashboard'))
                else:
                    return redirect(url_for('player.dashboard'))
        else:
            flash('Invalid verification code', 'danger')
    
    # For GET request or invalid OTP
    expiry_minutes = user.get_otp_expiry()
    return render_template('auth/verify_otp.html', form=form, title='Verify OTP', expiry_minutes=expiry_minutes)

@auth_bp.route('/resend-otp')
def resend_otp():
    # Check if we have the user ID in session
    if 'otp_user_id' not in session:
        flash('Please log in first', 'warning')
        return redirect(url_for('auth.login'))
    
    user_id = session['otp_user_id']
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('auth.login'))
    
    # Generate and send a new OTP
    otp_code = set_user_otp(user)
    send_otp_email(user, otp_code)
    
    flash('A new verification code has been sent to your email', 'info')
    return redirect(url_for('auth.verify_otp'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('auth.change_password'))
        
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been updated', 'success')
        return redirect(url_for('player.settings'))
    
    return render_template('auth/change_password.html', form=form, title='Change Password')