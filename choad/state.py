"""Thread-safe shared state: the 'now playing' info served to the overlay,
and a small ring-buffer log the web control panel polls."""
import threading
import time
import collections


class NowPlaying:
    """Mirrors the original $script:NowPlaying synchronized hashtable -
    written by the watcher thread, read by the Flask request threads."""

    def __init__(self):
        self._lock = threading.RLock()
        self.song = ""
        self.artist = ""
        self.charter = ""
        self.art_path = ""
        self.token = 0
        self.song_key = ""
        # style/config fields, mirrored from Settings so /nowplaying can
        # hand them to the overlay page in one response, same as the ps1.
        self.text_color = "#ffffff"
        self.bg_color = "#000000"
        self.panel_width = 900
        self.idle_text = ""
        self.idle_font_size = 48
        self.custom_font_path = ""
        self.layout = "left"
        self.bg_opacity = 100
        self.song_font_size = 74
        self.artist_font_size = 68
        self.charter_font_size = 60
        self.scroll_speed = 100
        self.scroll_pause_seconds = 2

    def update(self, **kwargs):
        with self._lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def bump_token(self):
        with self._lock:
            self.token += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "song": self.song,
                "artist": self.artist,
                "charter": self.charter,
                "token": self.token,
                "textColor": self.text_color,
                "bgColor": self.bg_color,
                "panelWidth": self.panel_width,
                "idleText": self.idle_text,
                "idleFontSize": self.idle_font_size,
                "customFontPath": self.custom_font_path,
                "layout": self.layout,
                "bgOpacity": self.bg_opacity,
                "songFontSize": self.song_font_size,
                "artistFontSize": self.artist_font_size,
                "charterFontSize": self.charter_font_size,
                "scrollSpeed": self.scroll_speed,
                "scrollPauseSeconds": self.scroll_pause_seconds,
            }

    def apply_settings(self, settings):
        """Push overlay-styling fields from Settings into NowPlaying - the
        overlay page picks these up on its next 1s poll."""
        with self._lock:
            self.text_color = settings.overlay_text_color
            self.bg_color = settings.overlay_bg_color
            self.panel_width = settings.overlay_panel_width
            self.idle_text = settings.overlay_idle_text
            self.idle_font_size = settings.overlay_idle_font_size
            self.custom_font_path = settings.overlay_custom_font_path
            self.layout = settings.overlay_layout
            self.bg_opacity = settings.overlay_bg_opacity
            self.song_font_size = settings.overlay_song_font_size
            self.artist_font_size = settings.overlay_artist_font_size
            self.charter_font_size = settings.overlay_charter_font_size
            self.scroll_speed = settings.overlay_scroll_speed
            self.scroll_pause_seconds = settings.overlay_scroll_pause_seconds


class Logger:
    """Small in-memory ring buffer the control panel polls (GET /api/log?since=N),
    equivalent to the ps1's log textbox."""

    def __init__(self, maxlen=1000):
        self._lock = threading.Lock()
        self._lines = collections.deque(maxlen=maxlen)
        self._next_id = 0

    def log(self, message: str):
        with self._lock:
            ts = time.strftime("%H:%M:%S")
            entry = {"id": self._next_id, "text": f"[{ts}] {message}"}
            self._next_id += 1
            self._lines.append(entry)
        print(entry["text"])

    def since(self, last_id: int):
        with self._lock:
            return [e for e in self._lines if e["id"] > last_id]
