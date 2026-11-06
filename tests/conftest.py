from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE = "custom_help_test_package"


def load_module(name):
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(PLUGIN_DIR)]
        sys.modules[PACKAGE] = package
    return importlib.import_module(f"{PACKAGE}.{name}")


@pytest.fixture
def service_module():
    return load_module("help_service")


@pytest.fixture
def catalog_path(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "id": "first",
                        "directory": "astrbot_plugin_first",
                        "title": "初始插件甲",
                        "version": "1.0.0",
                        "summary": "第一个插件",
                        "body": "/甲 查询甲的内容",
                        "default_enabled": True,
                        "aliases": [],
                    },
                    {
                        "id": "second",
                        "directory": "astrbot_plugin_second",
                        "title": "初始插件乙",
                        "version": "2.0.0",
                        "summary": "第二个插件",
                        "body": "/乙 查询乙的内容",
                        "default_enabled": False,
                        "aliases": [],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def service(service_module, catalog_path, tmp_path):
    return service_module.HelpService(tmp_path / "data", catalog_path)
