"""Run once (or whenever the icon/badge design changes) to (re)generate the
icon files used by the PyInstaller build. Not needed at app runtime - the
tray icon is drawn/loaded live from choad/branding.py instead.

Uses assets/icon_source.png if you've dropped one there, otherwise falls
back to the generated 'CH'/'OAD' badge - see choad/branding.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from choad.branding import get_icon_image, load_custom_icon  # noqa: E402

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    img = get_icon_image(512)
    source = "assets/icon_source.png" if load_custom_icon(512) else "generated badge"
    print(f"using: {source}")

    png_path = os.path.join(ASSETS, "icon.png")
    img.save(png_path)
    print("wrote", png_path)

    ico_path = os.path.join(ASSETS, "icon.ico")
    img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", ico_path)

    icns_path = os.path.join(ASSETS, "icon.icns")
    try:
        img.save(icns_path, format="ICNS")
        print("wrote", icns_path)
    except Exception as exc:
        print(f"skipped icon.icns ({exc}) - Pillow's ICNS writer needs a newer Pillow; "
              f"the macOS CI build falls back to icon.png if this file is missing.")


if __name__ == "__main__":
    main()
