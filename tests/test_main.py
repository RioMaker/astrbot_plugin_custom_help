from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_plugin_module():
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    event_module = types.ModuleType("astrbot.api.event")
    star_module = types.ModuleType("astrbot.api.star")
    core_module = types.ModuleType("astrbot.core")
    core_star_module = types.ModuleType("astrbot.core.star")
    core_filter_module = types.ModuleType("astrbot.core.star.filter")
    command_module = types.ModuleType("astrbot.core.star.filter.command")

    class AstrBotConfig(dict):
        pass

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class Star:
        def __init__(self, context):
            self.context = context

    class Logger:
        def __init__(self):
            self.warnings = []

        def warning(self, message):
            self.warnings.append(message)

    def command(name, **kwargs):
        def decorator(func):
            func._test_command = {"name": name, **kwargs}
            return func

        return decorator

    def register(*_args, **_kwargs):
        return lambda cls: cls

    api_module.AstrBotConfig = AstrBotConfig
    api_module.logger = Logger()
    event_module.AstrMessageEvent = AstrMessageEvent
    event_module.filter = types.SimpleNamespace(command=command)
    star_module.Context = Context
    star_module.Star = Star
    star_module.register = register
    command_module.GreedyStr = str

    modules = {
        "astrbot": astrbot_module,
        "astrbot.api": api_module,
        "astrbot.api.event": event_module,
        "astrbot.api.star": star_module,
        "astrbot.core": core_module,
        "astrbot.core.star": core_star_module,
        "astrbot.core.star.filter": core_filter_module,
        "astrbot.core.star.filter.command": command_module,
    }
    old_modules = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        spec = importlib.util.spec_from_file_location(
            "astrbot_plugin_custom_help.main",
            PLUGIN_DIR / "main.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in old_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


class _Event:
    def __init__(self):
        self.stopped = False

    def stop_event(self):
        self.stopped = True

    def plain_result(self, text):
        return ("plain", text)

    def image_result(self, url):
        return ("image", url)


async def _collect(async_generator):
    return [item async for item in async_generator]


def _blocks():
    return [
        {
            "enabled": True,
            "block_name": "绘图",
            "aliases": ["生图", "draw"],
            "title": "绘图插件",
            "summary": "生成或编辑图片。",
            "commands": "/生图 <提示词> — 生成图片\n/生图状态 — 查看进度",
            "details": "引用图片后可进行编辑。",
            "show_in_overview": True,
        },
        {
            "enabled": True,
            "block_name": "介绍",
            "aliases": ["关于"],
            "title": "机器人介绍",
            "summary": "机器人简介。",
            "commands": "",
            "details": "这里是详细介绍。",
            "show_in_overview": False,
        },
        {
            "enabled": False,
            "block_name": "停用块",
            "title": "停用块",
            "commands": "/disabled — 不应显示",
        },
    ]


def test_help_handler_has_priority_alias_and_greedy_subcommand():
    module = _load_plugin_module()
    command = module.CustomHelpPlugin.custom_help._test_command

    assert command["name"] == "help"
    assert command["alias"] == {"帮助"}
    assert command["priority"] > 0
    assert module.CustomHelpPlugin.custom_help.__annotations__["block_name"] == "GreedyStr"


def test_overview_only_lists_enabled_overview_commands():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(
        object(),
        {
            "output_mode": "text",
            "overview_title": "指令中心",
            "overview_footer": "查看详情：/help <块名称>",
            "help_blocks": _blocks(),
        },
    )
    event = _Event()

    results = asyncio.run(_collect(plugin.custom_help(event, "")))

    assert event.stopped is True
    assert results[0][0] == "plain"
    text = results[0][1]
    assert text.startswith("指令中心")
    assert "/生图 <提示词> — 生成图片" in text
    assert "引用图片后可进行编辑" not in text
    assert "这里是详细介绍" not in text
    assert "/disabled" not in text
    assert "可用帮助块：绘图、介绍" in text


def test_named_block_and_alias_return_detailed_help():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(
        object(),
        {"output_mode": "text", "help_blocks": _blocks()},
    )

    by_name = asyncio.run(_collect(plugin.custom_help(_Event(), "绘图")))[0][1]
    by_alias = asyncio.run(_collect(plugin.custom_help(_Event(), "生图")))[0][1]
    introduction = asyncio.run(_collect(plugin.custom_help(_Event(), "关于")))[0][1]

    assert by_name == by_alias
    assert "【绘图插件】" in by_name
    assert "生成或编辑图片。" in by_name
    assert "指令列表：" in by_name
    assert "详细说明：\n引用图片后可进行编辑。" in by_name
    assert "【机器人介绍】" in introduction
    assert "这里是详细介绍。" in introduction


def test_unknown_block_lists_available_names():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(
        object(),
        {"output_mode": "text", "help_blocks": _blocks()},
    )

    result = asyncio.run(_collect(plugin.custom_help(_Event(), "不存在")))[0][1]

    assert "没有找到帮助块：不存在" in result
    assert "可用帮助块：绘图、介绍" in result


def test_image_mode_uses_html_render_and_image_result():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(
        object(),
        {"output_mode": "image", "help_blocks": _blocks()},
    )
    captured = {}

    async def html_render(template, data, options):
        captured.update(template=template, data=data, options=options)
        return "https://example.test/help.png"

    plugin.html_render = html_render
    result = asyncio.run(_collect(plugin.custom_help(_Event(), "绘图")))

    assert result == [("image", "https://example.test/help.png")]
    assert captured["data"]["label"] == "详细帮助"
    assert "绘图插件" in captured["data"]["content"]
    assert captured["options"]["type"] == "png"


def test_image_render_failure_falls_back_to_plain_text():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(
        object(),
        {"output_mode": "image", "help_blocks": _blocks()},
    )

    async def html_render(*_args, **_kwargs):
        raise RuntimeError("renderer unavailable")

    plugin.html_render = html_render
    result = asyncio.run(_collect(plugin.custom_help(_Event(), "")))

    assert result[0][0] == "plain"
    assert "/生图状态 — 查看进度" in result[0][1]
    assert module.logger.warnings


def test_schema_exposes_repeatable_blocks_and_output_mode():
    schema = json.loads((PLUGIN_DIR / "_conf_schema.json").read_text(encoding="utf-8"))
    blocks = schema["help_blocks"]
    items = blocks["templates"]["help_block"]["items"]

    assert schema["output_mode"]["default"] == "image"
    assert blocks["type"] == "template_list"
    assert len(blocks["default"]) == 3
    assert {
        "enabled",
        "block_name",
        "aliases",
        "title",
        "summary",
        "commands",
        "details",
        "show_in_overview",
    } <= items.keys()
