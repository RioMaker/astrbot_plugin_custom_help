from __future__ import annotations

import asyncio
import base64
import inspect
import logging
import sys
import types
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import PACKAGE, load_module


@pytest.fixture
def plugin_module(monkeypatch, tmp_path, catalog_path):
    modules = {
        name: types.ModuleType(name)
        for name in (
            "astrbot",
            "astrbot.api",
            "astrbot.api.event",
            "astrbot.api.star",
            "astrbot.api.message_components",
            "astrbot.api.web",
        )
    }
    modules["astrbot"].__path__ = []
    modules["astrbot.api"].__path__ = []

    class Star:
        def __init__(self, context):
            self.context = context

    def command(name, **kwargs):
        def decorator(func):
            func._test_command = {"name": name, **kwargs}
            return func

        return decorator

    def event_message_type(event_type, **kwargs):
        def decorator(func):
            func._test_event = {"type": event_type, **kwargs}
            return func

        return decorator

    modules["astrbot.api"].AstrBotConfig = dict
    modules["astrbot.api"].logger = logging.getLogger("custom-help-tests")
    modules["astrbot.api.event"].AstrMessageEvent = object
    modules["astrbot.api.event"].filter = types.SimpleNamespace(
        command=command,
        event_message_type=event_message_type,
        EventMessageType=types.SimpleNamespace(GROUP_MESSAGE="group"),
    )
    modules["astrbot.api.star"].Star = Star
    modules["astrbot.api.star"].Context = object
    modules["astrbot.api.star"].StarTools = types.SimpleNamespace(
        get_data_dir=lambda _name: tmp_path / "runtime"
    )
    modules["astrbot.api.star"].register = lambda *_args, **_kwargs: lambda cls: cls
    modules["astrbot.api.message_components"].Image = types.SimpleNamespace(
        fromBase64=lambda data: {"type": "image", "base64": data}
    )
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, f"{PACKAGE}.main", raising=False)
    module = load_module("main")
    original_service = module.HelpService
    monkeypatch.setattr(
        module,
        "HelpService",
        lambda directory, _catalog, legacy="": original_service(
            directory, catalog_path, legacy
        ),
    )
    return module


class Event:
    def __init__(self, group_id="", platform_id="qq"):
        self.group_id = group_id
        self.platform_id = platform_id
        self.stopped = False
        self.sent = []
        self.stopped_when_sent = []

    def stop_event(self):
        self.stopped = True

    def get_group_id(self):
        return self.group_id

    def get_platform_id(self):
        return self.platform_id

    def get_platform_name(self):
        return "aiocqhttp"

    async def send(self, result):
        self.sent.append(result)
        self.stopped_when_sent.append(self.stopped)

    def plain_result(self, text):
        return text

    def chain_result(self, chain):
        return chain


async def deliver(plugin, event):
    await plugin.custom_help(event)
    return event.sent


def context_with_platforms(platforms=()):
    routes = []
    return types.SimpleNamespace(
        registered_web_apis=routes,
        register_web_api=lambda *args: routes.append(args),
        platform_manager=types.SimpleNamespace(get_insts=lambda: platforms),
    )


def test_help_handler_has_priority_and_alias(plugin_module):
    command = plugin_module.CustomHelpPlugin.custom_help._test_command
    assert command["name"] == "help"
    assert command["alias"] == {"帮助"}
    assert command["priority"] > 0
    assert inspect.iscoroutinefunction(plugin_module.CustomHelpPlugin.custom_help)
    assert not inspect.isasyncgenfunction(plugin_module.CustomHelpPlugin.custom_help)
    observer = plugin_module.CustomHelpPlugin.on_group_message._test_event
    assert observer["priority"] > command["priority"]


def test_private_help_preserves_legacy_text(plugin_module):
    plugin = plugin_module.CustomHelpPlugin(
        context_with_platforms(), {"help_text": "  第一行\n第二行  "}
    )
    event = Event()
    results = asyncio.run(deliver(plugin, event))
    assert event.stopped
    assert results == ["第一行\n第二行"]
    assert plugin.service.snapshot()["groups"] == []


def test_private_blank_help_uses_current_default_profile(plugin_module):
    plugin = plugin_module.CustomHelpPlugin(
        context_with_platforms(), {"help_text": "   "}
    )
    event = Event()
    results = asyncio.run(deliver(plugin, event))
    assert event.stopped
    assert len(results) == 1
    assert "/甲 查询甲的内容" in results[0]
    assert "/乙" not in results[0]


def test_private_long_legacy_is_chunked_without_losing_text(plugin_module):
    text = "完整的旧版帮助内容。" * 1000
    plugin = plugin_module.CustomHelpPlugin(
        context_with_platforms(), {"help_text": text}
    )
    event = Event()
    results = asyncio.run(deliver(plugin, event))
    assert len(results) > 1
    assert "".join(results) == text
    assert all(len(part) <= 3500 for part in results)
    assert all(event.stopped_when_sent)


def test_group_help_uses_group_override_and_shared_renderer(plugin_module):
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    plugin.service.observe_group("qq", "123", "编辑后的群名")
    state = plugin.service.snapshot()
    profile = state["default_profile"]
    profile["title"] = "本群专属帮助"
    profile["items"][0]["enabled"] = False
    profile["items"][1]["enabled"] = True
    state["groups"][0]["profile"] = profile
    plugin.service.save(state)
    event = Event("123")

    async def run():
        preview_bytes = await plugin.render_images(profile, "编辑后的群名")
        replies = await deliver(plugin, event)
        sent_bytes = [base64.b64decode(reply[0]["base64"]) for reply in replies]
        return preview_bytes, sent_bytes

    preview, sent = asyncio.run(run())
    assert event.stopped
    assert sent == preview
    assert sent[0].startswith(b"\x89PNG")


def test_group_render_failure_falls_back_to_its_selected_text(plugin_module):
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    plugin.render_images = AsyncMock(side_effect=OSError("font unavailable"))
    event = Event("123")
    results = asyncio.run(deliver(plugin, event))
    assert event.stopped
    assert "/甲 查询甲的内容" in "".join(results)
    assert "/乙" not in "".join(results)
    assert all(len(text) <= 3500 for text in results)


def test_stopped_event_still_sends_every_help_image(plugin_module):
    # AstrBot scheduler (local contract source, lines 52-74) breaks when an
    # async generator yields after stop_event. Direct event.send must deliver
    # all pages inside the coroutine before the scheduler checks the flag.
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    plugin.render_images = AsyncMock(return_value=[b"first-image", b"second-image"])
    event = Event("123")
    asyncio.run(plugin.custom_help(event))
    assert event.stopped
    assert event.stopped_when_sent == [True, True]
    assert [base64.b64decode(reply[0]["base64"]) for reply in event.sent] == [
        b"first-image",
        b"second-image",
    ]


def test_group_message_auto_discovers_without_sending_or_stopping(plugin_module):
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    event = Event("456", "bot-two")
    asyncio.run(plugin.on_group_message(event))
    assert not event.stopped
    groups = plugin.service.snapshot()["groups"]
    assert [(g["platform_id"], g["group_id"]) for g in groups] == [("bot-two", "456")]


def test_onebot_discovers_groups_for_each_connected_bot_and_keeps_platform_identity(
    plugin_module,
):
    client = types.SimpleNamespace(
        call_action=AsyncMock(
            side_effect=[
                [{"group_id": 11, "group_name": "甲群"}],
                {"status": "ok", "data": [{"group_id": 22, "group_name": "乙群"}]},
            ]
        ),
        _wsr_api_clients={"90001": object(), "90002": object()},
    )
    platform = types.SimpleNamespace(
        meta=lambda: types.SimpleNamespace(name="aiocqhttp", id="qq-instance"),
        get_client=lambda: client,
    )
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms([platform]), {})
    asyncio.run(plugin.discover_groups())
    assert client.call_action.await_count == 2
    assert {call.kwargs["self_id"] for call in client.call_action.await_args_list} == {
        "90001",
        "90002",
    }
    assert {
        (g["platform_id"], g["group_id"], g["name"])
        for g in plugin.service.snapshot()["groups"]
    } == {
        ("qq-instance", "11", "甲群"),
        ("qq-instance", "22", "乙群"),
    }
    assert plugin.discovery_errors == []


def test_failed_discovery_keeps_existing_groups_and_does_not_expose_error_details(
    plugin_module,
):
    client = types.SimpleNamespace(
        call_action=AsyncMock(side_effect=RuntimeError("private-connection-token"))
    )
    platform = types.SimpleNamespace(
        meta=lambda: types.SimpleNamespace(name="aiocqhttp", id="qq-instance"),
        get_client=lambda: client,
    )
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms([platform]), {})
    plugin.service.observe_group("qq-instance", "123", "已知群")
    asyncio.run(plugin.discover_groups())
    assert len(plugin.service.snapshot()["groups"]) == 1
    assert plugin.discovery_errors
    assert "private-connection-token" not in "".join(plugin.discovery_errors)


def test_render_cache_changes_when_description_changes(plugin_module, monkeypatch):
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    renderer = Mock(
        side_effect=lambda profile, name, styles: [profile["items"][0]["body"].encode()]
    )
    monkeypatch.setattr(plugin_module, "render_help", renderer)
    profile = plugin.service.snapshot()["default_profile"]

    async def run():
        first = await plugin.render_images(profile, "同群")
        assert await plugin.render_images(profile, "同群") == first
        profile["items"][0]["body"] = "保存后的新描述"
        second = await plugin.render_images(profile, "同群")
        assert first != second

    asyncio.run(run())
    assert renderer.call_count == 2


def test_lifecycle_registers_page_and_cancels_discovery_on_unload(plugin_module):
    context = context_with_platforms()
    plugin = plugin_module.CustomHelpPlugin(context, {})

    async def run():
        await plugin.initialize()
        assert len(context.registered_web_apis) == 4
        assert plugin.discovery_task is not None
        await asyncio.sleep(0)
        await plugin.terminate()
        assert plugin.discovery_task.done()

    asyncio.run(run())
    assert plugin.closed
    assert context.registered_web_apis == []
    assert not plugin.cache


def test_native_style_change_invalidates_chat_and_preview_cache(
    plugin_module, monkeypatch
):
    style_module = load_module("help_styles")
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    active_style = style_module.HelpStyle(fingerprint="original-native-style")
    plugin.read_styles = AsyncMock(
        return_value={"first": active_style, "second": style_module.HelpStyle()}
    )
    renderer_mock = Mock(
        side_effect=lambda profile, name, styles: [styles["first"].fingerprint.encode()]
    )
    monkeypatch.setattr(plugin_module, "render_help", renderer_mock)
    profile = plugin.service.snapshot()["default_profile"]

    async def run():
        first = await plugin.render_images(profile, "群")
        images, info = await plugin.render_images(profile, "群", with_styles=True)
        assert images == first
        assert info["first"]["label"] == active_style.label
        active_style.fingerprint = "updated-native-style"
        second = await plugin.render_images(profile, "群")
        assert second != first

    asyncio.run(run())
    assert renderer_mock.call_count == 2


def test_runtime_style_discovery_prefers_actual_loaded_instance_paths(
    plugin_module, monkeypatch, tmp_path
):
    style_module = load_module("help_styles")
    fake_module = types.ModuleType("loaded_ziwei_plugin")
    fake_module.__file__ = str(tmp_path / "renamed-install" / "main.py")
    monkeypatch.setitem(sys.modules, "loaded_ziwei_plugin", fake_module)
    instance_class = type("ZiweiPlugin", (), {"__module__": "loaded_ziwei_plugin"})
    instance = instance_class()
    instance.config = {"image_theme": "day"}
    instance.help_renderer = types.SimpleNamespace(font_path="installed-font.otf")
    context = types.SimpleNamespace(
        get_all_stars=lambda: [
            types.SimpleNamespace(name="astrbot_plugin_ziwei", star_cls=instance)
        ]
    )
    paths, options = style_module.runtime_sources(context)
    assert paths["astrbot_plugin_ziwei"] == (tmp_path / "renamed-install").resolve()
    assert options["astrbot_plugin_ziwei"] == {
        "theme": "day",
        "font_path": "installed-font.otf",
    }
