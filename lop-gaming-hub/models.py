"""LoP Gaming Hub - database models."""
from datetime import datetime, timedelta, timezone

from flask import current_app
from flask_login import UserMixin

from extensions import db


def now_utc():
    """Naive UTC timestamp used consistently across the app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # user | admin

    is_banned = db.Column(db.Boolean, nullable=False, default=False)
    ban_reason = db.Column(db.String(250))
    banned_at = db.Column(db.DateTime)
    banned_until = db.Column(db.DateTime)

    trial_started_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    premium_until = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    last_seen_at = db.Column(db.DateTime)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime)

    sessions = db.relationship("GameSession", back_populates="user", lazy="dynamic")
    messages = db.relationship("ChatMessage", back_populates="user", lazy="dynamic")
    payments = db.relationship("PaymentRequest", back_populates="user", lazy="dynamic",
                               foreign_keys="PaymentRequest.user_id")

    # ------------------------------------------------------------------ auth
    def set_password(self, raw: str) -> None:
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, raw)

    # ------------------------------------------------------------ properties
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def has_premium(self) -> bool:
        return self.premium_until is not None and self.premium_until > now_utc()

    @property
    def is_locked_out(self) -> bool:
        return self.locked_until is not None and self.locked_until > now_utc()

    @property
    def ban_is_active(self) -> bool:
        if not self.is_banned:
            return False
        if self.banned_until is None:          # permanent ban
            return True
        return self.banned_until > now_utc()

    def premium_status(self):
        """Return (state, end_datetime_or_None): admin | active | trial | expired | none."""
        if self.is_admin:
            return ("admin", None)
        if self.has_premium:
            return ("active", self.premium_until)
        trial_days = current_app.config["TRIAL_DURATION_DAYS"]
        if self.trial_started_at:
            trial_end = self.trial_started_at + timedelta(days=trial_days)
            if now_utc() < trial_end:
                return ("trial", trial_end)
            if self.premium_until is not None:
                return ("expired", self.premium_until)
            return ("expired", trial_end)
        return ("none", None)

    def can_access_premium(self) -> bool:
        return self.premium_status()[0] in ("admin", "active", "trial")

    def total_playtime(self) -> int:
        total = db.session.query(
            db.func.coalesce(db.func.sum(GameSession.duration_seconds), 0)
        ).filter(GameSession.user_id == self.id).scalar()
        return int(total or 0)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(60), nullable=False, default="Arcade")
    version = db.Column(db.String(30), nullable=False, default="1.0")

    folder = db.Column(db.String(160))            # relative to GAME_LIBRARY_DIR
    entry_file = db.Column(db.String(180), nullable=False, default="index.html")
    thumbnail = db.Column(db.String(220))         # public URL or path under /game-thumb/

    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    is_multiplayer = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_featured = db.Column(db.Boolean, nullable=False, default=False)

    play_count = db.Column(db.Integer, nullable=False, default=0)
    total_playtime = db.Column(db.Integer, nullable=False, default=0)  # seconds

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)
    updated_at = db.Column(db.DateTime, nullable=False, default=now_utc, onupdate=now_utc)

    chatroom = db.relationship("ChatRoom", back_populates="game", uselist=False)
    sessions = db.relationship("GameSession", back_populates="game", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Game {self.title}>"


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(90), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc)

    game = db.relationship("Game", back_populates="chatroom")
    messages = db.relationship("ChatMessage", back_populates="room", lazy="dynamic")
    presences = db.relationship("ChatPresence", back_populates="room", lazy="dynamic")

    def online_users(self, within_seconds: int = 60) -> list:
        from models import ChatPresence
        cutoff = now_utc() - timedelta(seconds=within_seconds)
        rows = ChatPresence.query.filter(
            ChatPresence.room_id == self.id,
            ChatPresence.last_seen >= cutoff,
        ).all()
        return [p.user.username for p in rows]

    def last_message(self):
        return self.messages.order_by(ChatMessage.id.desc()).first()

    def __repr__(self):
        return f"<ChatRoom {self.name}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc, index=True)

    room = db.relationship("ChatRoom", back_populates="messages")
    user = db.relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage {self.id}>"


class ChatPresence(db.Model):
    """Tracks who is currently online inside a chatroom (heartbeat table)."""
    __tablename__ = "chat_presence"

    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    last_seen = db.Column(db.DateTime, nullable=False, default=now_utc)

    room = db.relationship("ChatRoom", back_populates="presences")
    user = db.relationship("User")

    def __repr__(self):
        return f"<ChatPresence room={self.room_id} user={self.user_id}>"


class GameSession(db.Model):
    """One play session of a user in a game (drives activity + time tracking)."""
    __tablename__ = "game_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=now_utc, index=True)
    duration_seconds = db.Column(db.Integer, nullable=False, default=0)
    ip_address = db.Column(db.String(64))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user = db.relationship("User", back_populates="sessions")
    game = db.relationship("Game", back_populates="sessions")

    def __repr__(self):
        return f"<GameSession {self.id} game={self.game_id} user={self.user_id}>"


class PaymentRequest(db.Model):
    """LoP Premium token purchase awaiting admin verification (PayPal screenshot)."""
    __tablename__ = "payment_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False, default=10.0)
    paypal_email = db.Column(db.String(200), nullable=False)
    transaction_id = db.Column(db.String(120), nullable=False)
    screenshot_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    admin_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, nullable=False, default=now_utc, index=True)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    user = db.relationship("User", back_populates="payments", foreign_keys=[user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<PaymentRequest {self.id} {self.status}>"
