#!/usr/bin/env python3
"""
make_share_images.py

Generates the link-preview image (og-image.png, shown when the site link is
texted or posted) and the home-screen icon (apple-touch-icon.png). Only
needs re-running if the design or wording changes. Uses macOS fonts when
present, otherwise Liberation Sans + Noto Color Emoji (Linux).

Usage (from the repo root):
    python3 scripts/make_share_images.py
"""

import os

from PIL import Image, ImageDraw, ImageFont

# MN Select club colors (match index.html)
CRIMSON = (163, 28, 48)
CARD = (255, 255, 255)
TEXT = (27, 27, 27)
DIM = (93, 93, 100)
ON_RED_DIM = (245, 214, 219)


def first(*paths):
    return next(p for p in paths if os.path.exists(p))


BOLD = first("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")
REGULAR = first("/System/Library/Fonts/Supplemental/Arial.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")
EMOJI, EMOJI_SIZE = (("/System/Library/Fonts/Apple Color Emoji.ttc", 160)
                     if os.path.exists("/System/Library/Fonts/Apple Color Emoji.ttc")
                     else ("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109))


def emoji(size):
    # Color emoji fonts only render at their bitmap size, so draw at that
    # size and scale.
    font = ImageFont.truetype(EMOJI, EMOJI_SIZE)
    tile = Image.new("RGBA", (EMOJI_SIZE + 40, EMOJI_SIZE + 40), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((10, 10), "\U0001F3D0", font=font, embedded_color=True)
    tile = tile.crop(tile.getbbox())
    return tile.resize((size, size), Image.LANCZOS)


def share_card():
    img = Image.new("RGB", (1200, 630), CRIMSON)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, 70, 1140, 560], radius=28, fill=CARD)
    img.paste(ball := emoji(150), (950, 110), ball)
    d.text((110, 120), "MN SELECT 18-1 ALUMNI", font=ImageFont.truetype(BOLD, 34), fill=CRIMSON)
    title = ImageFont.truetype(BOLD, 76)
    d.text((110, 185), "College Volleyball", font=title, fill=TEXT)
    d.text((110, 275), "Schedules", font=title, fill=TEXT)
    sub = ImageFont.truetype(REGULAR, 34)
    d.text((110, 395), "Every game for our former players,", font=sub, fill=DIM)
    d.text((110, 440), "with times in your time zone.", font=sub, fill=DIM)
    d.text((110, 575), "mnselectboys.tuckerpearcecreative.com",
           font=ImageFont.truetype(REGULAR, 26), fill=ON_RED_DIM)
    img.save("og-image.png", optimize=True)


def touch_icon():
    img = Image.new("RGB", (180, 180), CRIMSON)
    img.paste(ball := emoji(130), (25, 25), ball)
    img.save("apple-touch-icon.png", optimize=True)


if __name__ == "__main__":
    share_card()
    touch_icon()
    print("Wrote og-image.png and apple-touch-icon.png")
