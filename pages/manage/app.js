const $ = (id) => document.getElementById(id);
const clone = (value) => JSON.parse(JSON.stringify(value));
const fields = ["title", "intro", "list_title", "list_text", "footer"];
const DEFAULT = "__default__";
let bridge;
let state;
let selected = DEFAULT;
let dirty = false;
let busy = false;
let previewBusy = false;
let previewGeneration = 0;
let previewHasImages = false;
const expanded = new Set();

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function notice(message = "", type = "") {
  $("notice").textContent = message;
  $("notice").className = `notice ${type}`;
  $("notice").hidden = !message;
}

function template() {
  return state?.templates.find((item) => item.id === selected);
}

function profile() {
  return template()?.profile || state.default_profile;
}

function templateName(id = selected) {
  return id === DEFAULT || id == null ? "默认模板" : state.templates.find((item) => item.id === id)?.name || "帮助模板";
}

function isAssigned(group) {
  return (group.template_id || DEFAULT) === selected;
}

function groupName() {
  const group = state.groups.find((item) => item.key === $("preview-group").value && isAssigned(item));
  return group?.name || group?.group_id || "";
}

function updateActions() {
  $("save").disabled = busy || !state || !dirty;
  $("save").textContent = busy ? "正在处理…" : "保存全部修改";
  $("save-state").textContent = !state ? "尚未载入" : dirty ? "有未保存的修改" : "全部修改已保存";
  $("save-state").className = `save-state${dirty ? " dirty" : ""}`;
  $("discover").disabled = busy || dirty;
  $("discover").title = dirty ? "请先保存修改，再刷新群聊" : "重新检测机器人所在的群聊";
  $("preview").disabled = busy || !state || previewBusy;
  $("preview").textContent = previewBusy ? "正在生成图片…" : "生成预览";
  $("editor-fields").disabled = busy || !state;
  $("workspace").inert = busy;
  $("reload").disabled = busy;
  $("export-draft").disabled = busy || !state;
}

function invalidatePreview(message = "内容已修改，请重新生成预览。") {
  previewGeneration += 1;
  if (previewHasImages) $("preview-images").classList.add("stale");
  $("preview-state").textContent = message;
}

function markDirty() {
  dirty = true;
  invalidatePreview();
  updateCounts();
  renderStyleLabels();
  updateActions();
}

function updateCounts() {
  if (!state) return;
  const active = profile().items.filter((item) => item.enabled).length;
  $("enabled-count").textContent = `${active} / ${profile().items.length} 项展示`;
  $("group-count").textContent = `${state.groups.length} 个群`;
}

function selectScope(key) {
  if (busy || key === selected) return;
  selected = key;
  expanded.clear();
  invalidatePreview("配置范围已切换，请为当前范围生成预览。");
  // Do not leave another group's image visible under the new group's controls.
  $("preview-images").replaceChildren(placeholder());
  $("preview-images").classList.remove("stale");
  previewHasImages = false;
  render();
}

function groupMatches(group, query) {
  return [group.name, group.group_id, group.platform_id].join(" ").toLocaleLowerCase().includes(query);
}

function memberList(groups) {
  const details = element("details", "template-members");
  details.append(element("summary", "", `应用 ${groups.length} 个群`));
  const list = element("ul");
  for (const group of groups) {
    const row = element("li");
    row.append(element("span", "", group.name || group.group_id), element("small", "", `${group.group_id} · ${group.platform_id}${group.shortcut_enabled ? " · 快捷帮助已开" : ""}`));
    list.append(row);
  }
  details.append(list);
  return details;
}

function renderGroups() {
  const query = $("group-search").value.trim().toLocaleLowerCase();
  $("default-scope").classList.toggle("active", selected === DEFAULT);
  $("default-scope").setAttribute("aria-current", String(selected === DEFAULT));
  $("default-members").replaceChildren(memberList(state.groups.filter((group) => !group.template_id && groupMatches(group, query))));
  const list = $("templates");
  list.replaceChildren();
  for (const item of state.templates) {
    const allMembers = state.groups.filter((group) => group.template_id === item.id);
    const members = allMembers.filter((group) => groupMatches(group, query));
    if (query && !item.name.toLocaleLowerCase().includes(query) && !members.length) continue;
    const card = element("div", "template-nav-card");
    const button = element("button", `scope-button${selected === item.id ? " active" : ""}`);
    button.type = "button";
    button.dataset.templateId = item.id;
    button.setAttribute("aria-current", String(selected === item.id));
    const names = element("span");
    names.append(element("strong", "", item.name), element("small", "", `${allMembers.length} 个群共用`));
    button.append(element("span", "scope-icon", "▤"), names);
    button.addEventListener("click", () => selectScope(item.id));
    card.append(button, memberList(query ? members : allMembers));
    list.append(card);
  }
  if (!list.children.length) list.append(element("p", "empty-groups", query ? "没有匹配的模板或群聊" : "尚无独立模板，点击上方新建。"));
  const errors = state.discovery_errors || [];
  $("discovery-errors").hidden = !errors.length;
  $("discovery-errors").textContent = errors.map((error) => typeof error === "string" ? error : error.message || JSON.stringify(error)).join("\n");
}

function visibleGroups() {
  const query = $("apply-search").value.trim().toLocaleLowerCase();
  return state.groups.filter((group) => groupMatches(group, query));
}

function refreshBindings() {
  markDirty();
  renderGroups();
  renderAssignments();
  renderPreviewGroups();
  renderScopeSummary();
}

function renderAssignments() {
  const list = $("group-assignments");
  list.replaceChildren();
  const groups = visibleGroups();
  for (const group of groups) {
    const assigned = isAssigned(group);
    const row = element("div", `assignment-row${assigned ? " assigned" : ""}`);
    row.dataset.groupKey = group.key;
    const label = element("label", "assignment-member");
    const checkbox = element("input", "assign-group");
    checkbox.type = "checkbox";
    checkbox.checked = assigned;
    checkbox.disabled = selected === DEFAULT && assigned;
    checkbox.setAttribute("aria-label", `应用到 ${group.name || group.group_id}`);
    checkbox.addEventListener("change", () => {
      group.template_id = checkbox.checked && selected !== DEFAULT ? selected : null;
      refreshBindings();
    });
    const info = element("span");
    info.append(element("strong", "", group.name || group.group_id), element("small", "", `${group.group_id} · ${group.platform_id}`), element("small", "binding-name", `当前：${templateName(group.template_id)}`));
    label.append(checkbox, info);
    const shortcut = element("input", "enable-shortcut");
    shortcut.type = "checkbox";
    shortcut.checked = group.shortcut_enabled;
    shortcut.disabled = !assigned;
    shortcut.setAttribute("aria-label", `${group.name || group.group_id} 开启快捷帮助`);
    shortcut.addEventListener("change", () => {
      group.shortcut_enabled = shortcut.checked;
      markDirty();
      renderGroups();
    });
    row.append(label, shortcut);
    list.append(row);
  }
  if (!groups.length) list.append(element("p", "empty-groups", "没有匹配的群聊，可刷新群聊或在群内发送消息。"));
  $("assigned-count").textContent = `${state.groups.filter(isAssigned).length} 个群使用此模板`;
  $("assignment-note").textContent = selected === DEFAULT
    ? "这里集中显示群的默认与独立模板归属。勾选其他模板的群可将它移回默认模板。"
    : "勾选群聊应用当前模板；已属于其他模板的群会移动到这里。取消勾选则回到默认模板。快捷帮助开关按群保留。";
  $("release-visible").hidden = selected === DEFAULT;
}

function renderPreviewGroups() {
  const select = $("preview-group");
  const previous = select.value;
  select.replaceChildren();
  const generic = element("option", "", "模板预览（不显示群名）");
  generic.value = "";
  select.append(generic);
  for (const group of state.groups.filter(isAssigned)) {
    const option = element("option", "", `${group.name || group.group_id} · ${group.group_id}`);
    option.value = group.key;
    select.append(option);
  }
  select.value = [...select.options].some((option) => option.value === previous) ? previous : "";
}

function renderScopeSummary() {
  $("scope-title").textContent = templateName();
  $("scope-description").textContent = `编辑一次，同步影响 ${state.groups.filter(isAssigned).length} 个应用此模板的群。`;
}

function createTemplate(source) {
  if (busy) return;
  let number = 1;
  while (state.templates.some((item) => item.name === `新模板 ${number}`)) number++;
  const id = `tpl_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
  $("group-search").value = "";
  state.templates.push({ id, name: `新模板 ${number}`, profile: clone(source) });
  markDirty();
  selectScope(id);
  $("template-name").focus();
  $("template-name").select();
}

function renderScope() {
  renderScopeSummary();
  $("template-name").value = templateName();
  $("template-name").readOnly = selected === DEFAULT;
  for (const key of ["at", "name", "poke"]) $("trigger-" + key).checked = profile().triggers[key];
  $("bot-name").value = profile().triggers.bot_name;
  const actions = $("scope-actions");
  actions.replaceChildren();
  const copy = element("button", "button small", "复制为新模板");
  copy.type = "button";
  copy.addEventListener("click", () => createTemplate(profile()));
  actions.append(copy);
  if (selected !== DEFAULT) {
    const remove = element("button", "button small", "删除模板");
    remove.type = "button";
    remove.addEventListener("click", () => {
      $("delete-description").textContent = `删除“${templateName()}”后，${state.groups.filter(isAssigned).length} 个群会回到默认模板，快捷帮助开关保留。保存后生效。`;
      $("delete-dialog").showModal();
    });
    actions.append(remove);
  }
  for (const name of fields) $("field-" + name).value = profile()[name] || "";
}

function moveItem(index, delta) {
  if (busy) return;
  const items = profile().items;
  const target = index + delta;
  if (target < 0 || target >= items.length) return;
  [items[index], items[target]] = [items[target], items[index]];
  markDirty();
  renderPlugins();
  const moved = [...$("plugin-list").children][target];
  moved.querySelector(delta < 0 ? ".move-up" : ".move-down")?.focus();
}

function renderPlugins() {
  const list = $("plugin-list");
  list.replaceChildren();
  const catalog = new Map((state.catalog || []).map((item) => [item.id, item]));
  profile().items.forEach((item, index) => {
    const card = element("article", `plugin-card${item.enabled ? " enabled" : ""}`);
    const toolbar = element("div", "plugin-toolbar");
    const position = element("span", "plugin-order", String(index + 1).padStart(2, "0"));
    const toggle = element("label", "plugin-toggle");
    const checkbox = element("input");
    checkbox.type = "checkbox";
    checkbox.checked = item.enabled;
    const title = element("span", "plugin-name", item.title || item.id);
    const names = element("span", "plugin-names");
    const styleBadge = element("small", "style-badge");
    styleBadge.dataset.styleId = item.id;
    names.append(title, styleBadge);
    checkbox.addEventListener("change", () => {
      item.enabled = checkbox.checked;
      card.classList.toggle("enabled", item.enabled);
      markDirty();
    });
    toggle.append(checkbox, names);
    const moves = element("div", "plugin-move");
    for (const [delta, text, label, className] of [[-1, "↑", "上移", "move-up"], [1, "↓", "下移", "move-down"]]) {
      const button = element("button", `icon-button ${className}`, text);
      button.type = "button";
      button.title = label;
      button.setAttribute("aria-label", `${label} ${item.title || item.id}`);
      button.disabled = delta < 0 ? index === 0 : index === profile().items.length - 1;
      button.addEventListener("click", () => moveItem(index, delta));
      moves.append(button);
    }
    const edit = element("button", "text-button edit-button", expanded.has(item.id) ? "收起说明" : "编辑说明");
    edit.type = "button";
    edit.setAttribute("aria-expanded", String(expanded.has(item.id)));
    const editor = element("div", "plugin-fields");
    editor.hidden = !expanded.has(item.id);
    editor.id = `plugin-editor-${index}`;
    edit.setAttribute("aria-controls", editor.id);
    edit.addEventListener("click", () => {
      if (expanded.has(item.id)) expanded.delete(item.id);
      else expanded.add(item.id);
      editor.hidden = !expanded.has(item.id);
      edit.textContent = editor.hidden ? "编辑说明" : "收起说明";
      edit.setAttribute("aria-expanded", String(!editor.hidden));
    });
    editor.append(element("p", "plugin-id", item.id));
    const source = element("p", "style-source");
    source.dataset.sourceId = item.id;
    editor.append(source);
    if (catalog.get(item.id)?.summary) editor.append(element("p", "plugin-description", catalog.get(item.id).summary));
    const titleLabel = element("label", "", "插件名称（同时用于表头清单）");
    const titleInput = element("input");
    titleInput.value = item.title;
    titleInput.maxLength = 120;
    titleInput.addEventListener("input", () => {
      item.title = titleInput.value;
      title.textContent = item.title || item.id;
      markDirty();
    });
    titleLabel.append(titleInput);
    const bodyLabel = element("label", "", "文字版说明");
    const bodyInput = element("textarea");
    bodyInput.value = item.body;
    bodyInput.rows = 8;
    bodyInput.maxLength = 6000;
    bodyInput.spellcheck = false;
    bodyInput.addEventListener("input", () => {
      item.body = bodyInput.value;
      markDirty();
    });
    bodyLabel.append(bodyInput, element("small", "", "支持多行纯文字，换行会保留。可直接修改指令、示例与使用说明。"));
    editor.append(titleLabel, bodyLabel);
    toolbar.append(position, toggle, moves, edit);
    card.append(toolbar, editor);
    list.append(card);
  });
  renderStyleLabels();
}

function renderStyleLabels() {
  const styles = state.styles || {};
  document.querySelectorAll("[data-style-id]").forEach((node) => {
    const style = styles[node.dataset.styleId];
    node.textContent = style ? `风格：${style.label}${style.status === "fallback" ? "（原风格暂不可用）" : ""}` : "风格：科技风";
    node.classList.toggle("fallback", style?.status === "fallback");
    node.title = style?.note || "";
  });
  document.querySelectorAll("[data-source-id]").forEach((node) => {
    const style = styles[node.dataset.sourceId];
    node.textContent = style ? `${style.note} 来源：${style.source}` : "未提供专用帮助样式，使用科技风。";
  });
  const missing = profile().items.filter((item) => item.enabled && styles[item.id]?.status === "fallback");
  $("style-warning").hidden = !missing.length;
  $("style-warning").textContent = missing.length ? `${missing.map((item) => item.title).join("、")}的原生样式暂不可用，本次使用科技风。请检查原插件是否安装完整，再重新预览。` : "";
}

function placeholder() {
  const box = element("div", "preview-placeholder");
  box.append(element("span", "", "▤"), element("strong", "", "你的帮助图会显示在这里"), element("p", "", "表头、插件清单与说明按当前顺序拼接"));
  return box;
}

function render() {
  renderGroups();
  renderScope();
  renderAssignments();
  renderPreviewGroups();
  renderPlugins();
  updateCounts();
  updateActions();
}

function acceptState(next) {
  if (!next || next.schema_version !== 2 || !Array.isArray(next.templates) || !Array.isArray(next.groups) || !Array.isArray(next.default_profile?.items)) throw new Error("服务器返回了无效的帮助配置。");
  state = clone(next);
  if (selected !== DEFAULT && !state.templates.some((item) => item.id === selected)) selected = DEFAULT;
  dirty = false;
  $("recovery").hidden = true;
  $("loading").hidden = true;
  $("workspace").hidden = false;
  render();
}

async function load() {
  busy = true;
  updateActions();
  try {
    const next = await bridge.apiGet("state");
    acceptState(next);
    invalidatePreview("配置已载入，可生成当前范围的帮助图预览。");
    notice();
  } catch (error) {
    notice(`载入失败：${error.message || error}`, "error");
    $("loading").hidden = true;
    $("recovery").hidden = false;
  } finally {
    busy = false;
    updateActions();
  }
}

async function save() {
  if (busy || !dirty) return;
  busy = true;
  updateActions();
  try {
    const result = await bridge.apiPost("save", {
      schema_version: state.schema_version,
      templates: clone(state.templates),
      revision: state.revision,
      default_profile: clone(state.default_profile),
      groups: clone(state.groups),
    });
    acceptState(result);
    invalidatePreview("配置已保存。重新生成预览可查看保存后的帮助图。");
    notice("已保存全部修改，群内发送 /help 或 /帮助 即可查看。支持图片的群聊将收到帮助图。");
  } catch (error) {
    notice(`保存失败，草稿已保留：${error.message || error}`, "error");
    $("recovery").hidden = false;
  } finally {
    busy = false;
    updateActions();
  }
}

async function discover() {
  if (busy || dirty) return;
  busy = true;
  updateActions();
  notice("正在检测群聊，请稍候…");
  try {
    const result = await bridge.apiPost("discover", {});
    acceptState(result);
    invalidatePreview("群聊信息已更新，可重新生成预览。");
    notice(`已更新群聊列表，共 ${state.groups.length} 个群。${state.discovery_errors?.length ? "部分平台未能刷新，详情见左侧。" : ""}`, state.discovery_errors?.length ? "warning" : "");
  } catch (error) {
    notice(`刷新失败：${error.message || error}`, "error");
  } finally {
    busy = false;
    updateActions();
  }
}

async function preview() {
  if (busy || previewBusy || !state) return;
  previewBusy = true;
  const generation = ++previewGeneration;
  const scope = groupName() || templateName();
  const draftAtRequest = dirty;
  $("preview-state").textContent = "正在渲染当前配置，内容较多时可能需要稍候…";
  updateActions();
  try {
    const result = await bridge.apiPost("preview", { profile: clone(profile()), group_name: groupName() });
    if (generation !== previewGeneration) return;
    if (result.styles) {
      state.styles = result.styles;
      renderStyleLabels();
    }
    if (!Array.isArray(result.images) || !result.images.length || !result.images.every((url) => typeof url === "string" && /^data:image\/png;base64,/.test(url))) throw new Error("未收到有效的预览图片。");
    const images = $("preview-images");
    images.replaceChildren();
    images.classList.remove("stale");
    result.images.forEach((url, index) => {
      const wrapper = element("div");
      const image = element("img");
      image.src = url;
      image.alt = `${scope}的帮助图，第 ${index + 1} / ${result.images.length} 张`;
      const zoom = element("button", "preview-zoom");
      zoom.type = "button";
      zoom.setAttribute("aria-label", `放大查看第 ${index + 1} 张帮助图`);
      zoom.addEventListener("click", () => {
        $("large-preview").src = url;
        $("large-preview").alt = image.alt;
        $("image-viewer").showModal();
      });
      zoom.append(image);
      wrapper.append(zoom);
      if (result.images.length > 1) wrapper.append(element("p", "preview-image-caption", `第 ${index + 1} / ${result.images.length} 张`));
      images.append(wrapper);
    });
    previewHasImages = true;
    $("preview-state").textContent = `${scope} · ${result.images.length} 张图片 · ${draftAtRequest ? "当前为未保存草稿，保存后生效" : "当前已保存配置"}`;
  } catch (error) {
    if (generation === previewGeneration) {
      $("preview-state").textContent = `预览失败：${error.message || error}`;
      if (previewHasImages) $("preview-images").classList.add("stale");
    }
  } finally {
    previewBusy = false;
    updateActions();
  }
}

function exportDraft() {
  if (!state) return;
  const blob = new Blob([JSON.stringify({ schema_version: state.schema_version, revision: state.revision, templates: state.templates, default_profile: state.default_profile, groups: state.groups }, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = element("a");
  link.href = url;
  link.download = "custom-help-draft.json";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

for (const name of fields) {
  $("field-" + name).addEventListener("input", (event) => {
    if (!state || busy) return;
    profile()[name] = event.target.value;
    markDirty();
  });
}
$("new-template").addEventListener("click", () => createTemplate(state.default_profile));
$("template-name").addEventListener("input", (event) => {
  if (!template() || busy) return;
  template().name = event.target.value;
  markDirty();
  renderGroups();
  renderScopeSummary();
});
for (const key of ["at", "name", "poke"]) {
  $("trigger-" + key).addEventListener("change", (event) => {
    profile().triggers[key] = event.target.checked;
    markDirty();
  });
}
$("bot-name").addEventListener("input", (event) => {
  profile().triggers.bot_name = event.target.value;
  markDirty();
});
$("apply-search").addEventListener("input", () => state && renderAssignments());
$("assign-visible").addEventListener("click", () => {
  for (const group of visibleGroups()) {
    if (!isAssigned(group)) {
      group.template_id = selected === DEFAULT ? null : selected;
    }
  }
  refreshBindings();
});
$("release-visible").addEventListener("click", () => {
  for (const group of visibleGroups().filter(isAssigned)) {
    group.template_id = null;
  }
  refreshBindings();
});
$("preview-group").addEventListener("change", () => invalidatePreview("预览群聊已切换，请重新生成。"));
$("cancel-delete").addEventListener("click", () => $("delete-dialog").close());
$("confirm-delete").addEventListener("click", () => {
  if (busy || selected === DEFAULT) return;
  for (const group of state.groups.filter(isAssigned)) {
    group.template_id = null;
  }
  state.templates = state.templates.filter((item) => item.id !== selected);
  $("delete-dialog").close();
  markDirty();
  selectScope(DEFAULT);
});
$("default-scope").addEventListener("click", () => selectScope(DEFAULT));
$("group-search").addEventListener("input", () => state && renderGroups());
$("save").addEventListener("click", save);
$("discover").addEventListener("click", discover);
$("preview").addEventListener("click", preview);
$("reload").addEventListener("click", load);
$("export-draft").addEventListener("click", exportDraft);
$("close-viewer").addEventListener("click", () => $("image-viewer").close());
window.addEventListener("beforeunload", (event) => {
  if (dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

async function boot() {
  try {
    bridge = window.AstrBotPluginView || window.AstrBotPluginPage;
    if (!bridge) throw new Error("请从 AstrBot WebUI 的插件详情中打开此页面。");
    await bridge.ready();
    await load();
  } catch (error) {
    $("loading").hidden = true;
    notice(error.message || String(error), "error");
  }
}

boot();
