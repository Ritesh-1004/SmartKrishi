"""
=============================================================================
SmartKrishi - Flask Application Factory
=============================================================================
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

# Load environment variables before everything else
load_dotenv()


def create_app(config_name: str = None) -> Flask:
    """Application factory pattern."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Configuration ──────────────────────────────────────────────────────────
    config_name = config_name or os.getenv("FLASK_ENV", "development")
    _configure_app(app, config_name)

    # ── Extensions ─────────────────────────────────────────────────────────────
    from app.models.database import db
    db.init_app(app)
    Migrate(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please login to access SmartKrishi."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.database import Farmer
        return db.session.get(Farmer, int(user_id))

    # ── Blueprints ─────────────────────────────────────────────────────────────
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.api import api_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    # ── Database Init ─────────────────────────────────────────────────────────
    with app.app_context():
        from app.models.database import db as database
        database.create_all()
        _init_services(app)

    # ── Logging ───────────────────────────────────────────────────────────────
    _setup_logging(app)

    # ── Error Handlers ────────────────────────────────────────────────────────
    _register_error_handlers(app)

    return app


def _configure_app(app: Flask, config_name: str):
    """Load configuration based on environment."""
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-in-production"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///smartkrishi.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)),
        WTF_CSRF_ENABLED=True,
        SESSION_COOKIE_SECURE=config_name == "production",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config_name == "development":
        app.config["DEBUG"] = True
        app.config["SQLALCHEMY_ECHO"] = False


def _init_services(app: Flask):
    """Initialize background services (watsonx, RAG)."""
    from app.services.watsonx_service import watsonx_service
    from app.rag.pipeline import vector_store

    watsonx_service.initialize()
    vector_store.initialize()

    app.logger.info("Services initialized: watsonx=%s, vector_store=%s",
                    watsonx_service.is_ready(), vector_store._initialized)


def _setup_logging(app: Flask):
    """Configure application logging."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_file = os.getenv("LOG_FILE", "logs/smartkrishi.log")

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    logging.getLogger("werkzeug").setLevel(logging.INFO)


def _register_error_handlers(app: Flask):
    """Register custom error handlers."""
    from flask import render_template, jsonify, request

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found", "status": 404}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error", "status": 500}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({
            "error": "Too many requests. Please wait before trying again.",
            "status": 429,
            "retry_after": 60
        }), 429

    @app.route("/health")
    def health_check():
        from app.services.watsonx_service import watsonx_service
        from app.rag.pipeline import vector_store
        return jsonify({
            "status": "healthy",
            "watsonx": watsonx_service.is_ready(),
            "vector_store": vector_store._initialized,
            "version": "1.0.0"
        })
