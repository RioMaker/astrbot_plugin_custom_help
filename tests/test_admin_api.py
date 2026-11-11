from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import load_module


@pytest.fixture
def admin(service):
    module = load_module("admin_api")
    request = SimpleNamespace(
        username="admin",
        headers={},
        content_type="application/json",
        body=AsyncMock(return_value=b"{}"),
    )
    web = SimpleNamespace(
        request=request,
        error_response=lambda message, status_code=400: {
            "error": message,
            "code": status_code,
        },
        json_response=lambda data, **kwargs: {
            "data": data,
            "headers": kwargs.get("headers", {}),
        },
    )
    routes = []
    plugin = SimpleNamespace(
        closed=False,
        service=service,
        context=SimpleNamespace(
            registered_web_apis=routes,
            register_web_api=lambda *args: routes.append(args),
        ),
        discovery_errors=[],
        discover_groups=AsyncMock(),
        render_images=AsyncMock(return_value=([b"png-image-bytes"], {})),
        read_styles=AsyncMock(return_value={}),
        page_state=AsyncMock(return_value=service.snapshot()),
        log_failure=Mock(),
    )
    return module.AdminAPI(plugin, web)


@pytest.mark.parametrize(
    "case,expected", [("anonymous", 401), ("cross-site", 403), ("closed", 503)]
)
def test_every_endpoint_requires_live_authenticated_dashboard(admin, case, expected):
    if case == "anonymous":
        admin.web.request.username = None
    elif case == "cross-site":
        admin.web.request.headers["Sec-Fetch-Site"] = "cross-site"
    else:
        admin.plugin.closed = True
    admin.register()
    for (
        _path,
        handler,
        _methods,
        _description,
    ) in admin.plugin.context.registered_web_apis:
        assert asyncio.run(handler())["code"] == expected
    admin.plugin.discover_groups.assert_not_awaited()
    admin.plugin.render_images.assert_not_awaited()


def test_preview_renders_draft_without_saving_and_returns_png_data_url(admin):
    original = admin.plugin.service.snapshot()
    draft = admin.plugin.service.snapshot()["default_profile"]
    draft["title"] = "尚未保存的草稿"
    admin.web.request.body.return_value = json.dumps(
        {"profile": draft, "group_name": "预览群"}
    ).encode()
    result = asyncio.run(admin.guard(admin.preview)())
    admin.plugin.render_images.assert_awaited_once_with(
        draft, "预览群", with_styles=True
    )
    assert result["data"]["images"] == [
        "data:image/png;base64," + base64.b64encode(b"png-image-bytes").decode()
    ]
    assert admin.plugin.service.snapshot() == original
    assert result["headers"]["Cache-Control"] == "no-store"


def test_save_reports_conflict_for_stale_page_without_losing_saved_data(admin):
    stale = admin.plugin.service.snapshot()
    current = admin.plugin.service.snapshot()
    current["default_profile"]["title"] = "最新已保存的内容"
    admin.plugin.service.save(current)
    admin.web.request.body.return_value = json.dumps(stale).encode()
    response = asyncio.run(admin.guard(admin.save)())
    assert response["code"] == 409
    assert (
        admin.plugin.service.snapshot()["default_profile"]["title"]
        == "最新已保存的内容"
    )


def test_long_image_limit_is_explained_in_preview_without_saving(admin):
    original = admin.plugin.service.snapshot()
    admin.web.request.body.return_value = json.dumps(
        {"profile": original["default_profile"]}
    ).encode()
    message = (
        "帮助长图超过 32000 像素的高度上限，请减少展示的插件或精简说明后重新预览。"
    )
    admin.plugin.render_images.side_effect = load_module(
        "help_render"
    ).ImageTooTallError(message)
    response = asyncio.run(admin.guard(admin.preview)())
    assert response == {"error": message, "code": 400}
    assert admin.plugin.service.snapshot() == original
    admin.plugin.log_failure.assert_not_called()


@pytest.mark.parametrize(
    "content_type,body,expected",
    [
        ("text/plain", b"{}", 415),
        ("application/json", b"not-json", 400),
        ("application/json", b"[]", 400),
        ("application/json", b" " * (8 * 1024 * 1024 + 1), 413),
    ],
    ids=["content-type", "broken-json", "array", "oversized"],
)
def test_malformed_or_oversized_requests_are_rejected(
    admin, content_type, body, expected
):
    admin.web.request.content_type = content_type
    admin.web.request.body.return_value = body
    assert asyncio.run(admin.guard(admin.save)())["code"] == expected


def test_unload_removes_only_this_plugins_handlers(admin):
    external = ("/other/plugin", object(), ["GET"], "other")
    admin.plugin.context.registered_web_apis.append(external)
    admin.register()
    assert len(admin.plugin.context.registered_web_apis) == 5
    admin.close()
    assert admin.plugin.context.registered_web_apis == [external]
