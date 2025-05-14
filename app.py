import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from flask import Flask, render_template, request, g, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_migrate import Migrate
from flask_mail import Mail

# Load environment variables early
load_dotenv()

# Configure logging based on environment
if os.getenv('FLASK_ENV') == 'production':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Init extensions
db = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()

# Create app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Set environment
app.config['ENV'] = os.getenv('FLASK_ENV', 'production')
app.config['DEBUG'] = app.config['ENV'] == 'development'
app.config['TESTING'] = app.config['ENV'] == 'testing'

# Force SESSION_COOKIE_SECURE = False for local development
if app.debug:
    app.config['SESSION_COOKIE_SECURE'] = False

# Set secrets
formcarry_url = os.getenv("FORMCARRY_ENDPOINT")

# Use environment variables for secrets, don't set fallback values for production
app.secret_key = os.getenv("SESSION_SECRET")
if not app.secret_key:
    if app.debug:
        import secrets
        logging.warning("No SESSION_SECRET environment variable set. Using randomly generated key for development.")
        app.secret_key = secrets.token_hex(32)
    else:
        logging.critical("No SESSION_SECRET environment variable set in production mode.")
        raise ValueError("SESSION_SECRET must be set in production mode")

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    # Only use the session secret as a fallback if available
    if app.secret_key:
        app.config['SECRET_KEY'] = app.secret_key
    elif app.debug:
        import secrets
        logging.warning("No SECRET_KEY environment variable set. Using randomly generated key for development.")
        app.config['SECRET_KEY'] = secrets.token_hex(32)
    else:
        logging.critical("No SECRET_KEY environment variable set in production mode.")
        raise ValueError("SECRET_KEY must be set in production mode")

#Upload folder
current_dir = os.getcwd()
upload_folder = os.path.join(current_dir, "uploads")

# Check if the folder exists, if not, create it
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder, exist_ok=True)
else:
    pass

# Security configurations
# Set secure cookies based on environment
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload

# Configure DB
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL not found in environment variables!")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Email Config
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")
app.config["MAIL_MAX_EMAILS"] = 5
app.config["MAIL_ASCII_ATTACHMENTS"] = False
app.config["MAIL_DEBUG"] = True

# Init extensions with app
db.init_app(app)
mail.init_app(app)
csrf.init_app(app)
migrate = Migrate(app, db)

# Import security middleware
from security import add_security_headers, security_checks, sanitize_html
from honeypot import check_honeypot_path, check_honeypot_fields, create_honeypot_routes
from ids import analyze_request
from ip_logging import log_ip_activity, get_client_ip
from session_security import init_session_security, require_session_security
from rate_limiter import ip_rate_limit, user_rate_limit, endpoint_rate_limit
from security_headers import init_security, require_csrf, sanitize_timestamp

# Initialize session security
init_session_security(app)

# Initialize security
init_security(app)

# Create honeypot routes with proper error handling
try:
    create_honeypot_routes(app)
except Exception as e:
    logging.error("Failed to create honeypot routes: %s", str(e))

# Apply security headers to all responses
@app.after_request
def apply_security_headers(response):
    return add_security_headers(response)

# Create log directories
def setup_logging_directories():
    # Ensure log directories exist
    for directory in ['logs', 'honeypot_data', 'ids_data']:
        if not os.path.exists(directory):
            os.makedirs(directory)

# Run setup
setup_logging_directories()

# Combine security and session update logic in a single before_request
@app.before_request
def combined_before_request():
    # Always update session timestamp and user info
    session.permanent = True
    session['last_active'] = sanitize_timestamp(datetime.utcnow().timestamp())
    if current_user.is_authenticated:
        g.user_id = current_user.id
        g.username = current_user.username
    else:
        g.user_id = None
        g.username = 'anonymous'

    # Log for debugging session/CSRF issues
    logging.debug(f"[BeforeRequest] Path: {request.path}, Method: {request.method}, Session Keys: {list(session.keys())}")

    # Skip custom security checks for static files and authentication routes
    if request.path.startswith('/static/') or request.path in ['/login', '/register', '/verify-otp', '/logout']:
        return None

    # Log the request
    log_ip_activity('request')

    # Check if path is a honeypot
    if check_honeypot_path():
        logging.warning(f"Honeypot triggered for path {request.path} from {get_client_ip()}")
        return render_template('honeypot/fake_login.html'), 200

    # Check form for honeypot fields
    if request.method == 'POST' and check_honeypot_fields(request.form):
        logging.warning(f"Honeypot form field triggered from {get_client_ip()}")
        return redirect(url_for('main.index')), 302

    # Run IDS analysis
    alerts = analyze_request()
    if alerts and len(alerts) > 0:
        logging.warning(f"IDS alerts triggered: {len(alerts)} for {request.path} from {get_client_ip()}")

    # Run security checks
    if not security_checks():
        logging.warning(f"Security check failed for {request.path} from {get_client_ip()}")
        return render_template('errors/403.html'), 403

# Flask-Login config
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Global template vars
@app.context_processor
def utility_processor():
    return dict(year=lambda: datetime.now().year)

@app.context_processor
def route_existence_processor():
    # Check if certain routes exist to prevent template errors
    # Import Flask related functionality here to avoid circular imports
    from flask import current_app
    
    # Create a dictionary of route existence flags
    route_exists = {
        'host_create_competition_exists': 'host.create_competition' in current_app.view_functions,
        'host_stats_exists': 'host.stats' in current_app.view_functions,
        'challenges_solved_exists': 'challenges.solved' in current_app.view_functions,
        'teams_my_team_exists': 'teams.my_team' in current_app.view_functions,
        'teams_join_team_exists': 'teams.join_team' in current_app.view_functions,
        'teams_create_team_exists': 'teams.create_team' in current_app.view_functions,
    }
    
    return route_exists

# Add static URL optimization
from static_optimization import add_static_url_processor
add_static_url_processor(app)

@app.before_request
def add_year_to_context():
    # Pass the current year to all templates
    from flask import g
    g.year = datetime.now().year

@app.route("/contact")
def contact():
    return render_template("contact.html", form_action=formcarry_url)

@app.route('/csp-violation-report-endpoint/', methods=['POST'])
def csp_violation_report():
    try:
        report = request.get_json(force=True, silent=True)
        if not report:
            app.logger.warning('CSP Violation: No report data received or invalid JSON.')
        else:
            app.logger.warning(f'CSP Violation: {report}')
    except Exception as e:
        app.logger.warning(f'CSP Violation: Failed to parse report. Error: {e}')
    return '', 204  # No Content

# Register routes & update competition status
with app.app_context():
    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.admin import admin_bp
    from routes.host import host_bp
    from routes.player import player_bp
    from routes.challenges import challenges_bp
    from routes.competitions import competitions_bp
    from routes.ads import ads_bp
    from routes.teams import teams_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(host_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(challenges_bp)
    app.register_blueprint(competitions_bp)
    app.register_blueprint(ads_bp)
    app.register_blueprint(teams_bp)

    from utils import update_competition_statuses

    # Removed the @app.before_request that called update_competition_statuses()
    # If you need to update competition statuses, call update_competition_statuses() at startup or use a scheduler.
    
    # Setup error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(429)
    def too_many_requests(e):
        return render_template('errors/429.html'), 429