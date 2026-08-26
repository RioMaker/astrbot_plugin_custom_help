from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _load_plugin_module():
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    event_module = types.ModuleType("astrbot.api.event")
    star_module = types.ModuleType("astrbot.api.star")

    class AstrBotConfig(dict):
        pass

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class Star:
        def __init__(self, context):
            self.context = context

    def command(name, **kwargs):
        def decorator(func):
            func._test_command = {"name": name, **kwargs}
            return func

        return decorator

    def register(*_args, **_kwargs):
        return lambda cls: cls

    api_module.AstrBotConfig = AstrBotConfig
    event_module.AstrMessageEvent = AstrMessageEvent
    event_module.filter = types.SimpleNamespace(command=command)
    star_module.Context = Context
    star_module.Star = Star
    star_module.register = register

    modules = {
        "astrbot": astrbot_module,
        "astrbot.api": api_module,
        "astrbot.api.event": event_module,
        "astrbot.api.star": star_module,
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
        return text


async def _collect(async_generator):
    return [item async for item in async_generator]


def test_help_handler_has_priority_and_alias():
    module = _load_plugin_module()

    command = module.CustomHelpPlugin.custom_help._test_command

    assert command["name"] == "help"
    assert command["alias"] == {"帮助"}
    assert command["priority"] > 0


def test_custom_help_stops_event_and_returns_configured_text():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(object(), {"help_text": "  第一行\n第二行  "})
    event = _Event()

    results = asyncio.run(_collect(plugin.custom_help(event)))

    assert event.stopped is True
    assert results == ["第一行\n第二行"]


def test_blank_help_text_uses_nonempty_fallback():
    module = _load_plugin_module()
    plugin = module.CustomHelpPlugin(object(), {"help_text": "   "})
    event = _Event()

    results = asyncio.run(_collect(plugin.custom_help(event)))

    assert event.stopped is True
    assert results == [module.DEFAULT_HELP_TEXT]

