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

function currentGroup() {
  return state?.groups.find((group) => group.key === selected);
}

function profile() {
  return currentGroup()?.profile || state.default_profile;
}

function inherited() {
  return selected !== DEFAULT && !currentGroup()?.profile;
}

function groupName() {
  return selected === DEFAULT ? "默认模板" : currentGroup()?.name || currentGroup()?.group_id || "群聊";
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
  $("editor-fields").disabled = busy || !state || inherited();
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

function renderGroups() {
  const query = $("group-search").value.trim().toLocaleLowerCase();
  $("default-scope").classList.toggle("active", selected === DEFAULT);
  $("default-scope").setAttribute("aria-current", selected === DEFAULT ? "true" : "false");
  const list = $("groups");
  list.replaceChildren();
  const groups = state.groups.filter((group) =>
    [group.name, group.group_id, group.platform_id].join(" ").toLocaleLowerCase().includes(query),
  );
  for (const group of groups) {
    const button = element("button", `scope-button${selected === group.key ? " active" : ""}`);
    button.type = "button";
    button.setAttribute("aria-current", selected === group.key ? "true" : "false");
    const mark = element("span", "group-mark", "群");
    mark.setAttribute("aria-hidden", "true");
    const info = element("span");
    info.append(element("strong", "", group.name || group.group_id));
    info.append(element("small", "", `${group.group_id} · ${group.platform_id}`));
    info.append(element("span", "group-note", group.profile ? "独立配置" : "使用默认模板"));
    button.append(mark, info);
    button.addEventListener("click", () => selectScope(group.key));
    list.append(button);
  }
  if (!groups.length) list.append(element("p", "empty-groups", query ? "没有找到匹配的群聊" : "暂未发现群聊，可点击刷新或在群内发送消息。"));
  const errors = state.discovery_errors || [];
  $("discovery-errors").hidden = !errors.length;
  $("discovery-errors").textContent = errors.map((error) => typeof error === "string" ? error : error.message || JSON.stringify(error)).join("\n");
}

function renderScope() {
  $("scope-title").textContent = groupName();
  $("scope-description").textContent = selected === DEFAULT
    ? "此处的修改会同步影响所有使用默认模板的群。"
    : `${currentGroup().platform_id} · 群 ${currentGroup().group_id} · ${inherited() ? "跟随默认模板" : "独立配置，仅影响本群"}`;
  $("inherit-note").hidden = !inherited();
  const actions = $("scope-actions");
  actions.replaceChildren();
  if (selected !== DEFAULT) {
    const button = element("button", "button small", inherited() ? "为本群单独配置" : "恢复使用默认模板");
    button.type = "button";
    button.addEventListener("click", () => {
      currentGroup().profile = inherited() ? clone(state.default_profile) : null;
      markDirty();
      render();
    });
    actions.append(button);
  }
  for (const name of fields) $("field-" + name).value = profile()[name] || "";
}

function moveItem(index, delta) {
  if (busy || inherited()) return;
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
    node.textContent = style ? `风格：${style.label}${style.status === "fallback" ? "（原风格暂不可用）" : ""}` : "风格：可可子风格";
    node.classList.toggle("fallback", style?.status === "fallback");
    node.title = style?.note || "";
  });
  document.querySelectorAll("[data-source-id]").forEach((node) => {
    const style = styles[node.dataset.sourceId];
    node.textContent = style ? `${style.note} 来源：${style.source}` : "默认使用内置可可子风格。";
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
  renderPlugins();
  updateCounts();
  updateActions();
}

function acceptState(next) {
  if (!next || !Array.isArray(next.groups) || !Array.isArray(next.default_profile?.items)) throw new Error("服务器返回了无效的帮助配置。");
  state = clone(next);
  if (selected !== DEFAULT && !state.groups.some((group) => group.key === selected)) selected = DEFAULT;
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
  const scope = groupName();
  const draftAtRequest = dirty;
  $("preview-state").textContent = "正在渲染当前配置，内容较多时可能需要稍候…";
  updateActions();
  try {
    const result = await bridge.apiPost("preview", { profile: clone(profile()), group_name: scope });
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
  const blob = new Blob([JSON.stringify({ revision: state.revision, default_profile: state.default_profile, groups: state.groups }, null, 2)], { type: "application/json;charset=utf-8" });
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
    if (!state || busy || inherited()) return;
    profile()[name] = event.target.value;
    markDirty();
  });
}
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
