"""System tray icon, mirroring New-BadgeIcon from the ps1 - drawn purely in
code (no bundled image asset needed) so it always matches the app's theme."""
import webbrowser

import pystray  # module-level, not inside run_tray() - see main.py's
# `from . import tray` for why this matters: that's wrapped in a
# try/except ImportError specifically so a missing pystray install falls
# back to headless mode instead of crashing. That only works if the
# import failure happens while *importing this module*, not later when
# run_tray() is actually called.

from .branding import make_badge_image


def run_tray(ctx, on_quit):
    """Blocks the calling thread (required on macOS) - call this last, from
    the main thread, after the web server thread is already running."""

    def open_panel(icon, item):
        webbrowser.open(f"http://127.0.0.1:{ctx.settings.overlay_port}/")

    def toggle_watch(icon, item):
        if ctx.watcher.running:
            ctx.watcher.stop()
        else:
            try:
                ctx.watcher.start()
            except ValueError as exc:
                ctx.logger.log(f"Couldn't start watching: {exc}")

    def watch_label(item):
        return "Stop Watching" if ctx.watcher.running else "Start Watching"

    def update_label(item):
        info = ctx.update_info
        return f"Update available: {info['version']} (click to open)" if info else "Check for Updates"

    def update_action(icon, item):
        if ctx.update_info:
            webbrowser.open(ctx.update_info["release_url"])
            return
        from . import updater
        result = updater.check_latest_release()
        ctx.update_info = result
        if result:
            webbrowser.open(result["release_url"])
        else:
            ctx.logger.log("No update available - you're running the latest version.")

    def quit_app(icon, item):
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Open Control Panel", open_panel, default=True),
        pystray.MenuItem(watch_label, toggle_watch),
        pystray.MenuItem(update_label, update_action),
        pystray.MenuItem("Quit", quit_app),
    )
    icon = pystray.Icon("choad", make_badge_image(), "CHOAD", menu)
    icon.run()
