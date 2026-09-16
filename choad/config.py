"""Config file location and settings persistence (cross-platform)."""
import json
import os
import sys
import threading
from dataclasses import dataclass, asdict, fields
from pathlib import Path


def get_config_dir() -> Path:
    """Per-user app config dir: %LOCALAPPDATA%\\CHOAD, ~/Library/Application
    Support/CHOAD, or ~/.config/CHOAD, mirroring the original PS1's use of
    %LOCALAPPDATA%\\CloneHeroAlbumArt."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        d = Path(base) / "CHOAD"
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "CHOAD"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        d = Path(base) / "CHOAD"
    d.mkdir(parents=True, exist_ok=True)
    return d


CONFIG_FILE = lambda: get_config_dir() / "config.json"
LIBRARY_CACHE_FILE = lambda: get_config_dir() / "library-cache.json"
PREVIEW_ART_FILE = lambda: get_config_dir() / "preview-art.jpg"
ART_FILE = lambda: get_config_dir() / "overlay-art.jpg"  # the overlay's own working copy - always written to, regardless of export_art_path


def get_fonts_dir() -> Path:
    """Where fonts added via the control panel's font picker are kept - once
    copied in here, the overlay can always find them by filename alone, so
    the person never needs to keep the original file anywhere in particular
    (or at all, after adding it)."""
    d = get_config_dir() / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Settings:
    current_song_file: str = ""  # the currentsong.txt Clone Hero itself writes while a song is playing
    output_image: str = ""  # deprecated - kept only so old config.json files still load; see export_art_path
    export_art_path: str = ""  # optional: also copy the resized art here, for a plain OBS Image Source instead of/alongside the overlay's own "Art only" layout
    default_image: str = ""  # shown when nothing is playing / no art was found
    songs_library_folder: str = ""  # ';'-separated multiple roots
    target_size: int = 500
    itunes_lookup_enabled: bool = True

    overlay_port: int = 8347
    overlay_text_color: str = "#ffffff"
    overlay_bg_color: str = "#000000"
    overlay_panel_width: int = 900
    overlay_idle_text: str = ""
    overlay_idle_font_size: int = 48
    overlay_custom_font_path: str = ""  # deprecated - kept only so old config.json files still load; see overlay_font_family
    overlay_font_family: str = ""  # a filename in the appdata font library (see fonts.py), or "" for the built-in default
    overlay_layout: str = "left"  # left | right | none | artonly
    overlay_bg_opacity: int = 100
    overlay_song_font_size: int = 74
    overlay_artist_font_size: int = 68
    overlay_charter_font_size: int = 60
    overlay_song_y_offset: int = 0
    overlay_artist_y_offset: int = 0
    overlay_charter_y_offset: int = 0
    overlay_scroll_speed: int = 100
    overlay_scroll_pause_seconds: int = 2

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid})


_lock = threading.Lock()


def load_settings() -> Settings:
    path = CONFIG_FILE()
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Migrate the old mandatory "output_image" setting into the new
            # optional "export_art_path" - anyone who had this configured
            # for a plain OBS Image Source keeps working without having to
            # re-enter the path.
            if data.get("output_image") and not data.get("export_art_path"):
                data["export_art_path"] = data["output_image"]
            return Settings.from_dict(data)
        except Exception:
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    path = CONFIG_FILE()
    with _lock:
        tmp = path.with_suffix(".json.new")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)
        os.replace(tmp, path)
