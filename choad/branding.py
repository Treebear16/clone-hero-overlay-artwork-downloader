"""Draws the 'CH'/'OAD' badge purely in code - mirrors New-BadgeIcon from
the ps1. Used both for the live tray icon and for pre-baking app icon files
for the PyInstaller build.

To use your own image instead of the generated badge, just drop a square
PNG at assets/icon_source.png (ideally 512x512+, transparent background is
fine) - get_icon_image() below picks it up automatically, both for the live
tray icon and for the .ico/.icns files scripts/build_icons.py generates.
No code changes needed; delete that file to fall back to the generated
badge again."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ACCENT = (88, 101, 242)  # change this to recolor the generated badge

_CUSTOM_ICON_RELATIVE_PATH = os.path.join("assets", "icon_source.png")


def _resource_path(relative_path):
    """Resolves a path relative to the project root when running from
    source, or PyInstaller's bundle dir when frozen."""
    base = getattr(sys, "_MEIPASS", None) or os.path.join(os.path.dirname(__file__), "..")
    return os.path.join(base, relative_path)


def make_badge_image(size=256):
    img = Image.new("RGBA", (size, size), ACCENT + (255,))
    draw = ImageDraw.Draw(img)
    lines = ["CH", "OAD"]

    font_size = int(size * 0.42)
    font = None
    while font_size > 8:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()
            break
        widths = [draw.textbbox((0, 0), ln, font=font)[2] for ln in lines]
        if max(widths) <= size * 0.82:
            break
        font_size -= 2

    heights = [draw.textbbox((0, 0), ln, font=font)[3] for ln in lines]
    total_h = sum(heights)
    y = (size - total_h) / 2
    for ln, h in zip(lines, heights):
        w = draw.textbbox((0, 0), ln, font=font)[2]
        draw.text(((size - w) / 2, y), ln, fill="white", font=font)
        y += h

    return img


def load_custom_icon(size=256):
    """Returns the user-supplied assets/icon_source.png, center-cropped to
    square and resized, or None if that file doesn't exist."""
    path = _resource_path(_CUSTOM_ICON_RELATIVE_PATH)
    if not os.path.isfile(path):
        return None
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    if w != h:
        crop_size = min(w, h)
        x = (w - crop_size) // 2
        y = (h - crop_size) // 2
        img = img.crop((x, y, x + crop_size, y + crop_size))
    return img.resize((size, size), Image.LANCZOS)


def get_icon_image(size=256):
    """What everything (tray icon, icon-file generator) should actually
    call - prefers a user-supplied image, falls back to the drawn badge."""
    return load_custom_icon(size) or make_badge_image(size)
