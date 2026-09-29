"""LoP Gaming Hub - end-to-end smoke test.

Runs against a LIVE dev server (start `python app.py` first, default
http://127.0.0.1:5000) and drives the real HTTP + JSON APIs the way a
browser would: register, login, play-session tracking, chat, premium
purchase submission, admin verification, game upload, ban/unban, grants.

Run:  python e2e_test.py
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import io
import os
import re
import sys
import time
import zipfile
from datetime import datetime

import requests

BASE = os.environ.get("LOP_BASE_URL", "http://127.0.0.1:5000")

STAMP = datetime.now().strftime("%H%M%S%f")[:8]
USERNAME = f"e2e_{STAMP}"
EMAIL = f"{USERNAME}@example.com"
PASSWORD = "e2ePass123"
ADMIN_USER = "admin"
ADMIN_PASS = "LoP-admin-2026!"
EXPIRED_USER = "expired_demo"
EXPIRED_PASS = "expired12345"

GAME_TITLE = f"E2E Blast {STAMP}"
GAME_SLUG = "e2e-blast-" + STAMP

# 1x1 transparent PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049"
    "454e44ae426082"
)

_OK: list[str] = []
_FAIL: list[str] = []


def ok(name: str, cond: bool, extra: str = "") -> None:
    if cond:
        _OK.append(name)
        print(f"  PASS  {name}")
    else:
        _FAIL.append(name)
        print(f"  FAIL  {name}  {extra}")


def get_csrf(sess: requests.Session, url: str) -> tuple[str, requests.Response]:
    """GET a page and pull the CSRF token out of the meta tag / form hidden input."""
    r = sess.get(url)
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
    if m:
        return m.group(1), r
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
    token = m.group(1) if m else ""
    return token, r


def login(sess: requests.Session, username: str, password: str) -> requests.Response:
    token, _ = get_csrf(sess, BASE + "/auth/login")
    return sess.post(
        BASE + "/auth/login",
        data={"csrf_token": token, "username": username, "password": password},
        allow_redirects=False,
    )


def logout(sess: requests.Session) -> requests.Response:
    return sess.get(BASE + "/auth/logout", allow_redirects=False)


def post_csrf(sess: requests.Session, url: str, data: dict, files: dict | None = None,
              **kw) -> requests.Response:
    token, _ = get_csrf(sess, url)
    data = dict(data)
    data["csrf_token"] = token
    return sess.post(url, data=data, files=files, **kw)


def build_game_zip() -> bytes:
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>E2E Blast</title></head>"
        "<body style='background:#0a0e17;color:#fff'><h1>E2E Blast</h1>"
        "<p>Uploaded by the end-to-end test.</p></body></html>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html)
    return buf.getvalue()


def main() -> None:
    s = requests.Session()

    # ------------------------------------------------------------------ #
    # 1. Public surface                                                  #
    # ------------------------------------------------------------------ #
    print("\n[1] Public surface")
    r = s.get(BASE + "/")
    ok("home 200 + brand", r.status_code == 200 and "LoP" in r.text)
    r = s.get(BASE + "/static/css/style.css")
    ok("static css 200", r.status_code == 200)
    r = s.get(BASE + "/definitely-not-here")
    ok("404 page", r.status_code == 404)
    r = s.get(BASE + "/games")
    ok("library requires login", r.status_code == 302 and "auth/login" in r.headers.get("Location", ""))

    # ------------------------------------------------------------------ #
    # 2. Registration                                                    #
    # ------------------------------------------------------------------ #
    print("\n[2] Registration")
    r = s.post(
        BASE + "/auth/register",
        data={"username": "ab", "email": "x", "password": "short", "confirm": "short"},
    )
    ok("weak input rejected", r.status_code == 200 and ("Username must" in r.text or "valid email" in r.text),
       f"status={r.status_code}")

    # fresh session for a clean CSRF cookie pair
    s = requests.Session()
    token, _ = get_csrf(s, BASE + "/auth/register")
    r = s.post(
        BASE + "/auth/register",
        data={"csrf_token": token, "username": USERNAME, "email": EMAIL,
              "password": PASSWORD, "confirm": PASSWORD},
        allow_redirects=False,
    )
    ok("register redirects to library", r.status_code == 302 and "/games" in r.headers.get("Location", ""))

    token, _ = get_csrf(s, BASE + "/auth/register")
    r = s.post(BASE + "/auth/register",
               data={"csrf_token": token, "username": USERNAME, "email": "other@example.com",
                     "password": PASSWORD, "confirm": PASSWORD})
    ok("duplicate username rejected", r.status_code == 200 and "already taken" in r.text)

    logout(s)

    # ------------------------------------------------------------------ #
    # 3. Login / lockout behaviour                                       #
    # ------------------------------------------------------------------ #
    print("\n[3] Login")
    r = login(s, USERNAME, "definitelyWrong1")
    ok("bad password rejected", r.status_code == 200 and "Invalid" in r.text)
    r = login(s, USERNAME, PASSWORD)
    ok("good password logs in", r.status_code == 302)
    r = s.get(BASE + "/games")
    ok("library shows seeded games", r.status_code == 200 and "Snake" in r.text and "Neon Pong" in r.text)

    # ------------------------------------------------------------------ #
    # 4. Play-session tracking API                                       #
    # ------------------------------------------------------------------ #
    print("\n[4] Play sessions")
    r = s.post(BASE + "/api/games/snake/session/start", json={})
    j = r.json()
    ok("session start ok", r.status_code == 200 and j.get("ok") and j.get("session_id"), str(j))
    sid = j.get("session_id")
    r = s.post(BASE + "/api/games/snake/session/heartbeat", json={"session_id": sid})
    ok("heartbeat ok", r.status_code == 200 and r.json().get("ok"))
    time.sleep(2)
    r = s.post(BASE + "/api/games/snake/session/end", data={"session_id": sid})
    ok("session end ok", r.status_code == 200 and r.json().get("ok"), str(r.text[:200]))

    r = s.post(BASE + "/api/games/neon-pong-2p/session/start", json={})
    j = r.json()
    sid2 = j.get("session_id")
    r = s.post(BASE + "/api/games/neon-pong-2p/session/end", data={"session_id": sid2})
    ok("second session end ok", r.status_code == 200 and r.json().get("ok"))

    r = s.get(BASE + "/auth/profile")
    ok("profile counts playtime", r.status_code == 200 and "Snake" in r.text)
    ok("profile shows plays", "plays" in r.text.lower())

    r = s.get(BASE + "/game-files/snake/index.html")
    ok("game files served after login", r.status_code == 200 and b"Snake" in r.content)

    # ------------------------------------------------------------------ #
    # 5. Chatrooms                                                       #
    # ------------------------------------------------------------------ #
    print("\n[5] Chat")
    r = s.get(BASE + "/chat")
    ok("chat hub lists Lobby", r.status_code == 200 and "Lobby" in r.text)
    r = s.get(BASE + "/chat/1")
    ok("room page ok", r.status_code == 200)
    token, _ = get_csrf(s, BASE + "/chat/1")
    r = s.post(BASE + "/chat/1/api/send",
               json={"content": "e2e hello from " + USERNAME},
               headers={"X-CSRFToken": token})
    j = r.json()
    ok("message sent", r.status_code == 200 and j.get("ok"), str(j))
    msg_id = j.get("message", {}).get("id")
    r = s.post(BASE + "/chat/1/api/send",
               json={"content": "spam"},
               headers={"X-CSRFToken": token})
    ok("rate limit blocks spam", r.status_code == 429, f"status={r.status_code}")
    time.sleep(1.7)
    r = s.post(BASE + "/chat/1/api/send",
               json={"content": "second message"},
               headers={"X-CSRFToken": token})
    ok("rate limit lifts", r.status_code == 200 and r.json().get("ok"))
    r = s.get(BASE + f"/chat/1/api/messages?after={msg_id}")
    j = r.json()
    ok("polling returns new message", any(m["content"] == "second message" for m in j["messages"]))
    ok("presence shows online user", USERNAME in j.get("online", []), str(j.get("online")))

    # ------------------------------------------------------------------ #
    # 6. Premium trial + purchase submission                             #
    # ------------------------------------------------------------------ #
    print("\n[6] Premium")
    r = s.get(BASE + "/premium")
    ok("trial visible", r.status_code == 200 and "trial" in r.text.lower(), r.text[:200])
    r = post_csrf(
        s, BASE + "/premium/request",
        data={"paypal_email": "gamer.paypal@example.com",
              "transaction_id": f"0PAE2ETEST{STAMP}"},
        files={"screenshot": ("proof.png", PNG_BYTES, "image/png")},
        allow_redirects=False,
    )
    ok("purchase submitted", r.status_code == 302, f"status={r.status_code}")
    r = s.get(BASE + "/premium")
    ok("submission awaiting verification", r.status_code == 200 and "submitted" in r.text.lower(),
       r.text[:300])

    # ------------------------------------------------------------------ #
    # 7. Admin: dashboard, users, approval, upload, ban                  #
    # ------------------------------------------------------------------ #
    print("\n[7] Admin")
    anon = requests.Session()
    r = anon.get(BASE + "/admin", allow_redirects=False)
    ok("admin requires login", r.status_code == 302 and "auth/login" in r.headers.get("Location", ""))

    a = requests.Session()
    r = login(a, ADMIN_USER, ADMIN_PASS)
    ok("admin login ok", r.status_code == 302)
    r = a.get(BASE + "/admin")
    ok("dashboard loads", r.status_code == 200 and "Dashboard" in r.text)
    ok("dashboard counts users", "users" in r.text.lower())

    r = a.get(BASE + "/admin/users?q=" + USERNAME)
    m = re.search(r'href="/admin/users/(\d+)"', r.text)
    ok("user search finds e2e user", r.status_code == 200 and USERNAME in r.text and bool(m),
       f"status={r.status_code}")
    uid = int(m.group(1))

    r = a.get(BASE + f"/admin/users/{uid}")
    ok("user detail page", r.status_code == 200 and USERNAME in r.text)

    r = a.get(BASE + "/admin/payments")
    m = re.search(r'review"|payments/(\d+)/review', r.text)
    pid = int(re.search(r"/admin/payments/(\d+)/review", r.text).group(1))
    ok("payment listed as pending", r.status_code == 200 and f"0PAE2ETEST{STAMP}" in r.text)

    r = a.get(BASE + f"/admin/payments/{pid}/screenshot")
    ok("screenshot served with nosniff", r.status_code == 200
       and r.headers.get("X-Content-Type-Options") == "nosniff")

    r = post_csrf(a, BASE + f"/admin/payments/{pid}/review",
                  data={"decision": "approve", "note": "verified by e2e"},
                  allow_redirects=False)
    ok("payment approved", r.status_code == 302)

    r = s.get(BASE + "/premium")
    ok("user now premium", r.status_code == 200
       and ("active" in r.text.lower() or "until" in r.text.lower()), r.text[:300])

    # game upload (premium + multiplayer + featured)
    r = post_csrf(
        a, BASE + "/admin/games/upload",
        data={"title": GAME_TITLE, "category": "Arcade", "version": "1.0",
              "description": "Uploaded by the e2e test.",
              "is_premium": "1", "is_multiplayer": "1", "is_featured": "1"},
        files={"zip_file": ("blast.zip", build_game_zip(), "application/zip")},
        allow_redirects=False,
    )
    ok("game upload accepted", r.status_code == 302, f"status={r.status_code}")
    r = a.get(BASE + "/admin/games")
    ok("uploaded game in admin list", GAME_TITLE in r.text)
    r = s.get(BASE + "/games?q=" + GAME_TITLE)
    ok("uploaded game in library", GAME_TITLE in r.text)
    r = s.get(BASE + "/chat")
    ok("auto-created game chatroom", GAME_TITLE + " Chat" in r.text)

    # premium gating: expired_demo must be locked out of the paid game
    e = requests.Session()
    r = login(e, EXPIRED_USER, EXPIRED_PASS)
    ok("expired_demo login", r.status_code == 302)
    slug = GAME_TITLE.lower().replace(" ", "-")
    r = e.get(BASE + f"/games/{slug}/play", allow_redirects=False)
    ok("premium play gated", r.status_code == 302 and "/premium" in r.headers.get("Location", ""),
       f"status={r.status_code} loc={r.headers.get('Location')}")

    # non-admin cannot open /admin
    r = s.get(BASE + "/admin", allow_redirects=False)
    ok("non-admin blocked from admin", r.status_code == 403, f"status={r.status_code}")

    # ban the e2e user
    r = post_csrf(a, BASE + f"/admin/users/{uid}/ban",
                  data={"reason": "e2e test ban", "days": "1"}, allow_redirects=False)
    ok("ban accepted", r.status_code == 302)
    r = a.get(BASE + f"/admin/users/{uid}")
    ok("user shown as banned", "banned" in r.text.lower(), "...")

    # banned user gets bounced on their next request
    r = s.get(BASE + "/games", allow_redirects=False)
    ok("banned user bounced to login", r.status_code == 302 and "auth/login" in r.headers.get("Location", ""),
       f"status={r.status_code} loc={r.headers.get('Location')}")
    r = login(s, USERNAME, PASSWORD)
    ok("banned login rejected", r.status_code == 200 and "suspended" in r.text.lower())

    # unban + login again
    r = post_csrf(a, BASE + f"/admin/users/{uid}/unban", data={}, allow_redirects=False)
    ok("unban accepted", r.status_code == 302)
    r = login(s, USERNAME, PASSWORD)
    ok("login works after unban", r.status_code == 302, f"status={r.status_code}")

    # admin grant premium days
    r = post_csrf(a, BASE + f"/admin/users/{uid}/grant",
                  data={"days": "365"}, allow_redirects=False)
    ok("grant accepted", r.status_code == 302)

    # toggle a seeded game's featured flag over JSON API
    r2 = a.get(BASE + "/admin/games")
    m = re.search(r'href="/admin/games/(\d+)/toggle"|data-id="(\d+)"', r2.text)
    gid = int(m.group(1) or m.group(2))
    token, _ = get_csrf(a, BASE + "/admin/games")
    r = a.post(BASE + f"/admin/games/{gid}/toggle", json={"field": "is_featured", "value": 0},
               headers={"X-CSRFToken": token})
    ok("toggle endpoint ok", r.status_code == 200 and r.json().get("ok"), str(r.text[:200]))

    # logout + expired_demo can still browse free games
    r = logout(s)
    ok("logout ok", r.status_code == 302)
    r = e.get(BASE + "/games")
    ok("expired user browses free library", r.status_code == 200 and "Snake" in r.text)

    # cleanup: delete the uploaded test game
    r2 = a.get(BASE + "/admin/games")
    m = re.search(r"/admin/games/(\d+)/delete", r2.text)
    matches = re.findall(r'action="/admin/games/(\d+)/delete"', r2.text)
    needle = None
    # find the id whose row contains the test title
    for candidate in matches:
        seg = r2.text[r2.text.find(f'action="/admin/games/{candidate}/delete"') - 600:
                      r2.text.find(f'action="/admin/games/{candidate}/delete"')]
        if GAME_TITLE in seg:
            needle = candidate
            break
    if needle:
        r = post_csrf(a, BASE + f"/admin/games/{needle}/delete", data={}, allow_redirects=False)
        ok("uploaded game deleted", r.status_code == 302)
    else:
        ok("uploaded game deleted", False, "could not locate delete form")

    # ------------------------------------------------------------------ #
    # Summary                                                            #
    # ------------------------------------------------------------------ #
    print(f"\n{'=' * 50}")
    print(f"PASS: {len(_OK)}   FAIL: {len(_FAIL)}")
    if _FAIL:
        print("Failed checks:")
        for f in _FAIL:
            print(f"  - {f}")
        sys.exit(1)
    print("ALL END-TO-END CHECKS PASSED")


if __name__ == "__main__":
    main()