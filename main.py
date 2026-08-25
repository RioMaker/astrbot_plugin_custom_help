"""Replace AstrBot's built-in /help with configurable overview and detail blocks."""

from __future__ import annotations

import re
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.star.filter.command import GreedyStr


PLUGIN_NAME = "astrbot_plugin_custom_help"
PLUGIN_AUTHOR = "Rio"
PLUGIN_DESC = "用可配置帮助块替换 AstrBot 默认帮助，支持总览、子命令和图片输出"
PLUGIN_VERSION = "1.1.0"
PLUGIN_REPO = "https://github.com/RioMaker/astrbot_plugin_custom_help"

HELP_PRIORITY = 1000
DEFAULT_OVERVIEW_TITLE = "可用指令"
DEFAULT_OVERVIEW_FOOTER = "发送 /help <块名称> 查看对应的详细帮助。"
DEFAULT_EMPTY_HELP = "尚未配置帮助块，请先在 AstrBot WebUI 中添加帮助块。"

HELP_IMAGE_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <style>
    * { box-sizing: border-box; }
    html, body { margin: 0; padding: 0; background: #edf1f7; }
    body {
      width: 920px;
      padding: 34px;
      color: #182033;
      font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
    }
    .card {
      width: 100%;
      padding: 42px 46px 46px;
      border: 1px solid #d9e0ec;
      border-radius: 26px;
      background: #ffffff;
      box-shadow: 0 18px 48px rgba(35, 48, 74, 0.12);
    }
    .eyebrow {
      margin-bottom: 14px;
      color: #52647f;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0.14em;
    }
    .content {
      margin: 0;
      color: #182033;
      font-family: "Noto Sans Mono CJK SC", "Microsoft YaHei", monospace;
      font-size: 25px;
      font-weight: 500;
      line-height: 1.72;
      overflow-wrap: anywhere;
      white-space: pre-wrap;
    }
    .rule {
      width: 72px;
      height: 6px;
      margin: 0 0 26px;
      border-radius: 999px;
      background: linear-gradient(90deg, #5b6cf9, #8b5cf6);
    }
  </style>
</head>
<body>
  <main class="card">
    <div class="eyebrow">{{ label|e }}</div>
    <div class="rule"></div>
    <pre class="content">{{ content|e }}</pre>
  </main>
</body>
</html>
"""


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

    @filter.command("help", alias={"帮助"}, priority=HELP_PRIORITY)
    async def custom_help(
        self,
        event: AstrMessageEvent,
        block_name: GreedyStr,
    ):
        """返回帮助总览或指定帮助块，并阻止框架默认帮助继续响应。"""
        query = str(block_name or "").strip()
        if query:
            text, label = self._build_detail(query), "详细帮助"
        else:
            text, label = self._build_overview(), "指令总览"

        event.stop_event()
        yield await self._build_result(event, text, label)

    async def _build_result(
        self,
        event: AstrMessageEvent,
        text: str,
        label: str,
    ):
        if self._output_mode() == "text":
            return event.plain_result(text)

        try:
            image_url = await self.html_render(
                HELP_IMAGE_TEMPLATE,
                {"content": text, "label": label},
                options={
                    "type": "png",
                    "full_page": True,
                    "animations": "disabled",
                },
            )
            if not image_url:
                raise RuntimeError("html_render returned an empty result")
            return event.image_result(image_url)
        except Exception as exc:
            logger.warning(
                "[custom_help] 帮助图片渲染失败，已回退为纯文本："
                f"{type(exc).__name__}"
            )
            return event.plain_result(text)

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
