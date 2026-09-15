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


@dataclass
class Settings:
    current_song_file: str = ""  # the currentsong.txt Clone Hero itself writes while a song is playing
    output_image: str = ""  # the art file this app writes, for OBS's Image Source to point at
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
    overlay_custom_font_path: str = ""
    overlay_layout: str = "left"  # left | right | none | artonly
    overlay_bg_opacity: int = 100
    overlay_song_font_size: int = 74
    overlay_artist_font_size: int = 68
    overlay_charter_font_size: int = 60
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
                return Settings.from_dict(json.load(f))
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
