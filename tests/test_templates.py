import json
from copy import deepcopy

import pytest


def test_many_groups_share_one_template_and_can_move_back(service):
    for platform, gid in [("qq", "1"), ("qq", "2"), ("other", "1")]:
        service.observe_group(platform, gid)
    state = service.snapshot()
    custom = deepcopy(state["default_profile"])
    custom["title"] = "共用帮助"
    custom["triggers"] = {"at": True, "name": True, "poke": True, "bot_name": "小可"}
    state["templates"] = [{"id": "shared", "name": "共用模板", "profile": custom}]
    for row in state["groups"][:2]:
        row.update(template_id="shared", shortcut_enabled=True)
    saved = service.save(state)
    assert service.profile_for("qq", "1") == service.profile_for("qq", "2") == custom
    assert service.settings_for("other", "1")[1] is False
    saved["templates"][0]["profile"]["title"] = "统一修改后"
    service.save(saved)
    assert service.profile_for("qq", "2")["title"] == "统一修改后"
    state = service.snapshot()
    state["groups"][0]["template_id"] = None
    service.save(state)
    assert service.profile_for("qq", "1") == state["default_profile"]
    assert service.settings_for("qq", "1")[1] is True
    assert service.profile_for("qq", "2")["title"] == "统一修改后"


def test_legacy_independent_profiles_migrate_once_with_backup(
    service, service_module, catalog_path
):
    service.observe_group("qq", "1", "一群")
    service.observe_group("qq", "2", "二群")
    legacy = service.snapshot()
    for key in ("schema_version", "templates", "catalog"):
        legacy.pop(key)
    legacy["default_profile"].pop("triggers")
    for row in legacy["groups"]:
        row.pop("template_id")
        row.pop("shortcut_enabled")
        row["profile"] = None
    custom = deepcopy(legacy["default_profile"])
    custom["title"] = "原本独立的标题"
    custom["items"].reverse()
    custom["items"][0]["body"] = "手动修改的说明"
    legacy["groups"][0]["profile"] = custom
    original_bytes = json.dumps(legacy, ensure_ascii=False).encode()
    service.path.write_bytes(original_bytes)
    upgraded = service_module.HelpService(service.path.parent, catalog_path)
    state = upgraded.snapshot()
    assert state["schema_version"] == 2
    assert state["revision"] == legacy["revision"] + 1
    assert len(state["templates"]) == 1
    assert state["groups"][0]["template_id"] == state["templates"][0]["id"]
    assert state["groups"][1]["template_id"] is None
    assert not any(row["shortcut_enabled"] for row in state["groups"])
    actual = upgraded.profile_for("qq", "1")
    actual.pop("triggers")
    assert actual == custom
    assert (
        service.path.with_name("help_profiles.v1.backup.json").read_bytes()
        == original_bytes
    )
    persisted = service.path.read_bytes()
    again = service_module.HelpService(service.path.parent, catalog_path)
    assert again.snapshot() == state
    assert service.path.read_bytes() == persisted
    with pytest.raises(service_module.HelpError, match="结构已升级"):
        upgraded.save(legacy)


@pytest.mark.parametrize(
    "mutation",
    [
        "dangling",
        "duplicate",
        "invalid_id",
        "blank_name",
        "bad_toggle",
        "bad_trigger",
        "blank_bot",
        "multiline_bot",
        "old_group",
    ],
)
def test_invalid_templates_never_replace_saved_configuration(
    service, service_module, mutation
):
    service.observe_group("qq", "1")
    before = service.path.read_bytes()
    state = service.snapshot()
    state["templates"] = [
        {"id": "test", "name": "模板", "profile": deepcopy(state["default_profile"])}
    ]
    row, template = state["groups"][0], state["templates"][0]
    if mutation == "dangling":
        row["template_id"] = "missing"
    elif mutation == "duplicate":
        state["templates"].append(deepcopy(template))
    elif mutation == "invalid_id":
        template["id"] = "../../invalid"
    elif mutation == "blank_name":
        template["name"] = " "
    elif mutation == "bad_toggle":
        row["shortcut_enabled"] = "false"
    elif mutation == "bad_trigger":
        template["profile"]["triggers"]["at"] = 1
    elif mutation == "blank_bot":
        template["profile"]["triggers"]["bot_name"] = " "
    elif mutation == "multiline_bot":
        template["profile"]["triggers"]["bot_name"] = "可可\n子"
    else:
        row["profile"] = deepcopy(state["default_profile"])
    with pytest.raises(service_module.HelpError):
        service.save(state)
    assert service.path.read_bytes() == before


def test_missing_configured_group_cannot_be_silently_dropped(service, service_module):
    service.observe_group("qq", "1")
    state = service.snapshot()
    state["groups"][0]["shortcut_enabled"] = True
    service.save(state)
    state = service.snapshot()
    state["groups"] = []
    with pytest.raises(service_module.HelpError):
        service.save(state)
    assert service.settings_for("qq", "1")[1] is True


def test_failed_migration_preserves_original_file(
    service, service_module, catalog_path, monkeypatch
):
    legacy = service.snapshot()
    legacy.pop("schema_version")
    legacy.pop("templates")
    original = json.dumps(legacy).encode()
    service.path.write_bytes(original)

    def fail(*args):
        raise OSError("read-only data")

    monkeypatch.setattr(service_module.os, "replace", fail)
    with pytest.raises(OSError):
        service_module.HelpService(service.path.parent, catalog_path)
    assert service.path.read_bytes() == original
