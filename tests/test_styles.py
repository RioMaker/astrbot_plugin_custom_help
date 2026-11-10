from __future__ import annotations

import json
import shutil
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from conftest import load_module
from PIL import Image

styles_module = load_module("help_styles")
renderer = load_module("help_render")

LIUYAO = "astrbot_plugin_liuyao"
ZIWEI = "astrbot_plugin_ziwei"
RTLINK = "rt_link"


@pytest.fixture
def native_sources(tmp_path):
    # Entry points and unselected module-level expressions MUST NOT execute.
    liu = tmp_path / LIUYAO
    liu.mkdir()
    (liu / "main.py").write_text("raise RuntimeError('do not start plugins')")
    (liu / "renderer.py").write_text(
        """
raise RuntimeError("do not import chart calculation code")
PAPER = "#F6F3EA"
INK = "#252C2A"
MUTED = "#737971"
JADE = "#234A3B"
RULE = "#D5DCCB"
def draw_bamboo_background(canvas, width):
    canvas.putpixel((0, 0), (1, 2, 3))
def draw_taiji_logo(draw, x, y, *, width=52, height=50, color=JADE):
    draw.ellipse((x, y, x + width, y + height), outline=color)
""",
        encoding="utf-8",
    )
    (liu / "textcard.py").write_text(
        """
PAPER_DEEP = "#EFEBDC"
JADE_PANEL = "#E9EEDF"
FRAME = "#D9D3C1"
SEAL = "#B34F40"
""",
        encoding="utf-8",
    )
    (liu / "assets" / "fonts").mkdir(parents=True)
    Image.new("RGBA", (20, 20)).save(liu / "assets" / "bamboo.png")
    for name in ("NotoSansCJKsc-Regular.otf", "LiuyaoEditorialSerif.otf"):
        shutil.copyfile(styles_module.FONT_PATH, liu / "assets" / "fonts" / name)
    # This is deliberately not the runtime plugin name: detect metadata instead.
    ziwei = tmp_path / "renamed-ziwei-folder"
    ziwei.mkdir()
    (ziwei / "metadata.yaml").write_text(f'name: "{ZIWEI}"\n', encoding="utf-8")
    (ziwei / "themes.py").write_text(
        """
class Palette:
    name: str
    bg: str
    paper: str
    center: str
    ink: str
    muted: str
    border: str
    accent: str
NIGHT = Palette("night", "#090f22", "#101c32", "#14233d", "#edf1fa", "#aebed5", "#3d5376", "#dec58c")
DAY = Palette("day", "#f8f4ed", "#fffef8", "#f5f0e6", "#3b3a3e", "#607071", "#d9d2c7", "#2e7d32")
""",
        encoding="utf-8",
    )
    (ziwei / "starfield.py").write_text(
        """
def _rgb(value):
    return tuple(int(value[i:i+2],16) for i in (1,3,5))
def starfield(width, height, palette):
    return Image.new("RGB", (width, height), palette.bg)
def orbit(draw, cx, cy, radius, palette):
    draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius), outline=palette.accent)
def constellation(draw, x, y, width, height, palette):
    draw.line((x,y,x+width,y+height), fill=palette.accent)
""",
        encoding="utf-8",
    )
    (ziwei / "help_renderer.py").write_text("# native help renderer", encoding="utf-8")
    rt = tmp_path / RTLINK
    rt.mkdir()
    (rt / "resource").mkdir()
    shutil.copyfile(styles_module.FONT_PATH, rt / "resource/NotoSansCJKsc-Regular.otf")
    (rt / "help_image.py").write_text(
        """
BG = "#ffffff"
BG_ALT = "#f6f6f7"
TEXT = "#3c3c43"
TEXT_2 = "#67676c"
DIVIDER = "#e2e2e3"
BRAND = "#6f54d5"
BRAND_SOFT = "#f0edf9"
""",
        encoding="utf-8",
    )
    return tmp_path


def catalog():
    return [{"id": name} for name in (LIUYAO, ZIWEI, RTLINK, "text-only")]


def test_reads_native_assets_without_importing_plugin_entry_points(native_sources):
    styles = styles_module.StyleReader(native_sources).load(catalog())
    assert [styles[name].kind for name in (LIUYAO, ZIWEI, RTLINK)] == [
        "liuyao",
        "ziwei",
        "rtlink",
    ]
    assert all(styles[name].status == "native" for name in (LIUYAO, ZIWEI, RTLINK))
    assert styles["text-only"].status == "default"
    assert "renamed-ziwei-folder" in styles[ZIWEI].source
    assert styles[LIUYAO].font_path.parent.parent.parent == native_sources / LIUYAO
    canvas = renderer._panel_background(styles[LIUYAO], 400)
    assert canvas.getpixel((0, 0)) == (1, 2, 3)  # actual native helper ran
    assert renderer._panel_background(styles[ZIWEI], 400).getpixel((0, 0)) == (
        9,
        15,
        34,
    )


def test_color_source_changes_invalidate_style_and_image(native_sources):
    reader = styles_module.StyleReader(native_sources)
    before = reader.load(catalog())[LIUYAO]
    source = native_sources / LIUYAO / "renderer.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("#234A3B", "#213E71"),
        encoding="utf-8",
    )
    after = reader.load(catalog())[LIUYAO]
    assert after.fingerprint != before.fingerprint
    assert after.palette["accent"] == "#213E71"
    assert before.palette["accent"] == "#234A3B"


def test_ziwei_follows_own_theme_setting(native_sources):
    reader = styles_module.StyleReader(native_sources)
    night = reader.load(catalog())[ZIWEI]
    day = reader.load(catalog(), options={ZIWEI: {"theme": "day"}})[ZIWEI]
    assert day.palette["bg"] == "#f8f4ed"
    assert day.fingerprint != night.fingerprint
    assert "浅色" in day.label


@pytest.mark.parametrize("failure", ["missing-font", "syntax", "helper-error"])
def test_unavailable_native_style_falls_back_without_affecting_others(
    native_sources, failure
):
    root = native_sources / LIUYAO
    if failure == "missing-font":
        (root / "assets/fonts/LiuyaoEditorialSerif.otf").unlink()
    elif failure == "syntax":
        (root / "renderer.py").write_text("not valid python !")
    else:
        source = root / "renderer.py"
        source.write_text(
            source.read_text().replace(
                "canvas.putpixel((0, 0), (1, 2, 3))",
                "raise ValueError('incompatible helper')",
            )
        )
    styles = styles_module.StyleReader(native_sources).load(catalog())
    assert styles[LIUYAO].kind == "tech"
    assert styles[LIUYAO].status == "fallback"
    assert "未能读取" in styles[LIUYAO].note
    assert styles[ZIWEI].status == "native"
    assert styles[RTLINK].status == "native"


def test_edited_text_and_native_style_survive_composition_in_selected_order(
    service, native_sources
):
    profile = service.snapshot()["default_profile"]
    profile["items"] = [
        {
            "id": name,
            "title": "可编辑标题" + str(index),
            "body": "/自定义指令 任意说明\n这是后台修改的正文。",
            "enabled": name != "text-only",
        }
        for index, name in enumerate((ZIWEI, LIUYAO, RTLINK, "text-only"))
    ]
    before = deepcopy(profile)
    styles = styles_module.StyleReader(native_sources).load(catalog())
    pages = renderer.render_help(profile, "测试群", styles)
    sections = []
    for png in pages:
        with Image.open(BytesIO(png)) as image:
            assert image.width == renderer.WIDTH
            assert image.height <= renderer.PAGE_HEIGHT
            sections.extend(json.loads(image.info["help_sections"]))
    assert [(section["id"], section["style"]) for section in sections] == [
        ("__index__", "tech"),
        (ZIWEI, "ziwei"),
        (LIUYAO, "liuyao"),
        (RTLINK, "rtlink"),
        ("__footer__", "tech"),
    ]
    assert profile == before
    profile["items"][1]["body"] = "修改后的文字仍须进入原生风格图片"
    assert renderer.render_help(profile, "测试群", styles) != pages


def test_native_long_text_continues_without_missing_characters(native_sources):
    style = styles_module.StyleReader(native_sources).load(catalog())[LIUYAO]
    text = "\n".join(f"/命令{i} " + "长说明" * 40 for i in range(50))
    item = {"id": LIUYAO, "title": "可编辑的长标题" * 8, "body": text}
    segments = renderer._section(item, 1, style)
    assert len(segments) > 1
    assert "".join(
        segment.text.replace("\n", "") for segment in segments
    ) == text.replace("\n", "")
    assert all(
        segment.style == "liuyao" and segment.image.height <= renderer.PAGE_HEIGHT
        for segment in segments
    )


def test_real_sibling_style_integration_if_present():
    root = Path(__file__).resolve().parents[2]
    if not (root / LIUYAO / "renderer.py").is_file():
        pytest.skip("real sibling plugins not installed in this test environment")
    styles = styles_module.StyleReader(root).load(catalog())
    for name in (LIUYAO, ZIWEI, RTLINK):
        assert styles[name].status == "native", styles[name].public()
        segment = renderer._section(
            {
                "id": name,
                "title": "可编辑的帮助说明",
                "body": "/help 查看本群帮助\n测试正文，保留原生图案。",
            },
            1,
            styles[name],
        )[0]
        assert segment.image.width == renderer.WIDTH
