"""Draws the 'CH'/'OAD' badge purely in code - mirrors New-BadgeIcon from
the ps1. Used both for the live tray icon and for pre-baking app icon files
for the PyInstaller build."""
from PIL import Image, ImageDraw, ImageFont

ACCENT = (88, 101, 242)


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
