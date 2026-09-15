"""Flask app serving two audiences on one port:
- the OBS browser-source overlay (/overlay, /art, /customfont, /api/nowplaying)
- the settings/control panel opened in a normal browser (/, /api/*)
"""
import os
import string
import sys

from flask import Flask, jsonify, request, send_file, Response, render_template

from .config import Settings, save_settings
from .library import get_library_roots


def create_app(ctx):
    """ctx is the AppContext (see main.py) holding settings/state/watcher/etc."""
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    # ---------------- overlay (served to OBS) ----------------

    @app.route("/overlay")
    @app.route("/overlay/")
    def overlay_page():
        resp = Response(render_template("overlay.html"), mimetype="text/html")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/nowplaying")
    def api_nowplaying():
        resp = jsonify(ctx.now_playing.snapshot())
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/art")
    def art():
        path = ctx.now_playing.art_path
        if path and os.path.isfile(path):
            resp = send_file(path, mimetype="image/jpeg", conditional=False)
            resp.headers["Cache-Control"] = "no-store"
            return resp
        return Response(status=204)

    @app.route("/customfont")
    def customfont():
        path = ctx.now_playing.custom_font_path
        if path and os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            mime = {
                ".otf": "font/otf",
                ".woff": "font/woff",
                ".woff2": "font/woff2",
            }.get(ext, "font/ttf")
            resp = send_file(path, mimetype=mime, conditional=False)
            resp.headers["Cache-Control"] = "no-store"
            return resp
        return Response(status=204)

    # ---------------- control panel ----------------

    @app.route("/")
    def control_panel():
        return render_template("control.html")

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        return jsonify(ctx.settings.to_dict())

    @app.route("/api/settings", methods=["POST"])
    def update_settings():
        body = request.get_json(force=True, silent=True) or {}
        new_settings = Settings.from_dict({**ctx.settings.to_dict(), **body})
        ctx.settings = new_settings
        save_settings(new_settings)
        ctx.now_playing.apply_settings(new_settings)
        return jsonify(ctx.settings.to_dict())

    @app.route("/api/status")
    def status():
        return jsonify(
            {
                "watching": ctx.watcher.running,
                "libraryCount": len(ctx.library_index),
                "overlayUrl": f"http://localhost:{ctx.settings.overlay_port}/overlay",
                "nowPlaying": ctx.now_playing.snapshot(),
            }
        )

    @app.route("/api/watch/start", methods=["POST"])
    def watch_start():
        try:
            roots = get_library_roots(ctx.settings.songs_library_folder)
            if roots:
                ctx.library_index.refresh(ctx.settings.songs_library_folder)
            ctx.now_playing.apply_settings(ctx.settings)
            ctx.watcher.start()
            return jsonify({"ok": True})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/watch/stop", methods=["POST"])
    def watch_stop():
        ctx.watcher.stop()
        return jsonify({"ok": True})

    @app.route("/api/reindex", methods=["POST"])
    def reindex():
        ctx.library_index.refresh(ctx.settings.songs_library_folder, force=True)
        return jsonify({"ok": True, "count": len(ctx.library_index)})

    @app.route("/api/log")
    def api_log():
        since = request.args.get("since", "-1")
        try:
            since_id = int(since)
        except ValueError:
            since_id = -1
        return jsonify(ctx.logger.since(since_id))

    # ---------------- filesystem browser (for picking paths from the web UI) ----------------

    @app.route("/api/fs/roots")
    def fs_roots():
        if sys.platform == "win32":
            roots = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        else:
            roots = [os.path.expanduser("~"), "/"]
        return jsonify(roots)

    @app.route("/api/fs/list")
    def fs_list():
        path = request.args.get("path") or os.path.expanduser("~")
        only_dirs = request.args.get("dirsOnly", "true") == "true"
        try:
            entries = []
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        is_dir = entry.is_dir()
                    except OSError:
                        continue
                    if only_dirs and not is_dir:
                        continue
                    if entry.name.startswith("."):
                        continue
                    entries.append({"name": entry.name, "path": entry.path, "isDir": is_dir})
            entries.sort(key=lambda e: (not e["isDir"], e["name"].lower()))
            parent = os.path.dirname(path.rstrip("/\\")) or None
            if parent == path:
                parent = None
            return jsonify({"path": path, "parent": parent, "entries": entries})
        except OSError as exc:
            return jsonify({"error": str(exc)}), 400

    return app
