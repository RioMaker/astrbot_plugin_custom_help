"""Dashboard-authenticated editor API. Preview never modifies saved settings."""

import json
from functools import wraps

from .help_service import HelpError

PLUGIN_NAME = "astrbot_plugin_custom_help"


class AdminAPI:
    def __init__(self, plugin, web):
        self.plugin, self.web = plugin, web
        self.handlers = []

    def register(self):
        for endpoint, handler, method in (
            ("state", self.state, "GET"),
            ("save", self.save, "POST"),
            ("discover", self.discover, "POST"),
            ("preview", self.preview, "POST"),
        ):
            guarded = self.guard(handler)
            self.plugin.context.register_web_api(
                f"/{PLUGIN_NAME}/{endpoint}", guarded, [method], "按群帮助配置"
            )
            self.handlers.append(guarded)

    def close(self):
        routes = getattr(self.plugin.context, "registered_web_apis", None)
        if isinstance(routes, list):
            routes[:] = [route for route in routes if route[1] not in self.handlers]

    def guard(self, handler):
        @wraps(handler)
        async def guarded(*args, **kwargs):
            if self.plugin.closed:
                return self.web.error_response(
                    "插件已重载，请刷新页面。", status_code=503
                )
            if not self.web.request.username:
                return self.web.error_response(
                    "请先登录 AstrBot 管理面板。", status_code=401
                )
            if (
                self.web.request.headers.get("Sec-Fetch-Site", "").lower()
                == "cross-site"
            ):
                return self.web.error_response("请通过管理面板访问。", status_code=403)
            try:
                return self.web.json_response(
                    await handler(*args, **kwargs),
                    headers={"Cache-Control": "no-store"},
                )
            except HelpError as exc:
                return self.web.error_response(str(exc), status_code=exc.status)
            except Exception:  # noqa: BLE001 - do not expose server or connection details
                self.plugin.log_failure("管理页面操作")
                return self.web.error_response(
                    "操作失败，请检查插件日志后重试。", status_code=500
                )

        return guarded

    async def payload(self):
        if (self.web.request.content_type or "").split(";", 1)[0] != "application/json":
            raise HelpError("请求格式应为 JSON。", 415)
        raw = await self.web.request.body()
        if len(raw) > 8 * 1024 * 1024:
            raise HelpError("请求过大，请减少单次配置内容。", 413)
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HelpError("无效的 JSON。") from exc
        if not isinstance(value, dict):
            raise HelpError("请求必须是对象。")
        return value

    async def state(self):
        return {
            **self.plugin.service.snapshot(),
            "discovery_errors": self.plugin.discovery_errors,
        }

    async def discover(self):
        await self.plugin.discover_groups()
        return await self.state()

    async def save(self):
        import asyncio

        result = await asyncio.to_thread(self.plugin.service.save, await self.payload())
        return {**result, "discovery_errors": self.plugin.discovery_errors}

    async def preview(self):
        import base64

        payload = await self.payload()
        profile = self.plugin.service.validate_profile(payload.get("profile"))
        name = payload.get("group_name", "")
        if not isinstance(name, str) or len(name) > 200:
            raise HelpError("群名称格式不合法。")
        images = await self.plugin.render_images(profile, name)
        return {
            "images": [
                "data:image/png;base64," + base64.b64encode(image).decode("ascii")
                for image in images
            ]
        }
