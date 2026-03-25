/**
 * Dev Portal — clusters.js  v1.2.0
 * Cluster configuration management.
 */

var allClusters = [];

async function clusterApiFetch(path, options) {
  options = options || {};
  var headers = Object.assign({ 'Content-Type': 'application/json' }, authHeaders());
  var res = await fetch('/api' + path, Object.assign({ headers: headers }, options));
  if (res.status === 401 || res.status === 403) {
    clearAuth();
    window.location.href = '/login';
    return;
  }
  if (!res.ok) {
    var msg = 'HTTP ' + res.status;
    try { var body = await res.json(); msg = body.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ============================================================
// Render
// ============================================================
function renderClusters(clusters) {
  var grid = document.getElementById('clustersGrid');
  var empty = document.getElementById('emptyState');
  var viewMeta = document.getElementById('viewMeta');

  grid.innerHTML = '';

  if (clusters.length === 0) {
    grid.classList.add('hidden');
    empty.classList.remove('hidden');
    viewMeta.textContent = '0 clusters';
    return;
  }

  grid.classList.remove('hidden');
  empty.classList.add('hidden');
  viewMeta.textContent = clusters.length + ' cluster' + (clusters.length !== 1 ? 's' : '');

  clusters.forEach(function (c) {
    grid.appendChild(buildClusterCard(c));
  });
}

function buildClusterCard(c) {
  var card = document.createElement('div');
  card.className = 'service-card';
  card.dataset.id = c.id;

  var authMethod = c.is_in_cluster ? 'In-Cluster SA' : c.has_token ? 'Token' : c.has_kubeconfig ? 'Kubeconfig' : 'None';
  var lastDisc = c.last_discovered_at ? formatTime(c.last_discovered_at) : 'Never';

  card.innerHTML =
    '<div class="card-header">' +
      '<div>' +
        '<div class="card-name">' + escHtml(c.name) + '</div>' +
        '<div class="card-team">' + escHtml(c.api_server_url || 'In-Cluster') + '</div>' +
      '</div>' +
      '<span class="status-badge ' + (c.is_in_cluster ? 'healthy' : 'unknown') + '">' +
        '<span class="dot dot-' + (c.is_in_cluster ? 'healthy' : 'unknown') + '"></span> ' + authMethod +
      '</span>' +
    '</div>' +
    '<div class="card-tags">' +
      (c.namespace_filter ? '<span class="tag-chip">ns: ' + escHtml(c.namespace_filter) + '</span>' : '<span class="tag-chip">all namespaces</span>') +
      (c.auto_discover ? '<span class="tag-chip">auto-discover</span>' : '') +
    '</div>' +
    '<div class="card-footer">' +
      '<span class="card-checked-at">Discovered ' + lastDisc + '</span>' +
      '<button class="card-check-btn cluster-discover-btn" data-id="' + c.id + '">Discover Now</button>' +
    '</div>';

  card.addEventListener('click', function (e) {
    if (e.target.closest('.cluster-discover-btn')) return;
    openEditClusterModal(c);
  });

  var discBtn = card.querySelector('.cluster-discover-btn');
  discBtn.addEventListener('click', function () { triggerDiscover(c.id, card); });

  return card;
}

function formatTime(isoString) {
  if (!isoString) return null;
  var d = new Date(isoString);
  var now = new Date();
  var diffMs = now - d;
  var diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return diffMins + 'm ago';
  var diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return diffHrs + 'h ago';
  return d.toLocaleDateString();
}

// ============================================================
// Load
// ============================================================
async function loadClusters() {
  try {
    var data = await clusterApiFetch('/clusters');
    allClusters = data.items;
    renderClusters(allClusters);
  } catch (err) {
    showToast('Failed to load clusters: ' + err.message, 'error');
  }
}

// ============================================================
// Discovery
// ============================================================
async function triggerDiscover(clusterId, cardEl) {
  var btn = cardEl.querySelector('.cluster-discover-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Discovering\u2026'; }
  try {
    var result = await clusterApiFetch('/clusters/' + clusterId + '/discover', { method: 'POST' });
    showToast(
      'Discovered ' + result.total_workloads + ' workloads: ' +
      result.created + ' created, ' + result.updated + ' updated',
      'success'
    );
    await loadClusters();
  } catch (err) {
    showToast('Discovery failed: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Discover Now'; }
  }
}

// ============================================================
// Modal
// ============================================================
function openAddClusterModal() {
  document.getElementById('modalTitle').textContent = 'Add Cluster';
  document.getElementById('clusterForm').reset();
  document.getElementById('formClusterId').value = '';
  document.getElementById('deleteClusterBtn').classList.add('hidden');
  document.getElementById('clusterModal').classList.remove('hidden');
  toggleInCluster();
  document.getElementById('formClusterName').focus();
}

function openEditClusterModal(c) {
  document.getElementById('modalTitle').textContent = 'Edit Cluster';
  document.getElementById('formClusterId').value = c.id;
  document.getElementById('formClusterName').value = c.name || '';
  document.getElementById('formApiServer').value = c.api_server_url || '';
  document.getElementById('formNamespaceFilter').value = c.namespace_filter || '';
  document.getElementById('formIsInCluster').checked = c.is_in_cluster;
  document.getElementById('formAutoDiscover').checked = c.auto_discover;
  document.getElementById('formToken').value = '';
  document.getElementById('formKubeconfig').value = '';
  document.getElementById('deleteClusterBtn').classList.remove('hidden');
  document.getElementById('clusterModal').classList.remove('hidden');
  toggleInCluster();
  document.getElementById('formClusterName').focus();
}

function closeClusterModal() {
  document.getElementById('clusterModal').classList.add('hidden');
}

function toggleInCluster() {
  var isIn = document.getElementById('formIsInCluster').checked;
  var extFields = document.getElementById('externalFields');
  extFields.style.display = isIn ? 'none' : '';
}

async function saveCluster() {
  var id = document.getElementById('formClusterId').value;
  var name = document.getElementById('formClusterName').value.trim();
  if (!name) { showToast('Cluster name is required.', 'error'); return; }

  var payload = { name: name };
  var isInCluster = document.getElementById('formIsInCluster').checked;
  payload.is_in_cluster = isInCluster;
  payload.auto_discover = document.getElementById('formAutoDiscover').checked;
  payload.namespace_filter = document.getElementById('formNamespaceFilter').value.trim() || null;

  if (!isInCluster) {
    payload.api_server_url = document.getElementById('formApiServer').value.trim() || null;
    var token = document.getElementById('formToken').value.trim();
    var kubeconfig = document.getElementById('formKubeconfig').value.trim();
    if (token) payload.token = token;
    if (kubeconfig) payload.kubeconfig = kubeconfig;
  }

  var btn = document.getElementById('saveClusterBtn');
  btn.disabled = true; btn.textContent = 'Saving\u2026';

  try {
    if (id) {
      await clusterApiFetch('/clusters/' + id, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Cluster updated.', 'success');
    } else {
      await clusterApiFetch('/clusters', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Cluster added.', 'success');
    }
    closeClusterModal();
    await loadClusters();
  } catch (err) {
    showToast('Save failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false; btn.textContent = 'Save';
  }
}

async function deleteCluster() {
  var id = document.getElementById('formClusterId').value;
  var name = document.getElementById('formClusterName').value;
  if (!confirm('Delete cluster "' + name + '"? Discovered services will become manual entries.')) return;
  try {
    await clusterApiFetch('/clusters/' + id, { method: 'DELETE' });
    showToast('Cluster deleted.', 'success');
    closeClusterModal();
    await loadClusters();
  } catch (err) {
    showToast('Delete failed: ' + err.message, 'error');
  }
}

// ============================================================
// Toast (shared pattern)
// ============================================================
function showToast(message, type) {
  type = type || 'info';
  var container = document.getElementById('toastContainer');
  var toast = document.createElement('div');
  toast.className = 'toast ' + type;
  var icon = type === 'success' ? '\u2713' : type === 'error' ? '\u2715' : '\u2139';
  toast.innerHTML = '<span>' + icon + '</span><span>' + escHtml(message) + '</span>';
  container.appendChild(toast);
  setTimeout(function () {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(function () { toast.remove(); }, 350);
  }, 3500);
}

// ============================================================
// Init
// ============================================================
document.addEventListener('DOMContentLoaded', async function () {
  requireAuth();
  var userEl = document.getElementById('currentUser');
  if (userEl) userEl.textContent = getUsername() || '';

  document.getElementById('addClusterBtn').addEventListener('click', openAddClusterModal);
  document.getElementById('emptyAddBtn').addEventListener('click', openAddClusterModal);
  document.getElementById('modalClose').addEventListener('click', closeClusterModal);
  document.getElementById('modalCancel').addEventListener('click', closeClusterModal);
  document.getElementById('clusterModal').addEventListener('click', function (e) {
    if (e.target === e.currentTarget) closeClusterModal();
  });
  document.getElementById('clusterForm').addEventListener('submit', function (e) {
    e.preventDefault(); saveCluster();
  });
  document.getElementById('deleteClusterBtn').addEventListener('click', deleteCluster);
  document.getElementById('formIsInCluster').addEventListener('change', toggleInCluster);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeClusterModal();
  });

  await loadClusters();
});
