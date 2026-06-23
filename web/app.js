"use strict";
// Local NotebookLM UI. No external dependencies, no trackers, no CDN.

const $ = (sel) => document.querySelector(sel);
const api = (path, opts) => fetch(path, opts);

let pollTimer = null;
let lastCitations = [];

// ---------- config / meta ----------
async function loadConfig() {
  try {
    const cfg = await (await api("/api/config")).json();
    const ok = cfg.adapter_available;
    $("#meta").innerHTML =
      `CLI: <b>${cfg.cli_adapter}</b> ${ok ? "✓" : "⚠ not found"} · ` +
      `embedder: ${cfg.embedder} (dim ${cfg.embedder_dim}) · transcriber: ${cfg.transcriber}`;
    renderReprocessBanner(cfg.needs_reprocess, (cfg.stale_source_ids || []).length);
  } catch {
    $("#meta").textContent = "server unreachable";
  }
}

// Shown when sources were embedded with a different dimension than the current
// embedder (e.g. after switching MMRAG_EMBEDDER). Those sources are excluded
// from search until reprocessed.
function renderReprocessBanner(needs, count) {
  let banner = $("#reprocess-banner");
  if (!needs) { if (banner) banner.remove(); return; }
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "reprocess-banner";
    banner.className = "banner";
    $(".sources").insertBefore(banner, $("#source-list"));
  }
  banner.innerHTML =
    `⚠ ${count} source(s) were embedded with a different model and are excluded ` +
    `from search. <button id="reprocess-all-btn">Reprocess all</button>`;
  $("#reprocess-all-btn").onclick = async () => {
    await api("/api/sources/reprocess-all", { method: "POST" });
    refreshSources();
    setTimeout(loadConfig, 1500);
  };
}

// ---------- sources ----------
function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}
function fmtSize(n) {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${u[i]}`;
}

async function refreshSources() {
  let sources = [];
  try { sources = await (await api("/api/sources")).json(); } catch { return; }
  const list = $("#source-list");
  list.innerHTML = "";
  let anyBusy = false;
  for (const s of sources) {
    if (s.status === "processing" || s.status === "pending") anyBusy = true;
    const li = document.createElement("li");
    li.className = "source-item";
    li.innerHTML = `
      <div class="row">
        <input type="checkbox" ${s.enabled ? "checked" : ""} title="Enable/disable" />
        <span class="name" title="${escapeHtml(s.path)}">${escapeHtml(s.name)}</span>
        <button class="icon-btn reprocess" title="Reprocess">↻</button>
        <button class="icon-btn remove" title="Remove">✕</button>
      </div>
      <div class="sub">
        <span>${s.modality} · ${fmtSize(s.size)} · ${s.chunk_count} chunks</span>
        ${badge(s.enabled ? s.status : "disabled")}
      </div>
      ${s.error ? `<div class="error-banner">${escapeHtml(s.error)}</div>` : ""}`;
    li.querySelector("input").onchange = (e) =>
      api(`/api/sources/${s.id}`, jsonPost("PATCH", { enabled: e.target.checked }))
        .then(refreshSources);
    li.querySelector(".reprocess").onclick = () =>
      api(`/api/sources/${s.id}/reprocess`, { method: "POST" }).then(refreshSources);
    li.querySelector(".remove").onclick = () =>
      api(`/api/sources/${s.id}`, { method: "DELETE" }).then(refreshSources);
    list.appendChild(li);
  }
  // Poll while anything is still processing.
  clearTimeout(pollTimer);
  if (anyBusy) pollTimer = setTimeout(refreshSources, 1200);
  else loadConfig();  // refresh the stale-embedder banner once ingestion settles
}

$("#add-form").onsubmit = async (e) => {
  e.preventDefault();
  const input = $("#path-input");
  const path = input.value.trim();
  if (!path) return;
  const res = await api("/api/sources", jsonPost("POST", { paths: [path] }));
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "Could not add that path.");
    return;
  }
  input.value = "";
  refreshSources();
};

// ---------- chat ----------
function addMessage(role, html) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = html;
  $("#messages").appendChild(div);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return div;
}

function renderCitations(citations) {
  lastCitations = citations;
  const box = $("#citations");
  if (!citations.length) {
    box.innerHTML = `<p class="hint">No sources matched this question.</p>`;
    return;
  }
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

// Turn [S1] markers in the answer into clickable links.
function linkifyCitations(text) {
  return escapeHtml(text).replace(/\[S(\d+)\]/g, (m, n) =>
    `<span class="cite" data-s="${n}">[S${n}]</span>`);
}

$("#chat-form").onsubmit = async (e) => {
  e.preventDefault();
  const input = $("#chat-input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  $("#send-btn").disabled = true;
  addMessage("user", escapeHtml(message));
  const out = addMessage("assistant", "<em>thinking…</em>");
  let answer = "";

  try {
    const res = await api("/api/chat", jsonPost("POST", { message }));
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
      for (const block of events) handleEvent(block, out, (t) => { answer += t; });
    }
  } catch (err) {
    out.innerHTML = `<span class="error-banner">Error: ${escapeHtml(String(err))}</span>`;
  } finally {
    $("#send-btn").disabled = false;
    bindCitationClicks(out);
  }
};

function handleEvent(block, out, appendAnswer) {
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
    appendAnswer(payload.text);
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

// ---------- helpers ----------
function jsonPost(method, body) {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// theme
$("#theme-toggle").onclick = () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
};

// init
loadConfig();
refreshSources();
