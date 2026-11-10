"""Read installed plugins' visual assets without starting their entry points.

Only known palette literals and named, presentation-only drawing functions are
loaded. Command handlers, data stores and network clients are never imported.
"""

from __future__ import annotations

import ast
import hashlib
import math
import random
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "NotoSansSC-Regular.otf"
NATIVE_IDS = {"astrbot_plugin_liuyao", "astrbot_plugin_ziwei", "rt_link"}
TECH_PALETTE = {
    "bg": "#071321",
    "paper": "#0C2033",
    "panel": "#112B42",
    "ink": "#E6F4FF",
    "muted": "#90AFC6",
    "border": "#24465E",
    "accent": "#49E0EA",
    "secondary": "#739AFF",
}


@dataclass
class HelpStyle:
    kind: str = "tech"
    label: str = "科技风"
    status: str = "default"
    note: str = "未检测到已适配的专用图片帮助样式，使用科技风排版。"
    source: str = "custom_help"
    palette: dict = field(default_factory=lambda: dict(TECH_PALETTE))
    font_path: Path = FONT_PATH
    heading_path: Path = FONT_PATH
    fingerprint: str = "tech-v1"
    drawing: dict[str, Callable] = field(default_factory=dict, repr=False)
    native_palette: object = None

    def public(self):
        return {
            key: getattr(self, key)
            for key in ("kind", "label", "status", "note", "source")
        }


def runtime_sources(context):
    """Prefer actual loaded paths/settings, including renamed install folders."""
    paths, options = {}, {}
    getter = getattr(context, "get_all_stars", None)
    if not callable(getter):
        return paths, options
    try:
        stars = getter()
        for star in stars:
            name = getattr(star, "name", "")
            if name not in NATIVE_IDS:
                continue
            instance = getattr(star, "star_cls", None)
            if instance is None or isinstance(instance, type):
                continue
            module = sys.modules.get(type(instance).__module__)
            source = getattr(module, "__file__", None)
            if source:
                paths[name] = Path(source).resolve().parent
            config = getattr(instance, "config", {})
            getter = getattr(config, "get", lambda *_: "")
            options[name] = {
                "theme": getter("image_theme", "night"),
                "font_path": str(getter("font_path", "") or ""),
            }
            if name == "astrbot_plugin_ziwei":
                font = getattr(
                    getattr(instance, "help_renderer", None), "font_path", None
                )
                if font:
                    options[name]["font_path"] = str(font)
    except Exception:  # noqa: BLE001 - optional plugin metadata must not block help
        return paths, options
    return paths, options


def _read(path):
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("style source too large")
    return path.read_text(encoding="utf-8-sig")


def _literals(tree, names):
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in names:
                result[target.id] = ast.literal_eval(node.value)
    if set(result) != set(names):
        raise ValueError("unsupported palette")
    for value in result.values():
        if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("invalid palette color")
    return result


def _drawing_functions(tree, names, values):
    """Load just the installed renderer's allowlisted drawing primitives.

    No module-level imports, initializers, classes or command functions run.
    These are trusted installed plugin source files, not editor input.
    """
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if {node.name for node in nodes} != set(names):
        raise ValueError("unsupported drawing helpers")
    namespace = {
        "Image": Image,
        "ImageDraw": ImageDraw,
        "ImageChops": ImageChops,
        "ImageFilter": ImageFilter,
        "math": math,
        "random": random,
        **values,
    }
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(module, "<installed-help-style>", "exec"), namespace)  # noqa: S102
    return {name: namespace[name] for name in names}


def _asset(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise OSError("native style asset missing")
    return path


def _font(path, fallback=FONT_PATH):
    candidate = Path(path).expanduser() if path else fallback
    return candidate if candidate.is_file() else fallback


class StyleReader:
    def __init__(self, plugin_root=None):
        self.root = (
            Path(plugin_root)
            if plugin_root is not None
            else Path(__file__).resolve().parent.parent
        )
        self.cache = {}

    def directories(self, catalog, overrides):
        # Runtime IDs, directory names and historical aliases all identify the
        # same source. Metadata handles arbitrary user-chosen install folders.
        found = dict(overrides)
        for entry in catalog:
            name = entry["id"]
            if name not in NATIVE_IDS or name in found:
                continue
            for candidate in dict.fromkeys(
                [entry.get("directory", ""), name, *entry.get("aliases", [])]
            ):
                if (
                    candidate
                    and Path(candidate).name == candidate
                    and (self.root / candidate).is_dir()
                ):
                    found[name] = self.root / candidate
                    break
        if NATIVE_IDS - found.keys() and self.root.is_dir():
            for directory in sorted(self.root.iterdir()):
                metadata = directory / "metadata.yaml"
                if not directory.is_dir() or not metadata.is_file():
                    continue
                try:
                    match = re.search(
                        r"^name:\s*['\"]?([\w-]+)", _read(metadata), re.MULTILINE
                    )
                    if match and match[1] in NATIVE_IDS and match[1] not in found:
                        found[match[1]] = directory
                except (OSError, ValueError, UnicodeError):
                    continue
        return found

    def load(self, catalog, overrides=None, options=None):
        roots = self.directories(catalog, overrides or {})
        styles = {}
        for entry in catalog:
            name = entry["id"]
            if name not in NATIVE_IDS:
                styles[name] = HelpStyle()
                if name == "astrbot_plugin_custom_help":
                    styles[name].note = "本插件的科技风，与开头清单一致。"
                continue
            try:
                root = roots[name].resolve()
                style = self._native(name, root, (options or {}).get(name, {}))
            except Exception:  # noqa: BLE001 - unsupported plugin versions fall back visibly
                style = HelpStyle(
                    status="fallback",
                    note="未能读取原插件的帮助样式或资源，暂用科技风。请检查对应插件是否安装完整。",
                )
            styles[name] = style
        return styles

    def _native(self, name, root, settings):
        files = {
            "astrbot_plugin_liuyao": ["renderer.py", "textcard.py"],
            "astrbot_plugin_ziwei": ["themes.py", "starfield.py", "help_renderer.py"],
            "rt_link": ["help_image.py"],
        }[name]
        sources = {file: _read(root / file) for file in files}
        assets = []
        if name == "astrbot_plugin_liuyao":
            assets = [
                _asset(root, relative)
                for relative in (
                    "assets/bamboo.png",
                    "assets/fonts/NotoSansCJKsc-Regular.otf",
                    "assets/fonts/LiuyaoEditorialSerif.otf",
                )
            ]
        elif name == "rt_link":
            assets = [_asset(root, "resource/NotoSansCJKsc-Regular.otf")]
        configured_font = _font(
            settings.get("font_path"), assets[0] if name == "rt_link" else FONT_PATH
        )
        signature = hashlib.sha256(
            repr(
                [
                    str(root),
                    sources,
                    settings,
                    [
                        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
                        for path in [*assets, configured_font]
                    ],
                ]
            ).encode()
        ).hexdigest()
        if signature in self.cache:
            return self.cache[signature]
        if name == "astrbot_plugin_liuyao":
            tree = ast.parse(sources["renderer.py"])
            p = _literals(tree, {"PAPER", "INK", "MUTED", "JADE", "RULE"})
            card = _literals(
                ast.parse(sources["textcard.py"]),
                {"PAPER_DEEP", "JADE_PANEL", "FRAME", "SEAL"},
            )
            functions = _drawing_functions(
                tree,
                {"draw_bamboo_background", "draw_taiji_logo"},
                {**p, "BAMBOO_PATH": assets[0]},
            )
            style = HelpStyle(
                kind="liuyao",
                label="六爻 · 竹影青玉",
                palette={
                    "bg": p["PAPER"],
                    "paper": card["PAPER_DEEP"],
                    "panel": card["JADE_PANEL"],
                    "ink": p["INK"],
                    "muted": p["MUTED"],
                    "border": card["FRAME"],
                    "accent": p["JADE"],
                    "secondary": card["SEAL"],
                },
                font_path=_font(settings.get("font_path"), assets[1]),
                heading_path=_font(settings.get("font_path"), assets[2]),
                drawing=functions,
            )
        elif name == "astrbot_plugin_ziwei":
            tree = ast.parse(sources["themes.py"])
            fields = next(
                [node.target.id for node in cls.body if isinstance(node, ast.AnnAssign)]
                for cls in tree.body
                if isinstance(cls, ast.ClassDef) and cls.name == "Palette"
            )
            theme = (
                "DAY" if settings.get("theme") in ("day", "白天", "日间") else "NIGHT"
            )
            call = next(
                node.value
                for node in tree.body
                if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == theme
            )
            if (
                not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id != "Palette"
            ):
                raise ValueError("unsupported Ziwei theme")
            values = dict(
                zip(fields, [ast.literal_eval(arg) for arg in call.args], strict=True)
            )
            native = SimpleNamespace(**values)
            functions = _drawing_functions(
                ast.parse(sources["starfield.py"]),
                {"_rgb", "starfield", "orbit", "constellation"},
                {},
            )
            style = HelpStyle(
                kind="ziwei",
                label="紫微 · 星空" if theme == "NIGHT" else "紫微 · 浅色星轨",
                palette={
                    "bg": native.bg,
                    "paper": native.paper,
                    "panel": native.center,
                    "ink": native.ink,
                    "muted": native.muted,
                    "border": native.border,
                    "accent": native.accent,
                    "secondary": native.accent,
                },
                font_path=configured_font,
                heading_path=configured_font,
                drawing=functions,
                native_palette=native,
            )
        else:
            p = _literals(
                ast.parse(sources["help_image.py"]),
                {"BG", "BG_ALT", "TEXT", "TEXT_2", "DIVIDER", "BRAND", "BRAND_SOFT"},
            )
            style = HelpStyle(
                kind="rtlink",
                label="RTLink · 白底紫色文档",
                palette={
                    "bg": p["BG"],
                    "paper": p["BG_ALT"],
                    "panel": p["BRAND_SOFT"],
                    "ink": p["TEXT"],
                    "muted": p["TEXT_2"],
                    "border": p["DIVIDER"],
                    "accent": p["BRAND"],
                    "secondary": p["BRAND"],
                },
                font_path=configured_font,
                heading_path=configured_font,
            )
        style.status = "native"
        style.source = root.name + "/" + "、".join(files)
        style.note = "读取原插件的配色与装饰，按当前可编辑说明重新排版。"
        style.fingerprint = signature
        ImageFont.truetype(str(style.font_path), 28)
        ImageFont.truetype(str(style.heading_path), 38)
        # Detect incompatible helper changes before reporting a native style.
        if style.kind == "liuyao":
            canvas = Image.new("RGB", (1080, 320), style.palette["bg"])
            style.drawing["draw_bamboo_background"](canvas, 1080)
            style.drawing["draw_taiji_logo"](ImageDraw.Draw(canvas), 20, 20)
        elif style.kind == "ziwei":
            canvas = style.drawing["starfield"](1080, 320, style.native_palette)
            draw = ImageDraw.Draw(canvas)
            style.drawing["orbit"](draw, 70, 70, 26, style.native_palette)
            style.drawing["constellation"](draw, 200, 40, 150, 60, style.native_palette)
        self.cache = {signature: style, **dict(list(self.cache.items())[:7])}
        return style
