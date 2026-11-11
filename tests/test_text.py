from copy import deepcopy
from io import BytesIO

import pytest
from conftest import load_module
from PIL import Image, ImageDraw, ImageFont

text_renderer = load_module("help_text")
renderer = load_module("help_render")
styles = load_module("help_styles")


def red_pixels(image):
    return sum(
        red > 130 and red > green * 1.7 and red > blue * 1.5
        for red, green, blue in image.convert("RGB").getdata()
    )


@pytest.mark.parametrize("size", [22, 23, 27, 28, 32, 38, 44])
def test_chocolate_renders_in_color_at_every_help_font_size(size):
    font = ImageFont.truetype(str(styles.FONT_PATH), size)
    image = Image.new("RGB", (300, 80), "white")
    text_renderer.draw_text(image, (5, 5), "🍫 abc中文", font=font, fill="black")
    assert red_pixels(image.crop((5, 5, 5 + size, 5 + size))) > 10
    assert image.crop((5 + size + 4, 5, 250, 65)).getextrema()[0][0] < 30


@pytest.mark.parametrize("anchor", ["lt", "mm"])
def test_text_without_chocolate_keeps_original_pillow_pixels(anchor):
    font = ImageFont.truetype(str(styles.FONT_PATH), 28)
    expected = Image.new("RGB", (560, 120), "#071321")
    actual = expected.copy()
    text = "原生样式 /help ABC gj 中文说明"
    ImageDraw.Draw(expected).text(
        (200, 40), text, font=font, fill="white", anchor=anchor
    )
    text_renderer.draw_text(
        actual, (200, 40), text, font=font, fill="white", anchor=anchor
    )
    assert actual.tobytes() == expected.tobytes()


def test_mixed_symbols_spaces_and_selectors_wrap_without_loss():
    font = ImageFont.truetype(str(styles.FONT_PATH), 28)
    text = "可可子 🍫 🍫\ufe0f /help " * 20
    lines = list(renderer._wrap(text, font, 190))
    assert "".join(lines) == text
    assert all(text_renderer.text_width(line, font) <= 190 for line in lines)
    assert all(not line.startswith("\ufe0f") for line in lines)
    assert text_renderer.text_width("🍫 ", font) == 28 + font.getlength(" ")
    assert text_renderer.text_width("🍫\ufe0f", font) == 28


def test_symbol_appears_in_header_directory_body_and_footer_without_editing_text(
    service,
):
    profile = service.snapshot()["default_profile"]
    for key in ("title", "intro", "list_title", "list_text", "footer"):
        profile[key] = "🍫 " + profile[key]
    profile["items"][0].update(title="🍫 插件", body="🍫 使用说明")
    before = deepcopy(profile)
    index = renderer._index(profile, "🍫 群名称")[0].image
    section = renderer._section(profile["items"][0], 1, styles.HelpStyle())[0].image
    footer = renderer._footer(profile["footer"])[0].image
    assert red_pixels(index) > 100
    assert red_pixels(section.crop((154, 60, 192, 110))) > 10
    assert red_pixels(section.crop((90, 220, 118, 260))) > 10
    assert red_pixels(footer) > 10
    pages = renderer.render_help(profile, "🍫 群名称")
    with Image.open(BytesIO(pages[0])) as image:
        assert red_pixels(image) > 100
    assert profile == before
    assert "🍫 使用说明" in renderer.format_text(profile)
