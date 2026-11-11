from __future__ import annotations

import json
from copy import deepcopy
from io import BytesIO
from unittest.mock import Mock

import pytest
from conftest import load_module
from PIL import Image, ImageFont


def test_header_list_and_body_follow_enabled_order_and_editable_text(service):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    profile["items"].reverse()
    profile["items"][0].update(enabled=True, title="定制乙标题", body="/乙 定制正文")
    profile["list_title"] = "本群能力一览"
    profile["list_text"] = "管理员编辑的目录前言\n{plugins}\n目录后记"
    text = renderer.format_text(profile)
    assert "本群能力一览" in text
    assert "管理员编辑的目录前言\n01  定制乙标题\n02  初始插件甲\n目录后记" in text
    assert text.index("定制乙标题\n/乙 定制正文") < text.index("初始插件甲\n/甲")

    profile["items"][1]["enabled"] = False
    text = renderer.format_text(profile)
    assert "初始插件甲" not in text
    assert "/甲" not in text


def test_editing_header_without_placeholder_keeps_actual_plugin_list(service):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    profile["list_text"] = "自由编辑的目录介绍"
    assert renderer.plugin_list(profile) == "自由编辑的目录介绍\n01  初始插件甲"


def test_empty_selection_has_explicit_help_message_and_valid_image(service):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    for item in profile["items"]:
        item["enabled"] = False
    assert "暂未开启" in renderer.format_text(profile)
    image_bytes = renderer.render_help(profile, "空配置群")
    assert len(image_bytes) == 1
    with Image.open(BytesIO(image_bytes[0])) as image:
        assert image.format == "PNG"
        assert image.width == renderer.WIDTH
        assert 0 < image.height <= renderer.MAX_IMAGE_HEIGHT


def test_long_instructions_form_one_image_without_repeated_sections(service):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    profile["items"][0]["body"] = "\n".join(
        f"/命令{i} 这是一条可以编辑的完整说明" for i in range(160)
    )
    before = deepcopy(profile)
    images = renderer.render_help(profile, "长说明测试群")
    assert len(images) == 1
    with Image.open(BytesIO(images[0])) as image:
        assert image.width == renderer.WIDTH
        assert 4800 < image.height <= renderer.MAX_IMAGE_HEIGHT
        sections = json.loads(image.info["help_sections"])
        assert [(s["id"], s["part"]) for s in sections] == [
            ("__index__", 1),
            ("first", 1),
            ("__footer__", 1),
        ]
    assert profile == before


def test_long_header_and_footer_stay_whole_in_the_same_image(service):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    profile["intro"] = "说明\n" * 120
    profile["footer"] = "提示\n" * 140
    images = renderer.render_help(profile)
    assert len(images) == 1
    with Image.open(BytesIO(images[0])) as image:
        sections = json.loads(image.info["help_sections"])
        assert [section["id"] for section in sections] == [
            "__index__",
            "first",
            "__footer__",
        ]
        assert all(section["part"] == 1 for section in sections)


def test_oversized_plugin_is_rejected_before_allocating_its_canvas(
    service, monkeypatch
):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    profile["items"][0]["body"] = "\n" * 5999
    background = Mock(wraps=renderer._panel_background)
    monkeypatch.setattr(renderer, "_panel_background", background)
    with pytest.raises(renderer.ImageTooTallError, match="请减少展示的插件"):
        renderer.render_help(profile)
    background.assert_not_called()


def test_total_canvas_limit_includes_preceding_panels(service, monkeypatch):
    renderer = load_module("help_render")
    profile = service.snapshot()["default_profile"]
    for item in profile["items"]:
        item.update(enabled=True, body="\n".join(["说明"] * 70))
    background = Mock(wraps=renderer._panel_background)
    monkeypatch.setattr(renderer, "MAX_IMAGE_HEIGHT", 5000)
    monkeypatch.setattr(renderer, "_panel_background", background)
    with pytest.raises(renderer.ImageTooTallError, match="5000"):
        renderer.render_help(profile)
    assert background.call_count == 1


def test_cjk_and_unbroken_commands_wrap_within_available_width():
    renderer = load_module("help_render")
    font = ImageFont.truetype(str(load_module("help_styles").FONT_PATH), 27)
    text = "超长中文帮助说明" * 30 + "/" + "long_unbroken_command" * 30
    lines = list(renderer._wrap(text, font, 250))
    assert len(lines) > 5
    assert "".join(lines) == text
    assert all(font.getlength(line) <= 250 for line in lines)
