"""Local Clone Hero library indexing: scans song.ini files to build a
(normalized artist|song) -> folder index, with an incremental cache keyed
on each song folder's song.ini mtime, mirroring the ps1's
Get-LibrarySignature / Get-LibraryChanges / Build-LibraryIndex."""
import json
import os
import re
import threading

from .config import LIBRARY_CACHE_FILE

_NAME_RE = re.compile(r"^\s*name\s*=\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_ARTIST_RE = re.compile(r"^\s*artist\s*=\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_ALBUM_ART_RE = re.compile(r"^album\.(png|jpg|jpeg)$", re.IGNORECASE)
_FEAT_RE = re.compile(r"\bfeat\.?\b", re.IGNORECASE)
_FT_RE = re.compile(r"\bft\.?\b", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")


def normalize_text(text: str) -> str:
    t = (text or "").lower()
    t = _FEAT_RE.sub("", t)
    t = _FT_RE.sub("", t)
    t = t.replace("&", "and")
    return _NON_ALNUM_RE.sub("", t)


def clean_tag(text: str) -> str:
    cleaned = re.sub(r"\(.*?\)", "", text or "")
    cleaned = re.sub(r"\[.*?\]", "", cleaned)
    return cleaned.strip()


def key_for(artist: str, song: str) -> str:
    return f"{normalize_text(artist)}|{normalize_text(song)}"


def get_library_roots(root_setting: str):
    """Supports multiple folders separated by semicolons."""
    if not root_setting or not root_setting.strip():
        return []
    roots = []
    for part in root_setting.split(";"):
        p = part.strip()
        if p and os.path.isdir(p):
            roots.append(p)
    # unique, preserve order
    seen = set()
    out = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _scan_signature(roots, on_progress=None):
    """folder -> song.ini mtime (ns), for every song.ini under the roots.
    Only stats files, never reads content - cheap even on huge libraries."""
    sig = {}
    scanned = 0
    for root in sorted(roots):
        for dirpath, _dirnames, filenames in os.walk(root):
            if "song.ini" in filenames:
                ini_path = os.path.join(dirpath, "song.ini")
                try:
                    sig[dirpath] = os.stat(ini_path).st_mtime_ns
                except OSError:
                    continue
                scanned += 1
                if on_progress and scanned % 500 == 0:
                    on_progress(scanned)
    if on_progress:
        on_progress(scanned)
    return sig


def _parse_song_ini(folder: str):
    ini_path = os.path.join(folder, "song.ini")
    try:
        with open(ini_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return None
    name_m = _NAME_RE.search(content)
    artist_m = _ARTIST_RE.search(content)
    if not (name_m and artist_m):
        return None
    return name_m.group(1).strip(), artist_m.group(1).strip()


def _build_index(folders, on_progress=None):
    index = {}
    scanned = 0
    found = 0
    for folder in folders:
        scanned += 1
        parsed = _parse_song_ini(folder)
        if parsed:
            song_name, artist_name = parsed
            index[key_for(artist_name, song_name)] = folder
            found += 1
        if on_progress and scanned % 100 == 0:
            on_progress(scanned, found)
    if on_progress:
        on_progress(scanned, found)
    return index


def _load_cache():
    path = LIBRARY_CACHE_FILE()
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(roots, signature, index):
    path = LIBRARY_CACHE_FILE()
    try:
        tmp = path.with_suffix(".json.new")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"roots": sorted(roots), "signature": signature, "index": index},
                f,
            )
        os.replace(tmp, path)
    except OSError:
        pass


class LibraryIndex:
    """Holds the in-memory index and (re)builds it incrementally, matching
    the ps1's cache-diff behaviour: only song folders whose song.ini mtime
    changed since last run get re-parsed."""

    def __init__(self, logger=None):
        self._lock = threading.Lock()
        self.index = {}
        self._logger = logger

    def _log(self, msg):
        if self._logger:
            self._logger.log(msg)

    def refresh(self, songs_library_folder: str, force: bool = False, progress_cb=None):
        roots = get_library_roots(songs_library_folder)
        if not roots:
            with self._lock:
                self.index = {}
            return

        current_sig = _scan_signature(roots, on_progress=progress_cb)
        cache = None if force else _load_cache()

        cached_sig = (cache or {}).get("signature", {}) if cache else {}
        cached_index = (cache or {}).get("index", {}) if cache else {}
        cached_roots = sorted((cache or {}).get("roots", [])) if cache else []

        if force or cached_roots != sorted(roots):
            changed = list(current_sig.keys())
            unchanged = []
        else:
            changed = [f for f, mtime in current_sig.items() if cached_sig.get(f) != mtime]
            unchanged = [f for f in current_sig.keys() if f not in changed]

        if not changed and cache is not None:
            with self._lock:
                self.index = dict(cached_index)
            self._log(f"Song library unchanged - loaded {len(self.index)} songs from cache instantly.")
            return

        self._log(
            f"Song library changed - {len(changed)} new/changed song(s) found out of "
            f"{len(cached_index)} previously indexed, updating..."
        )

        reverse = {}
        for k, folder in cached_index.items():
            reverse[folder] = k

        new_index = {}
        for folder in unchanged:
            if folder in reverse:
                new_index[reverse[folder]] = folder

        new_entries = _build_index(changed, on_progress=progress_cb)
        new_index.update(new_entries)

        with self._lock:
            self.index = new_index

        self._log(f"Index updated - {len(new_index)} songs with local artwork lookup available.")
        _save_cache(roots, current_sig, new_index)

    def get_local_album_art(self, artist: str, song: str):
        with self._lock:
            if not self.index:
                return None
            folder = self.index.get(key_for(artist, song))
        if not folder or not os.path.isdir(folder):
            return None
        try:
            for name in os.listdir(folder):
                if _ALBUM_ART_RE.match(name):
                    return os.path.join(folder, name)
        except OSError:
            return None
        return None

    def __len__(self):
        with self._lock:
            return len(self.index)
