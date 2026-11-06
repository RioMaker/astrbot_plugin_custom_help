"""Persistent, independently editable help profiles. No AstrBot dependencies."""

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path


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
            "revision": 0,
            "default_profile": {
                "title": "可可子 · 群聊帮助",
                "intro": legacy_text
                or "按需查看本群开放的功能，发送对应指令即可使用。",
                "list_title": "插件帮助清单",
                "list_text": "这份帮助图包含以下插件：\n{plugins}",
                "footer": "发送 /help 或 /帮助，再次查看本群帮助。",
                "items": [self.seed_item(p) for p in self.catalog],
            },
            "groups": [],
        }
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.state = self._validate_state(loaded)
            except (ValueError, KeyError, TypeError) as exc:
                # Never overwrite damaged user data with defaults.
                raise HelpError(
                    "帮助配置文件损坏，请检查 help_profiles.json 或恢复备份。", 500
                ) from exc
        else:
            self._write(self.state)

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

    def _validate_state(self, payload):
        if (
            not isinstance(payload, dict)
            or type(payload.get("revision")) is not int
            or payload["revision"] < 0
        ):
            raise HelpError("配置版本不合法。")
        groups = payload.get("groups")
        if not isinstance(groups, list) or len(groups) > 2000:
            raise HelpError("群列表不合法，最多支持 2000 个群。")
        result = {
            "revision": payload["revision"],
            "default_profile": self.validate_profile(payload.get("default_profile")),
            "groups": [],
        }
        seen = set()
        for group in groups:
            if not isinstance(group, dict):
                raise HelpError("群配置格式不合法。")
            platform = _text(group.get("platform_id"), "平台标识", 200, True)
            gid = _text(group.get("group_id"), "群号", 200, True)
            key = group_key(platform, gid)
            if key in seen or group.get("key") != key:
                raise HelpError("群标识不一致或重复。")
            seen.add(key)
            result["groups"].append(
                {
                    "key": key,
                    "platform_id": platform,
                    "group_id": gid,
                    "name": _text(group.get("name", gid), "群名称", 200),
                    "profile": None
                    if group.get("profile") is None
                    else self.validate_profile(group["profile"]),
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
            candidate["groups"].extend(
                deepcopy(g) for g in self.state["groups"] if g["key"] not in known
            )
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
                        "profile": None,
                    }
                )
            else:
                return
            self._write(candidate)
            self.state = candidate

    def profile_for(self, platform_id, group_id):
        key = group_key(str(platform_id), str(group_id))
        with self.lock:
            group = next((g for g in self.state["groups"] if g["key"] == key), None)
            return deepcopy(
                (group or {}).get("profile") or self.state["default_profile"]
            )
