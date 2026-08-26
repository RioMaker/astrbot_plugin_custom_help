"""Replace AstrBot's built-in /help with configurable overview and detail blocks."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.core.star.filter.command import GreedyStr

if __package__:
    from .renderer import HelpImageRenderer, HelpRenderError
else:  # pragma: no cover - direct local execution
    from renderer import HelpImageRenderer, HelpRenderError


PLUGIN_NAME = "astrbot_plugin_custom_help"
PLUGIN_AUTHOR = "Rio"
PLUGIN_DESC = "用可配置帮助块替换 AstrBot 默认帮助，支持总览、子命令和快速图片输出"
PLUGIN_VERSION = "1.2.0"
PLUGIN_REPO = "https://github.com/RioMaker/astrbot_plugin_custom_help"

HELP_PRIORITY = 1000
CACHE_FILE_LIMIT = 24
DEFAULT_OVERVIEW_TITLE = "可用指令"
DEFAULT_OVERVIEW_FOOTER = "发送 /help <块名称> 查看对应的详细帮助。"
DEFAULT_EMPTY_HELP = "尚未配置帮助块，请先在 AstrBot WebUI 中添加帮助块。"


@register(
    PLUGIN_NAME,
    PLUGIN_AUTHOR,
    PLUGIN_DESC,
    PLUGIN_VERSION,
    PLUGIN_REPO,
)
class CustomHelpPlugin(Star):
    """Serve a configurable command overview and named detail blocks."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._render_lock = asyncio.Lock()
        self.cache_dir: Path | None = None
        self.renderer: HelpImageRenderer | None = None

        try:
            data_dir = Path(StarTools.get_data_dir(PLUGIN_NAME))
            self.cache_dir = data_dir / "image_cache"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(
                "[custom_help] 无法创建帮助图片缓存目录，将回退纯文本："
                f"{type(exc).__name__}"
            )

        try:
            self.renderer = HelpImageRenderer(
                font_path=self._config_text("image_font_path", ""),
                theme=self._config_text("image_theme", "violet"),
            )
        except (HelpRenderError, OSError, ValueError) as exc:
            logger.warning(
                "[custom_help] 本地帮助图片渲染器不可用，将回退纯文本："
                f"{type(exc).__name__}"
            )

    @filter.command("help", alias={"帮助"}, priority=HELP_PRIORITY)
    async def custom_help(
        self,
        event: AstrMessageEvent,
        block_name: GreedyStr,
    ):
        """返回帮助总览或指定帮助块，并阻止框架默认帮助继续响应。"""
        query = str(block_name or "").strip()
        if query:
            text = self._build_detail(query)
        else:
            text = self._build_overview()

        event.stop_event()
        document = self._build_image_document(query)
        yield await self._build_result(event, text, document)

    async def _build_result(
        self,
        event: AstrMessageEvent,
        text: str,
        document: dict[str, Any],
    ):
        if self._output_mode() == "text":
            return event.plain_result(text)
        if self.renderer is None or self.cache_dir is None:
            return event.plain_result(text)

        try:
            image_path = await self._render_cached_image(document)
            return event.image_result(str(image_path.absolute()))
        except Exception as exc:
            logger.warning(
                "[custom_help] 帮助图片生成失败，已回退为纯文本："
                f"{type(exc).__name__}"
            )
            return event.plain_result(text)

    async def _render_cached_image(self, document: dict[str, Any]) -> Path:
        if self.renderer is None or self.cache_dir is None:
            raise HelpRenderError("renderer or cache directory is unavailable")

        cache_payload = {
            "renderer": self.renderer.cache_identity(),
            "document": document,
        }
        serialized = json.dumps(
            cache_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:24]
        output_path = self.cache_dir / f"help_{digest}.png"
        if self._valid_cached_image(output_path):
            return output_path

        async with self._render_lock:
            if self._valid_cached_image(output_path):
                return output_path
            await asyncio.to_thread(self.renderer.render, document, output_path)
            if not self._valid_cached_image(output_path):
                raise HelpRenderError("renderer did not produce a valid PNG")
            await asyncio.to_thread(self._prune_cache, output_path)
            return output_path

    def _prune_cache(self, current_path: Path) -> None:
        if self.cache_dir is None:
            return
        cached = sorted(
            (
                path
                for path in self.cache_dir.glob("help_*.png")
                if path.is_file() and path != current_path
            ),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for stale_path in cached[CACHE_FILE_LIMIT - 1 :]:
            try:
                stale_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _valid_cached_image(path: Path) -> bool:
        try:
            return path.is_file() and path.stat().st_size >= 128
        except OSError:
            return False

    def _build_overview(self) -> str:
        blocks = self._help_blocks()
        title = self._config_text("overview_title", DEFAULT_OVERVIEW_TITLE)
        sections: list[str] = []

        for block in blocks:
            if not block["show_in_overview"] or not block["commands"]:
                continue
            sections.append("\n".join([f"【{block['title']}】", *block["commands"]]))

        if not sections:
            legacy_text = self._config_text("help_text", "")
            if legacy_text:
                return legacy_text
            return DEFAULT_EMPTY_HELP

        parts = [title, "\n\n".join(sections)]
        footer = self._config_text("overview_footer", DEFAULT_OVERVIEW_FOOTER)
        if footer:
            parts.append(footer)

        names = "、".join(block["name"] for block in blocks)
        if names:
            parts.append(f"可用帮助块：{names}")
        return "\n\n".join(parts)

    def _build_detail(self, query: str) -> str:
        blocks = self._help_blocks()
        block = self._find_block(blocks, query)
        if block is None:
            names = "、".join(item["name"] for item in blocks) or "暂无"
            return (
                f"没有找到帮助块：{query}\n\n"
                f"可用帮助块：{names}\n"
                "发送 /help 查看全部指令。"
            )

        parts = [f"【{block['title']}】"]
        if block["summary"]:
            parts.append(block["summary"])
        if block["commands"]:
            parts.append("指令列表：\n" + "\n".join(block["commands"]))
        if block["details"]:
            parts.append("详细说明：\n" + block["details"])
        return "\n\n".join(parts)

    def _build_image_document(self, query: str) -> dict[str, Any]:
        blocks = self._help_blocks()
        if not query:
            visible_blocks = [
                block
                for block in blocks
                if block["show_in_overview"] and block["commands"]
            ]
            if not visible_blocks:
                return {
                    "kicker": "指令总览",
                    "title": self._config_text(
                        "overview_title",
                        DEFAULT_OVERVIEW_TITLE,
                    ),
                    "subtitle": "",
                    "cards": [
                        {
                            "badge": "提示",
                            "title": "尚未配置指令摘要",
                            "body": DEFAULT_EMPTY_HELP,
                            "commands": [],
                        }
                    ],
                    "footer": "",
                }

            names = "、".join(block["name"] for block in blocks)
            footer_parts = [
                self._config_text(
                    "overview_footer",
                    DEFAULT_OVERVIEW_FOOTER,
                )
            ]
            if names:
                footer_parts.append(f"可用帮助块：{names}")
            return {
                "kicker": "指令总览",
                "title": self._config_text(
                    "overview_title",
                    DEFAULT_OVERVIEW_TITLE,
                ),
                "subtitle": "选择一条指令开始使用",
                "cards": [
                    {
                        "badge": block["name"],
                        "title": block["title"],
                        "summary": "",
                        "commands": [
                            self._command_parts(line)
                            for line in block["commands"]
                        ],
                        "body": "",
                    }
                    for block in visible_blocks
                ],
                "footer": "\n".join(part for part in footer_parts if part),
            }

        block = self._find_block(blocks, query)
        if block is None:
            names = "、".join(item["name"] for item in blocks) or "暂无"
            return {
                "kicker": "帮助查询",
                "title": "没有找到这个帮助块",
                "subtitle": f"查询内容：{query}",
                "cards": [
                    {
                        "badge": "可用帮助块",
                        "title": names,
                        "summary": "",
                        "commands": [],
                        "body": "请检查名称或别名后重试。",
                    }
                ],
                "footer": "发送 /help 查看全部指令。",
            }

        cards = []
        if block["commands"]:
            cards.append(
                {
                    "badge": block["name"],
                    "title": "指令列表",
                    "summary": "",
                    "commands": [
                        self._command_parts(line)
                        for line in block["commands"]
                    ],
                    "body": "",
                }
            )
        if block["details"]:
            cards.append(
                {
                    "badge": "详细说明",
                    "title": "使用方法与注意事项",
                    "summary": "",
                    "commands": [],
                    "body": block["details"],
                }
            )
        if not cards:
            cards.append(
                {
                    "badge": block["name"],
                    "title": "暂无更多说明",
                    "summary": "",
                    "commands": [],
                    "body": "请在插件配置中补充指令摘要或详细说明。",
                }
            )
        return {
            "kicker": "详细帮助",
            "title": block["title"],
            "subtitle": block["summary"],
            "cards": cards,
            "footer": "发送 /help 返回全部指令。",
        }

    @staticmethod
    def _command_parts(line: str) -> dict[str, str]:
        parts = re.split(r"\s+[—–-]\s+", line, maxsplit=1)
        return {
            "command": parts[0].strip(),
            "description": parts[1].strip() if len(parts) == 2 else "",
        }

    def _help_blocks(self) -> list[dict[str, Any]]:
        raw_blocks = self.config.get("help_blocks", [])
        if not isinstance(raw_blocks, list):
            return []

        blocks: list[dict[str, Any]] = []
        for raw in raw_blocks:
            if not isinstance(raw, dict) or not self._as_bool(raw.get("enabled"), True):
                continue

            title = self._clean_text(raw.get("title"))
            name = self._clean_text(raw.get("block_name")) or title
            if not name:
                continue

            blocks.append(
                {
                    "name": name,
                    "title": title or name,
                    "aliases": self._aliases(raw.get("aliases")),
                    "summary": self._clean_text(raw.get("summary")),
                    "commands": self._lines(raw.get("commands")),
                    "details": self._clean_text(raw.get("details")),
                    "show_in_overview": self._as_bool(
                        raw.get("show_in_overview"),
                        True,
                    ),
                }
            )
        return blocks

    @staticmethod
    def _find_block(
        blocks: list[dict[str, Any]],
        query: str,
    ) -> dict[str, Any] | None:
        normalized = query.strip().casefold()
        for block in blocks:
            candidates = [block["name"], block["title"], *block["aliases"]]
            if any(item.casefold() == normalized for item in candidates):
                return block
        return None

    def _output_mode(self) -> str:
        value = self._config_text("output_mode", "image").casefold()
        if value in {"text", "文本", "纯文本"}:
            return "text"
        return "image"

    def _config_text(self, key: str, default: str) -> str:
        value = self._clean_text(self.config.get(key, default))
        return value or default

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _lines(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [text for item in value if (text := cls._clean_text(item))]
        return [line.strip() for line in str(value or "").splitlines() if line.strip()]

    @classmethod
    def _aliases(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return [text for item in value if (text := cls._clean_text(item))]
        return [
            item.strip()
            for item in re.split(r"[,，\n]+", str(value or ""))
            if item.strip()
        ]

    @staticmethod
    def _as_bool(value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "1", "yes", "on", "是", "开"}:
                return True
            if normalized in {"false", "0", "no", "off", "否", "关"}:
                return False
        return bool(value)
