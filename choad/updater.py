"""Checks GitHub Releases for a newer version and surfaces it to the
control panel + tray menu. Deliberately does NOT silently download and
replace the running executable: a PyInstaller onefile exe is locked while
running (can't overwrite it in place on Windows), and getting a
self-replace-and-relaunch dance right across three OSes without being able
to test the actual built binaries on each one is a good way to brick
someone's install. Instead this gets you 90% of "auto-update" - it checks
automatically, in the background, with no action needed - and hands you a
direct link to the right download for your OS the moment one's out."""
import sys
import threading
import time

import requests

from .version import APP_VERSION

# Fill this in once the repo exists on GitHub, e.g. "yourname/choad".
# Update checks are a no-op (silently do nothing) until this is set.
GITHUB_REPO = "Treebear16/clone-hero-overlay-artwork-downloader"

CHECK_INTERVAL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 8


def _parse_version(v: str):
    """'v1.2.3' -> (1, 2, 3), tolerant of a missing 'v' or extra suffixes."""
    v = v.lstrip("vV")
    parts = []
    for piece in v.split("."):
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _asset_download_url(assets):
    """Match this OS's zip from the release assets, by the naming convention
    the build.yml workflow uses (CHOAD-windows.zip / CHOAD-macos.zip / CHOAD-linux.zip)."""
    if sys.platform == "win32":
        key = "windows"
    elif sys.platform == "darwin":
        key = "macos"
    else:
        key = "linux"
    for asset in assets:
        if key in asset.get("name", "").lower():
            return asset.get("browser_download_url")
    return None


def check_latest_release():
    """Returns None if not configured, offline, or already up to date.
    Otherwise a dict: version, release_url, download_url (may be None if no
    matching asset was found), notes."""
    if not GITHUB_REPO:
        return None
    try:
        resp = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"Accept": "application/vnd.github+json"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except requests.RequestException:
        return None

    latest_tag = data.get("tag_name", "")
    if not latest_tag or _parse_version(latest_tag) <= _parse_version(APP_VERSION):
        return None

    return {
        "version": latest_tag,
        "release_url": data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest",
        "download_url": _asset_download_url(data.get("assets", [])),
        "notes": (data.get("body") or "").strip()[:500],
    }


def start_background_check(ctx):
    """Checks once at startup, then once a day for as long as the app runs.
    Writes the result to ctx.update_info (None, or the dict above) - simple
    attribute assignment is safe here without extra locking since nothing
    else ever mutates it."""

    def _loop():
        while True:
            info = check_latest_release()
            ctx.update_info = info
            if info:
                ctx.logger.log(
                    f"Update available: {info['version']} (currently running v{APP_VERSION}) "
                    f"- {info['release_url']}"
                )
            time.sleep(CHECK_INTERVAL_SECONDS)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t
