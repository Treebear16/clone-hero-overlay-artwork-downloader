"""Polls the Clone Hero song file for changes and drives artwork updates,
mirroring the ps1's $timer.Add_Tick block."""
import os
import threading
import time

from .artwork import resize_image_to_square, start_itunes_lookup_async

POLL_INTERVAL_SECONDS = 0.5


def parse_song_file(path: str):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.strip() for ln in f if ln.strip() != ""]

    if not lines:
        return None

    if len(lines) >= 2:
        # Confirmed CH format: line 1 = Song Name, line 2 = Artist,
        # line 3 (if present) = Charter.
        charter = lines[2] if len(lines) >= 3 else ""
        return {"song": lines[0], "artist": lines[1], "charter": charter}

    parts = lines[0].split(" - ", 1)
    if len(parts) == 2:
        return {"artist": parts[0].strip(), "song": parts[1].strip(), "charter": ""}
    return {"artist": "", "song": lines[0], "charter": ""}


class Watcher:
    def __init__(self, settings_getter, now_playing, logger, library_index):
        """settings_getter: zero-arg callable returning the current Settings
        (so live setting changes from the control panel apply on the next
        tick without restarting the watcher)."""
        self._settings_getter = settings_getter
        self.now_playing = now_playing
        self.logger = logger
        self.library_index = library_index

        self._thread = None
        self._stop_event = threading.Event()
        self._last_key = ""
        self._last_mtime = None
        self.running = False

    def _show_default_image(self, settings):
        if settings.default_image and os.path.isfile(settings.default_image):
            try:
                resize_image_to_square(
                    settings.default_image, settings.output_image, settings.target_size, settings.overlay_bg_color
                )
            except (OSError, ValueError) as exc:
                self.logger.log(f"Couldn't load default image: {exc}")
        self.now_playing.update(art_path=settings.output_image)
        self.now_playing.bump_token()

    def start(self):
        if self.running:
            return
        settings = self._settings_getter()
        if not settings.song_file or not os.path.isfile(settings.song_file):
            raise ValueError("Song file path is not set or doesn't exist.")
        if not settings.output_image:
            raise ValueError("Output image path is not set.")

        self._stop_event.clear()
        self._last_key = ""
        self._last_mtime = None
        self._show_default_image(settings)

        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.running = True
        self.logger.log(f"Started watching '{settings.song_file}'")

    def stop(self):
        if not self.running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.running = False
        self.logger.log("Stopped watching.")

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as exc:  # keep the watcher alive across transient errors
                self.logger.log(f"Watcher error: {exc}")
            self._stop_event.wait(POLL_INTERVAL_SECONDS)

    def _tick(self):
        settings = self._settings_getter()
        song_file = settings.song_file
        if not song_file or not os.path.isfile(song_file):
            return

        mtime = os.stat(song_file).st_mtime_ns
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime

        try:
            info = parse_song_file(song_file)
        except OSError as exc:
            self.logger.log(f"Couldn't read song file: {exc}")
            return

        if not info or not info.get("song"):
            if self._last_key != "":
                self._last_key = ""
                self.logger.log("No song playing - showing default image")
                self._show_default_image(settings)
            return

        key = f"{info['artist']}|{info['song']}"
        if key == self._last_key:
            return
        self._last_key = key

        self.logger.log(f"Now playing: {info['song']} - {info['artist']}")

        self.now_playing.update(
            song=info["song"],
            artist=info["artist"],
            charter=info["charter"],
            art_path=settings.output_image,
            song_key=key,
        )
        self.now_playing.bump_token()

        local_art = self.library_index.get_local_album_art(info["artist"], info["song"])
        if local_art:
            try:
                resize_image_to_square(
                    local_art, settings.output_image, settings.target_size, settings.overlay_bg_color
                )
                self.logger.log("  -> found local album art in song folder")
                return
            except (OSError, ValueError) as exc:
                self.logger.log(f"  -> local art found but failed to load, using default image instead: {exc}")
        elif settings.itunes_lookup_enabled:
            self.logger.log("  -> no local album art found, showing default image while iTunes is checked in the background")
        else:
            self.logger.log("  -> no local album art found, showing default image")

        if settings.default_image and os.path.isfile(settings.default_image):
            try:
                resize_image_to_square(
                    settings.default_image, settings.output_image, settings.target_size, settings.overlay_bg_color
                )
            except (OSError, ValueError):
                pass

        if settings.itunes_lookup_enabled:
            start_itunes_lookup_async(
                info["artist"],
                info["song"],
                settings.output_image,
                settings.target_size,
                key,
                self.now_playing,
                self.logger,
                settings.overlay_bg_color,
            )
