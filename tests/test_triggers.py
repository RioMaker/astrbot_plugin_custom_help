import asyncio
import base64
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from conftest import load_module
from test_main import Event, context_with_platforms
from test_main import plugin_module as plugin_module  # noqa: PLC0414 - pytest fixture re-export

trigger_for = load_module("help_triggers").trigger_for


def component(kind, **values):
    return type(kind, (), values)()


def event_with(chain=(), **raw):
    event = Event("123")
    event.message_obj.message = list(chain)
    event.message_obj.raw_message = raw
    return event


def poke_event(**overrides):
    raw = {
        "post_type": "notice",
        "notice_type": "notify",
        "sub_type": "poke",
        "self_id": 999,
        "target_id": 999,
        "user_id": 111,
        "group_id": 123,
    }
    raw.update(overrides)
    return event_with(**raw)


ALL = {"at": True, "name": True, "poke": True, "bot_name": "可可子"}


@pytest.mark.parametrize(
    "event,expected",
    [
        (event_with([component("At", qq=999)]), "at"),
        (
            event_with(
                [component("At", qq="999"), component("Plain", text=" \u200b\n")]
            ),
            "at",
        ),
        (event_with([component("Plain", text=" 可可子 ")]), "name"),
        (poke_event(), "poke"),
    ],
)
def test_three_explicit_shortcuts_and_independent_switches(event, expected):
    assert trigger_for(event, ALL) == expected
    assert trigger_for(event, {**ALL, expected: False}) is None


@pytest.mark.parametrize(
    "event",
    [
        event_with([component("At", qq=222)]),
        event_with([component("At", qq=999), component("At", qq=222)]),
        event_with([component("AtAll")]),
        event_with([component("At", qq=999), component("Plain", text="今天怎么样")]),
        event_with([component("At", qq=999), component("Plain", text="/六爻")]),
        event_with([component("At", qq=999), component("Image")]),
        event_with([component("At", qq=999), component("Reply", text="")]),
        event_with([component("Plain", text="可可子你好")]),
        event_with([component("Plain", text="/可可子")]),
        event_with([component("Plain", text="[CQ:at,qq=999]")]),
        event_with([component("Plain", text='{"sub_type":"poke","target_id":999}')]),
        poke_event(target_id=1234),
        poke_event(user_id=999),
        poke_event(self_id=1234),
        poke_event(group_id=456),
        poke_event(notice_type="group_upload"),
    ],
)
def test_chat_commands_other_targets_and_forged_notices_do_not_match(event):
    assert trigger_for(event, ALL) is None


def test_renaming_only_matches_the_configured_name_and_respects_command_dispatch():
    event = event_with([component("Plain", text="小可")])
    assert trigger_for(event, ALL) is None
    assert trigger_for(event, {**ALL, "bot_name": "小可"}) == "name"
    event.extras["handlers_parsed_params"] = {"another.command": {}}
    assert trigger_for(event, {**ALL, "bot_name": "小可"}) is None


def test_private_self_and_unsupported_notice_platform_are_ignored():
    event = poke_event()
    event.group_id = ""
    assert trigger_for(event, ALL) is None
    event = poke_event()
    event.get_sender_id = lambda: "999"
    assert trigger_for(event, ALL) is None
    event = poke_event()
    event.get_platform_name = lambda: "telegram"
    assert trigger_for(event, ALL) is None


@pytest.mark.parametrize("kind", ["at", "name", "poke"])
def test_shortcuts_send_current_group_template_once_and_never_call_model(
    plugin_module, kind
):
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    plugin.service.observe_group("qq", "123", "目标群")
    state = plugin.service.snapshot()
    profile = deepcopy(state["default_profile"])
    profile["title"] = "群绑定的共享模板"
    profile["triggers"] = dict(ALL)
    state["templates"] = [{"id": "one", "name": "快捷模板", "profile": profile}]
    state["groups"][0].update(template_id="one", shortcut_enabled=True)
    plugin.service.save(state)
    plugin.render_images = AsyncMock(return_value=[b"first-page", b"second-page"])
    event = {
        "at": event_with([component("At", qq=999)]),
        "name": event_with([component("Plain", text="可可子")]),
        "poke": poke_event(),
    }[kind]

    async def run():
        assert await plugin.handle_help_shortcut(event) is True
        assert await plugin.handle_help_shortcut(event) is False
        await plugin.on_group_message(event)

    asyncio.run(run())
    assert event.stopped and event.suppressed
    assert event.stopped_when_sent == [True, True]
    assert [base64.b64decode(message[0]["base64"]) for message in event.sent] == [
        b"first-page",
        b"second-page",
    ]
    plugin.render_images.assert_awaited_once_with(profile, "目标群")


def test_group_switch_and_platform_identity_control_all_shortcuts(plugin_module):
    plugin = plugin_module.CustomHelpPlugin(context_with_platforms(), {})
    plugin.service.observe_group("qq", "123")
    state = plugin.service.snapshot()
    state["default_profile"]["triggers"] = dict(ALL)
    plugin.service.save(state)
    event = poke_event()
    assert asyncio.run(plugin.handle_help_shortcut(event)) is False
    state = plugin.service.snapshot()
    state["groups"][0]["shortcut_enabled"] = True
    plugin.service.save(state)
    event.platform_id = "other-bot"
    assert asyncio.run(plugin.handle_help_shortcut(event)) is False
    assert not event.sent and not event.stopped
