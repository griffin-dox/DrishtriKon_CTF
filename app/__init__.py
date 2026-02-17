"""
DrishtriKon CTF Platform - Application Factory.

This module implements the Flask application factory pattern,
allowing multiple app instances with different configurations.
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request, g, session, redirect, url_for, jsonify
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from config import get_config
from app.extensions import init_extensions, db, csrf, login_manager, cache

# Load environment variables
load_dotenv()


class RequestFormatter(logging.Formatter):
    """Custom formatter that adds request context to log records."""
    
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


def setup_logging(app):
    """Configure application logging with rotation and context."""
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
    
    # Ensure logs directory exists
    log_dir = app.config.get('LOG_DIR', 'var/logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Remove default handlers to avoid duplicates
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(RequestFormatter(
        "[%(asctime)s] %(levelname)s [%(request_id)s] [user:%(user_id)s|%(username)s] %(name)s: %(message)s"
    ))
    
    # Rotating file handler
    log_file = os.path.join(log_dir, 'app.log')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(RequestFormatter(
        "[%(asctime)s] %(levelname)s [%(request_id)s] [user:%(user_id)s|%(username)s] %(name)s: %(message)s"
    ))
    
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )
    
    app.logger.info(f"Logging initialized at {log_level} level")


def create_runtime_dirs(app):
    """Create necessary runtime directories."""
    dirs = [
        app.config.get('UPLOAD_FOLDER', 'var/uploads'),
        app.config.get('LOG_DIR', 'var/logs'),
        app.config.get('CACHE_DIR', 'var/cache'),
        'honeypot_data',
        'ids_data',
    ]
    
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def register_blueprints(app):
    """Register all application blueprints."""
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.host import host_bp
    from app.routes.player import player_bp
    from app.routes.challenges import challenges_bp
    from app.routes.competitions import competitions_bp
    from app.routes.ads import ads_bp
    from app.routes.teams import teams_bp
    from app.routes.badge import badge_bp
    from app.routes.performance import performance_bp
    
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


def register_error_handlers(app):
    """Register custom error handlers."""
    
    @app.errorhandler(404)
    def page_not_found(_):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(_):
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 errors gracefully, check for DB errors."""
        app.logger.error(f"Internal server error: {str(error)}")
        
        error_str = str(error).lower()
        if any(keyword in error_str for keyword in [
            'connection', 'database', 'psycopg2', 'operational error',
            'lost connection', 'server closed', 'does not exist'
        ]):
            from app.services.db_health import render_db_error
            return render_db_error()
        
        return render_template('errors/500.html'), 500
        
    @app.errorhandler(429)
    def too_many_requests(_):
        return render_template('errors/429.html'), 429


def register_context_processors(app):
    """Register template context processors."""
    
    @app.context_processor
    def utility_processor():
        return dict(year=lambda: datetime.now().year)
    
    @app.context_processor
    def recaptcha_processor():
        return dict(
            recaptcha_enabled=app.config.get("RECAPTCHA_ENABLED", False),
            recaptcha_site_key=app.config.get("RECAPTCHA_SITE_KEY", "")
        )
    
    @app.context_processor
    def route_existence_processor():
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


def register_request_handlers(app):
    """Register before/after request handlers."""
    
    @app.before_request
    def before_request_all():
        """Global request processing with security checks."""
        from app.services.ip_logging import log_ip_activity, get_client_ip
        from app.security.security import security_checks
        from app.security.honeypot import check_honeypot_path, check_honeypot_fields
        from app.security.ids import analyze_request
        from app.security.security_headers import sanitize_timestamp
        
        # Assign request ID for distributed logging
        g.request_id = str(uuid.uuid4())
        
        # Skip ALL processing for static files (performance optimization)
        if request.path.startswith('/static/') or request.path.startswith('/favicon'):
            return None
        
        try:
            # Update session timestamp
            session.permanent = True
            session['last_active'] = sanitize_timestamp(datetime.now(timezone.utc).timestamp())
            
            # Set user context
            if current_user.is_authenticated:
                g.user_id = current_user.id
                g.username = current_user.username
            else:
                g.user_id = None
                g.username = 'anonymous'
            
            # Pass year to templates
            g.year = datetime.now().year
            
            # Skip security checks for auth/health routes
            if request.path in ['/login', '/register', '/verify-otp', '/logout', '/healthz', '/maintenance']:
                return None
            
            # Log request (non-static, non-auth only)
            log_ip_activity('request')
            
            # Run heavy security checks only for sensitive routes
            sensitive_routes = ['/admin', '/host', '/player', '/challenges', '/competitions']
            is_sensitive = any(request.path.startswith(route) for route in sensitive_routes)
            
            if is_sensitive or request.method == 'POST':
                # Honeypot path check
                if check_honeypot_path():
                    app.logger.warning(f"Honeypot triggered for path {request.path} from {get_client_ip()}")
                    return render_template('honeypot/fake_login.html'), 200
                
                # Honeypot form fields check
                if request.method == 'POST' and check_honeypot_fields(request.form):
                    app.logger.warning(f"Honeypot form field triggered from {get_client_ip()}")
                    return redirect(url_for('main.index')), 302
                
                # IDS analysis
                alerts = analyze_request()
                if alerts and len(alerts) > 0:
                    app.logger.warning(f"IDS alerts: {len(alerts)} for {request.path} from {get_client_ip()}")
                
                # Security checks
                if not security_checks():
                    app.logger.warning(f"Security check failed for {request.path} from {get_client_ip()}")
                    return render_template('errors/403.html'), 403
        
        except Exception as e:
            app.logger.warning(f"Error in before_request hook: {str(e)}")
            pass
        
        return None


def register_shell_context(app):
    """Register shell context for flask shell command."""
    
    @app.shell_context_processor
    def make_shell_context():
        from app.models import (
            User, Challenge, Competition, Team, Badge,
            Submission, UserCompetition, UserBadge
        )
        return {
            'db': db,
            'User': User,
            'Challenge': Challenge,
            'Competition': Competition,
            'Team': Team,
            'Badge': Badge,
            'Submission': Submission,
            'UserCompetition': UserCompetition,
            'UserBadge': UserBadge,
        }


def init_security(app):
    """Initialize security middleware and honeypot routes."""
    from app.security.session_security import init_session_security
    from app.security.security_headers import init_security as init_security_headers
    from app.security.honeypot import create_honeypot_routes
    
    init_session_security(app)
    init_security_headers(app)
    
    try:
        create_honeypot_routes(app)
    except Exception as e:
        app.logger.error(f"Failed to create honeypot routes: {e}")


def init_services(app):
    """Initialize application services (cache, cleanup tasks, etc.)."""
    with app.app_context():
        # Delete expired unverified users - wrap in try-except to not block startup
        try:
            from app.services.utils import delete_expired_unverified_users
            delete_expired_unverified_users()
        except Exception as e:
            app.logger.warning(f"Error during cleanup startup task: {str(e)}")
        
        # Start cache maintenance scheduler
        try:
            from app.services.cache.management import schedule_cache_maintenance
            schedule_cache_maintenance()
        except Exception as e:
            app.logger.warning(f"Error scheduling cache maintenance: {str(e)}")
        
        # Warm up critical caches
        try:
            from app.services.cache.performance import warm_critical_caches
            warm_critical_caches()
        except Exception as e:
            app.logger.warning(f"Error warming critical caches: {str(e)}")


def register_cli_routes(app):
    """Register additional CLI routes and health checks."""
    
    @app.route('/contact')
    def contact():
        formcarry_url = app.config.get('FORMCARRY_ENDPOINT')
        return render_template("contact.html", form_action=formcarry_url)
    
    @app.route('/csp-violation-report-endpoint/', methods=['POST'])
    def csp_violation_report():
        try:
            report = request.get_json(force=True, silent=True)
            if not report:
                app.logger.warning('CSP Violation: No report data received')
            else:
                app.logger.warning(f'CSP Violation: {report}')
        except Exception as e:
            app.logger.warning(f'CSP Violation: Failed to parse report - {e}')
        return '', 204
    
    csrf.exempt(csp_violation_report)
    
    @app.route('/maintenance')
    def maintenance():
        return render_template('maintenance.html'), 503
    
    @app.route('/healthz')
    def healthz():
        return jsonify({"status": "ok"}), 200


def create_app(config_name=None):
    """
    Application factory function.
    
    Args:
        config_name: Configuration environment ('development', 'production', 'testing')
    
    Returns:
        Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'production')
    
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    
    # Setup logging
    setup_logging(app)
    app.logger.info(f"Starting DrishtriKon CTF in {config_name} mode")
    
    # Create runtime directories
    create_runtime_dirs(app)
    
    # Proxy fix for production deployment
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions
    init_extensions(app)
    
    # Initialize security
    init_security(app)
    
    # Register components
    register_blueprints(app)
    register_error_handlers(app)
    register_context_processors(app)
    register_request_handlers(app)
    register_shell_context(app)
    register_cli_routes(app)
    
    # Add static URL optimization
    from app.services.static_optimization import add_static_url_processor
    add_static_url_processor(app)
    
    # Initialize services (cache, cleanup, etc.)
    init_services(app)
    
    return app
