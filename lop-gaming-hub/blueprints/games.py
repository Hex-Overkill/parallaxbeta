"""Game library, play pages, secure game-file serving and play-time tracking."""
from functools import wraps
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import current_user, login_required

from extensions import csrf, db
from models import Game, GameSession, User, now_utc

games_bp = Blueprint("games", __name__)


def _same_origin():
    """Reject cross-site requests for the low-risk session API (CSRF-lite)."""
    origin = request.headers.get("Origin")
    if origin is None:
        return True  # same-origin fetches, beacons and curl
    return f"{request.scheme}://{request.host}" == origin


def _session_api_guard(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not _same_origin():
            return jsonify(ok=False, error="bad origin"), 403
        return fn(*args, **kwargs)
    return wrapper


def _active_game_or_404(slug: str) -> Game:
    game = Game.query.filter_by(slug=slug).first_or_404()
    if not game.is_active:
        abort(404)
    return game


# --------------------------------------------------------------------------- #
# Library
# --------------------------------------------------------------------------- #
@games_bp.route("/games")
@login_required
def library():
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    sort = request.args.get("sort") or "popular"
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 12

    query = Game.query.filter_by(is_active=True)
    if q:
        query = query.filter(Game.title.ilike(f"%{q}%"))
    if category:
        query = query.filter_by(category=category)

    if sort == "newest":
        query = query.order_by(Game.created_at.desc())
    elif sort == "plays":
        query = query.order_by(Game.play_count.desc())
    else:  # popular = most playtime
        query = query.order_by(Game.total_playtime.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template(
        "games/library.html",
        games=pagination.items,
        pagination=pagination,
        q=q,
        category=category,
        sort=sort,
    )


# --------------------------------------------------------------------------- #
# Detail / play / files
# --------------------------------------------------------------------------- #
@games_bp.route("/games/<slug>")
@login_required
def detail(slug):
    game = _active_game_or_404(slug)
    locked = game.is_premium and not current_user.can_access_premium()

    top_players = (
        db.session.query(User.username, db.func.sum(GameSession.duration_seconds).label("t"))
        .join(GameSession, GameSession.user_id == User.id)
        .filter(GameSession.game_id == game.id, GameSession.is_active.is_(False))
        .group_by(User.id)
        .order_by(db.text("t DESC"))
        .limit(5)
        .all()
    )
    return render_template(
        "games/detail.html",
        game=game,
        locked=locked,
        top_players=top_players,
        my_stats=next(
            (s for s in _my_stats(game.id) if s["game_id"] == game.id), None
        ),
    )


def _my_stats(game_id: int) -> list:
    from helpers import user_game_stats
    return user_game_stats(current_user.id)


@games_bp.route("/games/<slug>/play")
@login_required
def play(slug):
    game = _active_game_or_404(slug)
    if game.is_premium and not current_user.can_access_premium():
        flash(
            f"{game.title} is a Premium game. Start a 1-month trial or activate "
            "LoP Premium to play.",
            "warning",
        )
        return redirect(url_for("premium.index"))
    return render_template("games/play.html", game=game)


@games_bp.route("/game-files/<slug>/<path:filename>")
@login_required
def files(slug, filename):
    game = Game.query.filter_by(slug=slug).first_or_404()
    if not game.is_active:
        abort(404)
    # Premium games are never served without an active premium (or trial / admin).
    if game.is_premium and not current_user.can_access_premium():
        abort(403)
    game_dir = current_app.config["GAME_LIBRARY_DIR"] / (game.folder or slug)
    requested = (game_dir / filename).resolve()
    if not str(requested).startswith(str(game_dir.resolve())):
        abort(404)
    if not requested.exists():
        abort(404)
    resp = send_from_directory(game_dir, filename)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@games_bp.route("/game-thumb/<path:name>")
def thumb(name):
    name = Path(name).name  # strip any path components
    thumb_dir = current_app.config["THUMBNAIL_DIR"]
    if not (thumb_dir / name).exists():
        abort(404)
    resp = send_from_directory(thumb_dir, name)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# --------------------------------------------------------------------------- #
# Play-time tracking API (deliberately CSRF-exempt, guarded by Origin check +
# server-side session ids; see README security notes)
# --------------------------------------------------------------------------- #
@games_bp.route("/api/games/<slug>/session/start", methods=["POST"])
@csrf.exempt
@_session_api_guard
def session_start(slug):
    game = _active_game_or_404(slug)
    if game.is_premium and not current_user.can_access_premium():
        return jsonify(ok=False, error="premium required"), 403

    grace = current_app.config["SESSION_END_GRACE_SECONDS"]
    existing = (
        GameSession.query.filter_by(
            user_id=current_user.id, game_id=game.id, is_active=True
        )
        .order_by(GameSession.started_at.desc())
        .first()
    )
    if existing and (now_utc() - existing.started_at).total_seconds() < grace:
        return jsonify(ok=True, session_id=existing.id, reused=True)

    session = GameSession(
        user_id=current_user.id,
        game_id=game.id,
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    db.session.add(session)
    db.session.commit()
    return jsonify(ok=True, session_id=session.id, reused=False)


@games_bp.route("/api/games/<slug>/session/heartbeat", methods=["POST"])
@csrf.exempt
@_session_api_guard
def session_heartbeat(slug):
    session_id = request.form.get("session_id") or request.get_json(silent=True) or {}
    if isinstance(session_id, dict):
        session_id = session_id.get("session_id")
    session = GameSession.query.filter_by(id=int(session_id or 0)).first()
    if not session or session.user_id != current_user.id:
        return jsonify(ok=False, error="unknown session"), 404
    if (now_utc() - session.started_at).total_seconds() > current_app.config["SESSION_MAX_SECONDS"]:
        session.is_active = False
        db.session.commit()
        return jsonify(ok=False, ended=True), 200
    return jsonify(ok=True)


@games_bp.route("/api/games/<slug>/session/end", methods=["POST"])
@csrf.exempt
@_session_api_guard
def session_end(slug):
    session_id = request.form.get("session_id") or ""
    session = GameSession.query.filter_by(id=int(session_id or 0)).first()
    if not session or session.user_id != current_user.id:
        return jsonify(ok=False, error="unknown session"), 404
    if not session.is_active:
        return jsonify(ok=True, duration=session.duration_seconds, already=True)

    elapsed = int((now_utc() - session.started_at).total_seconds())
    elapsed = min(elapsed, current_app.config["SESSION_MAX_SECONDS"])
    session.is_active = False
    session.duration_seconds = max(0, elapsed)
    game = session.game
    if elapsed >= 5:  # don't count accidental open/close
        game.play_count += 1
        game.total_playtime += elapsed
    db.session.commit()
    return jsonify(ok=True, duration=session.duration_seconds)
