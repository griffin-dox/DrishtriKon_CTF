from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse
from datetime import datetime, timedelta
from app.extensions import db, login_manager
from app.models import User
from app.forms import LoginForm, RegistrationForm, ChangePasswordForm, OTPForm
from app.services.utils import set_user_otp, send_otp_email, verify_otp as verify_otp_code
from app.services.recaptcha import verify_recaptcha_token
from app.security.session_security import generate_session_id
from app.services.db_health import require_db, render_db_error
from flask_wtf.csrf import generate_csrf
from app.security.rate_limit_policies import rate_limit_route, user_or_ip_identifier, otp_session_identifier
from app.services.health_checks import notify_health_check
import random
import logging

auth_bp = Blueprint('auth', __name__)

# Set up security logger for security events
security_logger = logging.getLogger('security')

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to load user {user_id}: {str(e)}")
        return None

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if current_user.is_authenticated:
            return redirect(url_for('main.index'))

        if request.method == 'GET':
            notify_health_check(request.remote_addr, request.path)
        
        # Get client IP for rate limiting
        ip_address = request.remote_addr
        
        # Import rate limiting and tracking functions
        from app.security.security import is_rate_limited, track_login_attempt
        
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
                # Log failed login attempt as a security event
                security_logger.warning(
                    f"Failed login attempt for username '{username}' from IP {ip_address}",
                    extra={"user": username, "ip": ip_address, "event": "failed_login"}
                )
                
                # Use a generic error message to avoid leaking valid usernames
                flash('Invalid credentials', 'danger')
                
                # Add a small delay to mitigate timing attacks
                import time
                time.sleep(0.5 + (hash(username + ip_address) % 10) / 10)
                
                return redirect(url_for('auth.login'))
            
            if not user.is_active_user():
                flash('Your account has been suspended or banned. Please contact an administrator.', 'danger')
                track_login_attempt(username, ip_address, False)
                # Log account lockout/suspension
                security_logger.warning(
                    f"Login attempt for locked/suspended user '{username}' from IP {ip_address}",
                    extra={"user": username, "ip": ip_address, "event": "account_locked"}
                )
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
                security_logger.info(
                    f"User '{user.username}' logged in from IP {ip_address}",
                    extra={"user": user.username, "ip": ip_address, "event": "login"}
                )
                return redirect(next_page or url_for('main.index'))
        
        return render_template('auth/login.html', form=form, title='Login')
    
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Database error during login: {str(e)}")
        return render_db_error("Unable to access database for login. Please try again shortly.")
        
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
            # Log failed login attempt as a security event
            security_logger.warning(
                f"Failed login attempt for username '{username}' from IP {ip_address}",
                extra={"user": username, "ip": ip_address, "event": "failed_login"}
            )
            
            # Use a generic error message to avoid leaking valid usernames
            flash('Invalid credentials', 'danger')
            
            # Add a small delay to mitigate timing attacks
            import time
            time.sleep(0.5 + (hash(username + ip_address) % 10) / 10)
            
            return redirect(url_for('auth.login'))
        
        if not user.is_active_user():
            flash('Your account has been suspended or banned. Please contact an administrator.', 'danger')
            track_login_attempt(username, ip_address, False)
            # Log account lockout/suspension
            security_logger.warning(
                f"Login attempt for locked/suspended user '{username}' from IP {ip_address}",
                extra={"user": username, "ip": ip_address, "event": "account_locked"}
            )
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
    if current_user.is_authenticated:
        security_logger.info(
            f"User '{current_user.username}' logged out from IP {request.remote_addr}",
            extra={"user": current_user.username, "ip": request.remote_addr, "event": "logout"}
        )
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@rate_limit_route(
    "register",
    10,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many registration attempts.",
    methods={"POST"},
)
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        notify_health_check(request.remote_addr, request.path)
    form = RegistrationForm()
    if form.validate_on_submit():
        recaptcha_token = request.form.get('recaptcha_token')
        if not verify_recaptcha_token(recaptcha_token, 'register'):
            security_logger.warning(
                f"Failed registration (reCAPTCHA) for email '{form.email.data}' from IP {request.remote_addr}",
                extra={"user": form.username.data, "ip": request.remote_addr, "event": "failed_registration_recaptcha"}
            )
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
            from app.services.email_service import send_otp
            send_otp(user.email, user.username, user.otp_secret)
            session['verify_email_user_id'] = user.id
            security_logger.info(
                f"User registered: '{user.username}' ({user.email}) from IP {request.remote_addr}",
                extra={"user": user.username, "ip": request.remote_addr, "event": "user_registered"}
            )
            flash('A verification code has been sent to your email. Please verify to complete registration.', 'info')
            return redirect(url_for('auth.verify_email'))
        except Exception as e:
            db.session.rollback()
            security_logger.warning(
                f"Failed registration for email '{form.email.data}' from IP {request.remote_addr}: {str(e)}",
                extra={"user": form.username.data, "ip": request.remote_addr, "event": "failed_registration"}
            )
            flash(f'Error creating account: {str(e)}', 'danger')
    return render_template('auth/register.html', form=form, title='Register')

@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if 'verify_email_user_id' not in session:
        security_logger.warning(
            f"Email verification attempt with no session from IP {request.remote_addr}",
            extra={"ip": request.remote_addr, "event": "verify_email_no_session"}
        )
        flash('No verification in progress. Please register.', 'warning')
        return redirect(url_for('auth.register'))
    user = User.query.get(session['verify_email_user_id'])
    if not user:
        security_logger.warning(
            f"Email verification attempt for missing user from IP {request.remote_addr}",
            extra={"ip": request.remote_addr, "event": "verify_email_no_user"}
        )
        flash('User not found. Please register again.', 'danger')
        return redirect(url_for('auth.register'))
    if not user.otp_valid_until or user.otp_valid_until < datetime.utcnow():
        db.session.delete(user)
        db.session.commit()
        session.pop('verify_email_user_id', None)
        security_logger.warning(
            f"Email verification code expired for user '{user.username}' from IP {request.remote_addr}",
            extra={"user": user.username, "ip": request.remote_addr, "event": "verify_email_expired"}
        )
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
            security_logger.info(
                f"Email verified for user '{user.username}' from IP {request.remote_addr}",
                extra={"user": user.username, "ip": request.remote_addr, "event": "email_verified"}
            )
            flash('Email verified! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            security_logger.warning(
                f"Invalid email verification code for user '{user.username}' from IP {request.remote_addr}",
                extra={"user": user.username, "ip": request.remote_addr, "event": "verify_email_invalid_otp"}
            )
            flash('Invalid verification code.', 'danger')
    return render_template('auth/verify_email.html', form=form, title='Verify Email')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    # Check if we have the user ID in session
    if 'otp_user_id' not in session:
        security_logger.warning(
            f"2FA verification attempt with no session from IP {request.remote_addr}",
            extra={"ip": request.remote_addr, "event": "verify_otp_no_session"}
        )
        flash('Please log in first', 'warning')
        return redirect(url_for('auth.login'))
    user_id = session['otp_user_id']
    user = User.query.get(user_id)
    if not user:
        security_logger.warning(
            f"2FA verification attempt for missing user from IP {request.remote_addr}",
            extra={"ip": request.remote_addr, "event": "verify_otp_no_user"}
        )
        flash('User not found', 'danger')
        return redirect(url_for('auth.login'))
    if not user.otp_valid_until or user.otp_valid_until < datetime.utcnow():
        security_logger.warning(
            f"2FA verification code expired for user '{user.username}' from IP {request.remote_addr}",
            extra={"user": user.username, "ip": request.remote_addr, "event": "verify_otp_expired"}
        )
        flash('Verification code has expired. Please log in again.', 'warning')
        return redirect(url_for('auth.login'))
    form = OTPForm()
    if form.validate_on_submit():
        otp_code = form.otp_code.data
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
            
            security_logger.info(
                f"2FA verified for user '{user.username}' from IP {request.remote_addr}",
                extra={"user": user.username, "ip": request.remote_addr, "event": "2fa_verified"}
            )

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
            security_logger.warning(
                f"Invalid 2FA code for user '{user.username}' from IP {request.remote_addr}",
                extra={"user": user.username, "ip": request.remote_addr, "event": "2fa_invalid_otp"}
            )
            flash('Invalid verification code', 'danger')
    
    # For GET request or invalid OTP
    expiry_minutes = user.get_otp_expiry()
    return render_template('auth/verify_otp.html', form=form, title='Verify OTP', expiry_minutes=expiry_minutes)

@auth_bp.route('/resend-otp')
@rate_limit_route(
    "otp_resend",
    3,
    600,
    identifier_func=otp_session_identifier,
    message="OTP resend limit reached.",
    methods={"GET"},
)
def resend_otp():
    # Check if we have the user ID in session
    if 'otp_user_id' not in session:
        security_logger.warning(
            f"OTP resend attempt with no session from IP {request.remote_addr}",
            extra={"ip": request.remote_addr, "event": "resend_otp_no_session"}
        )
        flash('Please log in first', 'warning')
        return redirect(url_for('auth.login'))
    user_id = session['otp_user_id']
    user = User.query.get(user_id)
    if not user:
        security_logger.warning(
            f"OTP resend attempt for missing user from IP {request.remote_addr}",
            extra={"ip": request.remote_addr, "event": "resend_otp_no_user"}
        )
        flash('User not found', 'danger')
        return redirect(url_for('auth.login'))
    # Generate and send a new OTP
    otp_code = set_user_otp(user)
    send_otp_email(user, otp_code)
    security_logger.info(
        f"OTP resent for user '{user.username}' from IP {request.remote_addr}",
        extra={"user": user.username, "ip": request.remote_addr, "event": "otp_resent"}
    )
    flash('A new verification code has been sent to your email', 'info')
    return redirect(url_for('auth.verify_otp'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
@rate_limit_route(
    "password_change",
    5,
    600,
    identifier_func=user_or_ip_identifier,
    message="Too many password change attempts.",
    methods={"POST"},
)
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.old_password.data):
            flash('Current password is incorrect.', 'danger')
            # Log failed password change attempt
            security_logger.warning(
                f"Failed password change attempt for user '{current_user.username}' from IP {request.remote_addr}",
                extra={"user": current_user.username, "ip": request.remote_addr, "event": "failed_password_change"}
            )
            return redirect(url_for('auth.change_password'))
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('Your password has been changed successfully.', 'success')
        # Log successful password change
        security_logger.info(
            f"Password changed for user '{current_user.username}' from IP {request.remote_addr}",
            extra={"user": current_user.username, "ip": request.remote_addr, "event": "password_changed"}
        )
        return redirect(url_for('main.index'))
    return render_template('auth/change_password.html', form=form, title='Change Password')