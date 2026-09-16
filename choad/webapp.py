"""Flask app serving two audiences on one port:
- the OBS browser-source overlay (/overlay, /art, /api/nowplaying)
- the settings/control panel opened in a normal browser (/, /api/*)
"""
import os

from flask import Flask, jsonify, request, send_file, Response, render_template

from .artwork import generate_sample_art
from .config import Settings, save_settings, PREVIEW_ART_FILE
from .fonts import list_fonts, add_font, font_path
from .library import get_library_roots

# Deliberately long/unwieldy so toggling "preview with sample data" on gives
# an immediate, visible check of marquee scroll speed and truncation without
# needing Clone Hero running or a real song queued up.
SAMPLE_SONG = "This Is An Absurdly Long Song Title Written Specifically To Stress-Test The Scrolling Marquee At Whatever Speed You've Got Set"
SAMPLE_ARTIST = "A Fictional Artist Collective With An Unnecessarily Long Band Name Featuring Several Guest Vocalists"
SAMPLE_CHARTER = "Charted by Someone Whose Charter Name Also Happens To Run On For Quite A While"
PREVIEW_TOKEN = -1  # real tokens only ever count up from 0, so this never collides


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
        snap = ctx.now_playing.snapshot()
        if ctx.preview_mode:
            # Style/layout fields (colors, sizes, panel width, idle text)
            # stay real, from settings - only the "now playing" fields are
            # swapped for sample data, so this doubles as a live style
            # preview too.
            snap["song"] = SAMPLE_SONG
            snap["artist"] = SAMPLE_ARTIST
            snap["charter"] = SAMPLE_CHARTER
            snap["token"] = PREVIEW_TOKEN
        resp = jsonify(snap)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/art")
    def art():
        path = str(PREVIEW_ART_FILE()) if ctx.preview_mode else ctx.now_playing.art_path
        if path and os.path.isfile(path):
            resp = send_file(path, mimetype="image/jpeg", conditional=False)
            resp.headers["Cache-Control"] = "no-store"
            return resp
        return Response(status=204)

    @app.route("/customfont")
    def customfont():
        # Kept only so an old cached OBS browser-source page hitting this
        # exact URL gets a clean 204 instead of a 404 - the font's actual
        # bytes are served from the library now, at /fonts/<filename>.
        return Response(status=204)

    @app.route("/fonts/<path:filename>")
    def serve_font(filename):
        path = font_path(filename)
        if not path:
            return Response(status=404)
        ext = os.path.splitext(path)[1].lower()
        mime = {
            ".otf": "font/otf",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
        }.get(ext, "font/ttf")
        resp = send_file(path, mimetype=mime, conditional=False)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---------------- control panel ----------------

    @app.route("/")
    def control_panel():
        return render_template("control.html")

    @app.route("/api/settings", methods=["GET"])
    def get_settings():
        return jsonify(ctx.settings.to_dict())

    @app.route("/api/fonts")
    def api_fonts():
        return jsonify({"fonts": list_fonts()})

    @app.route("/api/fonts/add", methods=["POST"])
    def api_fonts_add():
        body = request.get_json(force=True, silent=True) or {}
        source_path = body.get("path") or ""
        try:
            filename = add_font(source_path)
        except (ValueError, OSError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        ctx.logger.log(f"Added font '{filename}' to the library.")
        return jsonify({"ok": True, "filename": filename, "fonts": list_fonts()})

    @app.route("/api/settings", methods=["POST"])
    def update_settings():
        body = request.get_json(force=True, silent=True) or {}
        new_settings = Settings.from_dict({**ctx.settings.to_dict(), **body})
        ctx.settings = new_settings
        save_settings(new_settings)
        ctx.now_playing.apply_settings(new_settings)
        if ctx.preview_mode:
            # Colors/target size may have just changed - keep the sample
            # art in step so the preview reflects them too.
            try:
                generate_sample_art(PREVIEW_ART_FILE(), ctx.settings.target_size, ctx.settings.overlay_bg_color)
            except OSError as exc:
                ctx.logger.log(f"Couldn't refresh sample preview art: {exc}")
        return jsonify(ctx.settings.to_dict())

    @app.route("/api/preview", methods=["POST"])
    def set_preview():
        body = request.get_json(force=True, silent=True) or {}
        enabled = bool(body.get("enabled"))
        ctx.preview_mode = enabled
        if enabled:
            try:
                generate_sample_art(PREVIEW_ART_FILE(), ctx.settings.target_size, ctx.settings.overlay_bg_color)
            except OSError as exc:
                ctx.logger.log(f"Couldn't generate sample preview art: {exc}")
            ctx.logger.log("Preview mode enabled - overlay is showing sample data.")
        else:
            ctx.logger.log("Preview mode disabled - overlay is back to live data.")
        return jsonify({"ok": True, "enabled": ctx.preview_mode})

    @app.route("/api/status")
    def status():
        return jsonify(
            {
                "watching": ctx.watcher.running,
                "libraryCount": len(ctx.library_index),
                "overlayUrl": f"http://localhost:{ctx.settings.overlay_port}/overlay",
                "nowPlaying": ctx.now_playing.snapshot(),
                "updateAvailable": ctx.update_info,
                "previewMode": ctx.preview_mode,
            }
        )

    def _log_index_progress(*args):
        """Bridges library.py's on_progress callback (called with 1 arg
        during the folder scan, 2 args during the parse) to the log panel,
        so a slow first-time index on a big library doesn't look frozen."""
        if len(args) == 1:
            ctx.logger.log(f"Scanning song folders... {args[0]} found so far")
        else:
            scanned, found = args
            ctx.logger.log(f"Indexing songs... {scanned} folders parsed, {found} matched")

    @app.route("/api/watch/start", methods=["POST"])
    def watch_start():
        try:
            roots = get_library_roots(ctx.settings.songs_library_folder)
            if roots:
                ctx.library_index.refresh(ctx.settings.songs_library_folder, progress_cb=_log_index_progress)
            else:
                ctx.logger.log("No songs library folder configured - starting without local artwork lookup.")
            ctx.now_playing.apply_settings(ctx.settings)
            ctx.watcher.start()
            if ctx.preview_mode:
                # Don't leave sample data showing over real playback.
                ctx.preview_mode = False
                ctx.logger.log("Preview mode turned off automatically - now watching for real.")
            return jsonify({"ok": True})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/watch/stop", methods=["POST"])
    def watch_stop():
        ctx.watcher.stop()
        return jsonify({"ok": True})

    @app.route("/api/reindex", methods=["POST"])
    def reindex():
        ctx.library_index.refresh(
            ctx.settings.songs_library_folder, force=True, progress_cb=_log_index_progress
        )
        count = len(ctx.library_index)
        ctx.logger.log(f"Library index rebuilt - {count} songs indexed.")
        return jsonify({"ok": True, "count": count})

    @app.route("/api/log")
    def api_log():
        since = request.args.get("since", "-1")
        try:
            since_id = int(since)
        except ValueError:
            since_id = -1
        return jsonify(ctx.logger.since(since_id))

    # ---------------- native OS file/folder picker ----------------

    @app.route("/api/browse-native", methods=["POST"])
    def browse_native():
        body = request.get_json(force=True, silent=True) or {}
        mode = "dir" if body.get("mode") == "dir" else "file"
        initial_dir = body.get("initialDir") or ""
        from . import native_dialog

        path = native_dialog.pick_path(mode=mode, initial_dir=initial_dir)
        return jsonify({"path": path})

    return app
