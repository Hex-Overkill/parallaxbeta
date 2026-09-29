from pathlib import Path
import shutil

from app import create_app
from extensions import db
from models import Game

app = create_app()

PREFERRED_NAMES = (
    "thumbnail",
    "cover",
    "preview",
    "screenshot",
    "game",
)

EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

with app.app_context():
    game_dir_root = Path(app.config["GAME_LIBRARY_DIR"])
    thumbnail_dir = Path(app.config["THUMBNAIL_DIR"])
    thumbnail_dir.mkdir(parents=True, exist_ok=True)

    games = Game.query.all()

    for game in games:
        game_dir = game_dir_root / (game.folder or game.slug)

        if not game_dir.exists():
            print(f"[SKIP] {game.title}: folder not found")
            continue

        candidates = []

        for path in game_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
                continue

            stem = path.stem.lower()
            if stem in PREFERRED_NAMES:
                candidates.append(
                    (PREFERRED_NAMES.index(stem), len(path.parts), path)
                )

        if not candidates:
            print(f"[SKIP] {game.title}: no thumbnail image found")
            continue

        _, _, source = min(candidates, key=lambda x: (x[0], x[1]))

        ext = source.suffix.lower()
        destination = thumbnail_dir / f"{game.slug}{ext}"

        shutil.copy2(source, destination)

        game.thumbnail = f"game-thumb/{game.slug}{ext}"

        print(f"[OK] {game.title} -> {game.thumbnail}")

    db.session.commit()

print("\nDone. Restart Flask and refresh the Game Library.")