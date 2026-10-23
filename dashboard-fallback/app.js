/**
 * app.js — ZiwaVision dashboard application logic.
 *
 * Responsibilities:
 *  1. Fetch hotspot data from the API.
 *  2. Render the stats row and sortable/filterable table.
 *  3. Show the detail panel when a row is selected.
 *  4. Allow human verification via Verify / Flag as Uncertain buttons.
 *  5. Show toast notifications.
 *
 * API_BASE: set to the Flask local server by default.
 * For AWS deploy, change to the API Gateway URL before syncing to S3.
 *
 * Language rule: never say "hyacinth" — always "candidate floating vegetation".
 */

// ── Configuration ─────────────────────────────────────────────────────────────
const API_BASE = window.ZIWA_API_BASE || 'http://localhost:5050';

// ── State ──────────────────────────────────────────────────────────────────────
let allResults = [];
let selectedDate = null;
let sortKey = 'date';
let sortDir = -1;   // -1 = descending, 1 = ascending

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt(val, decimals = 2) {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'number') return val.toFixed(decimals);
  return val;
}

function fmtHa(val) {
  if (!val && val !== 0) return '—';
  return val.toFixed(2) + ' ha';
}

function fmtPct(val) {
  if (val === null || val === undefined) return '—';
  return (val * 100).toFixed(0) + '%';
}

const STATUS_LABELS = {
  needs_review: 'Needs Review',
  verified:     'Verified',
  uncertain:    'Uncertain',
  skipped:      'Skipped',
};

const ACTION_SHORT = {
  request_human_verification:  'Review →',
  process_another_observation: 'Retry',
  flag_uncertain:              'Uncertain',
};

function statusBadge(status) {
  const label = STATUS_LABELS[status] || status;
  return `<span class="badge badge-${status}" title="${status}">${label}</span>`;
}

function scoreBar(val) {
  const pct = Math.round((val || 0) * 100);
  return `<div class="td-bar-wrap">
    <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
    <span class="bar-val">${pct}%</span>
  </div>`;
}

// ── Toast ─────────────────────────────────────────────────────────────────────

function showToast(message, type = 'info') {
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-icon">${icon}</span><span>${message}</span>`;
  const container = document.getElementById('toast-container');
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── API ───────────────────────────────────────────────────────────────────────

async function fetchHotspots() {
  const res = await fetch(`${API_BASE}/api/hotspots`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function postVerify(date, verified, patchId = null) {
  const res = await fetch(`${API_BASE}/api/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, verified, patch_id: patchId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function overlayUrl(date) {
  return `${API_BASE}/api/overlay/${date}`;
}

// ── API status indicator ──────────────────────────────────────────────────────

function setApiStatus(ok) {
  const dot = document.getElementById('api-dot');
  const txt = document.getElementById('api-status-text');
  if (ok) {
    dot.style.background = '#00e5a0';
    dot.style.boxShadow = '0 0 6px #00e5a0';
    txt.textContent = 'API connected';
  } else {
    dot.style.background = '#ff6b6b';
    dot.style.boxShadow = '0 0 6px #ff6b6b';
    txt.textContent = 'API offline';
  }
}

// ── Stats row ─────────────────────────────────────────────────────────────────

function renderStats(results) {
  const total       = results.length;
  const patches     = results.reduce((s, r) => s + (r.n_patches || 0), 0);
  const area        = results.reduce((s, r) => s + (r.total_area_ha || 0), 0);
  const needsReview = results.filter(r => r.verification_status === 'needs_review').length;

  document.getElementById('stat-scenes').textContent  = total;
  document.getElementById('stat-patches').textContent = patches;
  document.getElementById('stat-area').textContent    = area.toFixed(1);
  document.getElementById('stat-review').textContent  = needsReview;
}

// ── Table ─────────────────────────────────────────────────────────────────────

const COLUMNS = [
  { key: 'date',                  label: 'Date',       class: 'td-date' },
  { key: 'location',              label: 'Location',   class: 'td-location' },
  { key: 'n_patches',             label: 'Patches',    class: 'td-patches' },
  { key: 'total_area_ha',         label: 'Area (ha)',  class: 'td-area' },
  { key: 'image_quality',         label: 'Quality',    bar: true },
  { key: 'mean_patch_confidence', label: 'Confidence', bar: true },
  { key: 'action',                label: 'Decision',   class: 'td-action' },
  { key: 'verification_status',   label: 'Status',     badge: true },
];

function buildTable(results) {
  if (!results.length) {
    return `<div class="no-results">No results match your filter.</div>`;
  }

  const headerCells = COLUMNS.map(col => {
    const isSorted = sortKey === col.key;
    const icon = isSorted ? (sortDir === 1 ? '↑' : '↓') : '↕';
    return `<th class="${isSorted ? 'sorted' : ''}"
                data-key="${col.key}"
                role="columnheader"
                aria-sort="${isSorted ? (sortDir === 1 ? 'ascending' : 'descending') : 'none'}"
                tabindex="0"
                title="Sort by ${col.label}">
              ${col.label}<span class="sort-icon">${icon}</span>
            </th>`;
  }).join('');

  const rows = results.map((r, i) => {
    const isSelected = r.date === selectedDate;
    const cells = COLUMNS.map(col => {
      if (col.badge) {
        return `<td>${statusBadge(r[col.key])}</td>`;
      }
      if (col.bar) {
        return `<td>${scoreBar(r[col.key])}</td>`;
      }
      if (col.key === 'action') {
        const short = ACTION_SHORT[r[col.key]] || r[col.key];
        return `<td><span class="action-badge">${short}</span></td>`;
      }
      if (col.key === 'total_area_ha') {
        return `<td class="${col.class || ''}">${fmtHa(r[col.key])}</td>`;
      }
      return `<td class="${col.class || ''}">${r[col.key] !== undefined ? r[col.key] : '—'}</td>`;
    }).join('');

    return `<tr class="${isSelected ? 'selected' : ''}"
               data-date="${r.date}"
               data-index="${i}"
               tabindex="0"
               role="row"
               aria-selected="${isSelected}"
               style="animation-delay:${i * 0.03}s">
              ${cells}
            </tr>`;
  }).join('');

  return `<table role="grid" aria-label="Hotspot observation log">
    <thead><tr role="row">${headerCells}</tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function renderTable(filtered) {
  const container = document.getElementById('table-container');
  container.innerHTML = buildTable(filtered);
  document.getElementById('row-count').textContent =
    `${filtered.length} scene${filtered.length !== 1 ? 's' : ''}`;

  // Row click
  container.querySelectorAll('tbody tr').forEach(tr => {
    tr.addEventListener('click', () => selectRow(tr.dataset.date));
    tr.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') selectRow(tr.dataset.date);
    });
  });

  // Column sort
  container.querySelectorAll('thead th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (sortKey === key) { sortDir *= -1; } else { sortKey = key; sortDir = -1; }
      applyFilterAndSort();
    });
    th.addEventListener('keydown', e => {
      if (e.key === 'Enter') th.click();
    });
  });
}

function sortedResults(results) {
  return [...results].sort((a, b) => {
    let va = a[sortKey], vb = b[sortKey];
    if (typeof va === 'string') return sortDir * va.localeCompare(vb);
    return sortDir * ((va || 0) - (vb || 0));
  });
}

function applyFilterAndSort() {
  const q = document.getElementById('filter-input').value.toLowerCase();
  let filtered = allResults;
  if (q) {
    filtered = allResults.filter(r =>
      (r.date || '').includes(q) ||
      (r.verification_status || '').includes(q) ||
      (r.action || '').includes(q) ||
      (r.location || '').toLowerCase().includes(q)
    );
  }
  renderTable(sortedResults(filtered));
}

// ── Detail panel ──────────────────────────────────────────────────────────────

function selectRow(date) {
  selectedDate = date;
  applyFilterAndSort();   // re-render table to highlight selected row
  const entry = allResults.find(r => r.date === date);
  if (entry) renderDetail(entry);
}

function renderDetail(entry) {
  const panel = document.getElementById('detail-panel');
  panel.classList.remove('empty');

  const imgUrl = overlayUrl(entry.date);

  // Patch cards HTML
  const patches = entry.patch_details || [];
  const patchCards = patches.map(p => `
    <div class="patch-card" id="patch-${entry.date}-${p.patch_id}">
      <div class="patch-row">
        <span class="patch-label">Patch #${p.patch_id}</span>
        <span class="patch-val">${fmtHa(p.area_ha)}</span>
      </div>
      <div class="patch-row">
        <span class="patch-label">NDVI</span>
        <span class="patch-val">${fmt(p.mean_ndvi, 3)}</span>
      </div>
      <div class="patch-row">
        <span class="patch-label">Confidence</span>
        <span class="patch-val">${fmt(p.confidence, 2)}</span>
      </div>
      ${p.centroid_latlon ? `
      <div class="patch-row">
        <span class="patch-label">Centroid</span>
        <span class="patch-val">${p.centroid_latlon[0].toFixed(4)}, ${p.centroid_latlon[1].toFixed(4)}</span>
      </div>` : ''}
      ${'reference_iou' in p ? `
      <div class="patch-row">
        <span class="patch-label">Ref. IoU</span>
        <span class="patch-val">${fmt(p.reference_iou, 3)}</span>
      </div>` : ''}
    </div>`).join('');

  const isVerifiable = entry.verification_status === 'needs_review' ||
                       entry.verification_status === 'uncertain';
  const isVerified   = entry.verification_status === 'verified';

  panel.innerHTML = `
    <div class="detail-header">
      <div class="detail-date">${entry.date}</div>
      ${statusBadge(entry.verification_status)}
      <div class="spacer"></div>
      <button class="close-btn" id="close-detail" aria-label="Close detail panel">✕</button>
    </div>

    <div class="detail-overlay">
      <img src="${imgUrl}"
           alt="Satellite overlay for ${entry.date} — candidate floating vegetation highlighted in yellow"
           id="overlay-img-${entry.date}"
           onerror="this.parentElement.innerHTML='<div style=&quot;display:flex;align-items:center;justify-content:center;height:100%;color:#6b7a99;font-size:0.8rem;padding:20px;text-align:center&quot;>Overlay image not available. Run the pipeline first.</div>'" />
      <div class="overlay-label">Sentinel-2 · Dunga Beach, Winam Gulf</div>
    </div>

    <div class="detail-metrics">
      <div class="metric-chip">
        <div class="m-label">Image Quality</div>
        <div class="m-value" style="color: ${scoreColor(entry.image_quality)}">${fmtPct(entry.image_quality)}</div>
      </div>
      <div class="metric-chip">
        <div class="m-label">Confidence</div>
        <div class="m-value" style="color: ${scoreColor(entry.mean_patch_confidence)}">${fmtPct(entry.mean_patch_confidence)}</div>
      </div>
      <div class="metric-chip">
        <div class="m-label">Patches</div>
        <div class="m-value">${entry.n_patches || 0}</div>
      </div>
      <div class="metric-chip">
        <div class="m-label">Total Area</div>
        <div class="m-value">${fmtHa(entry.total_area_ha)}</div>
      </div>
      <div class="metric-chip">
        <div class="m-label">Scene IoU</div>
        <div class="m-value">${fmt(entry.scene_iou, 3)}</div>
      </div>
      <div class="metric-chip">
        <div class="m-label">Lake Area</div>
        <div class="m-value">${fmtHa(entry.lake_area_ha)}</div>
      </div>
    </div>

    ${patches.length > 0 ? `
    <div class="detail-patches">
      <h3>Candidate Patches (${patches.length})</h3>
      ${patchCards}
    </div>` : ''}

    <div class="detail-reason">
      <strong>Agent decision:</strong>
      <span style="color:#00e5a0;margin:0 6px">${ACTION_SHORT[entry.action] || entry.action}</span>
      — ${entry.agent_reason || 'No reason recorded.'}
    </div>

    <div class="detail-actions">
      <button class="btn-verify"
              id="btn-verify-${entry.date}"
              ${isVerified ? 'disabled' : ''}
              aria-label="Mark detections as verified for ${entry.date}">
        ${isVerified ? '✓ Verified' : '✓ Mark Verified'}
      </button>
      <button class="btn-uncertain"
              id="btn-uncertain-${entry.date}"
              ${entry.verification_status === 'uncertain' ? 'disabled' : ''}
              aria-label="Flag as uncertain for ${entry.date}">
        ⚑ Flag Uncertain
      </button>
    </div>
  `;

  document.getElementById('close-detail').addEventListener('click', closeDetail);

  document.getElementById(`btn-verify-${entry.date}`)
    .addEventListener('click', () => handleVerify(entry.date, true));
  document.getElementById(`btn-uncertain-${entry.date}`)
    .addEventListener('click', () => handleVerify(entry.date, false));
}

function scoreColor(val) {
  if (!val && val !== 0) return '#6b7a99';
  if (val >= 0.7) return '#00e5a0';
  if (val >= 0.4) return '#fbbf24';
  return '#ff6b6b';
}

function closeDetail() {
  selectedDate = null;
  const panel = document.getElementById('detail-panel');
  panel.classList.add('empty');
  panel.innerHTML = `
    <div class="empty-icon" aria-hidden="true">🛰️</div>
    <p>Select a scene to view details and verify detections</p>
  `;
  applyFilterAndSort();
}

// ── Verification ──────────────────────────────────────────────────────────────

async function handleVerify(date, verified) {
  const btnVerify    = document.getElementById(`btn-verify-${date}`);
  const btnUncertain = document.getElementById(`btn-uncertain-${date}`);
  if (btnVerify)    btnVerify.disabled    = true;
  if (btnUncertain) btnUncertain.disabled = true;

  try {
    const result = await postVerify(date, verified);
    // Update local state
    const idx = allResults.findIndex(r => r.date === date);
    if (idx !== -1 && result.updated) {
      allResults[idx] = result.updated;
    }
    renderStats(allResults);
    applyFilterAndSort();
    // Re-render detail with updated data
    const updated = allResults.find(r => r.date === date);
    if (updated) renderDetail(updated);

    showToast(
      verified
        ? `Scene ${date} marked as verified.`
        : `Scene ${date} flagged as uncertain.`,
      'success'
    );
  } catch (err) {
    showToast(`Verification failed: ${err.message}`, 'error');
    if (btnVerify)    btnVerify.disabled    = false;
    if (btnUncertain) btnUncertain.disabled = false;
  }
}

// ── Filter input ──────────────────────────────────────────────────────────────

document.getElementById('filter-input').addEventListener('input', applyFilterAndSort);

// ── Bootstrap ─────────────────────────────────────────────────────────────────

async function init() {
  try {
    allResults = await fetchHotspots();
    setApiStatus(true);
    renderStats(allResults);
    applyFilterAndSort();

    // Auto-select the first needs_review entry for demo purposes
    const first = allResults.find(r => r.verification_status === 'needs_review');
    if (first) selectRow(first.date);

  } catch (err) {
    setApiStatus(false);
    document.getElementById('table-container').innerHTML = `
      <div class="loading-state">
        <p style="color:#ff6b6b">⚠ Could not connect to API at <code>${API_BASE}</code></p>
        <p style="font-size:0.78rem;color:#6b7a99;margin-top:8px">
          Run <code>python src/run_pipeline.py</code> then <code>python src/api.py</code>
        </p>
      </div>`;
    // Still render demo stats from empty data
    renderStats([]);
  }
}

init();
