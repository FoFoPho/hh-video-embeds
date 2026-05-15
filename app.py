import os
import time
import requests
from flask import Flask, render_template, jsonify

app = Flask(__name__)

VIMEO_TOKEN = os.environ.get("VIMEO_TOKEN", "")
VIMEO_USER = "hammerhaagsteel"
CACHE_TTL = 3600

_cache = {"data": None, "ts": 0}


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/videos")
def api_videos():
    try:
        data = fetch_videos()
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
