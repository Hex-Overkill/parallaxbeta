"""Public landing pages."""
from datetime import timedelta

from flask import Blueprint, render_template
from flask_login import current_user

from extensions import db
from helpers import active_players_count, fmt_duration
from models import ChatMessage, Game, GameSession, User, now_utc

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    featured = (
        Game.query.filter_by(is_active=True, is_featured=True)
        .order_by(Game.created_at.desc())
        .limit(6)
        .all()
    )
    if not featured:  # fall back to highest-traffic games
        featured = (
            Game.query.filter_by(is_active=True)
            .order_by(Game.total_playtime.desc())
            .limit(6)
            .all()
        )
    latest = (
        Game.query.filter_by(is_active=True)
        .order_by(Game.created_at.desc())
        .limit(8)
        .all()
    )

    games_total = Game.query.filter_by(is_active=True).count()
    users_total = User.query.filter_by(role="user").count()
    plays_total = db.session.query(db.func.sum(Game.play_count)).scalar() or 0
    time_total = db.session.query(db.func.sum(Game.total_playtime)).scalar() or 0

    recent_sessions = (
        db.session.query(GameSession, User.username, Game.title, Game.slug)
        .join(GameSession.user)
        .join(GameSession.game)
        .order_by(GameSession.started_at.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "index.html",
        featured=featured,
        latest=latest,
        stats={
            "games": games_total,
            "users": users_total,
            "plays": plays_total,
            "hours": fmt_duration(time_total),
            "online": active_players_count(10),
        },
        recent_sessions=recent_sessions,
    )
