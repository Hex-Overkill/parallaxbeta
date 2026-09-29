# LoP Gaming Hub 🎮

A professional Flask web app for hosting **your own web games**. Users sign up,
play in their browser, hang out in multiplayer chatrooms, and you run the whole
operation from a full admin panel — including **your game uploads**, playtime
analytics and the **LoP Premium token system** (yearly, $10, paid via PayPal
with screenshot verification).

---

## ✨ Features

| Area | What you get |
|---|---|
| 🎮 **Game library** | Grid storefront with search, categories and sorting; every game plays in a sandboxed iframe |
| 📦 **Admin uploads** | ZIP your game folder → upload → it just works. Auto entry-file detection (`index.html`), thumbnail extraction, safe extraction (zip-bomb / path-traversal guards) |
| 👥 **Users** | Signup/login, profiles, per-game playtime stats, account lockout after 5 failed logins |
| 🕹️ **Playtime tracking** | Server-side sessions — start / heartbeat / end (sendBeacon) → play counts and "time spent per game" per user |
| 💬 **Multiplayer chatrooms** | Global Lobby + one auto-created room per multiplayer game; presence (who's online), rate limiting |
| ⭐ **LoP Premium** | 30-day free trial → then Premium games lock. Yearly token is **$10**, paid to your PayPal; user uploads a payment screenshot with transaction ID → **you approve** in the admin panel → access granted for 365 days |
| 🚫 **Ban system** | Ban permanently or for N days with a reason; banned users are logged out and kept out mid-game |
| 🛡️ **Admin panel** | Dashboard (activity chart, top games/players), user management, game flags (premium/multiplayer/featured/live) toggles, payment review queue |

---

## 🚀 Quick start (Windows)

```bat
run.bat
```

That creates a virtualenv, installs dependencies, seeds the database with
six sample games + demo accounts, and starts the server at
**http://127.0.0.1:5000**.

Manual steps if you prefer:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed.py
python app.py
```

---

## 🔑 Seeded demo accounts

| Account | Password | Role |
|---|---|---|
| `admin` | `LoP-admin-2026!` | Admin panel access |
| `gamer1` / `gamer2` / `gamer3` | `gamer1pass123` / `gamer2pass123` / `gamer3pass123` | Regular users, trial active |
| `expired_demo` | `expired12345` | Regular user, **trial expired** (use to see Premium gating) |

Seeded games: **Snake**, **Neon Pong 2P** (multiplayer), **Memory Match**,
**Reflex Rush** (premium), **Space Dodger** (premium + multiplayer),
**TicTacToe Arena** (multiplayer).

---

## 🕹️ How uploading games works

1. Put your web game in one folder; the main page must be **`index.html`**.
2. Optional: add a `thumbnail.png` / `.jpg` / `.webp` at the root — it becomes the cover art.
3. Zip the folder: *right-click → Send to → Compressed (zipped) folder*.
4. Admin panel → **Games → Upload game** → pick the ZIP → publish.

Rules the upload pipeline enforces:

- Only `.html/.htm/.js/.css/.png/.jpg/.webp/.svg/.mp3/...` files are allowed (full whitelist in `config.py`).
- Path traversal inside the ZIP is rejected; extraction is confined to the game folder.
- Zip-bomb guards: ≤ 6000 files and ≤ 350 MB uncompressed.
- Games run in a sandboxed iframe (`allow-scripts allow-same-origin`, no `allow-top-navigation`, no forms escaping) — keep all assets local.

---

## ⭐ LoP Premium flow (your side)

1. User pays **$10/year** to your PayPal address (`PAYPAL_RECEIVER_EMAIL` in `config.py` / env var).
2. User submits the PayPal email + transaction ID + **payment screenshot** on the Premium page.
3. You go to **Admin → Payments**, click **View proof** to check the screenshot, then **Approve** (or reject with a note).
4. Approval extends the user's access by 365 days (stacking if they renew early).
5. Trial users (first 30 days after signup) and active tokens can play Premium games; everyone else sees the lock screen.

---

## 🛡️ Security notes

- CSRF protection on all forms (Flask-WTF); the play-session API is CSRF-exempt by design (sendBeacon cannot send headers) and is guarded by a same-origin check + session ownership checks.
- Passwords hashed with Werkzeug (`scrypt`), sessions are HttpOnly + SameSite=Lax, security headers (CSP, nosniff, frame-ancestors) set globally — game files are served without CSP since they carry their own inline scripts.
- Login lockout: 5 failed attempts → 15-minute lock. Ban check runs on every request.
- Screenshots are served to admins only and marked `Cache-Control: private, no-store`.
- Change `SECRET_KEY` and `PAYPAL_RECEIVER_EMAIL` in production (or via env vars).

> ⚠️ **Production**: `run.bat` and the defaults are for local development. In production run behind HTTPS (so `SESSION_COOKIE_SECURE=1`), harden the headers, and spot-check screenshots against the PayPal dashboard rather than only the image.

---

## 🧪 End-to-end test

```bat
.venv\Scripts\python test_e2e.py
```

Exercises: signup → login → library → play page → session start/heartbeat/end →
premium purchase screenshot upload → trial expiry gating (expired_demo) →
admin approve → chat send/poll → admin uploads a real game ZIP → ban/unban flow.

---

## 📁 Project layout

```
lop-gaming-hub/
├── app.py                 # app factory, headers, error pages, entry point
├── config.py              # all settings
├── models.py              # User, Game, ChatRoom/Message/Presence, GameSession, PaymentRequest
├── helpers.py             # zip ingestion, slugify, stats, jinja filters
├── seed.py                # demo users + 6 sample games + fake history
├── test_e2e.py            # end-to-end test suite
├── blueprints/            # main, auth, games, chat, premium, admin
├── templates/             # Jinja2 templates (public + admin + errors)
├── static/                # CSS + JS
├── uploads/
│   ├── games/<slug>/      # extracted game files (served via /game-files/…)
│   ├── game_zips/         # temp during upload
│   ├── payments/          # payment screenshots (admin only)
│   └── thumbnails/        # game cover art
└── instance/lopgaming.db  # SQLite database
```

---

Built with Flask 3, Flask-SQLAlchemy, Flask-Login, Flask-WTF. SQLite by default
(swap `DATABASE_URL` for PostgreSQL/MySQL in production).