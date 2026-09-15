"""Image pipeline (center-crop to square + flatten transparency onto the
configured bg color) and the iTunes Search API fallback lookup, mirroring
Resize-ImageToSquare / Get-AlbumArtUrl / Start-ItunesLookupAsync from the
ps1."""
import os
import threading

import requests
from PIL import Image

from .library import clean_tag, normalize_text

ITUNES_TIMEOUT = 10
ITUNES_DOWNLOAD_TIMEOUT = 15


def _hex_to_rgb(hex_color: str):
    h = (hex_color or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return (0, 0, 0)


def resize_image_to_square(source_path: str, dest_path: str, size: int, bg_color_hex: str = "#000000"):
    """Reads source_path read-only, never touches the caller's library
    folder. Writes dest_path atomically (tmp file + os.replace) so nothing
    reading it (OBS, the overlay's /art endpoint) ever sees a half-written
    file."""
    with open(source_path, "rb") as f:
        img = Image.open(f)
        img.load()

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, _hex_to_rgb(bg_color_hex))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    w, h = img.size
    crop_size = min(w, h)
    x = (w - crop_size) // 2
    y = (h - crop_size) // 2
    img = img.crop((x, y, x + crop_size, y + crop_size))
    img = img.resize((size, size), Image.LANCZOS)

    tmp_path = dest_path + ".new"
    img.save(tmp_path, "JPEG", quality=92)
    os.replace(tmp_path, dest_path)


def _get_album_art_url(artist: str, song: str):
    clean_artist = clean_tag(artist)
    clean_song = clean_tag(song)
    target_artist = normalize_text(clean_artist)
    target_song = normalize_text(clean_song)

    try:
        artist_id = None
        if target_artist:
            r = requests.get(
                "https://itunes.apple.com/search",
                params={"term": clean_artist, "entity": "musicArtist", "limit": 5},
                timeout=ITUNES_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            for a in results:
                if normalize_text(a.get("artistName", "")) == target_artist:
                    artist_id = a.get("artistId")
                    break
            if not artist_id:
                for a in results:
                    n = normalize_text(a.get("artistName", ""))
                    if n and (n in target_artist or target_artist in n):
                        artist_id = a.get("artistId")
                        break

        if artist_id:
            r = requests.get(
                "https://itunes.apple.com/lookup",
                params={"id": artist_id, "entity": "song", "limit": 200},
                timeout=ITUNES_TIMEOUT,
            )
            r.raise_for_status()
            songs = [s for s in r.json().get("results", []) if s.get("wrapperType") == "track"]
            for s in songs:
                if normalize_text(s.get("trackName", "")) == target_song:
                    return s.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
            for s in songs:
                sn = normalize_text(s.get("trackName", ""))
                if sn and (sn in target_song or target_song in sn):
                    return s.get("artworkUrl100", "").replace("100x100bb", "600x600bb")

        r = requests.get(
            "https://itunes.apple.com/search",
            params={"term": f"{clean_artist} {clean_song}", "entity": "song", "limit": 10},
            timeout=ITUNES_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("resultCount", 0) == 0:
            return None

        best = None
        if target_artist:
            for res in data["results"]:
                if normalize_text(res.get("artistName", "")) == target_artist:
                    best = res
                    break
            if not best:
                for res in data["results"]:
                    ra = normalize_text(res.get("artistName", ""))
                    if ra and (ra in target_artist or target_artist in ra):
                        best = res
                        break
        if not best:
            return None
        return best.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
    except requests.RequestException:
        return None


def start_itunes_lookup_async(artist, song, output_image, target_size, song_key, now_playing, logger, bg_color_hex):
    """Runs the iTunes lookup + download + resize on a background thread, so
    it never blocks the watcher loop. Bails out if the user has already
    moved on to a different song by the time it finishes."""

    def _run():
        art_url = _get_album_art_url(artist, song)
        if not art_url:
            logger.log(f"  -> no iTunes match found for '{song}' by '{artist}'")
            return

        if now_playing.song_key != song_key:
            return

        tmp_path = output_image + ".itunes.tmp"
        try:
            r = requests.get(art_url, timeout=ITUNES_DOWNLOAD_TIMEOUT)
            r.raise_for_status()
            with open(tmp_path, "wb") as f:
                f.write(r.content)

            if now_playing.song_key != song_key:
                return

            resize_image_to_square(tmp_path, output_image, target_size, bg_color_hex)
            now_playing.update(art_path=output_image)
            now_playing.bump_token()
            logger.log(f"  -> iTunes artwork applied for '{song}' by '{artist}'")
        except (requests.RequestException, OSError) as exc:
            logger.log(f"  -> iTunes lookup failed for '{song}' by '{artist}': {exc}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
