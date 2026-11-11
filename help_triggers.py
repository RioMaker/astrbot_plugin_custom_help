"""Recognize explicit help shortcuts, without interpreting ordinary chat."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping


def _visible(value):
    return "".join(
        char
        for char in str(value or "")
        if char.isspace() or unicodedata.category(char) not in {"Cf", "Cc"}
    ).strip()


def trigger_for(event, settings):
    """Only top-level messages or authenticated OneBot notices can match."""
    bot = str(event.get_self_id() or "")
    sender = str(event.get_sender_id() or "")
    group = str(event.get_group_id() or "")
    if not bot or not sender or not group or bot == sender:
        return None
    obj = event.message_obj
    raw = getattr(obj, "raw_message", None)
    if isinstance(raw, Mapping) and raw.get("post_type") == "notice":
        if (
            settings["poke"]
            and str(event.get_platform_name()).casefold()
            in {"aiocqhttp", "onebot", "onebot11", "napcat"}
            and (raw.get("notice_type"), raw.get("sub_type")) == ("notify", "poke")
            and str(raw.get("self_id", "")) == bot
            and str(raw.get("target_id", "")) == bot
            and str(raw.get("user_id", "")) == sender
            and str(raw.get("group_id", "")) == group
        ):
            return "poke"
        return None
    getter = getattr(event, "get_extra", None)
    if callable(getter) and getter("handlers_parsed_params", {}):
        return None
    chain = getattr(obj, "message", None)
    if chain is None:
        getter = getattr(event, "get_messages", None)
        chain = getter() if callable(getter) else None
    at_bot, texts = False, []
    if chain is None:
        texts.append(getattr(obj, "message_str", getattr(event, "message_str", "")))
    else:
        for part in chain:
            kind = type(part).__name__
            if kind == "At" and str(getattr(part, "qq", "")) == bot:
                at_bot = True
            elif kind == "Plain":
                texts.append(getattr(part, "text", ""))
            else:
                # Quotes, images, @others/@all, forwards and unknown components
                # carry their own intent; never turn them into a help shortcut.
                return None
    text = _visible("".join(texts))
    if at_bot and not text and settings["at"]:
        return "at"
    if not at_bot and settings["name"] and text == settings["bot_name"]:
        return "name"
    return None
