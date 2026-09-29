"""Authentication: register, login, logout, profile."""
import re
from datetime import timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required, login_user, logout_user

from extensions import db
from helpers import user_game_stats
from models import PaymentRequest, User, now_utc

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,24}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        errors = []
        if not USERNAME_RE.match(username):
            errors.append("Username must be 3-24 characters (letters, numbers, underscores).")
        if not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.isalpha() for c in password):
            errors.append("Password must be at least 8 characters with letters and numbers.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if User.query.filter_by(username=username).first():
            errors.append("That username is already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("auth/register.html", form=request.form)

        user = User(
            username=username,
            email=email,
            role="user",
            trial_started_at=now_utc(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(
            f"Welcome to the LoP Gaming Hub, {username}! "
            f"Your {current_app.config['TRIAL_DURATION_DAYS']}-day Premium trial has started.",
            "success",
        )
        return redirect(url_for("games.library"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.is_locked_out:
            mins = max(1, int((user.locked_until - now_utc()).total_seconds() // 60))
            flash(f"Too many failed attempts. Account locked. Try again in ~{mins} minutes.", "error")
            return render_template("auth/login.html")

        if user and user.check_password(password):
            if user.ban_is_active:
                flash(
                    f"Your account has been suspended. Reason: {user.ban_reason or 'violation of terms'}",
                    "error",
                )
                return render_template("auth/login.html")
            user.failed_attempts = 0
            user.locked_until = None
            user.last_seen_at = now_utc()
            db.session.commit()
            login_user(user, remember=bool(request.form.get("remember")))
            nxt = request.args.get("next") or url_for("games.library")
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(nxt)

        if user:
            user.failed_attempts = (user.failed_attempts or 0) + 1
            max_a = current_app.config["LOGIN_MAX_ATTEMPTS"]
            if user.failed_attempts >= max_a:
                user.locked_until = now_utc() + timedelta(
                    minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"]
                )
                flash(
                    f"Too many failed attempts. Account locked for "
                    f"{current_app.config['LOGIN_LOCKOUT_MINUTES']} minutes.",
                    "error",
                )
            db.session.commit()
        flash("Invalid username/email or password.", "error")
        return render_template("auth/login.html")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/profile")
@login_required
def profile():
    stats = user_game_stats(current_user.id)
    total_seconds = sum(s["seconds"] for s in stats)
    total_plays = sum(s["plays"] for s in stats)
    payments = PaymentRequest.query.filter_by(user_id=current_user.id).order_by(
        PaymentRequest.created_at.desc()
    ).all()
    return render_template(
        "user/profile.html",
        stats=stats,
        total_seconds=total_seconds,
        total_plays=total_plays,
        payments=payments,
    )
