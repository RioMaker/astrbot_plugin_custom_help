"""A shared, offline PNG renderer for chat delivery and the editor preview."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1000
PAGE_HEIGHT = 4800
MARGIN = 58
FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "NotoSansSC-Regular.otf"


def plugin_list(profile):
    items = [i for i in profile["items"] if i["enabled"]]
    listing = (
        "\n".join(f"{n:02d}  {item['title']}" for n, item in enumerate(items, 1))
        or "本群暂未开启插件帮助。"
    )
    template = profile["list_text"]
    return (
        template.replace("{plugins}", listing)
        if "{plugins}" in template
        else f"{template}\n{listing}".strip()
    )


def format_text(profile):
    parts = [
        profile["title"],
        profile["intro"],
        profile["list_title"],
        plugin_list(profile),
    ]
    parts.extend(f"{i['title']}\n{i['body']}" for i in profile["items"] if i["enabled"])
    parts.append(profile["footer"])
    return "\n\n".join(p for p in parts if p)


def _wrap(text, font, width):
    # Character wrapping also handles long unbroken commands, URLs and CJK.
    for paragraph in text.replace("\t", "    ").split("\n"):
        if not paragraph:
            yield ""
            continue
        line = ""
        for char in paragraph:
            if line and font.getlength(line + char) > width:
                yield line
                line = char
            else:
                line += char
        yield line


def render_help(profile, group_name="") -> list[bytes]:
    fonts = {
        size: ImageFont.truetype(str(FONT_PATH), size) for size in (23, 27, 32, 44)
    }
    rows = []

    def add(text, size=27, kind="body"):
        if text:
            rows.extend(
                (line, size, kind)
                for line in _wrap(
                    text,
                    fonts[size],
                    WIDTH - MARGIN * 2 - (28 if kind == "section" else 0),
                )
            )

    add(profile["title"], 44, "title")
    add(group_name or "默认帮助", 23, "muted")
    add(profile["intro"], 27)
    rows.append(("", 23, "gap"))
    add(profile["list_title"], 32, "section")
    add(plugin_list(profile))
    for index, item in enumerate((i for i in profile["items"] if i["enabled"]), 1):
        rows.append(("", 23, "gap"))
        add(f"{index:02d}  {item['title']}", 32, "section")
        add(item["body"] or "暂无说明。")
    rows.append(("", 23, "gap"))
    add(profile["footer"], 23, "muted")

    def height(row):
        return row[1] + (28 if row[2] in ("title", "section") else 14)

    pages, current, used = [], [], MARGIN
    for index, row in enumerate(rows):
        extra = (
            height(rows[index + 1])
            if row[2] == "section" and index + 1 < len(rows)
            else 0
        )
        if current and used + height(row) + extra > PAGE_HEIGHT - 90:
            pages.append(current)
            current, used = [], MARGIN
        current.append(row)
        used += height(row)
    if current:
        pages.append(current)
    results = []
    colors = {
        "title": "#143F40",
        "section": "#17675E",
        "body": "#263C40",
        "muted": "#617371",
        "gap": "#617371",
    }
    for page_index, page in enumerate(pages, 1):
        total_height = MARGIN + sum(height(row) for row in page) + 90
        canvas = Image.new("RGB", (WIDTH, total_height), "#F8FAF7")
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, WIDTH, 12), fill="#258979")
        y = MARGIN
        for line, size, kind in page:
            if kind == "section":
                draw.rounded_rectangle(
                    (MARGIN - 14, y - 6, WIDTH - MARGIN + 14, y + size + 16),
                    radius=10,
                    fill="#E4EFEB",
                )
            draw.text(
                (MARGIN, y), line, font=fonts[size], fill=colors[kind], anchor="lt"
            )
            y += height((line, size, kind))
        draw.line(
            (MARGIN, total_height - 64, WIDTH - MARGIN, total_height - 64),
            fill="#D7E2DC",
            width=2,
        )
        draw.text(
            (WIDTH - MARGIN, total_height - 48),
            f"{page_index} / {len(pages)}",
            font=fonts[23],
            fill="#617371",
            anchor="rt",
        )
        output = BytesIO()
        canvas.save(output, "PNG")
        results.append(output.getvalue())
    return results
