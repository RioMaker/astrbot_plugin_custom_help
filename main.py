"""Replace AstrBot's built-in /help response with configurable text."""

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


PLUGIN_NAME = "astrbot_plugin_custom_help"
PLUGIN_AUTHOR = "Rio"
PLUGIN_DESC = "拦截 AstrBot 默认帮助指令并返回可配置的自定义帮助信息"
PLUGIN_VERSION = "1.0.0"
PLUGIN_REPO = "https://github.com/RioMaker/astrbot_plugin_custom_help"

HELP_PRIORITY = 1000
DEFAULT_HELP_TEXT = """这里是自定义帮助信息。

请在 AstrBot WebUI 的插件配置中修改“自定义帮助内容”。"""


@register(
    PLUGIN_NAME,
    PLUGIN_AUTHOR,
    PLUGIN_DESC,
    PLUGIN_VERSION,
    PLUGIN_REPO,
)
class CustomHelpPlugin(Star):
    """Serve a custom response before AstrBot's built-in help handler."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    @filter.command("help", alias={"帮助"}, priority=HELP_PRIORITY)
    async def custom_help(self, event: AstrMessageEvent):
        """返回自定义帮助，并终止事件传播以屏蔽框架默认帮助。"""
        help_text = str(self.config.get("help_text", DEFAULT_HELP_TEXT) or "").strip()
        if not help_text:
            help_text = DEFAULT_HELP_TEXT

        # 必须独占该事件，否则内置 help handler 仍可能继续回复。
        event.stop_event()
        yield event.plain_result(help_text)

