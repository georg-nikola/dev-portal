/**
 * Dev Portal — app.js  v1.0.0
 * Vanilla JS — no frameworks, no build step.
 */

const API_BASE = '/api';
const REFRESH_INTERVAL_MS = 30_000;

// ============================================================
// State
// ============================================================
let allServices = [];
let activeFilters = { status: '', team: '', tag: '', q: '' };
let refreshTimer = null;
let confirmCallback = null;

// ============================================================
// API helpers
// ============================================================
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const body = await res.json(); msg = body.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function fetchServices() {
  const params = new URLSearchParams();
  if (activeFilters.q)      params.set('q', activeFilters.q);
  if (activeFilters.team)   params.set('team', activeFilters.team);
  if (activeFilters.status) params.set('status', activeFilters.status);
  if (activeFilters.tag)    params.set('tag', activeFilters.tag);
  const data = await apiFetch(`/services?${params}`);
  return data.items;
}

// ============================================================
// Render
// ============================================================
function formatTime(isoString) {
  if (!isoString) return null;
  const d = new Date(isoString);
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  return d.toLocaleDateString();
}

function statusDotHtml(status) {
  return `<span class="dot dot-${status}"></span>`;
}

function buildServiceCard(svc) {
  const card = document.createElement('div');
  card.className = 'service-card';
  card.dataset.id = svc.id;

  const tags = (svc.tags || [])
    .map(t => `<button class="tag-chip" data-tag="${escHtml(t)}">${escHtml(t)}</button>`)
    .join('');

  const links = [];
  if (svc.docs_url)       links.push(linkBtn(svc.docs_url, '📄', 'Docs'));
  if (svc.github_url)     links.push(linkBtn(svc.github_url, githubIcon(), 'GitHub'));
  if (svc.dashboard_url)  links.push(linkBtn(svc.dashboard_url, '📊', 'Dashboard'));

  const checkedAt = svc.last_checked_at ? `Checked ${formatTime(svc.last_checked_at)}` : '';
  const checkBtn = svc.status_url
    ? `<button class="card-check-btn" data-id="${svc.id}" title="Ping health check URL now">Check now</button>`
    : '';

  card.innerHTML = `
    <div class="card-header">
      <div>
        <div class="card-name">${escHtml(svc.name)}</div>
        ${svc.team ? `<div class="card-team">${escHtml(svc.team)}</div>` : ''}
      </div>
      <span class="status-badge ${svc.status}">${statusDotHtml(svc.status)} ${svc.status}</span>
    </div>
    ${svc.description ? `<p class="card-description">${escHtml(svc.description)}</p>` : ''}
    ${tags ? `<div class="card-tags">${tags}</div>` : ''}
    ${links.length ? `<div class="card-links">${links.join('')}</div>` : ''}
    <div class="card-footer">
      <span class="card-checked-at">${checkedAt}</span>
      ${checkBtn}
    </div>
  `;

  // Open edit modal when clicking the card body (not links/tags/check button)
  card.addEventListener('click', e => {
    if (e.target.closest('a') || e.target.closest('.tag-chip') || e.target.closest('.card-check-btn')) return;
    openEditModal(svc);
  });

  // Tag chip filter
  card.querySelectorAll('.tag-chip').forEach(btn => {
    btn.addEventListener('click', () => setTagFilter(btn.dataset.tag));
  });

  // Manual check button
  const checkBtnEl = card.querySelector('.card-check-btn');
  if (checkBtnEl) {
    checkBtnEl.addEventListener('click', () => triggerCheck(svc.id, card));
  }

  return card;
}

function linkBtn(url, icon, label) {
  return `<a class="card-link-btn" href="${escAttr(url)}" target="_blank" rel="noopener noreferrer" title="${escAttr(label)}" onclick="event.stopPropagation()">${icon} ${label}</a>`;
}

function githubIcon() {
  return `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.2 11.37.6.1.82-.26.82-.58v-2.03c-3.34.73-4.04-1.6-4.04-1.6-.55-1.4-1.34-1.77-1.34-1.77-1.1-.74.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.8 1.3 3.49 1 .1-.78.42-1.3.76-1.6-2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.17 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 3-.4c1.02 0 2.04.14 3 .4 2.29-1.55 3.3-1.23 3.3-1.23.66 1.65.25 2.87.12 3.17.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.57C20.57 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z"/></svg>`;
}

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str) {
  return escHtml(str);
}

function renderCards(services) {
  const grid = document.getElementById('cardsGrid');
  const empty = document.getElementById('emptyState');
  const emptyMsg = document.getElementById('emptyStateMsg');
  const viewMeta = document.getElementById('viewMeta');

  grid.innerHTML = '';

  if (services.length === 0) {
    grid.classList.add('hidden');
    empty.classList.remove('hidden');
    const hasFilters = Object.values(activeFilters).some(v => v);
    emptyMsg.textContent = hasFilters
      ? 'No services match your current filters.'
      : 'No services registered yet.';
    document.getElementById('emptyAddBtn').classList.toggle('hidden', hasFilters);
    viewMeta.textContent = '0 services';
    return;
  }

  grid.classList.remove('hidden');
  empty.classList.add('hidden');
  services.forEach(svc => grid.appendChild(buildServiceCard(svc)));

  const total = services.length;
  viewMeta.textContent = `${total} service${total !== 1 ? 's' : ''}`;
}

function updateSidebarStats(services) {
  const all = allServices; // always count from full dataset
  document.getElementById('statTotal').textContent    = all.length;
  document.getElementById('statHealthy').textContent  = all.filter(s => s.status === 'healthy').length;
  document.getElementById('statDegraded').textContent = all.filter(s => s.status === 'degraded').length;
  document.getElementById('statDown').textContent     = all.filter(s => s.status === 'down').length;
}

function updateTeamFilters(services) {
  const container = document.getElementById('teamFilters');
  const teams = [...new Set(services.map(s => s.team).filter(Boolean))].sort();

  // Remove all except "All Teams"
  container.querySelectorAll('[data-value]:not([data-value=""])').forEach(el => el.remove());

  teams.forEach(team => {
    const btn = document.createElement('button');
    btn.className = 'filter-chip' + (activeFilters.team === team ? ' active' : '');
    btn.dataset.filterType = 'team';
    btn.dataset.value = team;
    btn.textContent = team;
    btn.addEventListener('click', () => setFilter('team', team));
    container.appendChild(btn);
  });
}

function updateTagFilters(services) {
  const container = document.getElementById('tagFilters');
  container.innerHTML = '';
  const tags = [...new Set(services.flatMap(s => s.tags || []))].sort();

  tags.forEach(tag => {
    const btn = document.createElement('button');
    btn.className = 'filter-chip' + (activeFilters.tag === tag ? ' active' : '');
    btn.dataset.tag = tag;
    btn.textContent = tag;
    btn.addEventListener('click', () => setTagFilter(tag));
    container.appendChild(btn);
  });
}

// ============================================================
// Filtering
// ============================================================
function applyLocalFilters() {
  let filtered = allServices;

  if (activeFilters.q) {
    const q = activeFilters.q.toLowerCase();
    filtered = filtered.filter(s =>
      (s.name || '').toLowerCase().includes(q) ||
      (s.description || '').toLowerCase().includes(q) ||
      (s.team || '').toLowerCase().includes(q)
    );
  }
  if (activeFilters.status) {
    filtered = filtered.filter(s => s.status === activeFilters.status);
  }
  if (activeFilters.team) {
    filtered = filtered.filter(s => s.team === activeFilters.team);
  }
  if (activeFilters.tag) {
    filtered = filtered.filter(s => (s.tags || []).includes(activeFilters.tag));
  }

  renderCards(filtered);
}

function setFilter(type, value) {
  // Toggle off if already active
  if (activeFilters[type] === value) {
    activeFilters[type] = '';
  } else {
    activeFilters[type] = value;
  }
  syncFilterChipStates();
  applyLocalFilters();
}

function setTagFilter(tag) {
  setFilter('tag', tag);
}

function syncFilterChipStates() {
  document.querySelectorAll('.filter-chip[data-filter-type]').forEach(btn => {
    const type = btn.dataset.filterType;
    const value = btn.dataset.value;
    btn.classList.toggle('active', activeFilters[type] === value);
  });
  document.querySelectorAll('#tagFilters .filter-chip[data-tag]').forEach(btn => {
    btn.classList.toggle('active', activeFilters.tag === btn.dataset.tag);
  });
}

// ============================================================
// Data loading
// ============================================================
async function loadAllServices(quiet = false) {
  if (!quiet) setRefreshing(true);
  try {
    // Always fetch all (filtering done client-side for snappy UX)
    const params = new URLSearchParams();
    const data = await apiFetch('/services');
    allServices = data.items;
    updateTeamFilters(allServices);
    updateTagFilters(allServices);
    updateSidebarStats(allServices);
    applyLocalFilters();
  } catch (err) {
    if (!quiet) showToast(`Failed to load services: ${err.message}`, 'error');
  } finally {
    if (!quiet) setRefreshing(false);
  }
}

function setRefreshing(on) {
  document.getElementById('refreshIndicator').classList.toggle('refreshing', on);
}

function startAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(() => loadAllServices(true), REFRESH_INTERVAL_MS);
}

// ============================================================
// Manual status check
// ============================================================
async function triggerCheck(serviceId, cardEl) {
  const btn = cardEl.querySelector('.card-check-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Checking…';
  }
  try {
    const updated = await apiFetch(`/services/${serviceId}/check`, { method: 'POST' });
    // Update in allServices
    const idx = allServices.findIndex(s => s.id === serviceId);
    if (idx !== -1) allServices[idx] = updated;
    applyLocalFilters();
    showToast(`Status updated: ${updated.status}`, updated.status === 'healthy' ? 'success' : 'info');
  } catch (err) {
    showToast(`Check failed: ${err.message}`, 'error');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Check now';
    }
  }
}

// ============================================================
// Modal: Add / Edit
// ============================================================
function openAddModal() {
  document.getElementById('modalTitle').textContent = 'Add Service';
  document.getElementById('serviceForm').reset();
  document.getElementById('formServiceId').value = '';
  document.getElementById('deleteServiceBtn').classList.add('hidden');
  document.getElementById('serviceModal').classList.remove('hidden');
  document.getElementById('formName').focus();
}

function openEditModal(svc) {
  document.getElementById('modalTitle').textContent = 'Edit Service';
  document.getElementById('formServiceId').value = svc.id;
  document.getElementById('formName').value = svc.name || '';
  document.getElementById('formTeam').value = svc.team || '';
  document.getElementById('formDescription').value = svc.description || '';
  document.getElementById('formStatus').value = svc.status || 'unknown';
  document.getElementById('formTags').value = (svc.tags || []).join(', ');
  document.getElementById('formStatusUrl').value = svc.status_url || '';
  document.getElementById('formDocsUrl').value = svc.docs_url || '';
  document.getElementById('formGithubUrl').value = svc.github_url || '';
  document.getElementById('formDashboardUrl').value = svc.dashboard_url || '';
  document.getElementById('deleteServiceBtn').classList.remove('hidden');
  document.getElementById('serviceModal').classList.remove('hidden');
  document.getElementById('formName').focus();
}

function closeServiceModal() {
  document.getElementById('serviceModal').classList.add('hidden');
}

async function saveService() {
  const id = document.getElementById('formServiceId').value;
  const name = document.getElementById('formName').value.trim();
  if (!name) {
    showToast('Service name is required.', 'error');
    document.getElementById('formName').focus();
    return;
  }

  const tagsRaw = document.getElementById('formTags').value;
  const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];

  const payload = {
    name,
    team:          document.getElementById('formTeam').value.trim() || null,
    description:   document.getElementById('formDescription').value.trim() || null,
    status:        document.getElementById('formStatus').value,
    tags,
    status_url:    document.getElementById('formStatusUrl').value.trim() || null,
    docs_url:      document.getElementById('formDocsUrl').value.trim() || null,
    github_url:    document.getElementById('formGithubUrl').value.trim() || null,
    dashboard_url: document.getElementById('formDashboardUrl').value.trim() || null,
  };

  const btn = document.getElementById('saveServiceBtn');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    if (id) {
      await apiFetch(`/services/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Service updated.', 'success');
    } else {
      await apiFetch('/services', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Service added.', 'success');
    }
    closeServiceModal();
    await loadAllServices(true);
  } catch (err) {
    showToast(`Save failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save';
  }
}

function promptDelete(id, name) {
  document.getElementById('confirmMsg').textContent = `Delete "${name}"? This cannot be undone.`;
  confirmCallback = async () => {
    try {
      await apiFetch(`/services/${id}`, { method: 'DELETE' });
      showToast('Service deleted.', 'success');
      closeServiceModal();
      await loadAllServices(true);
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'error');
    }
  };
  document.getElementById('confirmModal').classList.remove('hidden');
}

// ============================================================
// Toast
// ============================================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span>${icon}</span><span>${escHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 350);
  }, 3500);
}

// ============================================================
// Event wiring
// ============================================================
function wireEvents() {
  // Add service button (header)
  document.getElementById('addServiceBtn').addEventListener('click', openAddModal);
  document.getElementById('emptyAddBtn').addEventListener('click', openAddModal);

  // Modal close
  document.getElementById('modalClose').addEventListener('click', closeServiceModal);
  document.getElementById('modalCancel').addEventListener('click', closeServiceModal);
  document.getElementById('serviceModal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeServiceModal();
  });

  // Save form
  document.getElementById('serviceForm').addEventListener('submit', e => {
    e.preventDefault();
    saveService();
  });
  document.getElementById('saveServiceBtn').addEventListener('click', saveService);

  // Delete button
  document.getElementById('deleteServiceBtn').addEventListener('click', () => {
    const id = document.getElementById('formServiceId').value;
    const name = document.getElementById('formName').value;
    promptDelete(id, name);
  });

  // Confirm modal
  document.getElementById('confirmClose').addEventListener('click', () => {
    document.getElementById('confirmModal').classList.add('hidden');
  });
  document.getElementById('confirmCancel').addEventListener('click', () => {
    document.getElementById('confirmModal').classList.add('hidden');
  });
  document.getElementById('confirmOk').addEventListener('click', async () => {
    document.getElementById('confirmModal').classList.add('hidden');
    if (confirmCallback) {
      await confirmCallback();
      confirmCallback = null;
    }
  });
  document.getElementById('confirmModal').addEventListener('click', e => {
    if (e.target === e.currentTarget) document.getElementById('confirmModal').classList.add('hidden');
  });

  // Search
  const searchInput = document.getElementById('searchInput');
  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      activeFilters.q = searchInput.value.trim();
      applyLocalFilters();
    }, 200);
  });

  // Status filter chips
  document.querySelectorAll('#statusFilters .filter-chip').forEach(btn => {
    btn.addEventListener('click', () => setFilter('status', btn.dataset.value));
  });

  // Keyboard
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (!document.getElementById('confirmModal').classList.contains('hidden')) {
        document.getElementById('confirmModal').classList.add('hidden');
      } else if (!document.getElementById('serviceModal').classList.contains('hidden')) {
        closeServiceModal();
      }
    }
  });
}

// ============================================================
// Init
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  wireEvents();
  await loadAllServices(false);
  startAutoRefresh();
});
