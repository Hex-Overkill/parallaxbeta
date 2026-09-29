"""LoP Gaming Hub - application factory & entry point."""
import os
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import current_user, logout_user

from config import Config
from extensions import csrf, db, login_manager
from helpers import register_jinja
from models import User, now_utc


def _ensure_dirs(app: Flask) -> None:
    for path in (
        app.config["INSTANCE_DIR"],
        app.config["GAME_LIBRARY_DIR"],
        app.config["GAME_ZIP_DIR"],
        app.config["SCREENSHOT_DIR"],
        app.config["THUMBNAIL_DIR"],
    ):
        path.mkdir(parents=True, exist_ok=True)


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    _ensure_dirs(app)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from blueprints.admin import admin_bp
    from blueprints.auth import auth_bp
    from blueprints.chat import chat_bp
    from blueprints.games import games_bp
    from blueprints.main import main_bp
    from blueprints.premium import premium_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(games_bp)
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(premium_bp, url_prefix="/premium")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    register_jinja(app)
    _register_handlers(app)
    _register_context(app)
    return app


# --------------------------------------------------------------------------- #
# login_manager user loader
# --------------------------------------------------------------------------- #
@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------- #
# Error pages, context, security headers
# --------------------------------------------------------------------------- #
def _register_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/413.html"), 413

    @app.errorhandler(Exception)
    def internal_error(e):
        app.logger.exception("Unhandled error")
        return render_template("errors/500.html"), 500


def _register_context(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        ctx = {
            "now_utc": now_utc,
            "premium_price": app.config["PREMIUM_PRICE_USD"],
            "premium_plan": app.config["PREMIUM_PLAN_NAME"],
            "paypal_receiver": app.config["PAYPAL_RECEIVER_EMAIL"],
            "trial_days": app.config["TRIAL_DURATION_DAYS"],
            "categories": app.config["GAME_CATEGORIES"],
            "max_game_size_mb": app.config["MAX_GAME_UNCOMPRESSED_SIZE"] // (1024 * 1024),
        }
        if current_user.is_authenticated:
            state, end = current_user.premium_status()
            ctx["premium_state"], ctx["premium_end"] = state, end
        return ctx

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # uploaded game files carry their own inline scripts -> no CSP there
        if not request.path.startswith("/game-files/"):
            resp.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; frame-src 'self'; media-src 'self' blob:; "
                "frame-ancestors 'self'; base-uri 'self'; form-action 'self'",
            )
        return resp

    @app.before_request
    def enforce_ban():
        from flask_login import current_user
        if current_user.is_authenticated and not current_user.is_admin:
            if current_user.ban_is_active:
                reason = current_user.ban_reason or "Account suspended by an administrator."
                logout_user()
                flash(f"Your account has been suspended. Reason: {reason}", "error")
                return redirect(url_for("auth.login"))


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="Run LoP Gaming Hub")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--debug", action="store_true", default=False)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)


if __name__ == "__main__":
    _cli()
