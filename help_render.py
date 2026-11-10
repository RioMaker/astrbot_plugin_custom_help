"""Compose a technology index, Keko image-help cards and native plugin panels."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

if __package__:
    from .help_styles import HelpStyle, StyleReader, keko_style
else:
    from help_styles import HelpStyle, StyleReader, keko_style

WIDTH = 1080
PAGE_HEIGHT = 4800
MARGIN = 62
GAP = 16
LINE = 44
_DEFAULT_READER = StyleReader()
RAINBOW = ("#E5A1B0", "#EAB881", "#E4CD7C", "#AEC98F", "#87BED3", "#B39DCE")


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


def _font(style, size, heading=False):
    return ImageFont.truetype(
        str(style.heading_path if heading else style.font_path), size
    )


def _tech_background(height):
    style = HelpStyle()
    p = style.palette
    image = Image.new("RGB", (WIDTH, height), p["bg"])
    draw = ImageDraw.Draw(image)
    for x in range(0, WIDTH, 48):
        draw.line((x, 0, x, height), fill="#0D2132")
    for y in range(0, height, 48):
        draw.line((0, y, WIDTH, y), fill="#0D2132")
    for x, direction in ((26, 1), (WIDTH - 27, -1)):
        for y, vertical in ((26, 1), (height - 27, -1)):
            draw.line((x, y, x + direction * 34, y), fill=p["accent"], width=2)
            draw.line((x, y, x, y + vertical * 26), fill=p["accent"], width=2)
    draw.line((MARGIN, 46, MARGIN + 82, 46), fill=p["accent"], width=4)
    draw.line((MARGIN + 94, 46, MARGIN + 126, 46), fill=p["secondary"], width=4)
    return image


def _keko_background(height):
    p = keko_style().palette
    image = Image.new("RGB", (WIDTH, height), p["bg"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (18, 18, WIDTH - 19, height - 19), radius=36, fill=p["panel"]
    )
    for n, color in enumerate(RAINBOW):
        x = MARGIN + n * 25
        draw.rounded_rectangle((x, 37, x + 18, 43), radius=3, fill=color)
    for y in range(105, height - 50, 176):
        for x in (37, WIDTH - 38):
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=p["border"])
    return image


@lru_cache(maxsize=8)
def _mascot_thumbnail(path, timestamp, width, height):
    with Image.open(path) as source:
        mascot = source.convert("RGBA")
    bounds = mascot.getchannel("A").getbbox()
    if bounds:
        mascot = mascot.crop(bounds)
    mascot.thumbnail((width, height), Image.Resampling.LANCZOS)
    return mascot


def _draw_mascot(image, style, right, bottom, width, height):
    if style.mascot_path is None:
        return
    try:
        mascot = _mascot_thumbnail(
            str(style.mascot_path), style.mascot_path.stat().st_mtime_ns, width, height
        )
    except (OSError, ValueError):
        # An absent decoration must not hide the actual help instructions.
        return
    image.paste(mascot, (right - mascot.width, bottom - mascot.height), mascot)


@dataclass
class Segment:
    image: Image.Image
    id: str
    style: str
    part: int
    text: str


def _index(profile, group_name):
    style = HelpStyle()
    fonts = {size: _font(style, size) for size in (22, 27, 32, 44)}
    rows = []

    def add(text, size, kind="body"):
        if text:
            rows.extend(
                (line, size, kind)
                for line in _wrap(text, fonts[size], WIDTH - 2 * MARGIN - 40)
            )

    add(profile["title"], 44, "title")
    add(group_name or "默认帮助", 22, "muted")
    add(profile["intro"], 27)
    add(profile["list_title"], 32, "label")
    # An editable list template can surround or repeat the automatic directory.
    template = profile["list_text"]
    if "{plugins}" not in template:
        template += "\n{plugins}"
    entries = [item for item in profile["items"] if item["enabled"]]
    for index, text in enumerate(template.split("{plugins}")):
        if index:
            if not entries:
                add("本群暂未开启插件帮助。", 27)
            for offset in range(0, len(entries), 2):
                pair = []
                for number, item in enumerate(entries[offset : offset + 2], offset + 1):
                    lines = list(
                        _wrap(
                            item["title"],
                            fonts[27],
                            (WIDTH - MARGIN * 2 - 20) // 2 - 94,
                        )
                    )
                    pair.append((number, lines))
                rows.append((pair, 27, "tiles"))
        add(text.strip("\n"), 27)

    def row_height(row):
        if row[2] == "tiles":
            return 36 + max(len(lines) for _, lines in row[0]) * 39
        return row[1] + (34 if row[2] in ("title", "label") else 18)

    batches, batch, used = [], [], 115
    for row in rows:
        if batch and used + row_height(row) > PAGE_HEIGHT - 80:
            batches.append(batch)
            batch, used = [], 115
        batch.append(row)
        used += row_height(row)
    if batch:
        batches.append(batch)
    result = []
    for part, batch in enumerate(batches, 1):
        height = 115 + sum(row_height(row) for row in batch) + 52
        image = _tech_background(height)
        draw = ImageDraw.Draw(image)
        p = style.palette
        draw.text(
            (MARGIN, 68),
            "CUSTOM HELP  /  FUNCTION DIRECTORY",
            font=fonts[22],
            fill=p["accent"],
            anchor="lt",
        )
        y = 115
        for text, size, kind in batch:
            if kind == "tiles":
                cell_width = (WIDTH - MARGIN * 2 - 20) // 2
                h = row_height((text, size, kind)) - 12
                for column, (number, lines) in enumerate(text):
                    x = MARGIN + column * (cell_width + 20)
                    draw.rounded_rectangle(
                        (x, y, x + cell_width, y + h),
                        radius=10,
                        fill=p["paper"],
                        outline=p["border"],
                    )
                    draw.text(
                        (x + 18, y + 16),
                        f"{number:02d}",
                        font=fonts[27],
                        fill=p["accent"],
                        anchor="lt",
                    )
                    for n, line in enumerate(lines):
                        draw.text(
                            (x + 74, y + 16 + n * 39),
                            line,
                            font=fonts[27],
                            fill=p["ink"],
                            anchor="lt",
                        )
            else:
                if kind == "label":
                    draw.line(
                        (MARGIN, y - 10, WIDTH - MARGIN, y - 10),
                        fill=p["border"],
                        width=1,
                    )
                color = (
                    p["accent"]
                    if kind == "label"
                    else p["muted"]
                    if kind == "muted"
                    else p["ink"]
                )
                draw.text((MARGIN, y), text, font=fonts[size], fill=color, anchor="lt")
            y += row_height((text, size, kind))
        result.append(Segment(image, "__index__", "tech", part, plugin_list(profile)))
    return result


def _panel_background(style, height):
    p = style.palette
    if style.kind == "keko":
        return _keko_background(height)
    if style.kind == "tech":
        return _tech_background(height)
    if style.kind == "ziwei":
        return style.drawing["starfield"](WIDTH, height, style.native_palette)
    image = Image.new("RGB", (WIDTH, height), p["bg"])
    if style.kind == "liuyao":
        style.drawing["draw_bamboo_background"](image, WIDTH)
        draw = ImageDraw.Draw(image)
        draw.rectangle((27, 25, WIDTH - 28, height - 26), outline=p["border"], width=2)
        draw.rectangle((35, 33, WIDTH - 36, height - 34), outline=p["border"], width=1)
    return image


def _section(item, number, style):
    p = style.palette
    title_font = _font(style, 38, heading=True)
    body_font = _font(style, 28)
    small_font = _font(style, 22)
    title_width = WIDTH - MARGIN * 2 - 110 - (230 if style.kind == "keko" else 0)
    titles = list(_wrap(item["title"], title_font, title_width))
    title_height = 54 * len(titles)
    body_top = max(220 if style.kind == "keko" else 0, 150 + title_height)
    # Preserve every edited character and explicit blank line. Pagination occurs
    # between wrapped lines, with a complete native-style frame on each part.
    lines = []
    for raw in (item["body"] or "暂无说明。").split("\n"):
        wrapped = list(_wrap(raw, body_font, WIDTH - MARGIN * 2 - 56))
        lines.extend((text, raw.lstrip().startswith("/")) for text in wrapped)
    count = max(1, (PAGE_HEIGHT - body_top - 100) // LINE)
    result = []
    for start in range(0, len(lines), count):
        part = start // count + 1
        chunk = lines[start : start + count]
        height = body_top + len(chunk) * LINE + 72
        image = _panel_background(style, height)
        if style.kind == "keko":
            _draw_mascot(image, style, WIDTH - MARGIN, 170, 210, 110)
        draw = ImageDraw.Draw(image)
        x = MARGIN
        if style.kind == "liuyao":
            style.drawing["draw_taiji_logo"](
                draw, x, 62, width=62, height=62, color=p["accent"]
            )
        elif style.kind == "ziwei":
            style.drawing["orbit"](draw, x + 31, 88, 29, style.native_palette)
            style.drawing["constellation"](
                draw,
                WIDTH - MARGIN - 186,
                140 + title_height - 54,
                172,
                32,
                style.native_palette,
            )
        else:
            draw.rounded_rectangle(
                (x, 62, x + 64, 124),
                radius=24 if style.kind == "keko" else 10,
                fill=p["paper"] if style.kind == "keko" else p["panel"],
                outline=p["border"],
            )
            draw.text(
                (x + 32, 93),
                f"{number:02d}",
                font=title_font,
                fill=p["accent"],
                anchor="mm",
            )
        for index, title in enumerate(titles):
            draw.text(
                (x + 92, 60 + index * 54),
                title,
                font=title_font,
                fill=p["accent"] if style.kind == "liuyao" else p["ink"],
                anchor="lt",
            )
        label = f"{number:02d} / 插件使用说明" + (f" · 续 {part}" if part > 1 else "")
        draw.text(
            (MARGIN + 94, 72 + title_height),
            label,
            font=small_font,
            fill=p["muted"],
            anchor="lt",
        )
        draw.line(
            (MARGIN, body_top - 20, WIDTH - MARGIN, body_top - 20),
            fill=p["border"],
            width=1,
        )
        if style.kind == "liuyao":
            # The original help emphasizes the primary instruction in jade.
            hero_count = 1
            while (
                hero_count < len(chunk)
                and hero_count < 3
                and chunk[hero_count][1]
                and not chunk[hero_count][0].startswith("/")
            ):
                hero_count += 1
            hero_h = hero_count * LINE + 28
            draw.rounded_rectangle(
                (MARGIN, body_top, WIDTH - MARGIN, body_top + hero_h),
                radius=12,
                fill=p["accent"],
            )
            for n, (line, _) in enumerate(chunk[:hero_count]):
                draw.text(
                    (MARGIN + 28, body_top + 14 + n * LINE),
                    line,
                    font=body_font,
                    fill=p["bg"],
                    anchor="lt",
                )
            y = body_top + hero_h + 18
            for line, command in chunk[hero_count:]:
                draw.text(
                    (MARGIN + 28, y),
                    line,
                    font=body_font,
                    fill=p["accent"] if command else p["ink"],
                    anchor="lt",
                )
                y += LINE
        else:
            if style.kind == "keko":
                draw.rounded_rectangle(
                    (MARGIN + 5, body_top + 5, WIDTH - MARGIN + 5, height - 40),
                    radius=24,
                    fill=p["border"],
                )
            draw.rounded_rectangle(
                (MARGIN, body_top - 1, WIDTH - MARGIN, height - 46),
                radius=24 if style.kind == "keko" else 14,
                fill=p["paper"],
                outline=p["border"],
            )
            if style.kind == "rtlink":
                draw.rounded_rectangle(
                    (MARGIN, body_top, MARGIN + 5, height - 46),
                    radius=2,
                    fill=p["accent"],
                )
            for n, (line, command) in enumerate(chunk):
                draw.text(
                    (MARGIN + 28, body_top + 18 + n * LINE),
                    line,
                    font=body_font,
                    fill=p["accent"] if command else p["ink"],
                    anchor="lt",
                )
        result.append(
            Segment(
                image,
                item["id"],
                style.kind,
                part,
                "\n".join(line for line, _ in chunk),
            )
        )
    return result


def _footer(text):
    if not text:
        return []
    style = HelpStyle()
    font = _font(style, 23)
    rows = list(_wrap(text, font, WIDTH - 2 * MARGIN))
    result = []
    count = (PAGE_HEIGHT - 130) // 38
    for start in range(0, len(rows), count):
        chunk = rows[start : start + count]
        image = _tech_background(130 + len(chunk) * 38)
        draw = ImageDraw.Draw(image)
        for n, line in enumerate(chunk):
            draw.text(
                (MARGIN, 74 + n * 38),
                line,
                font=font,
                fill=style.palette["muted"],
                anchor="lt",
            )
        result.append(
            Segment(image, "__footer__", "tech", start // count + 1, "\n".join(chunk))
        )
    return result


def compose(segments):
    """Pack complete styled panels together; never crop a plugin mid-panel."""
    batches, batch, height = [], [], 0
    for segment in segments:
        if batch and height + GAP + segment.image.height > PAGE_HEIGHT:
            batches.append(batch)
            batch, height = [], 0
        batch.append(segment)
        height += segment.image.height + (GAP if len(batch) > 1 else 0)
    if batch:
        batches.append(batch)
    outputs = []
    for batch in batches:
        height = sum(segment.image.height for segment in batch) + GAP * (len(batch) - 1)
        image = Image.new("RGB", (WIDTH, height), HelpStyle().palette["bg"])
        top = 0
        for segment in batch:
            image.paste(segment.image, (0, top))
            top += segment.image.height + GAP
        info = PngImagePlugin.PngInfo()
        info.add_text(
            "help_sections",
            json.dumps(
                [{"id": s.id, "style": s.style, "part": s.part} for s in batch],
                ensure_ascii=False,
            ),
        )
        output = BytesIO()
        image.save(output, "PNG", pnginfo=info)
        outputs.append(output.getvalue())
    return outputs


def render_help(profile, group_name="", styles=None) -> list[bytes]:
    if styles is None:
        styles = _DEFAULT_READER.load(profile["items"])
    segments = _index(profile, group_name)
    for number, item in enumerate((i for i in profile["items"] if i["enabled"]), 1):
        segments.extend(_section(item, number, styles.get(item["id"], HelpStyle())))
    segments.extend(_footer(profile["footer"]))
    return compose(segments)
