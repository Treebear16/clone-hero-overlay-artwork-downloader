import argparse
import sys
import threading

from .config import load_settings, save_settings
from .library import LibraryIndex
from .state import NowPlaying, Logger
from .version import APP_VERSION
from .watcher import Watcher
from .webapp import create_app


class AppContext:
    """Bag of shared objects passed to the Flask app and the tray icon.
    `settings` is reassigned (not mutated in place) whenever the control
    panel saves changes, so anything holding a reference to `ctx` (not
    `ctx.settings`) always sees the current value."""

    def __init__(self):
        self.settings = load_settings()
        self.logger = Logger()
        self.now_playing = NowPlaying()
        self.library_index = LibraryIndex(logger=self.logger)
        self.watcher = Watcher(
            settings_getter=lambda: self.settings,
            now_playing=self.now_playing,
            logger=self.logger,
            library_index=self.library_index,
        )
        self.now_playing.apply_settings(self.settings)
        self.update_info = None  # set by updater.start_background_check
        self.preview_mode = False  # toggled from the control panel - see webapp.py's /api/preview


def run_server(ctx, host="127.0.0.1"):
    app = create_app(ctx)
    # threaded=True: the overlay poller, the control panel, and /art can all
    # be hit concurrently by OBS + a browser at once.
    app.run(host=host, port=ctx.settings.overlay_port, threaded=True, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(description="CHOAD - Clone Hero Overlay Artwork Downloader")
    parser.add_argument("--no-tray", action="store_true", help="Run headless (no system tray icon)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    # Hidden, internal-only: the control panel's "Browse" buttons re-invoke
    # this same program with these flags to pop a native file/folder picker
    # in an isolated subprocess (see native_dialog.py for why), print the
    # chosen path as JSON, and exit - never shown to, or used directly by,
    # an end user.
    parser.add_argument("--native-dialog", choices=["file", "dir"], help=argparse.SUPPRESS)
    parser.add_argument("--initial-dir", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.native_dialog:
        from . import native_dialog
        native_dialog.run_dialog_and_print(args.native_dialog, args.initial_dir)
        return

    ctx = AppContext()
    save_settings(ctx.settings)  # write defaults on first run

    server_thread = threading.Thread(target=run_server, args=(ctx, args.host), daemon=True)
    server_thread.start()
    ctx.logger.log(f"CHOAD v{APP_VERSION}")
    ctx.logger.log(f"Control panel: http://{args.host}:{ctx.settings.overlay_port}/")
    ctx.logger.log(f"Overlay (add as OBS browser source): http://{args.host}:{ctx.settings.overlay_port}/overlay")

    from . import updater
    updater.start_background_check(ctx)

    if args.no_tray:
        try:
            server_thread.join()
        except KeyboardInterrupt:
            pass
        return

    try:
        from . import tray
    except ImportError:
        ctx.logger.log("pystray not available - running headless. Install pystray/Pillow or use --no-tray.")
        server_thread.join()
        return

    def on_quit():
        ctx.watcher.stop()
        sys.exit(0)

    tray.run_tray(ctx, on_quit)


if __name__ == "__main__":
    main()
