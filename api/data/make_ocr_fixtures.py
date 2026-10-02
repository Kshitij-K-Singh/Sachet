"""Render synthetic promo screenshots for OCR fixtures.

Run once (or after text changes):
  .venv/bin/python data/make_ocr_fixtures.py
Output: data/fixtures/shot_en.png, shot_hi.png (committed to the repo so
tests are reproducible without font/network access at test time).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "fixtures"
OUT.mkdir(exist_ok=True)

LATIN = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
DEVA = "/usr/share/fonts/noto/NotoSansDevanagari-Medium.ttf"

BG = (18, 15, 11)
ACCENT = (233, 90, 43)
WHITE = (245, 241, 232)


def render(lines: list[tuple[str, tuple[int, int, int]]], font_path: str, out: Path) -> None:
    font = ImageFont.truetype(font_path, 44)
    W, H = 900, 320
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    y = 48
    for text, color in lines:
        draw.text((60, y), text, font=font, fill=color)
        y += 72
    draw.rectangle([0, 0, W - 1, H - 1], outline=ACCENT, width=4)
    img.save(out)
    print("wrote", out)


render(
    [
        ("Guaranteed returns!", ACCENT),
        ("Double your money in 30 days.", WHITE),
        ("Join our premium group now.", WHITE),
    ],
    LATIN,
    OUT / "shot_en.png",
)
render(
    [
        ("पक्का मुनाफा!", ACCENT),
        ("30 दिन में पैसा डबल।", WHITE),
        ("अभी हमारा प्रीमियम ग्रुप जॉइन करें।", WHITE),
    ],
    DEVA,
    OUT / "shot_hi.png",
)
