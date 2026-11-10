"""Browser QA with a mock Dashboard bridge and the real service/PNG renderer."""

from __future__ import annotations

import base64
import json
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from help_render import render_help
from help_service import HelpService
from help_styles import StyleReader


def run(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as data:
        service = HelpService(Path(data), ROOT / "help_catalog.json")
        service.observe_group("qq-main", "10001", "太鼓交流一群")
        service.observe_group("qq-main", "10002", "可可子的朋友们")
        style_reader = StyleReader()

        def styles():
            return style_reader.load(service.catalog)

        def snapshot():
            return {
                **service.snapshot(),
                "styles": {name: style.public() for name, style in styles().items()},
            }

        def rpc(endpoint, payload):
            if endpoint == "save":
                service.save(payload)
                return snapshot()
            if endpoint == "preview":
                native_styles = styles()
                images = render_help(
                    service.validate_profile(payload["profile"]),
                    payload["group_name"],
                    native_styles,
                )
                for n, image in enumerate(images, 1):
                    (output / f"help-preview-{n}.png").write_bytes(image)
                return {
                    "images": [
                        "data:image/png;base64," + base64.b64encode(i).decode()
                        for i in images
                    ],
                    "styles": {
                        name: style.public() for name, style in native_styles.items()
                    },
                }
            if endpoint == "discover":
                service.observe_group("qq-main", "10003", "新发现的群")
            return snapshot()

        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(SimpleHTTPRequestHandler, directory=str(ROOT / "pages" / "manage")),
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    executable_path=os.environ.get("CUSTOM_HELP_CHROMIUM"),
                )
                page = browser.new_page(
                    viewport={"width": 1500, "height": 1080}, device_scale_factor=1
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.expose_function("qaRPC", rpc)
                page.add_init_script(
                    "window.AstrBotPluginPage={ready:async()=>({}),apiGet:(e)=>window.qaRPC(e,{}),apiPost:(e,p)=>window.qaRPC(e,p)}"
                )
                page.goto(f"http://127.0.0.1:{server.server_port}/index.html")
                page.locator("#workspace").wait_for(state="visible")
                assert page.locator(".plugin-card").count() == 19
                assert page.locator(".plugin-toggle input:checked").count() == 14
                assert (
                    "可可子 · 奶油浅绿"
                    in page.locator(
                        '[data-style-id="astrbot_plugin_liuyao"]'
                    ).inner_text()
                )
                assert (
                    "可可子 · 奶油浅绿"
                    in page.locator(
                        '[data-style-id="astrbot_plugin_ziwei"]'
                    ).inner_text()
                )
                page.locator("#groups button").first.click()
                assert page.locator("#field-title").is_disabled()
                page.locator("#scope-actions button").click()
                page.locator("#field-title").fill("太鼓一群 · 专属帮助")
                page.locator("#field-list_title").fill("本群插件帮助清单")
                page.locator("#field-list_text").fill("欢迎使用本群功能：\n{plugins}")
                page.locator(".edit-button").first.click()
                page.locator(".plugin-fields textarea").first.fill(
                    "/rp：查看今日人品。\n这段说明仅用于本群。"
                )
                page.locator(".move-down").first.click()
                page.locator(".plugin-toggle input").nth(5).uncheck()
                page.locator("#preview").click()
                page.locator("#preview-images img").first.wait_for(
                    state="visible", timeout=60000
                )
                assert "未保存草稿" in page.locator("#preview-state").inner_text()
                page.locator(".preview-zoom").first.click()
                assert page.locator("#image-viewer").is_visible()
                assert (
                    page.locator("#large-preview")
                    .get_attribute("src")
                    .startswith("data:image/png;base64,")
                )
                page.locator("#close-viewer").click()
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(output / "editor-overview.png"))
                page.screenshot(path=str(output / "editor-desktop.png"), full_page=True)
                page.locator("#save").click()
                page.wait_for_function(
                    "document.querySelector('#save-state').textContent==='全部修改已保存'"
                )
                first = service.profile_for("qq-main", "10001")
                assert first["title"] == "太鼓一群 · 专属帮助"
                assert first["items"][0]["id"] == "rt_link"
                assert not first["items"][5]["enabled"]
                assert (
                    service.profile_for("qq-main", "10002")["title"] != first["title"]
                )
                page.reload()
                page.locator("#workspace").wait_for(state="visible")
                page.locator("#groups button").first.click()
                assert page.locator("#field-title").input_value() == first["title"]
                page.locator("#discover").click()
                page.wait_for_function(
                    "document.querySelector('#group-count').textContent==='3 个群'"
                )
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                page.screenshot(path=str(output / "editor-mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1500, "height": 1080})
                page.evaluate("document.documentElement.dataset.theme='dark'")
                page.screenshot(path=str(output / "editor-dark.png"), full_page=True)
                assert not errors, errors
                browser.close()
                print(
                    json.dumps(
                        {
                            "browser": "passed",
                            "groups": 3,
                            "plugins": 19,
                            "screenshots": str(output),
                        },
                        ensure_ascii=False,
                    )
                )
        finally:
            server.shutdown()


if __name__ == "__main__":
    run(Path(sys.argv[1]))
