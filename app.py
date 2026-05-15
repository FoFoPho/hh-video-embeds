import os
import time
from functools import wraps

import requests
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

APP_PASSWORD = os.environ.get("APP_PASSWORD", "changeme")
VIMEO_TOKEN = os.environ.get("VIMEO_TOKEN", "")
VIMEO_USER = "hammerhaagsteel"
CACHE_TTL = 3600

_cache = {"data": None, "ts": 0}


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
            videos.append({
                "title": v.get("name", "Untitled"),
                "url": v.get("link", ""),
                "thumbnail": _pick_thumbnail(v.get("pictures")),
                "year": v.get("created_time", "0000")[:4],
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
        if request.form.get("password") == APP_PASSWORD:
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
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
