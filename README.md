# CHOAD (Python) — Clone Hero Overlay Artwork Downloader

A cross-platform rewrite of the original PowerShell/WinForms CHOAD. Same
core job: watch Clone Hero's current-song file, find album art (locally
first, then iTunes as a fallback), and serve an OBS browser-source overlay
with scrolling song/artist/charter text.

## What changed from the PS1 version

- **No native GUI toolkit.** Settings are a web page (Flask) you open in
  your normal browser — works identically on Windows/macOS/Linux, no
  WinForms/Qt dependency.
- **Runs from the system tray.** A tray icon gives you Open Control Panel /
  Start-Stop Watching / Quit. `--no-tray` runs it headless (e.g. on a
  server or if you don't want a tray icon).
- Song watching, library indexing (with the same incremental song.ini
  cache), local art lookup, iTunes fallback, and the image crop/resize
  pipeline are all ported 1:1 in behavior.
- The OBS overlay page itself (`/overlay`) is the **exact same HTML/CSS/JS**
  from the original, byte-for-byte, including the embedded Lato font — it
  didn't need to change, since it was always just a browser page polling
  a JSON endpoint.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`

## Running

```
python -m choad
```

This starts the local web server (default port 8347, configurable in the
control panel) and shows a tray icon. Click the tray icon → **Open Control
Panel**, or just go to `http://127.0.0.1:8347/` in your browser.

- **Control panel:** `http://127.0.0.1:8347/`
- **OBS Browser Source URL:** `http://127.0.0.1:8347/overlay` (add this as
  a Browser Source in OBS, sized to roughly `300 + panel width` x `300`)

Headless (no tray icon, e.g. on Linux without a desktop session):

```
python -m choad --no-tray
```

## Settings

Everything the original app had a field for is in the control panel:
song file, output image, default image, songs library folder(s)
(semicolon-separated, same as before), target art size, iTunes toggle,
and the full overlay customization set (colors, layout, panel width,
per-row font sizes, scroll speed/pause, idle text, custom font file).

Settings persist to the same kind of per-user config directory the
original used, just cross-platform:

- Windows: `%LOCALAPPDATA%\CHOAD\config.json`
- macOS: `~/Library/Application Support/CHOAD/config.json`
- Linux: `~/.config/CHOAD/config.json`

The library index cache lives alongside it (`library-cache.json`).

## Packaging into a standalone, double-click executable

### Using your own icon instead of the default badge

By default the app icon (tray icon + the built .exe/.app's file icon) is a
purple "CH"/"OAD" badge drawn in code (`choad/branding.py`). To use your
own image instead: drop a square PNG at `assets/icon_source.png` (512x512
or bigger, transparent background is fine — non-square images get
center-cropped automatically). That's it — no code changes. It's picked
up automatically by:
- the live tray icon (bundled into the build so it still shows up when frozen)
- `scripts/build_icons.py`, which generates `.ico`/`.icns`/`.png` from it
  instead of the drawn badge

Delete `assets/icon_source.png` to fall back to the generated badge again.
If you just want a different color on the same badge design, it's a
one-line change: `ACCENT` near the top of `choad/branding.py`.

End users never need Python or a terminal — they just run the built
`CHOAD.exe` / `CHOAD.app` / `CHOAD` file, and the tray icon appears.

**Option A — build it yourself, once per OS** (PyInstaller can't
cross-compile, so this has to run natively on each target OS):

```
pip install -r requirements.txt
pip install pyinstaller
python scripts/build_icons.py   # generates assets/icon.ico / .icns / .png
pyinstaller --noconfirm choad.spec
```

**Important:** run `pip install -r requirements.txt` first, in the same
environment you run `pyinstaller` from. PyInstaller only bundles packages
it finds already installed — if `pystray` (or Flask, Pillow, requests)
isn't installed at build time, PyInstaller leaves it out *silently* (no
build error), and you only find out when the built exe crashes on launch
with `ModuleNotFoundError: No module named 'pystray'`. If you hit that,
it means requirements weren't installed when you ran `pyinstaller` —
reinstall them and rebuild.

Output lands in `dist/` — `CHOAD.exe` (Windows), `CHOAD.app` (macOS), or
`CHOAD` (Linux). `choad.spec` already sets `--onefile`/no-console and the
right icon per platform, so you don't need to pass those flags by hand.

**Option B — let GitHub build all three for you** (`.github/workflows/build.yml`
is already set up for this — one-time setup, then it's automatic):

1. Push this project to `https://github.com/Treebear16/clone-hero-overlay-artwork-downloader`.
2. Tag a release and push the tag:
   ```
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions builds Windows, macOS, and Linux executables in the cloud
   and attaches them to a Release on that repo automatically. You (and
   anyone else) can then just download the right file from the Releases
   page and double-click it — no terminal, no build step, ever, for the
   end user.

Every push to `main` also runs the build (without publishing a Release) so
you can catch a broken build before tagging.

## Project layout

```
choad/
  config.py     - settings load/save, cross-platform config dir
  version.py    - APP_VERSION, bump this alongside each release tag
  updater.py    - background GitHub Releases check for a newer version
  state.py      - NowPlaying (shared with the overlay HTTP thread) + Logger
  library.py    - song.ini indexing with incremental cache, local art lookup
  artwork.py    - image crop/resize/flatten, iTunes Search API lookup
  watcher.py    - polls the song file, drives the pipeline
  webapp.py     - Flask app: overlay endpoints + control panel + JSON API
  tray.py       - system tray icon (pystray)
  branding.py   - the "CH"/"OAD" badge, drawn in code (tray icon + app icon)
  main.py       - wires it all together
  templates/
    overlay.html  - the OBS browser-source page (ported as-is from the ps1)
    control.html  - the settings/control panel page
run.py          - PyInstaller entry point (see note in the file)
choad.spec      - PyInstaller build config (onefile, no console, per-OS icon)
scripts/build_icons.py - generates assets/icon.{ico,icns,png}
.github/workflows/build.yml - CI build for all 3 OSes + auto-release on tag
```

## Auto-update checks

Once you've pushed this to a GitHub repo (see Packaging above), CHOAD can
check that repo's Releases for a newer version automatically — in the
background, once at startup and then once a day — and surface it as a
banner in the control panel and a tray menu item, both linking straight to
the right download for your OS.

Already pointed at `Treebear16/clone-hero-overlay-artwork-downloader` in
`choad/updater.py` (`GITHUB_REPO`) — nothing to configure. It'll just
return "no update" (silently) until that repo actually has a Release with
a tag newer than `APP_VERSION`, which happens automatically the first time
you push a `vX.Y.Z` tag (see Packaging above).

**Per-release step:** bump `APP_VERSION` in `choad/version.py` before you
tag each release, so it matches the tag you're about to push (e.g.
`APP_VERSION = "1.1.0"` before tagging `v1.1.0`) — that's how the updater
tells "newer" from "same".

This only works for a public repo (or one your users can already reach),
since it's just hitting the public GitHub Releases API — no server, no
account needed.

**What this deliberately does NOT do:** silently download and swap out the
running executable. A PyInstaller onefile binary is locked while it's
running (Windows won't let you overwrite it in place), and getting a
self-replace-and-relaunch sequence right on all three OSes without being
able to test it against the actual built binaries risks bricking someone's
install for the sake of skipping one click. So it's "automatically checks,
one click to grab the new version" rather than fully silent — a reasonable
middle ground, but say the word if you'd rather I build out true in-place
self-updating (it's doable, just wants real testing on each OS as we go).

## Notes / things worth knowing

- Only `album.png`/`album.jpg`/`album.jpeg` are recognized as local art,
  same as the original.
- The library scan/cache never writes into your song folders — read-only,
  same guarantee as the ps1.
- The overlay's `/art` endpoint always serves whatever is currently at
  `output_image`, refetched every second by the overlay page itself —
  point OBS's browser source at `/overlay`, not directly at the image file.
