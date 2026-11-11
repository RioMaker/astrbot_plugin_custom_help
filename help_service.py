"""Persistent, independently editable help profiles. No AstrBot dependencies."""

from __future__ import annotations

import json
import os
import re
import threading
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 2
DEFAULT_TRIGGERS = {"at": True, "name": False, "poke": False, "bot_name": "可可子"}


class HelpError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def group_key(platform_id: str, group_id: str) -> str:
    return json.dumps(
        [platform_id, group_id], ensure_ascii=False, separators=(",", ":")
    )


def _text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise HelpError(f"{label}必须是最多 {limit} 字的文本。")
    if required and not value.strip():
        raise HelpError(f"{label}不能为空。")
    # Strip control characters that cannot be rendered, preserving line breaks.
    return "".join(
        c for c in value.replace("\r\n", "\n") if c in "\n\t" or ord(c) >= 32
    )


class HelpService:
    def __init__(self, data_dir: Path, catalog_path: Path, legacy_text: str = ""):
        self.path = Path(data_dir) / "help_profiles.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))[
            "plugins"
        ]
        self.ids = {p["id"] for p in self.catalog}
        if len(self.ids) != len(self.catalog):
            raise HelpError("帮助目录包含重复插件标识。")
        self.lock = threading.RLock()
        if len(legacy_text) > 3000:
            legacy_text = "旧版帮助超过 3000 字，完整内容仍保存在插件配置的“旧版帮助文本 / 私聊帮助”中。请在此编辑群帮助开场说明。"
        self.state = {
            "schema_version": SCHEMA_VERSION,
            "revision": 0,
            "default_profile": {
                "title": "可可子 · 群聊帮助",
                "intro": legacy_text
                or "按需查看本群开放的功能，发送对应指令即可使用。",
                "list_title": "插件帮助清单",
                "list_text": "这份帮助图包含以下插件：\n{plugins}",
                "footer": "发送 /help 或 /帮助，再次查看本群帮助。",
                "items": [self.seed_item(p) for p in self.catalog],
                "triggers": dict(DEFAULT_TRIGGERS),
            },
            "templates": [],
            "groups": [],
        }
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.state = self._validate_state(loaded, allow_legacy=True)
            except (ValueError, KeyError, TypeError) as exc:
                # Never overwrite damaged user data with defaults.
                raise HelpError(
                    "帮助配置文件损坏，请检查 help_profiles.json 或恢复备份。", 500
                ) from exc
            if loaded.get("schema_version", 1) == 1:
                backup = self.path.with_name("help_profiles.v1.backup.json")
                if not backup.exists():
                    with backup.open("xb") as file:
                        file.write(self.path.read_bytes())
                self.state["revision"] += 1
                self._write(self.state)
            self._refresh_catalog_bodies()
        else:
            self._write(self.state)

    def _refresh_catalog_bodies(self):
        """Refresh explicitly listed stock text without replacing user edits."""
        updates = {p["id"]: p for p in self.catalog if p.get("previous_bodies")}
        if not updates:
            return
        candidate = deepcopy(self.state)
        profiles = [candidate["default_profile"]] + [
            template["profile"] for template in candidate["templates"]
        ]
        changed = False
        for profile in profiles:
            enabled_length = sum(
                len(item["body"]) for item in profile["items"] if item["enabled"]
            )
            for item in profile["items"]:
                plugin = updates.get(item["id"])
                if not plugin or item["body"] not in plugin["previous_bodies"]:
                    continue
                body = _text(plugin["body"], "body", 6000)
                if body == item["body"]:
                    continue
                delta = len(body) - len(item["body"]) if item["enabled"] else 0
                # A longer default must not make an otherwise valid profile unloadable.
                if enabled_length + delta > 30000:
                    continue
                item["body"] = body
                enabled_length += delta
                changed = True
        if changed:
            candidate["revision"] += 1
            self._write(candidate)
            self.state = candidate

    @staticmethod
    def seed_item(plugin):
        return {
            "id": plugin["id"],
            "title": plugin["title"],
            "body": plugin["body"],
            "enabled": plugin.get("default_enabled", False),
        }

    def validate_profile(self, value):
        if not isinstance(value, dict):
            raise HelpError("帮助模板必须是对象。")
        profile = {
            key: _text(value.get(key, ""), key, limit, key in ("title", "list_title"))
            for key, limit in (
                ("title", 120),
                ("intro", 3000),
                ("list_title", 120),
                ("list_text", 3000),
                ("footer", 1000),
            )
        }
        triggers = value.get("triggers", DEFAULT_TRIGGERS)
        if not isinstance(triggers, dict) or any(
            type(triggers.get(key)) is not bool for key in ("at", "name", "poke")
        ):
            raise HelpError("快捷帮助的触发开关必须是布尔值。")
        bot_name = _text(triggers.get("bot_name"), "点名名称", 40, True).strip()
        if any(char in bot_name for char in "\n\t"):
            raise HelpError("点名名称不能包含换行或制表符。")
        profile["triggers"] = {
            **{key: triggers[key] for key in ("at", "name", "poke")},
            "bot_name": bot_name,
        }
        items = value.get("items")
        if not isinstance(items, list) or len(items) > len(self.catalog):
            raise HelpError("插件帮助列表不合法。")
        seen = set()
        profile["items"] = []
        for item in items:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("id"), str)
                or item["id"] not in self.ids
                or item["id"] in seen
            ):
                raise HelpError("帮助列表包含未知或重复的插件。")
            seen.add(item["id"])
            if type(item.get("enabled")) is not bool:
                raise HelpError("帮助开关必须是布尔值。")
            profile["items"].append(
                {
                    "id": item["id"],
                    "title": _text(item.get("title"), "插件标题", 120, True),
                    "body": _text(item.get("body"), "插件说明", 6000),
                    "enabled": item["enabled"],
                }
            )
        # Catalog additions never silently enable new sections in saved templates.
        profile["items"].extend(
            {**self.seed_item(p), "enabled": False}
            for p in self.catalog
            if p["id"] not in seen
        )
        if sum(len(i["body"]) for i in profile["items"] if i["enabled"]) > 30000:
            raise HelpError("已开启的说明总长度不能超过 30000 字，请精简后再保存。")
        return profile

    def _validate_state(self, payload, *, allow_legacy=False):
        if (
            not isinstance(payload, dict)
            or type(payload.get("revision")) is not int
            or payload["revision"] < 0
        ):
            raise HelpError("配置版本不合法。")
        schema = payload.get("schema_version", 1)
        legacy = allow_legacy and schema == 1
        if type(schema) is not int or (schema != SCHEMA_VERSION and not legacy):
            raise HelpError("帮助配置结构已升级，请导出草稿后重新载入页面。", 409)
        groups = payload.get("groups")
        if not isinstance(groups, list) or len(groups) > 2000:
            raise HelpError("群列表不合法，最多支持 2000 个群。")
        result = {
            "schema_version": SCHEMA_VERSION,
            "revision": payload["revision"],
            "default_profile": self.validate_profile(payload.get("default_profile")),
            "templates": [],
            "groups": [],
        }
        templates = [] if legacy else payload.get("templates")
        if not isinstance(templates, list) or len(templates) > 2000:
            raise HelpError("帮助模板列表不合法，最多支持 2000 个模板。")
        template_ids = set()
        for template in templates:
            if not isinstance(template, dict):
                raise HelpError("模板配置格式不合法。")
            identifier = template.get("id")
            if (
                not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier)
                or identifier in template_ids
                or identifier == "__default__"
            ):
                raise HelpError("模板标识不合法或重复。")
            template_ids.add(identifier)
            result["templates"].append(
                {
                    "id": identifier,
                    "name": _text(template.get("name"), "模板名称", 80, True).strip(),
                    "profile": self.validate_profile(template.get("profile")),
                }
            )
        seen = set()
        for group in groups:
            if not isinstance(group, dict):
                raise HelpError("群配置格式不合法。")
            if not legacy and "profile" in group:
                raise HelpError("群独立配置已改为模板绑定，请重新载入页面。", 409)
            platform = _text(group.get("platform_id"), "平台标识", 200, True)
            gid = _text(group.get("group_id"), "群号", 200, True)
            key = group_key(platform, gid)
            if key in seen or group.get("key") != key:
                raise HelpError("群标识不一致或重复。")
            seen.add(key)
            template_id = group.get("template_id")
            if legacy:
                template_id = None
                if group.get("profile") is not None:
                    template_id = uuid4().hex
                    result["templates"].append(
                        {
                            "id": template_id,
                            "name": (
                                _text(group.get("name", gid), "群名称", 200) or gid
                            )[:70]
                            + " · 独立模板",
                            "profile": self.validate_profile(group["profile"]),
                        }
                    )
            elif template_id is not None and (
                not isinstance(template_id, str) or template_id not in template_ids
            ):
                raise HelpError("群聊引用了不存在的帮助模板。")
            shortcut_enabled = group.get("shortcut_enabled", False)
            if type(shortcut_enabled) is not bool:
                raise HelpError("群快捷帮助开关必须是布尔值。")
            result["groups"].append(
                {
                    "key": key,
                    "platform_id": platform,
                    "group_id": gid,
                    "name": _text(group.get("name", gid), "群名称", 200),
                    "template_id": template_id,
                    "shortcut_enabled": shortcut_enabled,
                }
            )
        return result

    def _write(self, state):
        tmp = self.path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as file:
                json.dump(state, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            os.replace(tmp, self.path)
        finally:
            tmp.unlink(missing_ok=True)

    def snapshot(self):
        with self.lock:
            return {**deepcopy(self.state), "catalog": deepcopy(self.catalog)}

    def save(self, payload):
        candidate = self._validate_state(payload)
        with self.lock:
            if candidate["revision"] != self.state["revision"]:
                raise HelpError(
                    "配置已被其他页面修改。请保留当前文案，重新载入后再保存。", 409
                )
            # Auto-discovery can add groups while the editor is open. Preserve them.
            known = {g["key"] for g in candidate["groups"]}
            if any(
                g["key"] not in known
                and (g["template_id"] is not None or g["shortcut_enabled"])
                for g in self.state["groups"]
            ):
                raise HelpError("已配置的群不能从保存内容中移除，请重新载入页面。", 409)
            candidate["groups"].extend(
                deepcopy(g) for g in self.state["groups"] if g["key"] not in known
            )
            if len(candidate["groups"]) > 2000:
                raise HelpError("合并自动发现的群后超过 2000 个，请重新载入页面。", 409)
            candidate["revision"] += 1
            self._write(candidate)
            self.state = candidate
            return self.snapshot()

    def observe_group(self, platform_id, group_id, name=""):
        platform_id, group_id = (
            str(platform_id or "").strip(),
            str(group_id or "").strip(),
        )
        if (
            not platform_id
            or not group_id
            or len(platform_id) > 200
            or len(group_id) > 200
        ):
            return
        name = str(name or "")[:200]
        key = group_key(platform_id, group_id)
        with self.lock:
            existing = next((g for g in self.state["groups"] if g["key"] == key), None)
            if existing and (not name or existing["name"] == name):
                return
            candidate = deepcopy(self.state)
            group = next((g for g in candidate["groups"] if g["key"] == key), None)
            if group:
                if not name or group["name"] == name:
                    return
                group["name"] = name
            elif len(candidate["groups"]) < 2000:
                candidate["groups"].append(
                    {
                        "key": key,
                        "platform_id": platform_id,
                        "group_id": group_id,
                        "name": name or group_id,
                        "template_id": None,
                        "shortcut_enabled": False,
                    }
                )
            else:
                return
            self._write(candidate)
            self.state = candidate

    def profile_for(self, platform_id, group_id):
        return self.settings_for(platform_id, group_id)[0]

    def settings_for(self, platform_id, group_id):
        """Resolve a shared template and the group's shortcut switch atomically."""
        key = group_key(str(platform_id), str(group_id))
        with self.lock:
            group = next((g for g in self.state["groups"] if g["key"] == key), None)
            template = next(
                (
                    t
                    for t in self.state["templates"]
                    if t["id"] == (group or {}).get("template_id")
                ),
                None,
            )
            return deepcopy(
                template["profile"] if template else self.state["default_profile"]
            ), bool(group and group["shortcut_enabled"])
