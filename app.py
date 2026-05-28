import html
import json
import os
import smtplib
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps

import requests
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

APP_PASSWORDS = [p.strip() for p in os.environ.get("APP_PASSWORD", "changeme").split(",") if p.strip()]
VIMEO_TOKEN = os.environ.get("VIMEO_TOKEN", "")
VIMEO_USER = "hammerhaagsteel"
CACHE_TTL = 3600

_cache = {"data": None, "ts": 0}

DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
os.makedirs(DATA_DIR, exist_ok=True)

COUNTS_FILE = os.path.join(DATA_DIR, "counts.json")


def _load_counts():
    try:
        with open(COUNTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _save_counts():
    with open(COUNTS_FILE, "w") as f:
        json.dump(_counts, f)


_counts = _load_counts()

COMMENTS_FILE = os.path.join(DATA_DIR, "comments.json")


def _load_comments():
    try:
        with open(COMMENTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _save_comments():
    with open(COMMENTS_FILE, "w") as f:
        json.dump(_comments, f)


_comments = _load_comments()


def send_notification(subject, body_text, body_html=None):
    smtp_user = os.environ.get("NOTIFY_GMAIL_USER")
    smtp_pass = os.environ.get("NOTIFY_GMAIL_APP_PASSWORD")
    notify_to = os.environ.get("NOTIFY_EMAIL")
    if not (smtp_user and smtp_pass and notify_to):
        return

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = smtp_user
            msg["To"] = notify_to
            msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, notify_to, msg.as_string())
        except Exception:
            pass

    threading.Thread(target=_send, daemon=True).start()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def _pick_thumbnail(pictures):
    if not pictures:
        return None
    base = pictures.get("base_link")
    sizes = pictures.get("sizes", [])
    if not sizes:
        return base
    for s in sizes:
        if s.get("width", 0) >= 640:
            return s["link"]
    return sizes[-1]["link"] if sizes else base


def fetch_videos():
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    if not VIMEO_TOKEN:
        raise ValueError("VIMEO_TOKEN environment variable is not set.")

    headers = {"Authorization": f"Bearer {VIMEO_TOKEN}"}
    fields = "uri,name,link,pictures,created_time"
    videos = []
    url = f"https://api.vimeo.com/users/{VIMEO_USER}/videos"
    params = {"per_page": 100, "fields": fields, "sort": "date", "direction": "desc"}

    while url:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        body = resp.json()
        for v in body.get("data", []):
            vurl = v.get("link", "")
            videos.append({
                "title": v.get("name", "Untitled"),
                "url": vurl,
                "thumbnail": _pick_thumbnail(v.get("pictures")),
                "year": v.get("created_time", "0000")[:4],
                "copies": _counts.get(vurl, 0),
                "open_comments": sum(1 for c in _comments.get(vurl, []) if not c["done"]),
            })
        nxt = body.get("paging", {}).get("next")
        url = f"https://api.vimeo.com{nxt}" if nxt else None
        params = {}

    by_year = {}
    for v in videos:
        by_year.setdefault(v["year"], []).append(v)

    result = [
        {"year": y, "videos": vids}
        for y, vids in sorted(by_year.items(), reverse=True)
    ]

    _cache["data"] = result
    _cache["ts"] = now
    return result


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password", "").strip() in APP_PASSWORDS:
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/videos")
@login_required
def api_videos():
    try:
        data = fetch_videos()
        return jsonify({"ok": True, "data": data, "total": sum(_counts.values())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sync", methods=["POST"])
@login_required
def api_sync():
    try:
        _cache["ts"] = 0
        data = fetch_videos()
        return jsonify({"ok": True, "data": data, "total": sum(_counts.values())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/copy", methods=["POST"])
@login_required
def api_copy():
    url = request.json.get("url", "") if request.is_json else ""
    if url:
        _counts[url] = _counts.get(url, 0) + 1
        _save_counts()
        if _cache["data"]:
            for group in _cache["data"]:
                for v in group["videos"]:
                    if v["url"] == url:
                        v["copies"] = _counts[url]
    total = sum(_counts.values())
    return jsonify({"ok": True, "copies": _counts.get(url, 0), "total": total})


@app.route("/api/comments", methods=["GET", "POST"])
@login_required
def api_comments():
    if request.method == "GET":
        url = request.args.get("url", "")
        comments = _comments.get(url, [])
        open_count = sum(1 for c in comments if not c["done"])
        return jsonify({"ok": True, "comments": comments, "open": open_count})

    data = request.json or {}
    url = data.get("url", "")
    text = data.get("text", "").strip()
    if not url or not text:
        return jsonify({"ok": False, "error": "url and text required"}), 400
    comment = {
        "id": os.urandom(4).hex(),
        "text": text,
        "author": data.get("author", "").strip(),
        "ts": int(time.time()),
        "done": False,
    }
    _comments.setdefault(url, []).append(comment)
    _save_comments()
    if _cache["data"]:
        for group in _cache["data"]:
            for v in group["videos"]:
                if v["url"] == url:
                    v["open_comments"] = sum(1 for c in _comments[url] if not c["done"])
    open_count = sum(1 for c in _comments[url] if not c["done"])

    author = comment["author"]
    video_name = url
    if _cache["data"]:
        for group in _cache["data"]:
            for v in group["videos"]:
                if v["url"] == url:
                    video_name = v["title"]
                    break
    send_notification(
        subject=f"New change request: {video_name}",
        body_text=(
            f"A new change request was added.\n\n"
            f"Video: {url}\n\n"
            f"From: {author or 'Anonymous'}\n\n"
            f"{text}"
        ),
        body_html=(
            f"<p><strong>New change request</strong></p>"
            f"<p><strong>Video:</strong> <a href='{html.escape(url)}'>{html.escape(video_name)}</a></p>"
            f"<p><strong>From:</strong> {html.escape(author or 'Anonymous')}</p>"
            f"<blockquote>{html.escape(text)}</blockquote>"
        ),
    )

    return jsonify({"ok": True, "comment": comment, "open": open_count})


@app.route("/api/comments/<cid>", methods=["PATCH", "DELETE"])
@login_required
def api_comment(cid):
    for url, comments in _comments.items():
        for i, c in enumerate(comments):
            if c["id"] != cid:
                continue
            just_resolved = False
            if request.method == "DELETE":
                comments.pop(i)
            else:
                was_done = c["done"]
                c["done"] = not c["done"]
                just_resolved = c["done"] and not was_done
            _save_comments()
            if _cache["data"]:
                for group in _cache["data"]:
                    for v in group["videos"]:
                        if v["url"] == url:
                            v["open_comments"] = sum(1 for x in comments if not x["done"])
            open_count = sum(1 for x in comments if not x["done"])

            if just_resolved:
                video_name = url
                if _cache["data"]:
                    for group in _cache["data"]:
                        for v in group["videos"]:
                            if v["url"] == url:
                                video_name = v["title"]
                                break
                send_notification(
                    subject=f"Change request resolved: {video_name}",
                    body_text=(
                        f"A change request was marked as resolved.\n\n"
                        f"Video: {url}\n\n"
                        f"Comment: {c['text']}\n"
                        f"By: {c.get('author') or 'Anonymous'}"
                    ),
                    body_html=(
                        f"<p><strong>Change request resolved</strong></p>"
                        f"<p><strong>Video:</strong> <a href='{html.escape(url)}'>{html.escape(video_name)}</a></p>"
                        f"<p><strong>Comment:</strong></p>"
                        f"<blockquote>{html.escape(c['text'])}</blockquote>"
                        f"<p><em>By {html.escape(c.get('author') or 'Anonymous')}</em></p>"
                    ),
                )

            return jsonify({"ok": True, "open": open_count})
    return jsonify({"ok": False, "error": "not found"}), 404


@app.route("/api/notify-check")
def api_notify_check():
    return jsonify({
        "NOTIFY_GMAIL_USER": bool(os.environ.get("NOTIFY_GMAIL_USER")),
        "NOTIFY_GMAIL_APP_PASSWORD": bool(os.environ.get("NOTIFY_GMAIL_APP_PASSWORD")),
        "NOTIFY_EMAIL": bool(os.environ.get("NOTIFY_EMAIL")),
    })


@app.route("/api/test-notify")
@login_required
def api_test_notify():
    import traceback
    try:
        smtp_user = os.environ.get("NOTIFY_GMAIL_USER")
        smtp_pass = os.environ.get("NOTIFY_GMAIL_APP_PASSWORD")
        notify_to = os.environ.get("NOTIFY_EMAIL")
        missing = [k for k, v in [("NOTIFY_GMAIL_USER", smtp_user), ("NOTIFY_GMAIL_APP_PASSWORD", smtp_pass), ("NOTIFY_EMAIL", notify_to)] if not v]
        if missing:
            return jsonify({"ok": False, "error": f"Missing env vars: {', '.join(missing)}"})
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "HH Vimeo Library - test notification"
        msg["From"] = smtp_user
        msg["To"] = notify_to
        msg.attach(MIMEText("Test email from HH Vimeo Library. Notifications are working.", "plain"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, notify_to, msg.as_string())
        return jsonify({"ok": True, "message": f"Test email sent to {notify_to}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
