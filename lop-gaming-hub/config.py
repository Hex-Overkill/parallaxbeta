"""LoP Gaming Hub - application configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # ---------------------------------------------------------------- core
    SECRET_KEY = os.environ.get("SECRET_KEY", "lop-gaming-hub-change-this-secret-2026")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'instance' / 'lopgaming.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------- session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # 7 days

    # ------------------------------------------------------------- storage
    PROJECT_ROOT = BASE_DIR
    INSTANCE_DIR = BASE_DIR / "instance"
    UPLOAD_DIR = BASE_DIR / "uploads"
    GAME_LIBRARY_DIR = UPLOAD_DIR / "games"
    GAME_ZIP_DIR = UPLOAD_DIR / "game_zips"
    SCREENSHOT_DIR = UPLOAD_DIR / "payments"
    THUMBNAIL_DIR = UPLOAD_DIR / "thumbnails"

    MAX_CONTENT_LENGTH = 220 * 1024 * 1024  # max HTTP request body (uploads)

    # -------------------------------------------------------------- uploads
    ALLOWED_ZIP_EXTENSIONS = {"zip"}
    ALLOWED_THUMB_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "svg"}
    ALLOWED_PROOF_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_GAME_FILE_EXTENSIONS = {
        "html", "htm", "js", "mjs", "css", "json", "xml", "txt", "md",
        "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp",
        "mp3", "wav", "ogg", "m4a", "mp4", "webm", "ogg",
        "ttf", "otf", "woff", "woff2", "eot",
        "wasm", "map", "glb", "gltf", "fbx", "obj", "mtl", "dae",
    }
    MAX_GAME_UNCOMPRESSED_SIZE = 350 * 1024 * 1024  # zip bomb guard
    MAX_GAME_FILES = 6000                            # zip bomb guard
    MAX_PROOF_SIZE_MB = 10
    MAX_THUMB_SIZE_MB = 10

    # ------------------------------------------------------------ categories
    GAME_CATEGORIES = [
        "Arcade", "Action", "Puzzle", "Strategy",
        "Multiplayer", "Sports", "Racing", "RPG", "Other",
    ]

    # --------------------------------------------------------- premium plan
    PREMIUM_PRICE_USD = 10
    PREMIUM_PLAN_NAME = "LoP Premium"
    PREMIUM_DURATION_DAYS = 365          # yearly token
    TRIAL_DURATION_DAYS = 30             # one month free trial
    PAYPAL_RECEIVER_EMAIL = os.environ.get(
        "PAYPAL_RECEIVER_EMAIL", "payments@lopgaming.example.com"
    )

    # -------------------------------------------------------------- security
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    CHAT_RATE_LIMIT_SECONDS = 1.5
    MESSAGE_MAX_LENGTH = 500
    SESSION_END_GRACE_SECONDS = 300  # reuse an active play-session within 5 min
    SESSION_MAX_SECONDS = 8 * 3600   # hard cap per play session
