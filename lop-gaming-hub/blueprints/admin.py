"""Admin panel: dashboard, user management, game management, payment review."""
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import current_user, login_required

from extensions import db
from helpers import (GameUploadError, delete_game, fmt_duration, ingest_game_zip,
                     slugify, unique_slug, user_game_stats)
from models import (ChatMessage, ChatRoom, Game, GameSession, PaymentRequest, User,
                    now_utc)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@admin_bp.route("")
@admin_required
def dashboard():
    users_total = User.query.filter_by(role="user").count()
    games_total = Game.query.count()
    active_games = Game.query.filter_by(is_active=True).count()
    plays_total = db.session.query(db.func.sum(Game.play_count)).scalar() or 0
    time_total = db.session.query(db.func.sum(Game.total_playtime)).scalar() or 0
    pending_payments = PaymentRequest.query.filter_by(status="pending").count()
    banned_users = User.query.filter_by(is_banned=True).count()
    free_plays_7d = (
        db.session.query(db.func.count(db.func.distinct(GameSession.user_id)))
        .filter(GameSession.started_at >= now_utc() - timedelta(days=7))
        .scalar()
        or 0
    )

    top_games = (
        Game.query.order_by(Game.total_playtime.desc()).limit(5).all()
    )
    top_users = (
        db.session.query(User, db.func.sum(GameSession.duration_seconds).label("t"))
        .join(GameSession, GameSession.user_id == User.id)
        .filter(GameSession.is_active.is_(False))
        .group_by(User.id)
        .order_by(db.text("t DESC"))
        .limit(5)
        .all()
    )
    latest_users = User.query.filter_by(role="user").order_by(User.created_at.desc()).limit(8).all()
    pending_list = (
        PaymentRequest.query.filter_by(status="pending")
        .order_by(PaymentRequest.created_at.asc())
        .limit(6)
        .all()
    )

    # activity per day, last 14 days
    daily = []
    for i in range(13, -1, -1):
        day = (now_utc() - timedelta(days=i)).date()
        start = datetime(day.year, day.month, day.day)
        end = start + timedelta(days=1)
        count = (
            db.session.query(db.func.count(db.func.distinct(GameSession.user_id)))
            .filter(GameSession.started_at >= start, GameSession.started_at < end)
            .scalar()
            or 0
        )
        daily.append({"label": day.strftime("%b %d"), "count": count})

    return render_template(
        "admin/dashboard.html",
        counters={
            "users": users_total,
            "games_total": games_total,
            "active_games": active_games,
            "plays": plays_total,
            "hours": fmt_duration(time_total),
            "pending": pending_payments,
            "banned": banned_users,
            "players_7d": free_plays_7d,
        },
        daily=daily,
        top_games=top_games,
        top_users=top_users,
        latest_users=latest_users,
        pending_list=pending_list,
    )


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@admin_bp.route("/users")
@admin_required
def users():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(User.username.ilike(like), User.email.ilike(like))
        )
    if status == "banned":
        query = query.filter(User.is_banned.is_(True))
    elif status == "premium":
        query = query.filter(User.premium_until > now_utc())
    elif status == "trial":
        query = query.filter(
            User.premium_until.is_(None),
            User.trial_started_at > now_utc() - timedelta(days=current_app.config["TRIAL_DURATION_DAYS"]),
        )
    query = query.order_by(User.created_at.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    rows = []
    for u in pagination.items:
        st, end = u.premium_status()
        rows.append(
            {
                "user": u,
                "premium_state": st,
                "premium_end": end,
                "playtime": u.total_playtime(),
                "sessions": u.sessions.count(),
            }
        )
    return render_template(
        "admin/users.html",
        rows=rows,
        pagination=pagination,
        q=q,
        status=status,
    )


@admin_bp.route("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    user = db.session.get(User, user_id) or abort(404)
    st, end = user.premium_status()
    activity = user_game_stats(user.id)
    recent_sessions = (
        user.sessions.order_by(GameSession.started_at.desc()).limit(15).all()
    )
    payments = (
        PaymentRequest.query.filter_by(user_id=user.id)
        .order_by(PaymentRequest.created_at.desc())
        .all()
    )
    chat_count = user.messages.count()
    return render_template(
        "admin/user_detail.html",
        u=user,
        premium_state=st,
        premium_end=end,
        activity=activity,
        recent_sessions=recent_sessions,
        payments=payments,
        chat_count=chat_count,
    )


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def user_ban(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.is_admin:
        flash("You cannot ban an administrator account.", "error")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    reason = (request.form.get("reason") or "").strip()
    days = request.form.get("days", "").strip()
    user.is_banned = True
    user.ban_reason = reason or "Violation of LoP Gaming Hub terms."
    user.banned_at = now_utc()
    user.banned_until = None
    if days:
        try:
            d = int(days)
            if 1 <= d <= 3650:
                user.banned_until = now_utc() + timedelta(days=d)
        except (TypeError, ValueError):
            pass
    # close any live play sessions so they stop counting time immediately
    GameSession.query.filter_by(user_id=user.id, is_active=True).update(
        {"is_active": False}, synchronize_session=False
    )
    db.session.commit()
    flash(f"User @{user.username} has been banned.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@admin_required
def user_unban(user_id):
    user = db.session.get(User, user_id) or abort(404)
    user.is_banned = False
    user.ban_reason = None
    user.banned_at = None
    user.banned_until = None
    db.session.commit()
    flash(f"User @{user.username} has been unbanned.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.route("/users/<int:user_id>/grant", methods=["POST"])
@admin_required
def user_grant(user_id):
    user = db.session.get(User, user_id) or abort(404)
    try:
        days = max(1, min(3650, int(request.form.get("days", 30))))
    except (TypeError, ValueError):
        days = 30
    base = max(now_utc(), user.premium_until or now_utc())
    user.premium_until = base + timedelta(days=days)
    db.session.commit()
    flash(
        f"Granted @{user.username} {days} extra days of {current_app.config['PREMIUM_PLAN_NAME']}.",
        "success",
    )
    return redirect(url_for("admin.user_detail", user_id=user.id))


# --------------------------------------------------------------------------- #
# Games
# --------------------------------------------------------------------------- #
@admin_bp.route("/games")
@admin_required
def games():
    games = Game.query.order_by(Game.created_at.desc()).all()
    return render_template("admin/games.html", games=games)


@admin_bp.route("/games/upload", methods=["GET", "POST"])
@admin_required
def game_upload():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        category = request.form.get("category") or "Arcade"
        version = (request.form.get("version") or "1.0").strip()
        zip_file = request.files.get("zip_file")
        thumb_file = request.files.get("thumbnail")

        if not title:
            flash("Title is required.", "error")
            return render_template("admin/game_upload.html")
        if not zip_file or not zip_file.filename:
            flash("Please choose the game ZIP file.", "error")
            return render_template("admin/game_upload.html")
        if zip_file.filename.rsplit(".", 1)[-1].lower() != "zip":
            flash("Game packages must be .zip files.", "error")
            return render_template("admin/game_upload.html")

        # stream upload to disk inside the protected uploads area
        zip_dir = current_app.config["GAME_ZIP_DIR"]
        zip_dir.mkdir(parents=True, exist_ok=True)
        tmp_zip = zip_dir / f"{slugify(title)}-{now_utc().strftime('%Y%m%d%H%M%S')}.zip"
        zip_file.save(tmp_zip)

        extra_thumb = None
        if thumb_file and thumb_file.filename:
            ext = thumb_file.filename.rsplit(".", 1)[-1].lower()
            if ext not in current_app.config["ALLOWED_THUMB_EXTENSIONS"]:
                flash("Thumbnail must be PNG, JPG, WebP or SVG.", "error")
                tmp_zip.unlink(missing_ok=True)
                return render_template("admin/game_upload.html")
            extra_thumb = Path(tmp_zip.parent) / f"extra-thumb-{now_utc().strftime('%H%M%S%f')}.{ext}"
            thumb_file.save(extra_thumb)

        try:
            game = ingest_game_zip(
                tmp_zip,
                {
                    "title": title,
                    "description": description,
                    "category": category,
                    "version": version,
                    "is_premium": bool(request.form.get("is_premium")),
                    "is_multiplayer": bool(request.form.get("is_multiplayer")),
                    "is_featured": bool(request.form.get("is_featured")),
                    "uploaded_by_id": current_user.id,
                },
                extra_thumb_path=extra_thumb,
            )
            flash(f"Game '{game.title}' uploaded and published to the library!", "success")
        except GameUploadError as exc:
            flash(f"Upload failed: {exc}", "error")
        finally:
            tmp_zip.unlink(missing_ok=True)
            if extra_thumb:
                extra_thumb.unlink(missing_ok=True)
        return redirect(url_for("admin.games"))

    return render_template("admin/game_upload.html")


@admin_bp.route("/games/<int:game_id>/toggle", methods=["POST"])
@admin_required
def game_toggle(game_id):
    game = db.session.get(Game, game_id) or abort(404)
    field = request.form.get("field")
    value = request.form.get("value") == "1"
    if field not in {"is_premium", "is_multiplayer", "is_active", "is_featured"}:
        return jsonify(ok=False, error="bad field"), 400
    setattr(game, field, value)
    if field == "is_multiplayer":
        if value and not game.chatroom:
            room = ChatRoom(
                name=f"{game.title} Chat",
                slug=unique_slug(slugify(f"{game.title}-chat")),
                game_id=game.id,
            )
            db.session.add(room)
        elif not value and game.chatroom:
            room = game.chatroom
            room.is_active = value
            # keep record but deactivate so chat history survives re-enable
    db.session.commit()
    return jsonify(ok=True, field=field, value=value)


@admin_bp.route("/games/<int:game_id>/delete", methods=["POST"])
@admin_required
def game_delete(game_id):
    game = db.session.get(Game, game_id) or abort(404)
    title = game.title
    delete_game(game)
    flash(f"Game '{title}' deleted along with all its files.", "success")
    return redirect(url_for("admin.games"))


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #
@admin_bp.route("/payments")
@admin_required
def payments():
    tab = request.args.get("tab") or "pending"
    statuses = {
        "pending": "pending",
        "approved": "approved",
        "rejected": "rejected",
        "all": None,
    }
    query = PaymentRequest.query
    st = statuses.get(tab)
    if st:
        query = query.filter_by(status=st)
    items = query.order_by(PaymentRequest.created_at.desc()).limit(300).all()
    counts = {
        s: PaymentRequest.query.filter_by(status=s).count()
        for s in ("pending", "approved", "rejected")
    }
    return render_template("admin/payments.html", items=items, tab=tab, counts=counts)


@admin_bp.route("/payments/<int:payment_id>/review", methods=["POST"])
@admin_required
def payment_review(payment_id):
    payment = db.session.get(PaymentRequest, payment_id) or abort(404)
    decision = request.form.get("decision")
    note = (request.form.get("note") or "").strip()[:300]

    if decision == "approve":
        user = payment.user
        base = max(now_utc(), user.premium_until or now_utc())
        user.premium_until = base + timedelta(days=current_app.config["PREMIUM_DURATION_DAYS"])
        payment.status = "approved"
        payment.admin_note = note or "Payment verified - thank you!"
        flash(
            f"Approved! @{user.username} now has {current_app.config['PREMIUM_PLAN_NAME']} "
            f"until {user.premium_until:%Y-%m-%d}.",
            "success",
        )
    elif decision == "reject":
        payment.status = "rejected"
        payment.admin_note = note or "Payment could not be verified."
        flash(
            f"Payment request #{payment.id} rejected. "
            f"@{payment.user.username} can resubmit with a valid screenshot.",
            "warning",
        )
    else:
        flash("Invalid decision.", "error")
        return redirect(url_for("admin.payments", tab="pending"))

    payment.reviewed_at = now_utc()
    payment.reviewed_by_id = current_user.id
    db.session.commit()
    return redirect(url_for("admin.payments", tab="pending"))


@admin_bp.route("/payments/<int:payment_id>/screenshot")
@admin_required
def payment_screenshot(payment_id):
    payment = db.session.get(PaymentRequest, payment_id) or abort(404)
    shot_dir = current_app.config["SCREENSHOT_DIR"]
    name = Path(payment.screenshot_path).name
    if not (shot_dir / name).exists():
        abort(404)
    resp = send_from_directory(shot_dir, name)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "private, no-store"
    return resp
