import json
import os
import time
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

COUNTS_FILE = os.path.join(os.path.dirname(__file__), "counts.json")


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
