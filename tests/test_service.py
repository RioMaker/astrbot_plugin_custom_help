from __future__ import annotations

import json
from copy import deepcopy

import pytest


def group(state, platform, group_id):
    return next(
        entry
        for entry in state["groups"]
        if entry["platform_id"] == platform and entry["group_id"] == group_id
    )


def test_first_start_uses_catalog_defaults_and_isolates_snapshot(service):
    first = service.snapshot()
    assert [p["id"] for p in first["default_profile"]["items"]] == ["first", "second"]
    assert [p["enabled"] for p in first["default_profile"]["items"]] == [True, False]
    first["default_profile"]["items"][0]["body"] = "浏览器未保存的修改"
    assert (
        service.snapshot()["default_profile"]["items"][0]["body"] == "/甲 查询甲的内容"
    )


def test_group_customization_isolated_by_platform_and_survives_reload(
    service, service_module, catalog_path, tmp_path
):
    service.observe_group("bot-a", "123", "甲群")
    service.observe_group("bot-b", "123", "乙群")
    state = service.snapshot()
    customized = deepcopy(state["default_profile"])
    customized["title"] = "甲群专属说明"
    customized["items"].reverse()
    customized["items"][0].update(enabled=True, body="/乙 仅甲群展示的说明")
    group(state, "bot-a", "123")["profile"] = customized
    service.save(state)

    assert service.profile_for("bot-a", "123")["title"] == "甲群专属说明"
    assert service.profile_for("bot-b", "123")["title"] != "甲群专属说明"
    reloaded = service_module.HelpService(tmp_path / "data", catalog_path)
    assert reloaded.profile_for("bot-a", "123") == customized
    assert len(reloaded.snapshot()["groups"]) == 2


def test_default_edits_only_change_inherited_groups_and_reset_restores_inheritance(
    service,
):
    service.observe_group("qq", "1", "独立群")
    service.observe_group("qq", "2", "继承群")
    state = service.snapshot()
    group(state, "qq", "1")["profile"] = deepcopy(state["default_profile"])
    group(state, "qq", "1")["profile"]["title"] = "独立群原题"
    state["default_profile"]["title"] = "新的默认标题"
    service.save(state)
    assert service.profile_for("qq", "1")["title"] == "独立群原题"
    assert service.profile_for("qq", "2")["title"] == "新的默认标题"

    state = service.snapshot()
    group(state, "qq", "1")["profile"] = None
    service.save(state)
    assert service.profile_for("qq", "1")["title"] == "新的默认标题"


def test_second_browser_cannot_overwrite_newer_changes(service, service_module):
    old_tab = service.snapshot()
    new_tab = deepcopy(old_tab)
    new_tab["default_profile"]["title"] = "已保存的新标题"
    service.save(new_tab)
    old_tab["default_profile"]["title"] = "过期标签页标题"
    with pytest.raises(service_module.HelpError) as error:
        service.save(old_tab)
    assert error.value.status == 409
    assert service.snapshot()["default_profile"]["title"] == "已保存的新标题"


def test_observing_existing_group_does_not_reset_customization(service):
    service.observe_group("qq", "1", "原群名")
    state = service.snapshot()
    group(state, "qq", "1")["profile"] = deepcopy(state["default_profile"])
    group(state, "qq", "1")["profile"]["title"] = "保留的帮助"
    service.save(state)
    service.observe_group("qq", "1", "新群名")
    assert service.profile_for("qq", "1")["title"] == "保留的帮助"
    assert group(service.snapshot(), "qq", "1")["name"] == "新群名"
    assert len(service.snapshot()["groups"]) == 1


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "not_bool", "not_text"])
def test_invalid_plugin_configuration_rejected_without_mutating_state(
    service, service_module, mutation
):
    original = service.snapshot()
    state = deepcopy(original)
    items = state["default_profile"]["items"]
    if mutation == "unknown":
        items[0]["id"] = "not-in-catalog"
    elif mutation == "duplicate":
        items[1]["id"] = items[0]["id"]
    elif mutation == "not_bool":
        items[0]["enabled"] = "false"
    else:
        items[0]["body"] = {"unexpected": "object"}
    with pytest.raises(service_module.HelpError):
        service.save(state)
    assert service.snapshot() == original


def test_all_help_entries_can_be_disabled_and_persisted(
    service, service_module, catalog_path, tmp_path
):
    state = service.snapshot()
    for entry in state["default_profile"]["items"]:
        entry["enabled"] = False
    service.save(state)
    reloaded = service_module.HelpService(tmp_path / "data", catalog_path)
    assert not any(
        item["enabled"] for item in reloaded.snapshot()["default_profile"]["items"]
    )


def test_legacy_help_is_preserved_during_first_initialization_only(
    service_module, catalog_path, tmp_path
):
    first = service_module.HelpService(
        tmp_path / "data", catalog_path, "旧版自定义介绍"
    )
    assert "旧版自定义介绍" in first.snapshot()["default_profile"]["intro"]
    state = first.snapshot()
    state["default_profile"]["intro"] = "后台编辑的介绍"
    first.save(state)
    reloaded = service_module.HelpService(
        tmp_path / "data", catalog_path, "旧版自定义介绍"
    )
    assert reloaded.snapshot()["default_profile"]["intro"] == "后台编辑的介绍"


def test_oversized_legacy_intro_migrates_to_reloadable_configuration(
    service_module, catalog_path, tmp_path
):
    long_legacy = "旧版说明" * 2000
    first = service_module.HelpService(tmp_path / "data", catalog_path, long_legacy)
    intro = first.snapshot()["default_profile"]["intro"]
    assert len(intro) <= 3000
    assert "旧版" in intro
    reloaded = service_module.HelpService(tmp_path / "data", catalog_path, long_legacy)
    assert reloaded.snapshot()["default_profile"]["intro"] == intro


def test_group_discovered_while_editing_is_preserved_on_save(service):
    browser = service.snapshot()
    service.observe_group("qq", "new", "编辑期间新发现的群")
    browser["default_profile"]["title"] = "编辑后的标题"
    service.save(browser)
    assert group(service.snapshot(), "qq", "new")["name"] == "编辑期间新发现的群"
    assert service.profile_for("qq", "new")["title"] == "编辑后的标题"


def test_failed_disk_replace_keeps_memory_and_last_saved_file(
    service, service_module, monkeypatch
):
    original = service.snapshot()
    original_file = service.path.read_bytes()
    state = deepcopy(original)
    state["default_profile"]["title"] = "不可保存的修改"

    def deny_replace(*_args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(service_module.os, "replace", deny_replace)
    with pytest.raises(OSError):
        service.save(state)
    assert service.snapshot() == original
    assert service.path.read_bytes() == original_file


def test_corrupt_configuration_is_not_silently_overwritten(
    service, service_module, catalog_path, tmp_path
):
    service.path.write_text("invalid JSON user data", encoding="utf-8")
    with pytest.raises(service_module.HelpError):
        service_module.HelpService(tmp_path / "data", catalog_path)
    assert service.path.read_text(encoding="utf-8") == "invalid JSON user data"


def test_catalog_upgrade_adds_new_section_disabled_without_replacing_edits(
    service, service_module, catalog_path, tmp_path
):
    state = service.snapshot()
    state["default_profile"]["items"][0]["body"] = "管理员已修改的甲说明"
    service.save(state)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"][0]["body"] = "新版甲默认说明"
    catalog["plugins"].append(
        {"id": "third", "title": "新增插件", "body": "/丙", "default_enabled": True}
    )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    reloaded = service_module.HelpService(tmp_path / "data", catalog_path)
    items = reloaded.snapshot()["default_profile"]["items"]
    assert items[0]["body"] == "管理员已修改的甲说明"
    assert items[-1]["id"] == "third"
    assert items[-1]["enabled"] is False


def test_stock_body_upgrade_preserves_profiles_and_persists_once(
    service, service_module, catalog_path, tmp_path
):
    service.observe_group("qq", "custom", "独立群")
    service.observe_group("qq", "inherited", "继承群")
    state = service.snapshot()
    profile = deepcopy(state["default_profile"])
    profile["title"] = "群专属帮助"
    profile["items"].reverse()
    profile["items"][-1].update(title="自定义栏目标题", enabled=False)
    group(state, "qq", "custom")["profile"] = profile
    original = service.save(state)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    old_body = catalog["plugins"][0]["body"]
    catalog["plugins"][0].update(
        previous_bodies=[old_body], body="/甲 新功能的完整说明"
    )
    # A different plugin's seed change has no explicitly approved migration.
    catalog["plugins"][1]["body"] = "乙的新种子，保留已存说明"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

    reloaded = service_module.HelpService(tmp_path / "data", catalog_path)
    expected = deepcopy(original)
    expected.pop("catalog")
    expected["revision"] += 1
    expected["default_profile"]["items"][0]["body"] = "/甲 新功能的完整说明"
    group(expected, "qq", "custom")["profile"]["items"][-1]["body"] = (
        "/甲 新功能的完整说明"
    )
    assert json.loads(service.path.read_text(encoding="utf-8")) == expected
    assert reloaded.profile_for("qq", "inherited") == expected["default_profile"]
    assert (
        reloaded.profile_for("qq", "custom")
        == group(expected, "qq", "custom")["profile"]
    )
    with pytest.raises(service_module.HelpError) as error:
        reloaded.save(original)
    assert error.value.status == 409

    persisted = service.path.read_bytes()
    again = service_module.HelpService(tmp_path / "data", catalog_path)
    assert again.snapshot() == reloaded.snapshot()
    assert service.path.read_bytes() == persisted


@pytest.mark.parametrize("custom_body", ["/甲 查询甲的内容\n本群附注", ""])
def test_stock_body_upgrade_keeps_edited_or_cleared_text(
    service, service_module, catalog_path, tmp_path, custom_body
):
    state = service.snapshot()
    state["default_profile"]["items"][0]["body"] = custom_body
    service.save(state)
    persisted = service.path.read_bytes()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"][0].update(
        previous_bodies=[catalog["plugins"][0]["body"]], body="/甲 新版说明"
    )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    reloaded = service_module.HelpService(tmp_path / "data", catalog_path)
    assert reloaded.profile_for("qq", "1")["items"][0]["body"] == custom_body
    assert service.path.read_bytes() == persisted


def test_stock_body_upgrade_keeps_profiles_with_no_space_for_longer_text(
    service_module, catalog_path, tmp_path
):
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"][0]["body"] = "旧说明"
    catalog["plugins"].extend(
        {
            "id": f"long-{i}",
            "title": "长说明",
            "body": "字" * 5999,
            "default_enabled": True,
        }
        for i in range(5)
    )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    service = service_module.HelpService(tmp_path / "data", catalog_path)
    # Existing configuration is valid but has only two characters of headroom.
    service.save(service.snapshot())
    persisted = service.path.read_bytes()
    catalog["plugins"][0].update(previous_bodies=["旧说明"], body="新版更长的说明")
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    reloaded = service_module.HelpService(tmp_path / "data", catalog_path)
    assert reloaded.profile_for("qq", "1")["items"][0]["body"] == "旧说明"
    assert service.path.read_bytes() == persisted


def test_failed_stock_body_upgrade_keeps_original_saved_configuration(
    service, service_module, catalog_path, tmp_path, monkeypatch
):
    persisted = service.path.read_bytes()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["plugins"][0].update(
        previous_bodies=[catalog["plugins"][0]["body"]], body="/甲 新版说明"
    )
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

    def deny_replace(*_args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(service_module.os, "replace", deny_replace)
    with pytest.raises(OSError):
        service_module.HelpService(tmp_path / "data", catalog_path)
    assert service.path.read_bytes() == persisted
