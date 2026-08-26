"""Fast local Pillow renderer for custom help cards."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
OUTER_MARGIN = 54
CARD_PADDING = 34
CONTENT_WIDTH = WIDTH - OUTER_MARGIN * 2
CACHE_FORMAT_VERSION = 1

THEMES = {
    "violet": {
        "background_top": "#F4F1FF",
        "background_bottom": "#EEF4FF",
        "surface": "#FFFFFF",
        "surface_soft": "#F6F4FF",
        "text": "#1C2033",
        "muted": "#68708A",
        "accent": "#6C5CE7",
        "accent_dark": "#5142C7",
        "accent_soft": "#E9E5FF",
        "border": "#E1DDF5",
    },
    "blue": {
        "background_top": "#EFF7FF",
        "background_bottom": "#EDF2FF",
        "surface": "#FFFFFF",
        "surface_soft": "#F0F6FF",
        "text": "#17243A",
        "muted": "#60718A",
        "accent": "#3478F6",
        "accent_dark": "#245FCD",
        "accent_soft": "#DCEAFF",
        "border": "#D7E4F6",
    },
    "green": {
        "background_top": "#EFFBF6",
        "background_bottom": "#F2F7EE",
        "surface": "#FFFFFF",
        "surface_soft": "#EFF9F4",
        "text": "#183129",
        "muted": "#607A70",
        "accent": "#24966D",
        "accent_dark": "#187453",
        "accent_soft": "#D8F3E7",
        "border": "#D4EADF",
    },
    "rose": {
        "background_top": "#FFF1F5",
        "background_bottom": "#F7F1FF",
        "surface": "#FFFFFF",
        "surface_soft": "#FFF3F7",
        "text": "#34202A",
        "muted": "#816675",
        "accent": "#E05286",
        "accent_dark": "#BE3D6D",
        "accent_soft": "#FFE0EB",
        "border": "#F1D8E2",
    },
}


class HelpRenderError(RuntimeError):
    """Raised when the help image cannot be rendered."""


class HelpImageRenderer:
    """Render structured help content as a polished local PNG."""

    def __init__(self, *, font_path: str = "", theme: str = "violet"):
        normalized_theme = str(theme or "").strip().casefold()
        self.theme_name = normalized_theme if normalized_theme in THEMES else "violet"
        self.palette = THEMES[self.theme_name]
        custom_font = Path(font_path).expanduser() if font_path else None
        if custom_font is not None and custom_font.is_file():
            self.regular_font_path = custom_font
            self.bold_font_path = custom_font
        else:
            self.regular_font_path = self._find_font(bold=False)
            self.bold_font_path = self._find_font(bold=True)

    def cache_identity(self) -> dict[str, Any]:
        font_stat = self.regular_font_path.stat()
        bold_stat = self.bold_font_path.stat()
        return {
            "format": CACHE_FORMAT_VERSION,
            "theme": self.theme_name,
            "regular_font": str(self.regular_font_path),
            "regular_font_mtime": font_stat.st_mtime_ns,
            "bold_font": str(self.bold_font_path),
            "bold_font_mtime": bold_stat.st_mtime_ns,
        }

    def render(self, document: dict[str, Any], output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        fonts = {
            "kicker": self._font(22, bold=True),
            "title": self._font(48, bold=True),
            "subtitle": self._font(25),
            "badge": self._font(20, bold=True),
            "card_title": self._font(31, bold=True),
            "command": self._font(27, bold=True),
            "description": self._font(22),
            "body": self._font(24),
            "footer": self._font(21),
        }
        measure = ImageDraw.Draw(Image.new("RGB", (4, 4), "white"))
        layout = self._layout_document(measure, document, fonts)
        canvas = self._gradient_canvas(layout["height"])
        draw = ImageDraw.Draw(canvas)

        self._draw_decorations(draw, layout["height"])
        self._draw_header(draw, layout["header"], fonts)

        for card in layout["cards"]:
            self._draw_card(draw, card, fonts)

        self._draw_footer(draw, layout["footer"], fonts)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=output.parent,
                prefix=f".{output.stem}-",
                suffix=".png",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
            canvas.save(temporary_path, format="PNG", compress_level=3)
            temporary_path.replace(output)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
        return output

    def _layout_document(
        self,
        draw: ImageDraw.ImageDraw,
        document: dict[str, Any],
        fonts: dict[str, ImageFont.FreeTypeFont],
    ) -> dict[str, Any]:
        content_x = OUTER_MARGIN
        inner_width = CONTENT_WIDTH - CARD_PADDING * 2
        kicker = str(document.get("kicker") or "帮助中心").strip()
        title = str(document.get("title") or "帮助").strip()
        subtitle = str(document.get("subtitle") or "").strip()

        title_lines = self._wrap(draw, title, fonts["title"], CONTENT_WIDTH)
        subtitle_lines = self._wrap(draw, subtitle, fonts["subtitle"], CONTENT_WIDTH)
        header_height = (
            42
            + len(title_lines) * 66
            + (18 + len(subtitle_lines) * 38 if subtitle_lines else 0)
        )
        header = {
            "x": content_x,
            "y": 52,
            "kicker": kicker,
            "title_lines": title_lines,
            "subtitle_lines": subtitle_lines,
        }

        y = header["y"] + header_height + 24
        cards = []
        for raw_card in document.get("cards") or []:
            card = self._layout_card(
                draw,
                raw_card,
                fonts,
                x=content_x,
                y=y,
                width=CONTENT_WIDTH,
                inner_width=inner_width,
            )
            cards.append(card)
            y += card["height"] + 22

        footer_text = str(document.get("footer") or "").strip()
        footer_lines = self._wrap(draw, footer_text, fonts["footer"], CONTENT_WIDTH)
        footer = {
            "x": content_x,
            "y": y + 8,
            "lines": footer_lines,
        }
        footer_height = len(footer_lines) * 31 if footer_lines else 0
        height = max(620, footer["y"] + footer_height + 54)
        return {
            "height": height,
            "header": header,
            "cards": cards,
            "footer": footer,
        }

    def _layout_card(
        self,
        draw: ImageDraw.ImageDraw,
        raw_card: dict[str, Any],
        fonts: dict[str, ImageFont.FreeTypeFont],
        *,
        x: int,
        y: int,
        width: int,
        inner_width: int,
    ) -> dict[str, Any]:
        badge = str(raw_card.get("badge") or "").strip()
        title = str(raw_card.get("title") or "").strip()
        summary = str(raw_card.get("summary") or "").strip()
        body = str(raw_card.get("body") or "").strip()

        title_lines = self._wrap(draw, title, fonts["card_title"], inner_width)
        summary_lines = self._wrap(draw, summary, fonts["description"], inner_width)
        body_lines = self._wrap(draw, body, fonts["body"], inner_width)

        command_layouts = []
        command_width = inner_width - 36
        for command in raw_card.get("commands") or []:
            command_text = str(command.get("command") or "").strip()
            description = str(command.get("description") or "").strip()
            command_lines = self._wrap(
                draw,
                command_text,
                fonts["command"],
                command_width,
            )
            description_lines = self._wrap(
                draw,
                description,
                fonts["description"],
                command_width,
            )
            row_height = 26 + len(command_lines) * 39
            if description_lines:
                row_height += 8 + len(description_lines) * 32
            command_layouts.append(
                {
                    "command_lines": command_lines,
                    "description_lines": description_lines,
                    "height": row_height,
                }
            )

        content_height = CARD_PADDING
        if badge:
            content_height += 34 + 18
        if title_lines:
            content_height += len(title_lines) * 44
        if summary_lines:
            content_height += 10 + len(summary_lines) * 32
        if command_layouts:
            content_height += 24
            content_height += sum(item["height"] for item in command_layouts)
            content_height += 12 * (len(command_layouts) - 1)
        if body_lines:
            content_height += 24 + len(body_lines) * 36
        content_height += CARD_PADDING

        return {
            "x": x,
            "y": y,
            "width": width,
            "height": content_height,
            "badge": badge,
            "title_lines": title_lines,
            "summary_lines": summary_lines,
            "commands": command_layouts,
            "body_lines": body_lines,
        }

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        header: dict[str, Any],
        fonts: dict[str, ImageFont.FreeTypeFont],
    ) -> None:
        x = header["x"]
        y = header["y"]
        kicker = header["kicker"]
        kicker_width = int(draw.textlength(kicker, font=fonts["kicker"])) + 30
        draw.rounded_rectangle(
            (x, y, x + kicker_width, y + 38),
            radius=19,
            fill=self.palette["accent"],
        )
        draw.text(
            (x + 15, y + 6),
            kicker,
            font=fonts["kicker"],
            fill="#FFFFFF",
        )
        y += 58
        for line in header["title_lines"]:
            draw.text((x, y), line, font=fonts["title"], fill=self.palette["text"])
            y += 66
        if header["subtitle_lines"]:
            y += 4
            for line in header["subtitle_lines"]:
                draw.text(
                    (x, y),
                    line,
                    font=fonts["subtitle"],
                    fill=self.palette["muted"],
                )
                y += 38

    def _draw_card(
        self,
        draw: ImageDraw.ImageDraw,
        card: dict[str, Any],
        fonts: dict[str, ImageFont.FreeTypeFont],
    ) -> None:
        x = card["x"]
        y = card["y"]
        right = x + card["width"]
        bottom = y + card["height"]
        draw.rounded_rectangle(
            (x + 4, y + 8, right + 4, bottom + 8),
            radius=30,
            fill="#DDE3F0",
        )
        draw.rounded_rectangle(
            (x, y, right, bottom),
            radius=30,
            fill=self.palette["surface"],
            outline=self.palette["border"],
            width=2,
        )
        draw.rounded_rectangle(
            (x, y, x + 12, bottom),
            radius=6,
            fill=self.palette["accent"],
        )

        cursor_x = x + CARD_PADDING
        cursor_y = y + CARD_PADDING
        if card["badge"]:
            badge_width = int(
                draw.textlength(card["badge"], font=fonts["badge"])
            ) + 28
            draw.rounded_rectangle(
                (cursor_x, cursor_y, cursor_x + badge_width, cursor_y + 34),
                radius=17,
                fill=self.palette["accent_soft"],
            )
            draw.text(
                (cursor_x + 14, cursor_y + 5),
                card["badge"],
                font=fonts["badge"],
                fill=self.palette["accent_dark"],
            )
            cursor_y += 52

        for line in card["title_lines"]:
            draw.text(
                (cursor_x, cursor_y),
                line,
                font=fonts["card_title"],
                fill=self.palette["text"],
            )
            cursor_y += 44

        if card["summary_lines"]:
            cursor_y += 10
            for line in card["summary_lines"]:
                draw.text(
                    (cursor_x, cursor_y),
                    line,
                    font=fonts["description"],
                    fill=self.palette["muted"],
                )
                cursor_y += 32

        if card["commands"]:
            cursor_y += 24
            command_width = card["width"] - CARD_PADDING * 2
            for index, command in enumerate(card["commands"]):
                row_bottom = cursor_y + command["height"]
                draw.rounded_rectangle(
                    (
                        cursor_x,
                        cursor_y,
                        cursor_x + command_width,
                        row_bottom,
                    ),
                    radius=18,
                    fill=self.palette["surface_soft"],
                )
                text_y = cursor_y + 13
                for line in command["command_lines"]:
                    draw.text(
                        (cursor_x + 18, text_y),
                        line,
                        font=fonts["command"],
                        fill=self.palette["accent_dark"],
                    )
                    text_y += 39
                if command["description_lines"]:
                    text_y += 5
                    for line in command["description_lines"]:
                        draw.text(
                            (cursor_x + 18, text_y),
                            line,
                            font=fonts["description"],
                            fill=self.palette["muted"],
                        )
                        text_y += 32
                cursor_y = row_bottom
                if index < len(card["commands"]) - 1:
                    cursor_y += 12

        if card["body_lines"]:
            cursor_y += 24
            for line in card["body_lines"]:
                draw.text(
                    (cursor_x, cursor_y),
                    line,
                    font=fonts["body"],
                    fill=self.palette["text"],
                )
                cursor_y += 36

    def _draw_footer(
        self,
        draw: ImageDraw.ImageDraw,
        footer: dict[str, Any],
        fonts: dict[str, ImageFont.FreeTypeFont],
    ) -> None:
        y = footer["y"]
        for line in footer["lines"]:
            draw.text(
                (footer["x"], y),
                line,
                font=fonts["footer"],
                fill=self.palette["muted"],
            )
            y += 31

    def _gradient_canvas(self, height: int) -> Image.Image:
        top = self._hex_rgb(self.palette["background_top"])
        bottom = self._hex_rgb(self.palette["background_bottom"])
        image = Image.new("RGB", (WIDTH, height), top)
        draw = ImageDraw.Draw(image)
        denominator = max(1, height - 1)
        for y in range(height):
            ratio = y / denominator
            color = tuple(
                round(top[index] + (bottom[index] - top[index]) * ratio)
                for index in range(3)
            )
            draw.line((0, y, WIDTH, y), fill=color)
        return image

    def _draw_decorations(self, draw: ImageDraw.ImageDraw, height: int) -> None:
        draw.ellipse(
            (WIDTH - 250, -120, WIDTH + 100, 230),
            fill=self.palette["accent_soft"],
        )
        draw.ellipse(
            (-170, height - 230, 150, height + 90),
            fill=self.palette["accent_soft"],
        )
        draw.ellipse(
            (WIDTH - 94, 98, WIDTH - 70, 122),
            fill=self.palette["accent"],
        )

    def _font(self, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
        path = self.bold_font_path if bold else self.regular_font_path
        return ImageFont.truetype(str(path), size=size)

    @staticmethod
    def _find_font(*, bold: bool) -> Path:
        regular = [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/simsun.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        ]
        bold_candidates = [
            Path("C:/Windows/Fonts/msyhbd.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
            Path("/System/Library/Fonts/PingFang.ttc"),
        ]
        candidates = bold_candidates + regular if bold else regular
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        kind = "粗体" if bold else "常规"
        raise HelpRenderError(f"未找到可用于帮助图片的中文{kind}字体")

    @staticmethod
    def _wrap(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> list[str]:
        if not text:
            return []

        lines: list[str] = []
        for paragraph in text.splitlines():
            if not paragraph:
                lines.append("")
                continue
            current = ""
            for char in paragraph:
                candidate = current + char
                if current and draw.textlength(candidate, font=font) > max_width:
                    lines.append(current)
                    current = char
                else:
                    current = candidate
            if current:
                lines.append(current)
        return lines

    @staticmethod
    def _hex_rgb(value: str) -> tuple[int, int, int]:
        normalized = value.lstrip("#")
        return tuple(
            int(normalized[index : index + 2], 16)
            for index in (0, 2, 4)
        )
