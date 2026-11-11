"""Inline pictographs for characters absent from the installed text fonts."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

CHOCOLATE_PATH = Path(__file__).parent / "assets" / "emoji" / "chocolate.png"
# Keep the presentation selector attached when wrapping or drawing the symbol.
_SYMBOL = re.compile("(🍫[\ufe0e\ufe0f]?)")


def text_units(text):
    """Yield original characters, except pictographs and their selectors stay whole."""
    for run in _SYMBOL.split(text):
        if run.startswith("🍫"):
            yield run
        else:
            yield from run


def text_width(text, font):
    if "🍫" not in text:
        return font.getlength(text)
    return sum(
        font.size if run.startswith("🍫") else font.getlength(run)
        for run in _SYMBOL.split(text)
    )


@lru_cache(maxsize=32)
def _chocolate(size):
    # A bundled PNG works on Linux/Windows without system emoji fonts or RAQM.
    with Image.open(CHOCOLATE_PATH) as source:
        return source.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


def draw_text(image, xy, text, *, font, fill, anchor="lt"):
    if "🍫" not in text:
        ImageDraw.Draw(image).text(xy, text, font=font, fill=fill, anchor=anchor)
        return
    runs = _SYMBOL.split(text)
    plain = "".join(run for run in runs if not run.startswith("🍫"))
    bounds = font.getbbox(plain or "国", anchor="ls")
    text_height = bounds[3] - bounds[1]
    height = max(font.size, text_height)
    width = text_width(text, font)
    # Share one baseline across text runs, including Latin descenders. The image
    # occupies exactly the advance used by wrapping; original spaces stay intact.
    layer = Image.new("RGBA", (math.ceil(width) + 2, height))
    draw = ImageDraw.Draw(layer)
    baseline = (height - text_height) / 2 - bounds[1]
    cursor = 0.0
    for run in runs:
        if run.startswith("🍫"):
            icon = _chocolate(font.size)
            layer.alpha_composite(icon, (round(cursor), (height - font.size) // 2))
            cursor += font.size
        elif run:
            draw.text((cursor, baseline), run, font=font, fill=fill, anchor="ls")
            cursor += font.getlength(run)
    x, y = xy
    if anchor == "mm":
        x, y = x - width / 2, y - height / 2
    elif anchor != "lt":
        raise ValueError("Inline pictographs support lt or mm anchors")
    image.paste(layer, (round(x), round(y)), layer)
