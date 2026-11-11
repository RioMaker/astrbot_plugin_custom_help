"""Exercise both real plugins; only AstrBot's transport/API is replaced locally."""

import asyncio
import importlib
import sys
import types
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from test_main import Event, context_with_platforms
from test_main import plugin_module as plugin_module  # noqa: PLC0414 - fixture re-export
from test_triggers import ALL, component


class GroupEvent(Event):
    def __init__(self, kind):
        super().__init__("123", "qq")
        self.unified_msg_origin = "qq:GroupMessage:123"
        self.is_at_or_wake_command = kind == "at"
        self.message_str = "可可子" if kind == "name" else ""
        self.message_obj.message = (
            [component("At", qq=999)]
            if kind == "at"
            else [component("Plain", text=self.message_str)]
        )
        if kind == "poke":
            self.message_obj.raw_message = {
                "post_type": "notice",
                "notice_type": "notify",
                "sub_type": "poke",
                "self_id": 999,
                "target_id": 999,
                "user_id": 111,
                "group_id": 123,
                "time": 1794362400,
            }

    def is_private_chat(self):
        return False

    def is_admin(self):
        return False

    def set_extra(self, key, value):
        self.extras[key] = value

    def get_sender_name(self):
        return "测试用户"


@pytest.fixture
def plugins(plugin_module, monkeypatch, tmp_path):
    gate_dir = Path(__file__).resolve().parents[2] / "astrbot_plugin_access_gate"
    if not (gate_dir / "main.py").is_file():
        pytest.skip("requires the sibling access_gate checkout")
    # The custom-help test API already supplies Star and the message decorators.
    monkeypatch.setattr(
        plugin_module.filter.EventMessageType, "ALL", "all", raising=False
    )
    command = types.ModuleType("astrbot.core.star.filter.command")
    command.GreedyStr = str
    monkeypatch.setitem(sys.modules, command.__name__, command)
    package = types.ModuleType("help_gate_integration")
    package.__path__ = [str(gate_dir)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    gate_module = importlib.import_module(f"{package.__name__}.main")
    economy_module = importlib.import_module(f"{package.__name__}.economy")

    context = context_with_platforms()
    help_plugin = plugin_module.CustomHelpPlugin(context, {})
    help_plugin.service.observe_group("qq", "123", "测试群")
    state = help_plugin.service.snapshot()
    profile = deepcopy(state["default_profile"])
    profile["title"] = "当前群的帮助模板"
    profile["triggers"] = dict(ALL)
    state["templates"] = [{"id": "shared", "name": "共享模板", "profile": profile}]
    state["groups"][0].update(template_id="shared", shortcut_enabled=True)
    help_plugin.service.save(state)
    context.get_all_stars = lambda: [
        types.SimpleNamespace(
            name=plugin_module.PLUGIN_NAME,
            activated=True,
            module_path=plugin_module.__name__,
            star_cls=help_plugin,
        )
    ]
    gate = gate_module.AccessGatePlugin(
        context,
        {
            "group_whitelist": ["123"],
            "poke_reward_probability": 100,
            "poke_reward_min": 3,
            "poke_reward_max": 3,
            "poke_reward_reply_mode": "text",
        },
    )
    gate.economy = economy_module.Economy(tmp_path / "credits.db")
    yield gate, help_plugin
    gate.economy.store.close()


def activate(event, help_plugin):
    # AstrBot 4.29.4's WakingCheckStage stores handler metadata, not names.
    event.extras["activated_handlers"] = [
        types.SimpleNamespace(handler_module_path=type(help_plugin).__module__)
    ]
    event.extras["handlers_parsed_params"] = {}


@pytest.mark.parametrize("entry", ["enforce_access", "route_wake"])
@pytest.mark.parametrize(
    "kind,mode",
    [
        ("at", "text"),
        ("name", "text"),
        ("poke", "text"),
        ("poke", "image"),
        ("poke", "both"),
    ],
)
def test_real_gate_and_help_deliver_only_the_current_help_image(
    plugins, entry, kind, mode
):
    gate, help_plugin = plugins
    gate.config["poke_reward_reply_mode"] = mode
    gate.poke_cards = types.SimpleNamespace(render=Mock())
    event = GroupEvent(kind)
    activate(event, help_plugin)

    async def run():
        reference = GroupEvent("at")
        await help_plugin.custom_help(reference)
        await getattr(gate, entry)(event)
        await gate.route_wake(event)
        await help_plugin.on_group_message(event)
        assert event.sent == reference.sent
        assert event.stopped and event.suppressed
        assert event.sent and all(isinstance(message, list) for message in event.sent)
        assert await gate.economy.balance("qq", "111") == (3 if kind == "poke" else 0)
        assert (await gate.economy.ledger({"kind": "poke"}))["total"] == (
            1 if kind == "poke" else 0
        )

    asyncio.run(run())
    gate.poke_cards.render.assert_not_called()


def test_failed_help_delivery_still_records_poke_reward_once(plugins):
    gate, help_plugin = plugins
    event = GroupEvent("poke")
    activate(event, help_plugin)
    event.send = AsyncMock(side_effect=OSError("transport unavailable"))

    async def run():
        await gate.enforce_access(event)
        await gate.route_wake(event)
        assert event.stopped and event.suppressed
        assert await gate.economy.balance("qq", "111") == 3
        assert (await gate.economy.ledger({"kind": "poke"}))["total"] == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "block", ["group_switch", "template_switch", "session", "access"]
)
def test_shortcut_controls_are_honored_across_both_plugins(plugins, block):
    gate, help_plugin = plugins
    event = GroupEvent("at")
    activate(event, help_plugin)
    state = help_plugin.service.snapshot()
    if block == "group_switch":
        state["groups"][0]["shortcut_enabled"] = False
    elif block == "template_switch":
        state["templates"][0]["profile"]["triggers"]["at"] = False
    elif block == "session":
        event.extras["activated_handlers"] = []
    else:
        gate.config["group_whitelist"] = []
    help_plugin.service.save(state)
    help_plugin.render_images = Mock(side_effect=AssertionError("must not render"))
    asyncio.run(gate.enforce_access(event))
    assert event.sent == ([] if block == "access" else ["我在，请继续说。"])
    help_plugin.render_images.assert_not_called()
