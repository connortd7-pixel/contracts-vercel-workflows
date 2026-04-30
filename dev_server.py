"""
Local dev server for testing the diff pipeline without Supabase.

Accepts file uploads directly — no credentials needed.

Usage:
    pip install -r requirements-dev.txt
    python dev_server.py

Then open http://localhost:5000 in your browser.
Set ANTHROPIC_API_KEY in your environment (or .env) to enable the Analyze feature.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify, render_template_string
from core.parser import parse_file
from core.differ import compute_diff

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB per upload

# ---------------------------------------------------------------------------
# HTML / CSS / JS — all inline so there are no static file dependencies
# ---------------------------------------------------------------------------

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Contract Diff Tester</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    background: #f0f2f5;
    color: #1a1a1a;
    padding: 24px;
  }

  h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .subtitle { color: #666; font-size: 13px; margin-bottom: 24px; }

  /* ── Upload card ─────────────────────────────────────────────── */
  .card {
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
  }

  .upload-row {
    display: grid;
    grid-template-columns: 1fr 1fr auto auto;
    gap: 16px;
    align-items: end;
  }

  .file-group label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #555;
    margin-bottom: 8px;
  }

  .drop-zone {
    border: 2px dashed #ccc;
    border-radius: 6px;
    padding: 20px 16px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    position: relative;
  }
  .drop-zone:hover, .drop-zone.dragover { border-color: #4f6ef7; background: #f5f7ff; }
  .drop-zone.has-file { border-color: #22a06b; background: #f0faf5; }
  .drop-zone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .drop-zone .dz-icon { font-size: 24px; margin-bottom: 6px; }
  .drop-zone .dz-label { font-size: 13px; color: #555; }
  .drop-zone .dz-filename { font-size: 12px; color: #22a06b; font-weight: 500; margin-top: 4px; }

  button {
    background: #4f6ef7;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 10px 24px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
    height: 80px;
  }
  button:hover { background: #3b5ae0; }
  button:disabled { background: #a0aec0; cursor: not-allowed; }

  .btn-analyze {
    background: #7c3aed;
    height: 80px;
  }
  .btn-analyze:hover:not(:disabled) { background: #6d28d9; }

  /* ── Stats bar ───────────────────────────────────────────────── */
  .stats-bar {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .stat-pill {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 99px;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .stat-pill .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .pill-unchanged  { background: #f0f0f0; color: #555; }
  .pill-unchanged  .dot { background: #aaa; }
  .pill-modified   { background: #fff8e1; color: #7a5700; }
  .pill-modified   .dot { background: #f0a500; }
  .pill-added      { background: #e6ffed; color: #1a6e3e; }
  .pill-added      .dot { background: #22a06b; }
  .pill-removed    { background: #ffeef0; color: #8b1a26; }
  .pill-removed    .dot { background: #e5534b; }

  /* ── View toggle ─────────────────────────────────────────────── */
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    flex-wrap: wrap;
    gap: 10px;
  }
  .toolbar-right { display: flex; align-items: center; gap: 8px; }
  .view-toggle { display: flex; gap: 4px; }
  .view-btn {
    background: #e8eaf0;
    color: #444;
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    height: auto;
  }
  .view-btn.active { background: #4f6ef7; color: #fff; }
  .view-btn.active-analysis { background: #7c3aed; color: #fff; }
  .view-btn:hover:not(.active):not(.active-analysis) { background: #d5d9e8; }

  .analyze-inline-btn {
    background: #7c3aed;
    color: #fff;
    border: none;
    border-radius: 5px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    height: auto;
    white-space: nowrap;
    transition: background 0.15s;
  }
  .analyze-inline-btn:hover:not(:disabled) { background: #6d28d9; }
  .analyze-inline-btn:disabled { background: #a0aec0; cursor: not-allowed; }

  /* ── Diff table — shared ─────────────────────────────────────── */
  .diff-wrap { overflow-x: auto; }

  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th {
    background: #f5f5f5;
    text-align: left;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #666;
    border-bottom: 1px solid #e0e0e0;
    position: sticky;
    top: 0;
    z-index: 1;
  }
  td {
    padding: 5px 12px;
    border-bottom: 1px solid #f0f0f0;
    vertical-align: top;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12.5px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .ln { color: #aaa; font-size: 11px; text-align: right; min-width: 36px; user-select: none; }

  /* ── Side-by-side row colors ─────────────────────────────────── */
  tr.row-unchanged td.cell-before,
  tr.row-unchanged td.cell-after   { background: #fff; }
  tr.row-added     td.cell-before  { background: #fafafa; }
  tr.row-added     td.cell-after   { background: #e6ffed; }
  tr.row-removed   td.cell-before  { background: #ffeef0; }
  tr.row-removed   td.cell-after   { background: #fafafa; }
  tr.row-modified  td.cell-before  { background: #fff5f5; }
  tr.row-modified  td.cell-after   { background: #f0fff4; }

  /* ── Redline colors ──────────────────────────────────────────── */
  tr.row-added     td.cell-redline { background: #e6ffed; }
  tr.row-removed   td.cell-redline { background: #ffeef0; }
  tr.row-modified  td.cell-redline { background: #fffbea; }

  /* ── Inline token highlights ─────────────────────────────────── */
  .tok-removed {
    background: #fdb8c0;
    text-decoration: line-through;
    border-radius: 2px;
    padding: 0 1px;
  }
  .tok-added {
    background: #acf2bd;
    border-radius: 2px;
    padding: 0 1px;
  }

  /* ── Analysis cards ──────────────────────────────────────────── */
  .analysis-list { display: flex; flex-direction: column; gap: 14px; }

  .analysis-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
  }
  .analysis-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-bottom: 1px solid #e8e8e8;
  }
  .analysis-card.type-modified .analysis-card-header { background: #fffbeb; }
  .analysis-card.type-added    .analysis-card-header { background: #f0fdf4; }
  .analysis-card.type-removed  .analysis-card-header { background: #fff1f2; }

  .change-badge {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 3px 8px;
    border-radius: 4px;
  }
  .badge-modified { background: #fef3c7; color: #92400e; }
  .badge-added    { background: #d1fae5; color: #065f46; }
  .badge-removed  { background: #fee2e2; color: #991b1b; }

  .clause-ref {
    font-size: 13px;
    font-weight: 600;
    color: #1a1a1a;
  }
  .block-num {
    font-size: 11px;
    color: #aaa;
    margin-left: auto;
  }

  .analysis-card-body {
    padding: 14px 16px;
    background: #fff;
  }
  .analysis-summary {
    font-size: 14px;
    font-weight: 500;
    color: #111;
    margin-bottom: 6px;
    line-height: 1.5;
  }
  .analysis-detail {
    font-size: 13px;
    color: #444;
    line-height: 1.6;
    margin-bottom: 12px;
  }

  .snippets {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 10px;
  }
  .snippet-block { border-radius: 5px; overflow: hidden; }
  .snippet-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    padding: 4px 10px;
  }
  .snippet-before .snippet-label { background: #fee2e2; color: #991b1b; }
  .snippet-after  .snippet-label { background: #d1fae5; color: #065f46; }
  .snippet-text {
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11.5px;
    line-height: 1.55;
    padding: 8px 10px;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .snippet-before .snippet-text { background: #fff5f5; color: #444; }
  .snippet-after  .snippet-text { background: #f0fdf4; color: #444; }
  .snippet-none   .snippet-text { background: #f8f8f8; color: #aaa; font-style: italic; }

  .analysis-notice {
    font-size: 12px;
    color: #888;
    padding: 10px 0 0 0;
    border-top: 1px solid #f0f0f0;
    margin-top: 12px;
  }

  /* ── Empty / error states ────────────────────────────────────── */
  .placeholder {
    text-align: center;
    padding: 48px 0;
    color: #aaa;
    font-size: 14px;
  }
  .error-msg {
    background: #ffeef0;
    border: 1px solid #f5c6cb;
    color: #8b1a26;
    border-radius: 6px;
    padding: 12px 16px;
    font-size: 13px;
  }
  .spinner {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 6px;
  }
  .spinner-dark {
    display: inline-block;
    width: 14px; height: 14px;
    border: 2px solid rgba(124,58,237,0.25);
    border-top-color: #7c3aed;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 5px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .analyzing-notice {
    font-size: 13px;
    color: #7c3aed;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 12px 0;
  }
</style>
</head>
<body>

<h1>Contract Diff Tester</h1>
<p class="subtitle">Upload two contracts (PDF or DOCX) to compare them locally — no Supabase needed.</p>

<div class="card">
  <div class="upload-row">
    <div class="file-group">
      <label>Original (before)</label>
      <div class="drop-zone" id="zone-a">
        <div class="dz-icon">📄</div>
        <div class="dz-label">Click or drag a PDF / DOCX here</div>
        <div class="dz-filename" id="name-a"></div>
        <input type="file" id="file-a" accept=".pdf,.docx">
      </div>
    </div>
    <div class="file-group">
      <label>Revised (after)</label>
      <div class="drop-zone" id="zone-b">
        <div class="dz-icon">📄</div>
        <div class="dz-label">Click or drag a PDF / DOCX here</div>
        <div class="dz-filename" id="name-b"></div>
        <input type="file" id="file-b" accept=".pdf,.docx">
      </div>
    </div>
    <button id="compare-btn" disabled>Compare</button>
    <button id="analyze-btn" class="btn-analyze" disabled title="Requires ANTHROPIC_API_KEY">Analyze<br>with Claude</button>
  </div>
</div>

<div id="result-area"></div>

<script>
// ── State ──────────────────────────────────────────────────────────────────

let currentLines    = [];
let currentAnalysis = null;
let currentView     = "sidebyside";   // "sidebyside" | "redline" | "analysis"

// ── File input wiring ──────────────────────────────────────────────────────

function wireZone(zoneId, inputId, nameId) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  const name  = document.getElementById(nameId);

  input.addEventListener("change", () => {
    const f = input.files[0];
    if (f) {
      name.textContent = f.name;
      zone.classList.add("has-file");
    }
    updateBtns();
  });

  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", ()  => zone.classList.remove("dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("dragover");
    const f = e.dataTransfer.files[0];
    if (f) {
      const dt = new DataTransfer();
      dt.items.add(f);
      input.files = dt.files;
      name.textContent = f.name;
      zone.classList.add("has-file");
      updateBtns();
    }
  });
}

wireZone("zone-a", "file-a", "name-a");
wireZone("zone-b", "file-b", "name-b");

function bothFilesSelected() {
  return !!(document.getElementById("file-a").files[0] &&
            document.getElementById("file-b").files[0]);
}

function updateBtns() {
  const ok = bothFilesSelected();
  document.getElementById("compare-btn").disabled = !ok;
  document.getElementById("analyze-btn").disabled  = !ok;
}

// ── Compare ────────────────────────────────────────────────────────────────

document.getElementById("compare-btn").addEventListener("click", async () => {
  const btn  = document.getElementById("compare-btn");
  const area = document.getElementById("result-area");

  btn.innerHTML = '<span class="spinner"></span>Comparing…';
  btn.disabled  = true;
  area.innerHTML = "";

  const form = new FormData();
  form.append("file_a", document.getElementById("file-a").files[0]);
  form.append("file_b", document.getElementById("file-b").files[0]);

  try {
    const res  = await fetch("/compare", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok || data.error) {
      area.innerHTML = `<div class="error-msg">⚠ ${data.error || "Unknown error"}</div>`;
    } else {
      currentLines    = data.lines;
      currentAnalysis = null;
      currentView     = "sidebyside";
      renderAll();
    }
  } catch (err) {
    area.innerHTML = `<div class="error-msg">⚠ Request failed: ${err.message}</div>`;
  } finally {
    btn.innerHTML = "Compare";
    btn.disabled  = !bothFilesSelected();
  }
});

// ── Analyze ────────────────────────────────────────────────────────────────

document.getElementById("analyze-btn").addEventListener("click", runAnalysis);

async function runAnalysis() {
  const btn  = document.getElementById("analyze-btn");
  const area = document.getElementById("result-area");

  btn.innerHTML = '<span class="spinner"></span>Analyzing…';
  btn.disabled  = true;

  const form = new FormData();
  form.append("file_a", document.getElementById("file-a").files[0]);
  form.append("file_b", document.getElementById("file-b").files[0]);

  // If we haven't run compare yet, show the diff area with a loading notice first
  if (!currentLines.length) {
    area.innerHTML = `<div class="card"><div class="analyzing-notice">
      <span class="spinner-dark"></span>
      Running comparison and sending to Claude for analysis — this may take 15–30 seconds…
    </div></div>`;
  } else {
    // Already have diff; show analysis loading in-place
    currentView = "analysis";
    renderAll(true /* loading */);
  }

  try {
    const res  = await fetch("/analyze", { method: "POST", body: form });
    const data = await res.json();

    if (!res.ok || data.error) {
      area.innerHTML = `<div class="error-msg">⚠ ${data.error || "Unknown error"}</div>`;
    } else {
      currentLines    = data.lines;
      currentAnalysis = data.analyses;
      currentView     = "analysis";
      renderAll();
    }
  } catch (err) {
    area.innerHTML = `<div class="error-msg">⚠ Request failed: ${err.message}</div>`;
  } finally {
    btn.innerHTML = "Analyze<br>with Claude";
    btn.disabled  = !bothFilesSelected();
  }
}

// ── Rendering — shared ─────────────────────────────────────────────────────

function countByStatus(lines) {
  const c = { unchanged: 0, modified: 0, added: 0, removed: 0 };
  for (const l of lines) c[l.status] = (c[l.status] || 0) + 1;
  return c;
}

function renderStats(lines) {
  const c = countByStatus(lines);
  const pills = [
    { key: "unchanged", label: "Unchanged" },
    { key: "modified",  label: "Modified"  },
    { key: "added",     label: "Added"     },
    { key: "removed",   label: "Removed"   },
  ];
  return `<div class="stats-bar">` +
    pills.filter(p => c[p.key] > 0).map(p =>
      `<span class="stat-pill pill-${p.key}">
         <span class="dot"></span>${c[p.key]} ${p.label}
       </span>`
    ).join("") +
  `</div>`;
}

function esc(str) {
  if (!str) return "";
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function renderTokens(tokens) {
  return tokens.map(t => {
    const txt = esc(t.text);
    if (t.type === "removed") return `<span class="tok-removed">${txt}</span>`;
    if (t.type === "added")   return `<span class="tok-added">${txt}</span>`;
    return txt;
  }).join("");
}

function renderAll(analysisLoading = false) {
  const area = document.getElementById("result-area");

  const hasAnalysis = currentAnalysis !== null;
  const analysisBtnClass = currentView === "analysis" ? "active-analysis" : "";

  const toolbar = `
    <div class="toolbar">
      ${renderStats(currentLines)}
      <div class="toolbar-right">
        <div class="view-toggle">
          <button class="view-btn ${currentView === 'sidebyside' ? 'active' : ''}"
                  onclick="switchView('sidebyside')">Side by Side</button>
          <button class="view-btn ${currentView === 'redline' ? 'active' : ''}"
                  onclick="switchView('redline')">Redline</button>
          ${hasAnalysis
            ? `<button class="view-btn ${currentView === 'analysis' ? 'active-analysis' : ''}"
                       onclick="switchView('analysis')">Analysis</button>`
            : ""}
        </div>
        <button class="analyze-inline-btn" onclick="runAnalysis()"
                ${analysisLoading ? "disabled" : ""}>
          ${analysisLoading
            ? `<span class="spinner-dark"></span>Analyzing…`
            : (hasAnalysis ? "Re-Analyze" : "Analyze with Claude")}
        </button>
      </div>
    </div>`;

  let content;
  if (currentView === "analysis") {
    content = analysisLoading
      ? `<div class="analyzing-notice"><span class="spinner-dark"></span>Sending to Claude — this may take 15–30 seconds…</div>`
      : renderAnalysis(currentAnalysis);
  } else if (currentView === "sidebyside") {
    content = `<div class="diff-wrap">${renderSideBySide(currentLines)}</div>`;
  } else {
    content = `<div class="diff-wrap">${renderRedline(currentLines)}</div>`;
  }

  area.innerHTML = `<div class="card">${toolbar}${content}</div>`;
}

function switchView(view) {
  currentView = view;
  if (currentLines.length) renderAll();
}

// ── Diff views ─────────────────────────────────────────────────────────────

function renderSideBySide(lines) {
  const rows = lines.map(l => {
    const before = l.before != null ? esc(l.before) : `<span style="color:#ccc">—</span>`;
    const after  = l.after  != null ? esc(l.after)  : `<span style="color:#ccc">—</span>`;
    return `<tr class="row-${l.status}">
      <td class="ln">${l.line_number}</td>
      <td class="cell-before">${before}</td>
      <td class="cell-after">${after}</td>
    </tr>`;
  }).join("");

  return `<table>
    <thead>
      <tr>
        <th class="ln">#</th>
        <th>Before</th>
        <th>After</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderRedline(lines) {
  const rows = lines.map(l => {
    let content;
    if (l.status === "unchanged") {
      content = esc(l.after);
    } else if (l.status === "added") {
      content = `<span class="tok-added">${esc(l.after)}</span>`;
    } else if (l.status === "removed") {
      content = `<span class="tok-removed">${esc(l.before)}</span>`;
    } else {
      content = l.tokens && l.tokens.length ? renderTokens(l.tokens) : esc(l.after);
    }
    return `<tr class="row-${l.status}">
      <td class="ln">${l.line_number}</td>
      <td class="cell-redline">${content}</td>
    </tr>`;
  }).join("");

  return `<table>
    <thead>
      <tr><th class="ln">#</th><th>Redline View</th></tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// ── Analysis view ──────────────────────────────────────────────────────────

function renderAnalysis(analyses) {
  if (!analyses || !analyses.length) {
    return `<div class="placeholder">No changes found — contracts appear identical.</div>`;
  }

  const cards = analyses.map(a => {
    const type      = a.change_type || "modified";
    const badgeCls  = `badge-${type}`;
    const cardCls   = `type-${type}`;
    const clauseRef = esc(a.clause_ref || "Unknown");
    const summary   = esc(a.summary   || "");
    const detail    = esc(a.detail    || "");

    const beforeHTML = a.before_snippet
      ? `<div class="snippet-block snippet-before">
           <div class="snippet-label">Before</div>
           <div class="snippet-text">${esc(a.before_snippet)}</div>
         </div>`
      : `<div class="snippet-block snippet-none">
           <div class="snippet-label" style="background:#f0f0f0;color:#aaa">Before</div>
           <div class="snippet-text">— not present in original —</div>
         </div>`;

    const afterHTML = a.after_snippet
      ? `<div class="snippet-block snippet-after">
           <div class="snippet-label">After</div>
           <div class="snippet-text">${esc(a.after_snippet)}</div>
         </div>`
      : `<div class="snippet-block snippet-none">
           <div class="snippet-label" style="background:#f0f0f0;color:#aaa">After</div>
           <div class="snippet-text">— removed in revised version —</div>
         </div>`;

    return `
      <div class="analysis-card ${cardCls}">
        <div class="analysis-card-header">
          <span class="change-badge ${badgeCls}">${type}</span>
          <span class="clause-ref">${clauseRef}</span>
          <span class="block-num">#${a.block_id}</span>
        </div>
        <div class="analysis-card-body">
          <div class="analysis-summary">${summary}</div>
          <div class="analysis-detail">${detail}</div>
          <div class="snippets">${beforeHTML}${afterHTML}</div>
          <div class="analysis-notice">
            ⓘ Changes identified by deterministic diff engine — Claude provides explanation only.
          </div>
        </div>
      </div>`;
  }).join("");

  return `<div class="analysis-list">${cards}</div>`;
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML)


@app.route("/compare", methods=["POST"])
def compare():
    file_a = request.files.get("file_a")
    file_b = request.files.get("file_b")

    if not file_a or not file_b:
        return jsonify({"error": "Both files are required"}), 400

    ext_a = (file_a.filename or "").rsplit(".", 1)[-1].lower()
    ext_b = (file_b.filename or "").rsplit(".", 1)[-1].lower()

    if ext_a not in ("pdf", "docx") or ext_b not in ("pdf", "docx"):
        return jsonify({"error": "Only PDF and DOCX files are supported"}), 400

    try:
        lines_a = parse_file(file_a.read(), ext_a)
        lines_b = parse_file(file_b.read(), ext_b)
        diff    = compute_diff(lines_a, lines_b)
        return jsonify({"status": "ok", "lines": diff})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/analyze", methods=["POST"])
def analyze():
    from core.analyzer import analyze_diff

    file_a = request.files.get("file_a")
    file_b = request.files.get("file_b")

    if not file_a or not file_b:
        return jsonify({"error": "Both files are required"}), 400

    ext_a = (file_a.filename or "").rsplit(".", 1)[-1].lower()
    ext_b = (file_b.filename or "").rsplit(".", 1)[-1].lower()

    if ext_a not in ("pdf", "docx") or ext_b not in ("pdf", "docx"):
        return jsonify({"error": "Only PDF and DOCX files are supported"}), 400

    try:
        lines_a  = parse_file(file_a.read(), ext_a)
        lines_b  = parse_file(file_b.read(), ext_b)
        diff     = compute_diff(lines_a, lines_b)
        analyses = analyze_diff(diff)
        return jsonify({"status": "ok", "lines": diff, "analyses": analyses})
    except (ValueError, ImportError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"\n  Contract Diff Tester → http://localhost:{port}")
    print(f"  ANTHROPIC_API_KEY: {'set ✓' if key_set else 'NOT SET — Analyze button will error'}\n")
    app.run(debug=True, port=port)
