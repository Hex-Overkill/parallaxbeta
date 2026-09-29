"""Shared helpers: slugs, safe zip ingestion for uploaded web games, stats."""
from __future__ import annotations

import re
import shutil
import unicodedata
import zipfile
from datetime import timedelta
from pathlib import Path

from flask import current_app

from extensions import db
from models import ChatRoom, Game, GameSession, User, now_utc

# --------------------------------------------------------------------------- #
# Slug / text
# --------------------------------------------------------------------------- #
def slugify(value: str, max_len: int = 60) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    value = re.sub(r"-{2,}", "-", value)
    return value[:max_len].rstrip("-") or "game"


def unique_slug(base: str) -> str:
    """Return base or base-2, base-3 ... that is not already used as a game slug."""
    slug = base
    n = 2
    while Game.query.filter_by(slug=slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


def fmt_duration(seconds: int) -> str:
    """28852 -> '8h 0m'."""
    seconds = int(seconds or 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def time_ago(dt) -> str:
    if dt is None:
        return "never"
    delta = now_utc() - dt
    s = int(delta.total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{s // 60}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    if s < 86400 * 30:
        return f"{s // 86400}d ago"
    return dt.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# Zip ingestion for uploaded web games (admin upload + seeding share this path)
# --------------------------------------------------------------------------- #
class GameUploadError(Exception):
    pass


def _allowed_game_file(rel_path: str) -> bool:
    ext = rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
    return ext in current_app.config["ALLOWED_GAME_FILE_EXTENSIONS"]


def validate_and_extract(zip_path: Path, dest_dir: Path) -> str:
    """Safely extract a web-game zip. Returns the relative entry file (e.g. index.html)."""
    cfg = current_app.config
    if not zip_path.exists():
        raise GameUploadError("Uploaded zip file is missing on disk.")

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise GameUploadError("The uploaded file is not a valid ZIP archive.") from None

    infos = zf.infolist()
    if not infos:
        zf.close()
        raise GameUploadError("The ZIP archive is empty.")

    if len(infos) > cfg["MAX_GAME_FILES"]:
        zf.close()
        raise GameUploadError("ZIP contains too many files (zip-bomb guard).")

    total_uncompressed = sum(i.file_size for i in infos)
    if total_uncompressed > cfg["MAX_GAME_UNCOMPRESSED_SIZE"]:
        zf.close()
        raise GameUploadError("ZIP uncompressed size exceeds the safety limit.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()

    html_candidates: list[tuple[str, Path]] = []
    for info in infos:
        raw = info.filename.replace("\\", "/")
        if raw.endswith("/") or raw == "":
            continue  # directory entry
        parts = [p for p in raw.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts) or raw.startswith("/"):
            zf.close()
            raise GameUploadError(f"Unsafe path inside zip: {raw!r}")
        target = (dest_dir.joinpath(*parts)).resolve()
        if not str(target).startswith(str(dest_root)):
            zf.close()
            raise GameUploadError(f"Unsafe target path: {raw!r}")
        if not _allowed_game_file(raw):
            zf.close()
            raise GameUploadError(
                f"File type not allowed for games: {raw.rsplit('.', 1)[-1].lower()!r}"
            )
        if raw.split("/")[-1].lower().endswith((".html", ".htm")):
            html_candidates.append((raw, target))

    if not html_candidates:
        zf.close()
        raise GameUploadError("No .html entry point found inside the ZIP (need index.html).")

    # extract member-by-member with size guard already validated above
    for info in infos:
        if info.is_dir() or info.filename == "":
            continue
        raw = info.filename.replace("\\", "/")
        parts = [p for p in raw.split("/") if p not in ("", ".")]
        target = dest_dir.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
    zf.close()

    # prefer a root-level index.html, else the first html found
    root_index = next((p for p in html_candidates if p[0].lower() == "index.html"), None)
    if root_index:
        return root_index[0]
    entry = min(html_candidates, key=lambda p: (len(p[0].split("/")), p[0]))
    return entry[0]


def _extract_zip_thumbnail(zip_path: Path, slug: str) -> str | None:
    """Find a suitable thumbnail image in the ZIP and save it."""
    thumb_dir = current_app.config["THUMBNAIL_DIR"]
    thumb_dir.mkdir(parents=True, exist_ok=True)

    preferred = ("thumbnail", "cover", "preview", "screenshot", "game")
    extensions = ("png", "jpg", "jpeg", "webp")

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        return None

    candidates = []
    for info in zf.infolist():
        raw = info.filename.replace("\\", "/")
        name = raw.rsplit("/", 1)[-1].lower()
        stem = name.rsplit(".", 1)[0] if "." in name else ""
        ext = name.rsplit(".", 1)[-1] if "." in name else ""

        if stem in preferred and ext in extensions:
            candidates.append((preferred.index(stem), len(raw.split("/")), info))

    if not candidates:
        zf.close()
        return None

    _, _, info = min(candidates, key=lambda x: (x[0], x[1]))
    ext = info.filename.rsplit(".", 1)[-1].lower()
    out = thumb_dir / f"{slug}.{ext}"

    with zf.open(info) as src, open(out, "wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)

    zf.close()
    return f"game-thumb/{slug}.{ext}"


def ingest_game_zip(zip_path: Path, meta: dict, extra_thumb_path: Path | None = None) -> Game:
    """Run the full admin upload pipeline. meta keys:
    title, description, category, version, is_premium, is_multiplayer,
    is_featured, uploaded_by_id (all booleans already pythonized).
    """
    cfg = current_app.config
    slug = unique_slug(slugify(meta["title"]))

    dest_dir = cfg["GAME_LIBRARY_DIR"] / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        entry = validate_and_extract(zip_path, dest_dir)
    except GameUploadError:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise

    thumbnail = _extract_zip_thumbnail(zip_path, slug)
    if thumbnail and extra_thumb_path:
        # explicit upload wins over in-zip thumbnail
        thumb_ext = extra_thumb_path.suffix.lower()
        target = cfg["THUMBNAIL_DIR"] / f"{slug}-uploaded{thumb_ext}"
        shutil.copyfile(extra_thumb_path, target)
        thumbnail = f"game-thumb/{slug}-uploaded{thumb_ext}"

    game = Game(
        title=meta["title"].strip(),
        slug=slug,
        description=(meta.get("description") or "").strip(),
        category=meta.get("category") or "Arcade",
        version=meta.get("version") or "1.0",
        folder=slug,
        entry_file=entry,
        thumbnail=thumbnail,
        is_premium=bool(meta.get("is_premium")),
        is_multiplayer=bool(meta.get("is_multiplayer")),
        is_featured=bool(meta.get("is_featured")),
        is_active=True,
        uploaded_by_id=meta.get("uploaded_by_id"),
    )
    db.session.add(game)
    db.session.flush()

    if game.is_multiplayer and not game.chatroom:
        room = ChatRoom(
            name=f"{game.title} Chat",
            slug=unique_slug(slugify(f"{game.title}-chat")),
            game_id=game.id,
        )
        db.session.add(room)
    db.session.commit()
    return game


def delete_game(game: Game) -> None:
    """Remove a game, its sessions, and its files on disk."""
    cfg = current_app.config

    folder = cfg["GAME_LIBRARY_DIR"] / game.folder if game.folder else None
    thumbnail_path = None

    if game.thumbnail and game.thumbnail.startswith("game-thumb/"):
        thumbnail_path = cfg["THUMBNAIL_DIR"] / Path(game.thumbnail).name

    try:
        # GameSession.game_id is NOT NULL, so sessions must be
        # deleted before deleting the parent Game.
        db.session.query(GameSession).filter(
            GameSession.game_id == game.id
        ).delete(synchronize_session=False)

        # Remove any chatroom belonging to this game as well.
        db.session.query(ChatRoom).filter(
            ChatRoom.game_id == game.id
        ).delete(synchronize_session=False)

        db.session.delete(game)
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    # Only remove files after the database transaction succeeds.
    if thumbnail_path:
        thumbnail_path.unlink(missing_ok=True)

    if folder:
        shutil.rmtree(folder, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Stats helpers
# --------------------------------------------------------------------------- #
def user_game_stats(user_id: int) -> list[dict]:
    rows = (
        db.session.query(
            Game.id,
            Game.title,
            Game.slug,
            Game.is_premium,
            db.func.count(GameSession.id).label("plays"),
            db.func.coalesce(db.func.sum(GameSession.duration_seconds), 0).label("seconds"),
            db.func.max(GameSession.started_at).label("last_played"),
        )
        .join(GameSession, GameSession.game_id == Game.id)
        .filter(GameSession.user_id == user_id)
        .group_by(Game.id)
        .order_by(db.text("seconds DESC"))
        .all()
    )
    return [
        {
            "game_id": r.id,
            "title": r.title,
            "slug": r.slug,
            "is_premium": r.is_premium,
            "plays": int(r.plays),
            "seconds": int(r.seconds),
            "last_played": r.last_played,
        }
        for r in rows
    ]


def recompute_game_stats() -> None:
    """Re-aggregate play_count / total_playtime for every game from finished sessions."""
    for game in Game.query.all():
        row = (
            db.session.query(
                db.func.count(GameSession.id),
                db.func.coalesce(db.func.sum(GameSession.duration_seconds), 0),
            )
            .filter(GameSession.game_id == game.id, GameSession.is_active.is_(False))
            .one()
        )
        game.play_count = int(row[0])
        game.total_playtime = int(row[1])
    db.session.commit()


def active_players_count(minutes: int = 5) -> int:
    cutoff = now_utc() - timedelta(minutes=minutes)
    return (
        db.session.query(db.func.count(db.func.distinct(GameSession.user_id)))
        .filter(GameSession.started_at >= cutoff, GameSession.is_active.is_(True))
        .scalar()
        or 0
    )


def register_jinja(app) -> None:
    app.jinja_env.filters["fmt_duration"] = fmt_duration
    app.jinja_env.filters["time_ago"] = time_ago
