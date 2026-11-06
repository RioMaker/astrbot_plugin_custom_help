"""Editable group help and an AstrBot management page."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
from collections import OrderedDict
from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image
from astrbot.api.star import Context, Star, StarTools, register

from .admin_api import AdminAPI
from .help_render import format_text, render_help
from .help_service import HelpService

PLUGIN_NAME = "astrbot_plugin_custom_help"
PLUGIN_VERSION = "2.0.0"
HELP_PRIORITY = 1000
DEFAULT_HELP_TEXT = (
    "这里是自定义帮助信息。\n\n请在 AstrBot WebUI 的插件配置中修改“自定义帮助内容”。"
)


@register(
    PLUGIN_NAME,
    "Rio",
    "按群编辑、预览和发送插件帮助图",
    PLUGIN_VERSION,
    "https://github.com/RioMaker/astrbot_plugin_custom_help",
)
class CustomHelpPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        legacy = str(config.get("help_text", "") or "").strip()
        if legacy == DEFAULT_HELP_TEXT:
            legacy = ""
        self.service = HelpService(
            StarTools.get_data_dir(PLUGIN_NAME),
            Path(__file__).with_name("help_catalog.json"),
            legacy,
        )
        self.closed = False
        self.admin = None
        self.discovery_errors = []
        self.discovery_lock = asyncio.Lock()
        self.render_lock = asyncio.Lock()
        self.cache = OrderedDict()
        self.discovery_task = None

    def log_failure(self, action):
        logger.error(
            "[custom_help] %s失败，请检查平台连接、数据目录和字体资源。", action
        )

    async def initialize(self):
        try:
            web = importlib.import_module("astrbot.api.web")
            self.admin = AdminAPI(self, web)
            self.admin.register()
        except (ImportError, AttributeError):
            logger.warning(
                "[custom_help] 当前 AstrBot 缺少插件页面 API，请升级后使用按群帮助配置页。"
            )
        self.discovery_task = asyncio.create_task(self._discovery_loop())

    async def _discovery_loop(self):
        while not self.closed:
            try:
                await self.discover_groups()
            except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
                self.log_failure("自动发现群聊")
            await asyncio.sleep(300)

    async def discover_groups(self):
        async with self.discovery_lock:
            errors = []
            try:
                manager = getattr(self.context, "platform_manager", None)
                platforms = manager.get_insts() if manager else []
            except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
                platforms = []
                errors.append("平台列表暂不可用；收到群消息时仍会自动登记。")

            async def fetch(platform_id, client, bot_id):
                try:
                    rows = await asyncio.wait_for(
                        client.call_action(
                            "get_group_list",
                            **({"self_id": bot_id} if bot_id is not None else {}),
                        ),
                        timeout=5,
                    )
                    if isinstance(rows, dict):
                        if rows.get("status", "ok") != "ok":
                            raise ValueError("group lookup failed")
                        rows = rows.get("data")
                    if not isinstance(rows, list):
                        raise TypeError("invalid group response")
                    for row in rows:
                        if isinstance(row, dict) and type(row.get("group_id")) in (
                            str,
                            int,
                        ):
                            await asyncio.to_thread(
                                self.service.observe_group,
                                platform_id,
                                row["group_id"],
                                row.get("group_name", ""),
                            )
                except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
                    errors.append(
                        f"平台 {platform_id} 群列表暂不可用，已保留原有群设置；收到消息后可自动登记。"
                    )

            calls = []
            for platform in platforms:
                try:
                    meta = platform.meta()
                    if meta.name != "aiocqhttp":
                        continue
                    client = platform.get_client()
                    connections = getattr(client, "_wsr_api_clients", None)
                    bot_ids = (
                        list(connections)
                        if isinstance(connections, dict) and connections
                        else [None]
                    )
                    calls.extend(
                        fetch(str(meta.id), client, bot_id) for bot_id in bot_ids
                    )
                except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
                    errors.append(
                        "某个平台暂不支持群列表发现，将在收到群消息时自动登记。"
                    )
            if calls:
                await asyncio.gather(*calls)
            self.discovery_errors = list(dict.fromkeys(errors))

    async def render_images(self, profile, group_name=""):
        key = json.dumps([profile, group_name], ensure_ascii=False, sort_keys=True)
        async with self.render_lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            images = await asyncio.to_thread(render_help, profile, group_name)
            self.cache[key] = images
            while (
                len(self.cache) > 12
                or sum(len(image) for batch in self.cache.values() for image in batch)
                > 24 * 1024 * 1024
            ):
                self.cache.popitem(last=False)
            return images

    async def _observe_event(self, event):
        gid = str(event.get_group_id() or "")
        if gid:
            platform_id = str(event.get_platform_id() or event.get_platform_name())
            await asyncio.to_thread(self.service.observe_group, platform_id, gid)

    @filter.event_message_type(
        filter.EventMessageType.GROUP_MESSAGE, priority=HELP_PRIORITY + 1
    )
    async def on_group_message(self, event: AstrMessageEvent):
        try:
            await self._observe_event(event)
        except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
            self.log_failure("群聊登记")

    @filter.command("help", alias={"帮助"}, priority=HELP_PRIORITY)
    async def custom_help(self, event: AstrMessageEvent):
        event.stop_event()
        gid = str(event.get_group_id() or "")
        if not gid:
            legacy = str(self.config.get("help_text", "") or "").strip()
            text = (
                legacy
                if legacy and legacy != DEFAULT_HELP_TEXT
                else format_text(self.service.snapshot()["default_profile"])
            )
            for offset in range(0, len(text), 3500):
                await event.send(event.plain_result(text[offset : offset + 3500]))
            return
        platform_id = str(event.get_platform_id() or event.get_platform_name())
        try:
            await self._observe_event(event)
        except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
            self.log_failure("群聊登记")
        profile = self.service.profile_for(platform_id, gid)
        groups = self.service.snapshot()["groups"]
        group = next(
            (
                g
                for g in groups
                if g["platform_id"] == platform_id and g["group_id"] == gid
            ),
            None,
        )
        name = group["name"] if group else gid
        try:
            images = await self.render_images(profile, name)
        except Exception:  # noqa: BLE001 - isolate platform, storage and rendering failures
            self.log_failure("帮助图生成")
            text = format_text(profile)
            for offset in range(0, len(text), 3500):
                await event.send(event.plain_result(text[offset : offset + 3500]))
            return
        for image in images:
            await event.send(
                event.chain_result(
                    [Image.fromBase64(base64.b64encode(image).decode("ascii"))]
                )
            )

    async def terminate(self):
        self.closed = True
        if self.discovery_task:
            self.discovery_task.cancel()
            try:
                await self.discovery_task
            except asyncio.CancelledError:
                pass
        if self.admin:
            self.admin.close()
        self.cache.clear()
