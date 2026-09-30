#!/usr/bin/env python3
"""
make_share_images.py

Generates the link-preview image (og-image.png, shown when the site link is
texted or posted) and the home-screen icon (apple-touch-icon.png). Only
needs re-running if the design or wording changes. macOS fonts required.

Usage (from the repo root):
    python3 scripts/make_share_images.py
"""

from PIL import Image, ImageDraw, ImageFont

INK = (14, 26, 38)
PANEL = (20, 36, 51)
TEXT = (238, 242, 245)
DIM = (159, 176, 189)
AMBER = (232, 163, 61)
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"


def emoji(size):
    # Apple Color Emoji only renders at its bitmap size, so draw at 160
    # and scale.
    font = ImageFont.truetype(EMOJI, 160)
    tile = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((10, 10), "\U0001F3D0", font=font, embedded_color=True)
    return tile.resize((size, size), Image.LANCZOS)


def share_card():
    img = Image.new("RGB", (1200, 630), INK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1200, 12], fill=AMBER)
    d.rounded_rectangle([60, 70, 1140, 560], radius=28, fill=PANEL)
    img.paste(ball := emoji(150), (950, 110), ball)
    d.text((110, 120), "MN SELECT 18-1 ALUMNI", font=ImageFont.truetype(BOLD, 34), fill=AMBER)
    title = ImageFont.truetype(BOLD, 76)
    d.text((110, 185), "College Volleyball", font=title, fill=TEXT)
    d.text((110, 275), "Schedules", font=title, fill=TEXT)
    sub = ImageFont.truetype(REGULAR, 34)
    d.text((110, 395), "Every game for our former players,", font=sub, fill=DIM)
    d.text((110, 440), "with times in your time zone.", font=sub, fill=DIM)
    d.text((110, 575), "mnselectboys.tuckerpearcecreative.com",
           font=ImageFont.truetype(REGULAR, 26), fill=DIM)
    img.save("og-image.png", optimize=True)


def touch_icon():
    img = Image.new("RGB", (180, 180), INK)
    img.paste(ball := emoji(130), (25, 25), ball)
    img.save("apple-touch-icon.png", optimize=True)


if __name__ == "__main__":
    share_card()
    touch_icon()
    print("Wrote og-image.png and apple-touch-icon.png")
