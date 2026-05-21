#!/usr/bin/env node
// Generates ~/Desktop/c1-price-verification.html from the C1 BOM and
// component_functions.json. Run with: node scripts/build-price-verification.mjs

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..');
const BOM_CSV = path.join(REPO, 'src-tauri/data/bom-c1-main.csv');
const FUNCTIONS_JSON = path.join(REPO, 'src-tauri/data/component_functions.json');
const OUTPUT = path.join(os.homedir(), 'Desktop', 'c1-price-verification.html');

const EXCLUDE = new Set([
  'OSO-BOOK-C2-01',
  'GDEW042T2',
]);

const FLAGS = {
  'CL21B105KAFNNNE':
    'Mouser PN in upstream BOM ends in F (187-CL21B105KAFNNNF) — likely a typo; MPN ends in E. Verify what Mouser actually lists.',
  'TL1107AF180WQ':
    'Mouser PN 612-TL1107 is a series number — may land on a family page, not the specific variant.',
};

function parseCsv(text) {
  const lines = text.split(/\r?\n/).filter(l => l.length > 0);
  const rows = lines.map(parseCsvLine);
  const header = rows[0];
  return rows.slice(1).map(cells => Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ''])));
}

function parseCsvLine(line) {
  const out = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') { inQuotes = false; }
      else { cur += c; }
    } else {
      if (c === '"') { inQuotes = true; }
      else if (c === ',') { out.push(cur); cur = ''; }
      else { cur += c; }
    }
  }
  out.push(cur);
  return out;
}

function dkUrl(pn) {
  return `https://www.digikey.com/en/products/result?keywords=${encodeURIComponent(pn)}`;
}

function mouserUrl(pn) {
  return `https://www.mouser.com/ProductDetail/${pn}`;
}

function fmtUsd(v) {
  if (v == null) return '—';
  return '$' + Number(v).toFixed(2);
}

function buildRows() {
  const csvRows = parseCsv(readFileSync(BOM_CSV, 'utf8'));
  const fns = JSON.parse(readFileSync(FUNCTIONS_JSON, 'utf8'));
  const rows = [];
  const skipped = [];
  for (const r of csvRows) {
    const mpn = r['MPN']?.trim();
    if (!mpn) continue;
    if (EXCLUDE.has(mpn)) {
      skipped.push({ mpn, reason: explainSkip(mpn) });
      continue;
    }
    const fn = fns[mpn] ?? {};
    const dkPn = (r['Digikey'] || fn.digikey_pn || '').trim();
    const mouserPn = (r['Mouser'] || fn.mouser_pn || '').trim();
    if (!dkPn && !mouserPn) {
      skipped.push({ mpn, reason: 'no DigiKey or Mouser PN on file' });
      continue;
    }
    rows.push({
      mpn,
      fn: fn.function || r['Description'] || '',
      qty: Number(r['Qty']) || 1,
      expected: fmtUsd(fn.unitCostUsd ?? null),
      flag: FLAGS[mpn] || null,
      preferredDistributor: null,
      distributors: {
        dk: {
          default: dkPn ? dkUrl(dkPn) : '',
          label: dkPn ? `DK ${dkPn}` : '',
          url: '',
          status: null,
          unitPrice: '',
          notes: '',
        },
        mouser: {
          default: mouserPn ? mouserUrl(mouserPn) : '',
          label: mouserPn ? `Mouser ${mouserPn}` : '',
          url: '',
          status: null,
          unitPrice: '',
          notes: '',
        },
      },
    });
  }
  return { rows, skipped };
}

function explainSkip(mpn) {
  if (mpn === 'OSO-BOOK-C2-01') return 'custom PCBA, priced as a single module ($30–80)';
  if (mpn === 'GDEW042T2') return 'display ordered direct from Good Display; no Western distributor';
  return 'excluded';
}

function escAttr(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function renderHtml({ rows, skipped }) {
  const seedJson = JSON.stringify(rows, null, 2);
  const skippedHtml = skipped
    .map(s => `<li><code>${escAttr(s.mpn)}</code> — ${escAttr(s.reason)}</li>`)
    .join('\n      ');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>C1 Main Board — Price Verification</title>
<style>
  body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
  h1 { font-size: 18px; color: #f1f5f9; margin-bottom: 4px; }
  .subtitle { font-size: 12px; color: #64748b; margin-bottom: 16px; max-width: 760px; line-height: 1.5; }
  .toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
  button { background: #2563eb; color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600; }
  button:hover { background: #3b82f6; }
  button.secondary { background: #334155; }
  button.secondary:hover { background: #475569; }
  .saved-indicator { font-size: 11px; color: #64748b; }
  .qty-control { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #cbd5e1; }
  .qty-control input { width: 64px; }
  table { border-collapse: collapse; width: 100%; font-size: 12px; }
  th { text-align: left; padding: 8px 10px; background: #1e293b; color: #94a3b8; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid #334155; }
  td { padding: 8px 10px; border-bottom: 1px solid #1e293b; vertical-align: top; }
  tr.row-body:hover td { background: #16213a; }
  tr.row-flag td { background: #422006; color: #fbbf24; padding: 6px 10px; font-size: 11px; border-bottom: none; }
  tr.row-flag td::before { content: '⚠ '; }
  .mpn { font-family: monospace; font-weight: 600; color: #f1f5f9; white-space: nowrap; }
  .price-expected { font-family: monospace; color: #4ade80; white-space: nowrap; }
  .qty { font-family: monospace; color: #94a3b8; text-align: center; }
  .function { color: #94a3b8; font-size: 11px; max-width: 220px; line-height: 1.4; }
  a { color: #60a5fa; text-decoration: none; font-size: 11px; }
  a:hover { text-decoration: underline; }
  .cell { display: flex; flex-direction: column; gap: 4px; min-width: 220px; padding: 6px; border-radius: 4px; border: 1px solid transparent; }
  .cell.status-active      { border-color: #16a34a; background: rgba(22,163,74,0.06); }
  .cell.status-nrnd        { border-color: #d97706; background: rgba(217,119,6,0.08); }
  .cell.status-obsolete    { border-color: #dc2626; background: rgba(220,38,38,0.10); }
  .cell.status-oos         { border-color: #f59e0b; background: rgba(245,158,11,0.06); }
  .cell.status-factory_hold{ border-color: #b91c1c; background: rgba(185,28,28,0.10); }
  .cell.status-not_found   { border-color: #475569; background: rgba(71,85,105,0.10); }
  .cell-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  .cell-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  input[type="checkbox"], input[type="radio"] { accent-color: #4ade80; margin: 0; cursor: pointer; }
  input[type="text"], input[type="url"], select, textarea {
    background: #0f172a; border: 1px solid #334155; color: #e2e8f0;
    padding: 4px 6px; border-radius: 3px; font-size: 11px; font-family: monospace;
    width: 100%; box-sizing: border-box;
  }
  input:focus, select:focus, textarea:focus { outline: none; border-color: #2563eb; }
  textarea { resize: vertical; min-height: 24px; font-family: -apple-system, sans-serif; }
  select { cursor: pointer; }
  .price-input { width: 90px; text-align: right; flex: 0 0 90px; }
  .price-label { font-size: 10px; color: #64748b; white-space: nowrap; }
  .pref-cell { text-align: center; vertical-align: middle; }
  .pref-cell label { display: block; font-size: 10px; color: #64748b; margin-top: 2px; }
  .note { font-size: 11px; color: #64748b; margin-top: 16px; line-height: 1.6; max-width: 880px; }
  .note ul { margin: 4px 0 0 0; padding-left: 20px; }
  .note code { color: #cbd5e1; }
  .warn { color: #fbbf24; }
  .dash { color: #475569; }
</style>
</head>
<body>
<h1>C1 Main Board — Price Verification</h1>
<p class="subtitle">
  Pick a target quantity, then verify each part on each distributor: lifecycle status, unit price at that qty, and any notes (tariffs, MOQ, factory holds). Pick a "preferred" distributor per row to mark which price you'd use for the canonical update. <strong>Part Status</strong> on a distributor's product page maps to the Status dropdown — that's the only product attribute worth recording per part.
</p>

<div class="toolbar">
  <div class="qty-control">
    <label for="targetQty">Target qty:</label>
    <input id="targetQty" type="number" min="1" step="1" value="1">
    <span class="dash">(updates the "@ qty" labels below)</span>
  </div>
  <button onclick="downloadHtml()">Download updated HTML</button>
  <button class="secondary" onclick="clearAll()">Clear all</button>
  <span class="saved-indicator" id="savedAt">Not saved</span>
</div>

<table id="verifyTable">
<thead>
<tr>
  <th>MPN</th>
  <th>Function</th>
  <th>Qty</th>
  <th>Exp.</th>
  <th>DigiKey</th>
  <th>Mouser</th>
  <th>Pref</th>
</tr>
</thead>
<tbody id="tbody"></tbody>
</table>

<div class="note">
  <strong>How it works:</strong> State auto-saves to browser localStorage under <code>c1-price-verification-v2</code>. Click <em>Download updated HTML</em> and overwrite this file to persist outside the browser. Re-running the generator script overwrites the seed but leaves your localStorage state alone.
  <br><br>
  <strong>Status legend:</strong>
  <span style="color:#4ade80">Active</span> ·
  <span style="color:#f59e0b">NRND</span> (not recommended for new designs) ·
  <span style="color:#dc2626">Obsolete</span> ·
  <span style="color:#fb923c">Out of stock</span> (temporary) ·
  <span style="color:#ef4444">Factory hold</span> (factory not accepting orders) ·
  <span style="color:#94a3b8">Not found</span>
  <br><br>
  <strong>Not in this file:</strong>
  <ul>
      ${skippedHtml}
  </ul>
</div>

<script type="application/json" id="rowData">
${seedJson}
</script>

<script>
const STORAGE_KEY = 'c1-price-verification-v2';
const QTY_KEY = 'c1-price-verification-v2-qty';
const DISTRIBUTORS = ['dk', 'mouser'];
const DIST_LABEL = { dk: 'DigiKey', mouser: 'Mouser' };
const STATUS_OPTIONS = [
  ['',             '— unchecked —'],
  ['active',       'Active'],
  ['nrnd',         'NRND'],
  ['obsolete',     'Obsolete'],
  ['oos',          'Out of stock'],
  ['factory_hold', 'Factory hold'],
  ['not_found',    'Not found'],
];

function loadData() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    try { return JSON.parse(saved); } catch (e) {}
  }
  return JSON.parse(document.getElementById('rowData').textContent);
}

function loadTargetQty() {
  const v = Number(localStorage.getItem(QTY_KEY));
  return Number.isFinite(v) && v >= 1 ? v : 1;
}

function saveData(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  const now = new Date();
  document.getElementById('savedAt').textContent = 'Saved locally at ' + now.toLocaleTimeString();
}

function saveTargetQty(q) {
  localStorage.setItem(QTY_KEY, String(q));
}

let rows = loadData();
let targetQty = loadTargetQty();

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}
function escapeAttr(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function render() {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  document.getElementById('targetQty').value = String(targetQty);
  rows.forEach((row, i) => {
    if (row.flag) {
      const flagTr = document.createElement('tr');
      flagTr.className = 'row-flag';
      flagTr.innerHTML = '<td colspan="7"><strong>' + escapeHtml(row.mpn) + ':</strong> ' + escapeHtml(row.flag) + '</td>';
      tbody.appendChild(flagTr);
    }
    const tr = document.createElement('tr');
    tr.className = 'row-body';
    tr.innerHTML =
      '<td class="mpn">' + escapeHtml(row.mpn) + '</td>' +
      '<td class="function">' + escapeHtml(row.fn) + '</td>' +
      '<td class="qty">' + row.qty + '</td>' +
      '<td class="price-expected">' + escapeHtml(row.expected) + '</td>' +
      DISTRIBUTORS.map(d => renderDistCell(row, i, d)).join('') +
      renderPrefCell(row, i);
    tbody.appendChild(tr);
  });
  attachHandlers();
}

function renderDistCell(row, rowIdx, distKey) {
  const d = row.distributors[distKey];
  const hasDefault = !!d.default;
  const hasCustom = !!d.url;
  const activeUrl = d.url || d.default;
  const status = d.status || '';
  const cellClass = status ? 'cell status-' + status : 'cell';
  const optsHtml = STATUS_OPTIONS
    .map(([v, label]) => '<option value="' + v + '"' + (v === status ? ' selected' : '') + '>' + escapeHtml(label) + '</option>')
    .join('');

  const linkRow = (hasDefault || hasCustom)
    ? '<div class="cell-row"><a class="cell-label" href="' + escapeAttr(activeUrl) + '" target="_blank">' + escapeHtml(d.label || '—') + '</a></div>'
    : '<div class="cell-row"><span class="dash">— not stocked —</span></div>';

  return '<td>' +
    '<div class="' + cellClass + '">' +
      linkRow +
      '<div class="cell-row">' +
        '<select data-row="' + rowIdx + '" data-dist="' + distKey + '" data-field="status">' + optsHtml + '</select>' +
      '</div>' +
      '<div class="cell-row">' +
        '<input type="text" class="price-input" data-row="' + rowIdx + '" data-dist="' + distKey + '" data-field="unitPrice" value="' + escapeAttr(d.unitPrice) + '" placeholder="$0.00">' +
        '<span class="price-label">@ qty <span class="qty-echo">' + targetQty + '</span></span>' +
      '</div>' +
      '<input type="url" data-row="' + rowIdx + '" data-dist="' + distKey + '" data-field="url" value="' + escapeAttr(d.url) + '" placeholder="paste actual URL (optional)">' +
      '<textarea data-row="' + rowIdx + '" data-dist="' + distKey + '" data-field="notes" rows="1" placeholder="notes (tariff %, MOQ, etc.)">' + escapeHtml(d.notes) + '</textarea>' +
    '</div>' +
  '</td>';
}

function renderPrefCell(row, rowIdx) {
  return '<td class="pref-cell">' +
    DISTRIBUTORS.map(d => {
      const checked = row.preferredDistributor === d ? ' checked' : '';
      return '<div>' +
        '<input type="radio" name="pref-' + rowIdx + '" data-row="' + rowIdx + '" data-field="preferredDistributor" value="' + d + '"' + checked + '>' +
        '<label>' + DIST_LABEL[d] + '</label>' +
      '</div>';
    }).join('') +
  '</td>';
}

function attachHandlers() {
  document.querySelectorAll('[data-row]').forEach(el => {
    el.addEventListener('change', onFieldChange);
    if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'url')) {
      el.addEventListener('input', onFieldChange);
    }
    if (el.tagName === 'TEXTAREA') {
      el.addEventListener('input', onFieldChange);
    }
  });
  document.getElementById('targetQty').addEventListener('input', onTargetQtyChange);
}

function onFieldChange(ev) {
  const el = ev.target;
  const rowIdx = Number(el.dataset.row);
  const field = el.dataset.field;
  const dist = el.dataset.dist;
  const row = rows[rowIdx];

  if (dist) {
    const slot = row.distributors[dist];
    if (field === 'status')        slot.status = el.value || null;
    else if (field === 'unitPrice') slot.unitPrice = el.value;
    else if (field === 'url')      { slot.url = el.value.trim(); render(); saveData(rows); return; }
    else if (field === 'notes')    slot.notes = el.value;
    if (field === 'status') render();
  } else if (field === 'preferredDistributor') {
    row.preferredDistributor = el.checked ? el.value : null;
  }
  saveData(rows);
}

function onTargetQtyChange(ev) {
  const v = Math.max(1, Math.floor(Number(ev.target.value) || 1));
  targetQty = v;
  saveTargetQty(targetQty);
  document.querySelectorAll('.qty-echo').forEach(n => { n.textContent = String(targetQty); });
}

function clearAll() {
  if (!confirm('Clear all statuses, prices, notes, URLs, and preferred-distributor selections?')) return;
  localStorage.removeItem(STORAGE_KEY);
  rows = loadData();
  render();
  document.getElementById('savedAt').textContent = 'Cleared.';
}

function downloadHtml() {
  const doc = document.documentElement.cloneNode(true);
  const seed = doc.querySelector('#rowData');
  seed.textContent = '\\n' + JSON.stringify(rows, null, 2) + '\\n';
  const html = '<!DOCTYPE html>\\n<html lang="en">\\n' + doc.innerHTML + '\\n</html>';
  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'c1-price-verification.html';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

render();
if (localStorage.getItem(STORAGE_KEY)) {
  document.getElementById('savedAt').textContent = 'Loaded from localStorage';
}
</script>
</body>
</html>
`;
}

const built = buildRows();
writeFileSync(OUTPUT, renderHtml(built), 'utf8');
console.log(`wrote ${built.rows.length} rows (${built.skipped.length} skipped) to ${OUTPUT}`);
