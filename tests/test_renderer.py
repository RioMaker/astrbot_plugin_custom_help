from pathlib import Path

from PIL import Image

from renderer import HelpImageRenderer, THEMES, WIDTH


def _document():
    return {
        "kicker": "指令总览",
        "title": "可用指令",
        "subtitle": "选择一条指令开始使用",
        "cards": [
            {
                "badge": "绘图",
                "title": "绘图插件",
                "summary": "",
                "commands": [
                    {
                        "command": "/生图 <提示词>",
                        "description": "根据提示生成图片",
                    },
                    {
                        "command": "/生图状态",
                        "description": "查看任务进度与配额",
                    },
                ],
                "body": "",
            },
            {
                "badge": "六爻",
                "title": "六爻起卦",
                "summary": "",
                "commands": [
                    {
                        "command": "/六爻 <问题>",
                        "description": "即时起卦并解读",
                    }
                ],
                "body": "",
            },
        ],
        "footer": "发送 /help <块名称> 查看对应的详细帮助。",
    }


def test_renderer_creates_valid_dynamic_png(tmp_path):
    renderer = HelpImageRenderer(theme="violet")
    output = renderer.render(_document(), tmp_path / "help.png")

    assert output == tmp_path / "help.png"
    assert output.stat().st_size > 10_000
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.width == WIDTH
        assert image.height > 800
        assert image.getpixel((0, 0)) != image.getpixel((0, image.height - 1))


def test_all_configured_themes_have_complete_palettes():
    required = {
        "background_top",
        "background_bottom",
        "surface",
        "surface_soft",
        "text",
        "muted",
        "accent",
        "accent_dark",
        "accent_soft",
        "border",
    }

    assert set(THEMES) == {"violet", "blue", "green", "rose"}
    assert all(required <= palette.keys() for palette in THEMES.values())


def test_cache_identity_changes_with_theme():
    violet = HelpImageRenderer(theme="violet").cache_identity()
    blue = HelpImageRenderer(theme="blue").cache_identity()

    assert violet["theme"] == "violet"
    assert blue["theme"] == "blue"
    assert violet != blue
