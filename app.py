import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from flask import Flask, render_template, request, g, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_migrate import Migrate
from flask_mail import Mail

# Load environment variables early
load_dotenv()

# Logging
logging.basicConfig(level=logging.DEBUG)

# Init extensions
db = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()

# Create app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Set secrets
formcarry_url = os.getenv("FORMCARRY_ENDPOINT")
app.secret_key = os.getenv("SESSION_SECRET")
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Security configurations
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
app.config['UPLOAD_FOLDER'] = os.getenv("UPLOAD_FOLDER", "./uploads")
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
from honeypot import check_honeypot_path, check_honeypot_fields
from ids import analyze_request
from ip_logging import log_ip_activity, get_client_ip

# Honeypot routes disabled for now due to application stability
# TODO: Re-enable after resolving endpoint conflicts
# from honeypot import create_honeypot_routes
# create_honeypot_routes(app)

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

# Check security before processing request
@app.before_request
def check_security():
    # Skip security checks for static files
    if request.path.startswith('/static/'):
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

# Update session activity timestamp
@app.before_request
def update_session_timestamp():
    session.permanent = True
    session['last_active'] = datetime.utcnow().isoformat()
    
    # Store user info for audit logging
    if current_user.is_authenticated:
        g.user_id = current_user.id
        g.username = current_user.username
    else:
        g.user_id = None
        g.username = 'anonymous'

# Flask-Login config
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
login_manager.session_protection = "strong"

# Global template vars
@app.context_processor
def utility_processor():
    return dict(year=lambda: datetime.now().year)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

@app.before_request
def add_year_to_context():
    # Pass the current year to all templates
    from flask import g
    g.year = datetime.now().year

@app.route("/contact")
def contact():
    return render_template("contact.html", form_action=formcarry_url)

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

    @app.before_request
    def before_request():
        update_competition_statuses()
        
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