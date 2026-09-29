"""LoP Premium: yearly token purchase via PayPal with admin screenshot verification."""
from datetime import timedelta
from pathlib import Path

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from extensions import db
from models import PaymentRequest, now_utc

premium_bp = Blueprint("premium", __name__)


def _save_screenshot(file_storage) -> str:
    """Persist a payment proof screenshot, return path relative to SCREENSHOT_DIR."""
    cfg = current_app.config
    if file_storage is None or not file_storage.filename:
        raise ValueError("Screenshot is required.")
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in cfg["ALLOWED_PROOF_EXTENSIONS"]:
        raise ValueError("Screenshot must be PNG, JPG, GIF or WebP.")
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > cfg["MAX_PROOF_SIZE_MB"] * 1024 * 1024:
        raise ValueError(f"Screenshot exceeds {cfg['MAX_PROOF_SIZE_MB']} MB.")

    cfg["SCREENSHOT_DIR"].mkdir(parents=True, exist_ok=True)
    stamp = now_utc().strftime("%Y%m%d%H%M%S")
    name = f"user{current_user.id}_{stamp}.{ext}"
    file_storage.save(cfg["SCREENSHOT_DIR"] / name)
    return name


@premium_bp.route("")
@login_required
def index():
    state, end = current_user.premium_status()
    submissions = (
        PaymentRequest.query.filter_by(user_id=current_user.id)
        .order_by(PaymentRequest.created_at.desc())
        .all()
    )
    return render_template(
        "premium.html",
        state=state,
        premium_end=end,
        submissions=submissions,
        days_left=(
            max(1, (end - now_utc()).days) if end else 0
        ),
    )


@premium_bp.route("/request", methods=["POST"])
@login_required
def request_purchase():
    cfg = current_app.config
    paypal_email = (request.form.get("paypal_email") or "").strip()
    transaction_id = (request.form.get("transaction_id") or "").strip()
    screenshot = request.files.get("screenshot")

    try:
        filename = _save_screenshot(screenshot)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("premium.index"))

    if not paypal_email or "@" not in paypal_email:
        flash("Please provide the PayPal email you paid from.", "error")
        return redirect(url_for("premium.index"))
    if not transaction_id:
        flash("Please provide the PayPal transaction ID (looks like 0PA12345ABC678901).", "error")
        return redirect(url_for("premium.index"))

    existing_pending = PaymentRequest.query.filter_by(
        user_id=current_user.id, status="pending"
    ).first()
    if existing_pending:
        flash("You already have a purchase awaiting verification.", "warning")
        return redirect(url_for("premium.index"))

    submission = PaymentRequest(
        user_id=current_user.id,
        amount=cfg["PREMIUM_PRICE_USD"],
        paypal_email=paypal_email,
        transaction_id=transaction_id,
        screenshot_path=filename,
        status="pending",
    )
    db.session.add(submission)
    db.session.commit()
    flash(
        "Purchase submitted! Our team verifies PayPal payments within 24 hours. "
        "Your yearly LoP Premium token activates as soon as it is approved.",
        "success",
    )
    return redirect(url_for("premium.index"))
