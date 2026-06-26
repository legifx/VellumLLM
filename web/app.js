"use strict";
// Vellum UI. No external dependencies, no trackers, no CDN.

const $ = (sel) => document.querySelector(sel);
const api = (path, opts) => fetch(path, opts);

const state = {
  config: null,
  nb: null,           // current notebook {id, name, ...}
  sources: [],
  model: "",
  pollTimer: null,
  lang: "en",
};

const t = (key, ...args) => {
  const v = (window.I18N[state.lang] || window.I18N.en)[key];
  return typeof v === "function" ? v(...args) : (v ?? key);
};

function applyLanguage(code) {
  state.lang = window.I18N[code] ? code : "en";
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPh);
  });
}

// ============================ config ============================
async function loadConfig() {
  try {
    state.config = await (await api("/api/config")).json();
    applyLanguage(state.config.language || "en");
    state.model = state.config.model || (state.config.models?.[0]?.id ?? "");
    renderNetBadge();
  } catch {
    state.config = { models: [] };
  }
}

function renderNetBadge() {
  const badge = $("#net-badge");
  if (state.config?.network_exposed) {
    badge.classList.remove("hidden");
    badge.textContent = "⚠ " + t("networkOn");
    badge.title = t("networkWarn", state.config.host);
  } else {
    badge.classList.add("hidden");
  }
}

// ============================ start screen ============================
async function showStart() {
  $("#vellum-view").classList.add("hidden");
  $("#start-view").classList.remove("hidden");
  clearTimeout(state.pollTimer);
  await renderVellumGrid();
}

async function renderVellumGrid() {
  let notebooks = [];
  try { notebooks = await (await api("/api/notebooks")).json(); } catch { /* offline */ }
  const grid = $("#vellum-grid");
  grid.innerHTML = "";
  notebooks.forEach((nb, i) => {
    const card = document.createElement("div");
    card.className = "vellum-card";
    card.style.animationDelay = `${i * 40}ms`;
    card.innerHTML = `
      <div class="vc-menu">
        <button class="vc-rename" title="${t("rename")}">✎</button>
        <button class="vc-delete" title="${t("delete")}">🗑</button>
      </div>
      <div class="vc-top">
        ${nb.category ? `<div class="vc-cat">${escapeHtml(nb.category)}</div>` : ""}
        <div class="vc-name">${escapeHtml(nb.name)}</div>
      </div>
      <div class="vc-meta"><span class="vc-dot"></span>${nb.source_count} ${t("sourcesLower")}</div>`;
    card.onclick = () => openVellum(nb);
    card.querySelector(".vc-rename").onclick = (e) => { e.stopPropagation(); renameVellum(nb); };
    card.querySelector(".vc-delete").onclick = (e) => { e.stopPropagation(); deleteVellum(nb); };
    grid.appendChild(card);
  });
  const add = document.createElement("div");
  add.className = "vellum-card add-card";
  add.innerHTML = `<span>＋ ${t("newVellum")}</span>`;
  add.onclick = createVellum;
  grid.appendChild(add);
}

function createVellum() {
  openFormModal({
    title: t("newVellum"),
    fields: [
      { name: "name", label: t("vellumName"), value: "" },
      { name: "category", label: t("vellumCategory"), value: "" },
    ],
    submitLabel: t("create"),
    onSubmit: async (vals) => {
      if (!vals.name.trim()) return false;
      await api("/api/notebooks", jsonPost("POST", vals));
      renderVellumGrid();
      return true;
    },
  });
}

function renameVellum(nb) {
  openFormModal({
    title: t("rename"),
    fields: [
      { name: "name", label: t("vellumName"), value: nb.name },
      { name: "category", label: t("vellumCategory"), value: nb.category || "" },
    ],
    submitLabel: t("save"),
    onSubmit: async (vals) => {
      await api(`/api/notebooks/${nb.id}`, jsonPost("PATCH", vals));
      renderVellumGrid();
      return true;
    },
  });
}

async function deleteVellum(nb) {
  if (!confirm(t("confirmDelete", nb.name))) return;
  await api(`/api/notebooks/${nb.id}`, { method: "DELETE" });
  renderVellumGrid();
}

// ============================ vellum view ============================
async function openVellum(nb) {
  state.nb = nb;
  $("#start-view").classList.add("hidden");
  $("#vellum-view").classList.remove("hidden");
  $("#vellum-title").textContent = nb.name;
  $("#messages").innerHTML = "";
  $("#citations").innerHTML = `<p class="hint">${t("citationsHint")}</p>`;
  buildModelPicker();
  await refreshSources();
}

const nbApi = (suffix) => `/api/notebooks/${state.nb.id}${suffix}`;

// ---------- sources tree ----------
const MOD_ICON = { document: "📄", image: "🖼", audio: "🎧", video: "🎬" };

function folderOf(path) {
  const norm = path.replace(/\\/g, "/");
  const i = norm.lastIndexOf("/");
  return i >= 0 ? norm.slice(0, i) : norm;
}
function baseName(path) {
  const norm = path.replace(/\\/g, "/");
  return norm.slice(norm.lastIndexOf("/") + 1) || norm;
}

async function refreshSources() {
  let data;
  try { data = await (await api(nbApi("/sources"))).json(); } catch { return; }
  state.sources = data.sources || [];
  renderReprocessBanner(data.needs_reprocess, (data.stale_source_ids || []).length);

  // group by parent folder
  const groups = new Map();
  for (const s of state.sources) {
    const folder = folderOf(s.path);
    if (!groups.has(folder)) groups.set(folder, []);
    groups.get(folder).push(s);
  }

  const tree = $("#source-tree");
  const openFolders = new Set(
    [...tree.querySelectorAll(".tree-folder:not(.collapsed)")].map((f) => f.dataset.folder));
  tree.innerHTML = "";
  if (!state.sources.length) {
    tree.innerHTML = `<p class="hint">${t("emptySources")}</p>`;
  }

  let anyBusy = false;
  for (const [folder, items] of groups) {
    const wrap = document.createElement("div");
    wrap.className = "tree-folder";
    wrap.dataset.folder = folder;
    if (openFolders.size && !openFolders.has(folder)) wrap.classList.add("collapsed");
    const head = document.createElement("div");
    head.className = "tree-folder-head";
    head.innerHTML = `<span class="caret">▼</span>
      <span class="tree-folder-name" title="${escapeHtml(folder)}">${escapeHtml(baseName(folder))}/</span>
      <span class="tree-folder-count">${items.length}</span>`;
    head.onclick = () => wrap.classList.toggle("collapsed");
    wrap.appendChild(head);

    const ul = document.createElement("ul");
    ul.className = "tree-files";
    for (const s of items) {
      if (s.status === "processing" || s.status === "pending") anyBusy = true;
      ul.appendChild(renderFileItem(s));
    }
    wrap.appendChild(ul);
    tree.appendChild(wrap);
  }

  clearTimeout(state.pollTimer);
  if (anyBusy) state.pollTimer = setTimeout(refreshSources, 1200);
}

function renderFileItem(s) {
  const li = document.createElement("li");
  li.className = "tree-file";
  const previewable = ["image", "video", "document"].includes(s.modality);
  li.innerHTML = `
    <div class="row">
      <input type="checkbox" ${s.enabled ? "checked" : ""} title="${t("toggle")}" />
      <span class="modicon">${MOD_ICON[s.modality] || "•"}</span>
      <span class="fname" title="${escapeHtml(s.path)}">${escapeHtml(s.name)}</span>
      <button class="icon-btn reprocess" title="${t("reprocessOne")}">↻</button>
      <button class="icon-btn remove" title="${t("remove")}">✕</button>
    </div>
    <div class="sub">
      <span>${fmtSize(s.size)} · ${s.chunk_count} ${t("chunks")}</span>
      ${badge(s.enabled ? s.status : "disabled")}
    </div>
    ${s.error ? `<div class="error-banner">${escapeHtml(s.error)}</div>` : ""}`;
  li.querySelector("input").onchange = (e) =>
    api(nbApi(`/sources/${s.id}`), jsonPost("PATCH", { enabled: e.target.checked })).then(refreshSources);
  const fname = li.querySelector(".fname");
  if (previewable) fname.onclick = () => openPreview(s);
  else fname.style.cursor = "default";
  li.querySelector(".reprocess").onclick = () =>
    api(nbApi(`/sources/${s.id}/reprocess`), { method: "POST" }).then(refreshSources);
  li.querySelector(".remove").onclick = () =>
    api(nbApi(`/sources/${s.id}`), { method: "DELETE" }).then(refreshSources);
  return li;
}

function badge(status) { return `<span class="badge ${status}">${status}</span>`; }
function fmtSize(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

function renderReprocessBanner(needs, count) {
  const slot = $("#reprocess-slot");
  if (!needs) { slot.innerHTML = ""; return; }
  slot.innerHTML = `<div class="banner">⚠ ${t("reprocess", count)}
    <button id="reprocess-all-btn">${t("reprocessBtn")}</button></div>`;
  $("#reprocess-all-btn").onclick = async () => {
    await api(nbApi("/sources/reprocess-all"), { method: "POST" });
    refreshSources();
  };
}

// ============================ file preview ============================
function openPreview(s) {
  const root = $("#preview-root");
  const body = $("#preview-body");
  $("#preview-name").textContent = s.name;
  const url = nbApi(`/sources/${s.id}/file`);
  const ext = (s.name.split(".").pop() || "").toLowerCase();
  body.innerHTML = `<p class="preview-fallback">${t("loading")}</p>`;
  root.classList.remove("hidden");

  if (s.modality === "image") {
    body.innerHTML = `<img src="${url}" alt="${escapeHtml(s.name)}" />`;
  } else if (s.modality === "video") {
    body.innerHTML = `<video src="${url}" controls autoplay></video>`;
  } else if (ext === "pdf") {
    body.innerHTML = `<iframe src="${url}#view=FitH" title="${escapeHtml(s.name)}"></iframe>`;
  } else if (["txt", "md", "csv", "html", "htm"].includes(ext)) {
    fetch(url).then((r) => r.text()).then((text) => {
      body.innerHTML = `<pre>${escapeHtml(text.slice(0, 200000))}</pre>`;
    }).catch(() => { body.innerHTML = previewFallback(url, s.name); });
  } else {
    body.innerHTML = previewFallback(url, s.name);
  }
}
function previewFallback(url, name) {
  return `<div class="preview-fallback">${t("noPreview")}<br>
    <a href="${url}" target="_blank" rel="noopener">${escapeHtml(name)}</a></div>`;
}
function closePreview() {
  $("#preview-root").classList.add("hidden");
  $("#preview-body").innerHTML = "";
}

// ============================ add via file browser ============================
let fbState = null;   // { path, parent, entries, shortcuts }
function openFileBrowser() {
  const root = $("#modal-root");
  root.classList.remove("hidden");
  root.innerHTML = `
    <div class="modal-backdrop" data-close></div>
    <div class="modal-card fb-card">
      <h3>${t("addTitle")}</h3>
      <div class="fb-shortcuts" id="fb-shortcuts"></div>
      <div class="fb-bar">
        <button class="ghost" id="fb-up" title="${t("up")}">↑</button>
        <input id="fb-pathinput" class="fb-pathinput" placeholder="${t("pathPlaceholder")}" />
        <button class="ghost" id="fb-go">${t("goBtn")}</button>
        <button class="chip-btn" id="fb-add-path" title="${t("addPathTip")}">＋</button>
      </div>
      <div class="fb-bar">
        <input id="fb-filter" class="fb-filter" placeholder="${t("searchPlaceholder")}" />
        <button class="ghost" id="fb-search">${t("searchBtn")}</button>
      </div>
      <div class="fb-list" id="fb-list"></div>
      <p class="fb-hint" id="fb-hint">${t("addHint")}</p>
      <div class="modal-actions">
        <button class="ghost" data-close>${t("cancel")}</button>
        <button class="primary-btn" id="fb-add-current">${t("addThisFolder")}</button>
      </div>
    </div>`;
  root.querySelectorAll("[data-close]").forEach((el) => (el.onclick = closeModal));
  $("#fb-up").onclick = () => { if (fbState?.parent) browseTo(fbState.parent); };
  $("#fb-add-current").onclick = () => fbState && addPaths([fbState.path]);
  $("#fb-go").onclick = () => browseTo($("#fb-pathinput").value.trim() || null);
  $("#fb-add-path").onclick = () => {
    const p = $("#fb-pathinput").value.trim();
    if (p) addPaths([p]);
  };
  $("#fb-pathinput").onkeydown = (e) => { if (e.key === "Enter") $("#fb-go").click(); };
  $("#fb-filter").oninput = applyFilter;
  $("#fb-filter").onkeydown = (e) => { if (e.key === "Enter") searchHere(); };
  $("#fb-search").onclick = searchHere;
  browseTo(null);
}

async function browseTo(path) {
  let data;
  try {
    const u = new URL("/api/fs/browse", location.origin);
    if (path) u.searchParams.set("path", path);
    const res = await api(u);
    if (!res.ok) throw new Error((await res.json()).detail);
    data = await res.json();
  } catch (e) {
    $("#fb-list").innerHTML = `<div class="fb-row fb-warn">${escapeHtml(String(e.message || e))}</div>`;
    return;
  }
  fbState = data;
  $("#fb-pathinput").value = data.path;
  $("#fb-up").disabled = !data.parent;
  $("#fb-filter").value = "";
  $("#fb-hint").textContent = t("addHint");

  const sc = $("#fb-shortcuts");
  sc.innerHTML = "";
  (data.shortcuts || []).forEach((s) => {
    const b = document.createElement("button");
    b.className = "chip-btn"; b.textContent = s.label; b.title = s.path;
    b.onclick = () => browseTo(s.path);
    sc.appendChild(b);
  });
  renderFbRows(data.entries, false);
}

// Instant client-side filter of the current folder listing.
function applyFilter() {
  if (!fbState) return;
  const q = $("#fb-filter").value.trim().toLowerCase();
  const rows = q
    ? fbState.entries.filter((e) => e.name.toLowerCase().includes(q))
    : fbState.entries;
  renderFbRows(rows, false);
}

// Recursive server-side search under the current folder (bounded, fast).
async function searchHere() {
  if (!fbState) return;
  const q = $("#fb-filter").value.trim();
  if (!q) { applyFilter(); return; }
  $("#fb-list").innerHTML = `<div class="fb-row">${t("searching")}</div>`;
  try {
    const u = new URL("/api/fs/search", location.origin);
    u.searchParams.set("path", fbState.path);
    u.searchParams.set("q", q);
    const res = await api(u);
    if (!res.ok) throw new Error((await res.json()).detail);
    const data = await res.json();
    renderFbRows(data.results, true);
    $("#fb-hint").textContent = data.results.length
      ? (data.truncated ? t("searchTruncated", data.results.length) : t("searchHits", data.results.length))
      : t("searchNoHits");
  } catch (e) {
    $("#fb-list").innerHTML = `<div class="fb-row fb-warn">${escapeHtml(String(e.message || e))}</div>`;
  }
}

function renderFbRows(entries, searchMode) {
  const list = $("#fb-list");
  list.innerHTML = "";
  if (!entries.length) {
    list.innerHTML = `<div class="fb-row">${t("emptyFolder")}</div>`;
    return;
  }
  for (const e of entries) {
    const row = document.createElement("div");
    row.className = "fb-row" + (e.is_dir ? "" : " is-file");
    const sub = searchMode ? `<span class="fb-sub" title="${escapeHtml(e.path)}">${escapeHtml(folderOf(e.path))}</span>` : "";
    row.innerHTML = `<span class="fb-ic">${e.is_dir ? "📁" : "📄"}</span>
      <span class="fb-nm">${escapeHtml(e.name)}</span>${sub}
      ${e.is_dir ? `<span class="fb-pick">${t("open")} ›</span>`
                 : `<span class="fb-pick">＋ ${t("addFile")}</span>`}`;
    row.onclick = () => (e.is_dir ? browseTo(e.path) : addPaths([e.path]));
    list.appendChild(row);
  }
}

async function addPaths(paths) {
  const res = await api(nbApi("/sources"), jsonPost("POST", { paths }));
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || t("addFailed"));
    return;
  }
  closeModal();
  refreshSources();
}

// ============================ model picker ============================
function buildModelPicker() {
  const wrap = $("#model-picker");
  const models = state.config?.models || [];
  if (!models.length) { wrap.innerHTML = ""; return; }
  if (!models.some((m) => m.id === state.model)) state.model = models[0].id;

  wrap.innerHTML = `
    <button class="mp-button" id="mp-button">
      <span>🧠</span><span class="mp-label" id="mp-label"></span><span>▾</span>
    </button>
    <div class="mp-panel hidden" id="mp-panel">
      <input id="mp-search" placeholder="${t("searchModels")}" />
      <div class="mp-list" id="mp-list"></div>
    </div>`;
  updateModelLabel();
  const panel = $("#mp-panel");
  $("#mp-button").onclick = (e) => {
    e.stopPropagation();
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) { renderModelList(""); $("#mp-search").focus(); }
  };
  $("#mp-search").oninput = (e) => renderModelList(e.target.value);
  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) panel.classList.add("hidden");
  });
}

function updateModelLabel() {
  const m = (state.config?.models || []).find((x) => x.id === state.model);
  const label = $("#mp-label");
  if (label) label.textContent = m ? m.label : t("defaultModel");
}

function renderModelList(filter) {
  const list = $("#mp-list");
  const q = filter.toLowerCase();
  const models = (state.config?.models || []).filter(
    (m) => m.label.toLowerCase().includes(q) || m.id.toLowerCase().includes(q));
  list.innerHTML = "";
  if (!models.length) { list.innerHTML = `<div class="mp-empty">${t("noModels")}</div>`; return; }
  for (const m of models) {
    const item = document.createElement("div");
    item.className = "mp-item" + (m.id === state.model ? " active" : "");
    item.textContent = m.label;
    item.title = m.id;
    item.onclick = () => {
      state.model = m.id;
      updateModelLabel();
      $("#mp-panel").classList.add("hidden");
    };
    list.appendChild(item);
  }
}

// ============================ chat ============================
function addMessage(role, html) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = html;
  $("#messages").appendChild(div);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return div;
}

function renderCitations(citations) {
  const box = $("#citations");
  if (!citations.length) { box.innerHTML = `<p class="hint">${t("noMatch")}</p>`; return; }
  box.innerHTML = "";
  citations.forEach((c, i) => {
    const el = document.createElement("div");
    el.className = "citation";
    el.id = `cite-S${i + 1}`;
    el.innerHTML = `
      <div><span class="marker">[S${i + 1}]</span> <span class="src">${escapeHtml(c.source_name)}</span></div>
      ${c.locator ? `<div class="loc">${escapeHtml(c.locator)}</div>` : ""}
      <div class="snippet">${escapeHtml(c.snippet)}</div>`;
    box.appendChild(el);
  });
}

function linkifyCitations(text) {
  return escapeHtml(text).replace(/\[S(\d+)\]/g, (m, n) =>
    `<span class="cite" data-s="${n}">[S${n}]</span>`);
}

async function sendChat(e) {
  e.preventDefault();
  const input = $("#chat-input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  $("#send-btn").disabled = true;
  addMessage("user", escapeHtml(message));
  const out = addMessage("assistant", `<em>${t("thinking")}</em>`);

  try {
    const res = await api(nbApi("/chat"), jsonPost("POST", { message, model: state.model }));
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    out.innerHTML = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const events = buf.split("\n\n");
      buf = events.pop();
      for (const block of events) handleEvent(block, out);
    }
  } catch (err) {
    out.innerHTML = `<span class="error-banner">Error: ${escapeHtml(String(err))}</span>`;
  } finally {
    $("#send-btn").disabled = false;
    bindCitationClicks(out);
  }
}

function handleEvent(block, out) {
  const lines = block.split("\n");
  let event = "message", data = "";
  for (const ln of lines) {
    if (ln.startsWith("event:")) event = ln.slice(6).trim();
    else if (ln.startsWith("data:")) data += ln.slice(5).trim();
  }
  if (!data) return;
  let payload;
  try { payload = JSON.parse(data); } catch { return; }
  if (event === "citations") {
    renderCitations(payload);
  } else if (event === "token") {
    out.dataset.raw = (out.dataset.raw || "") + payload.text;
    out.innerHTML = linkifyCitations(out.dataset.raw);
    $("#messages").scrollTop = $("#messages").scrollHeight;
  } else if (event === "error") {
    out.innerHTML = `<span class="error-banner">${escapeHtml(payload.message)}</span>`;
  }
}

function bindCitationClicks(out) {
  out.querySelectorAll(".cite").forEach((el) => {
    el.onclick = () => {
      const target = document.getElementById(`cite-S${el.dataset.s}`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("flash");
        setTimeout(() => target.classList.remove("flash"), 1200);
      }
    };
  });
}

// ============================ generic form modal ============================
function openFormModal({ title, fields, submitLabel, onSubmit }) {
  const root = $("#modal-root");
  root.classList.remove("hidden");
  root.innerHTML = `
    <div class="modal-backdrop" data-close></div>
    <div class="modal-card">
      <h3>${escapeHtml(title)}</h3>
      ${fields.map((f) => `
        <label>${escapeHtml(f.label)}</label>
        <input data-field="${f.name}" value="${escapeHtml(f.value)}" />`).join("")}
      <div class="modal-actions">
        <button class="ghost" data-close>${t("cancel")}</button>
        <button class="primary-btn" id="modal-submit">${escapeHtml(submitLabel)}</button>
      </div>
    </div>`;
  root.querySelectorAll("[data-close]").forEach((el) => (el.onclick = closeModal));
  const inputs = [...root.querySelectorAll("[data-field]")];
  inputs[0]?.focus();
  $("#modal-submit").onclick = async () => {
    const vals = {};
    inputs.forEach((i) => (vals[i.dataset.field] = i.value));
    const ok = await onSubmit(vals);
    if (ok !== false) closeModal();
  };
}
function closeModal() { $("#modal-root").classList.add("hidden"); $("#modal-root").innerHTML = ""; }

// ============================ helpers ============================
function jsonPost(method, body) {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function toggleTheme() {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
}

// ============================ wiring ============================
$("#new-vellum-btn").onclick = createVellum;
$("#back-btn").onclick = showStart;
$("#add-btn").onclick = openFileBrowser;
$("#chat-form").onsubmit = sendChat;
$("#theme-toggle").onclick = toggleTheme;
$("#start-theme").onclick = toggleTheme;
$("#preview-close").onclick = closePreview;
$(".preview-backdrop").onclick = closePreview;
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closePreview(); closeModal(); }
});

// init
(async () => { await loadConfig(); await showStart(); })();
