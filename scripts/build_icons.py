"""Run once (or whenever the badge design changes) to (re)generate the icon
files used by the PyInstaller build. Not needed at app runtime - the tray
icon is drawn live from choad/branding.py instead."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from choad.branding import make_badge_image  # noqa: E402

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    img = make_badge_image(512)

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
