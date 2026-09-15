import argparse
import sys
import threading

from .config import load_settings, save_settings
from .library import LibraryIndex
from .state import NowPlaying, Logger
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


def run_server(ctx, host="127.0.0.1"):
    app = create_app(ctx)
    # threaded=True: the overlay poller, the control panel, and /art can all
    # be hit concurrently by OBS + a browser at once.
    app.run(host=host, port=ctx.settings.overlay_port, threaded=True, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(description="CHOAD - Clone Hero Overlay Artwork Downloader")
    parser.add_argument("--no-tray", action="store_true", help="Run headless (no system tray icon)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    ctx = AppContext()
    save_settings(ctx.settings)  # write defaults on first run

    server_thread = threading.Thread(target=run_server, args=(ctx, args.host), daemon=True)
    server_thread.start()
    ctx.logger.log(f"Control panel: http://{args.host}:{ctx.settings.overlay_port}/")
    ctx.logger.log(f"Overlay (add as OBS browser source): http://{args.host}:{ctx.settings.overlay_port}/overlay")

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
