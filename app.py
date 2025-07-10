# ...existing imports...
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from dotenv import load_dotenv
import uuid

from flask import Flask, render_template, request, g, session, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_migrate import Migrate
from flask_mail import Mail
from flask_caching import Cache

from utils.discord_alerts import setup_logging as setup_discord_security_logging

# Load environment variables early
load_dotenv()

# --- Improved Logging Setup ---
LOG_LEVEL = logging.DEBUG if os.getenv('FLASK_ENV') == 'development' else logging.INFO

# Ensure logs directory exists
if not os.path.exists("logs"):
    os.makedirs("logs")

# Remove default handlers to avoid duplicate logs
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Enhance logging: add request ID and user context to all logs
class RequestFormatter(logging.Formatter):
    def format(self, record):
        from flask import g, has_request_context
        if has_request_context():
            record.request_id = getattr(g, 'request_id', '-')
            record.user_id = getattr(g, 'user_id', '-')
            record.username = getattr(g, 'username', '-')
        else:
            record.request_id = '-'
            record.user_id = '-'
            record.username = '-'
        return super().format(record)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(LOG_LEVEL)
console_handler.setFormatter(RequestFormatter(
    "[%(asctime)s] %(levelname)s [%(request_id)s] [user:%(user_id)s|%(username)s] %(name)s: %(message)s"
))

# Rotating file handler
file_handler = RotatingFileHandler(
    "logs/app.log", maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
)
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(RequestFormatter(
    "[%(asctime)s] %(levelname)s [%(request_id)s] [user:%(user_id)s|%(username)s] %(name)s: %(message)s"
))

logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger(__name__)
# --- End Improved Logging Setup ---

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
        logger.warning("No SESSION_SECRET environment variable set. Using randomly generated key for development.")
        app.secret_key = secrets.token_hex(32)
    else:
        logger.critical("No SESSION_SECRET environment variable set in production mode.")
        raise ValueError("SESSION_SECRET must be set in production mode")

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
if not app.config['SECRET_KEY']:
    # Only use the session secret as a fallback if available
    if app.secret_key:
        app.config['SECRET_KEY'] = app.secret_key
    elif app.debug:
        import secrets
        logger.warning("No SECRET_KEY environment variable set. Using randomly generated key for development.")
        app.config['SECRET_KEY'] = secrets.token_hex(32)
    else:
        logger.critical("No SECRET_KEY environment variable set in production mode.")
        raise ValueError("SECRET_KEY must be set in production mode")

#Upload folder
current_dir = os.getcwd()
upload_folder = os.path.join(current_dir, "uploads")

# Check if the folder exists, if not, create it
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder, exist_ok=True)

# Security configurations
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
    "pool_size": 20,
    "max_overflow": 30,
    "pool_timeout": 30,
    "echo": False,  # Disable SQL logging in production
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Cache Configuration - Simple and reliable
cache_type = os.getenv('CACHE_TYPE', 'simple')
if cache_type == 'filesystem':
    app.config['CACHE_TYPE'] = 'filesystem'
    app.config['CACHE_DIR'] = os.getenv('CACHE_DIR', 'cache_data')
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300
    app.config['CACHE_THRESHOLD'] = 1000  # Max number of items in cache
    # Create cache directory if it doesn't exist
    cache_dir = app.config['CACHE_DIR']
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    logger.info(f"Using filesystem cache in directory: {cache_dir}")
else:
    app.config['CACHE_TYPE'] = 'simple'
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300
    logger.info("Using simple in-memory cache")

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

# reCAPTCHA Config
app.config["RECAPTCHA_SITE_KEY"] = os.getenv("RECAPTCHA_SITE_KEY")
app.config["RECAPTCHA_SECRET_KEY"] = os.getenv("RECAPTCHA_SECRET_KEY")
app.config["RECAPTCHA_ENABLED"] = bool(app.config["RECAPTCHA_SITE_KEY"] and app.config["RECAPTCHA_SECRET_KEY"])

# Log reCAPTCHA configuration status
if app.config["RECAPTCHA_ENABLED"]:
    logger.info("reCAPTCHA v3 is enabled")
else:
    logger.warning("reCAPTCHA v3 is disabled - missing RECAPTCHA_SITE_KEY or RECAPTCHA_SECRET_KEY")

# Init extensions with app
db.init_app(app)
mail.init_app(app)
csrf.init_app(app)
migrate = Migrate(app, db)

# Import security middleware
from security.security import security_checks
from security.honeypot import create_honeypot_routes, check_honeypot_path, check_honeypot_fields
from security.ids import analyze_request
from core.ip_logging import log_ip_activity, get_client_ip
from security.session_security import init_session_security
from security.security_headers import init_security, sanitize_timestamp

# Initialize session security
init_session_security(app)

# Initialize security
init_security(app)

# Create honeypot routes with proper error handling
try:
    create_honeypot_routes(app)
except Exception as e:
    logger.error("Failed to create honeypot routes: %s", str(e))

# Create log directories
def setup_logging_directories():
    # Ensure log directories exist
    for directory in ['logs', 'honeypot_data', 'ids_data']:
        if not os.path.exists(directory):
            os.makedirs(directory)

# Run setup
setup_logging_directories()

# Optimized before_request with reduced security overhead for static files
@app.before_request
def before_request_all():
    # Assign request ID first for logging
    g.request_id = str(uuid.uuid4())
    
    # Skip ALL processing for static files to improve performance
    if request.path.startswith('/static/') or request.path.startswith('/favicon'):
        return None
    
    # Always update session timestamp and user info for non-static requests
    session.permanent = True
    session['last_active'] = sanitize_timestamp(datetime.now(timezone.utc).timestamp())
    
    if current_user.is_authenticated:
        g.user_id = current_user.id
        g.username = current_user.username
    else:
        g.user_id = None
        g.username = 'anonymous'
    
    # Pass the current year to all templates
    g.year = datetime.now().year

    # Skip intensive security checks for authentication routes and health checks
    if request.path in ['/login', '/register', '/verify-otp', '/logout', '/healthz', '/maintenance']:
        return None

    # Log the request (only for non-static, non-auth routes)
    log_ip_activity('request')

    # Only run heavy security checks for sensitive routes
    sensitive_routes = ['/admin', '/host', '/player', '/challenges', '/competitions']
    is_sensitive = any(request.path.startswith(route) for route in sensitive_routes)
    
    if is_sensitive or request.method == 'POST':
        # Check if path is a honeypot
        if check_honeypot_path():
            logger.warning(f"Honeypot triggered for path {request.path} from {get_client_ip()}")
            return render_template('honeypot/fake_login.html'), 200

        # Check form for honeypot fields
        if request.method == 'POST' and check_honeypot_fields(request.form):
            logger.warning(f"Honeypot form field triggered from {get_client_ip()}")
            return redirect(url_for('main.index')), 302

        # Run IDS analysis only for sensitive routes
        alerts = analyze_request()
        if alerts and len(alerts) > 0:
            logger.warning(f"IDS alerts triggered: {len(alerts)} for {request.path} from {get_client_ip()}")

        # Run security checks
        if not security_checks():
            logger.warning(f"Security check failed for {request.path} from {get_client_ip()}")
            return render_template('errors/403.html'), 403

# Flask-Login config
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'  # type: ignore
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
login_manager.session_protection = "strong"

@login_manager.user_loader
def load_user(user_id):
    from core.models import User
    return User.query.get(int(user_id))

# Global template vars
@app.context_processor
def utility_processor():
    return dict(year=lambda: datetime.now().year)

@app.context_processor
def recaptcha_processor():
    """Make reCAPTCHA configuration available in templates"""
    return dict(
        recaptcha_enabled=app.config.get("RECAPTCHA_ENABLED", False),
        recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY", "")
    )

@app.context_processor
def route_existence_processor():
    # Check if certain routes exist to prevent template errors
    from flask import current_app
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
from core.static_optimization import add_static_url_processor
add_static_url_processor(app)

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
csrf.exempt(csp_violation_report)

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html'), 503

@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"}), 200

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
    from routes.badge import badge_bp
    from routes.performance import performance_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(host_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(challenges_bp)
    app.register_blueprint(competitions_bp)
    app.register_blueprint(ads_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(badge_bp)
    app.register_blueprint(performance_bp)

    # --- Periodic Cleanup for Unverified Users ---
    from utils.utils import delete_expired_unverified_users
    delete_expired_unverified_users()  # Run once at startup (optional)
    
    # --- Initialize cache manager and start maintenance ---
    from core.cache_management import schedule_cache_maintenance
    schedule_cache_maintenance()  # Setup automatic cache cleanup and optimization

    # --- Warm up critical caches ---
    from core.performance_cache import warm_critical_caches
    warm_critical_caches()  # Pre-populate frequently accessed data
    
    # Setup error handlers
    @app.errorhandler(404)
    def page_not_found(_):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(_):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_server_error(_):
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(429)
    def too_many_requests(_):
        return render_template('errors/429.html'), 429