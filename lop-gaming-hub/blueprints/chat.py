"""Multiplayer chatrooms: hub, room pages and the polling JSON API."""
from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, jsonify,
                   render_template, request)
from flask_login import current_user, login_required

from extensions import db
from models import ChatMessage, ChatPresence, ChatRoom, now_utc

chat_bp = Blueprint("chat", __name__)

PRESENCE_TTL_SECONDS = 60      # considered "online"
PRESENCE_PRUNE_MINUTES = 10


def _prune_presences(room_id: int) -> None:
    cutoff = now_utc() - timedelta(minutes=PRESENCE_PRUNE_MINUTES)
    ChatPresence.query.filter(
        ChatPresence.room_id == room_id,
        ChatPresence.last_seen < cutoff,
    ).delete(synchronize_session=False)
    db.session.commit()


def _touch_presence(room_id: int) -> None:
    presence = ChatPresence.query.get((room_id, current_user.id))
    if presence is None:
        presence = ChatPresence(room_id=room_id, user_id=current_user.id)
        db.session.add(presence)
    presence.last_seen = now_utc()
    db.session.commit()


def _active_room_or_404(room_id: int) -> ChatRoom:
    room = db.session.get(ChatRoom, room_id)
    if room is None or not room.is_active:
        abort(404)
    return room


def _message_payload(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "user": msg.user.username if msg.user else "deleted",
        "content": msg.content,
        "ts": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
@chat_bp.route("")
@login_required
def hub():
    rooms = ChatRoom.query.filter_by(is_active=True).order_by(ChatRoom.created_at.asc()).all()
    cards = []
    for room in rooms:
        last = room.last_message()
        cards.append(
            {
                "room": room,
                "online": room.online_users(PRESENCE_TTL_SECONDS),
                "online_count": len(room.online_users(PRESENCE_TTL_SECONDS)),
                "message_count": room.messages.count(),
                "last": last,
                "game": room.game,
            }
        )
    return render_template("chat/hub.html", rooms=cards)


@chat_bp.route("/<int:room_id>")
@login_required
def room(room_id):
    room = _active_room_or_404(room_id)
    _touch_presence(room_id)
    messages = (
        room.messages.order_by(ChatMessage.id.asc()).limit(200).all()
    )
    return render_template(
        "chat/room.html",
        room=room,
        messages=messages,
        online=room.online_users(PRESENCE_TTL_SECONDS),
    )


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #
@chat_bp.route("/<int:room_id>/api/messages")
@login_required
def api_messages(room_id):
    room = _active_room_or_404(room_id)
    _prune_presences(room_id)
    _touch_presence(room_id)

    after = request.args.get("after", 0, type=int)
    query = room.messages.order_by(ChatMessage.id.asc())
    if after:
        query = query.filter(ChatMessage.id > after)
    messages = [ _message_payload(m) for m in query.limit(100).all() ]
    online = room.online_users(PRESENCE_TTL_SECONDS)
    return jsonify(
        messages=messages,
        online=online,
        online_count=len(online),
        server_time=now_utc().strftime("%Y-%m-%d %H:%M:%S"),
    )


@chat_bp.route("/<int:room_id>/api/send", methods=["POST"])
@login_required
def api_send(room_id):
    room = _active_room_or_404(room_id)
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    max_len = current_app.config["MESSAGE_MAX_LENGTH"]

    if not content:
        return jsonify(ok=False, error="Empty message."), 400
    if len(content) > max_len:
        return jsonify(ok=False, error=f"Message too long (max {max_len} chars)."), 400

    last = (
        ChatMessage.query.filter_by(user_id=current_user.id)
        .order_by(ChatMessage.id.desc())
        .first()
    )
    if last:
        limit = current_app.config["CHAT_RATE_LIMIT_SECONDS"]
        since = (now_utc() - last.created_at).total_seconds()
        if since < limit:
            return jsonify(ok=False, error="You are sending messages too fast."), 429

    msg = ChatMessage(
        room_id=room.id,
        user_id=current_user.id,
        content=content[:max_len],
    )
    db.session.add(msg)
    db.session.commit()
    _touch_presence(room_id)
    return jsonify(ok=True, message=_message_payload(msg))
