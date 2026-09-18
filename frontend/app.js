/**
 * Project Nirman — Integrated Web Platform Core Application JS
 * Connects directly to FastAPI backend REST endpoints:
 * - /api/analytics/*
 * - /api/projects/*
 * - /api/risk/*
 * - /api/documents/*
 * - /api/assistant/*
 */

const API_BASE = (window.location.protocol.startsWith('http') && window.location.port === '8000')
  ? `${window.location.origin}/api`
  : 'http://localhost:8000/api';


// Global Application State
const state = {
  activeView: 'dashboard',
  portfolioKPIs: null,
  earlyWarnings: [],
  projects: [],
  totalProjectsCount: 0,
  currentPage: 1,
  pageSize: 15,
  selectedProjectCode: '020100044',
  activeRiskIntelligence: null,
  activeEvidenceMap: {},
  chatHistory: []
};

// ==========================================================================
// Initialization & Event Listeners
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initDrawers();
  initGlobalSearch();
  initFilters();
  initRiskLookup();
  initRAGSearch();
  initAssistant();

  // Attach refresh button listener
  const refreshBtn = document.getElementById('refresh-data-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      checkBackendStatus();
      loadDashboardData();
      loadProjectExplorerData();
      if (state.selectedProjectCode) analyzeProjectRisk(state.selectedProjectCode);
    });
  }

  // Initial Data Fetch & Poll Health Monitor
  checkBackendStatus().then(online => {
    loadDashboardData();
    loadProjectExplorerData();
    analyzeProjectRisk(state.selectedProjectCode);
  });

  // Auto-poll health every 5 seconds
  setInterval(() => {
    checkBackendStatus();
  }, 5000);
});

async function checkBackendStatus() {
  const statusEl = document.querySelector('.system-status');
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: 'no-store' });
    if (res.ok) {
      if (statusEl) {
        statusEl.innerHTML = '<span class="status-indicator online"></span><span>Backend Connected (v1.0)</span>';
      }
      return true;
    }
  } catch (err) {
    // Connection error
  }
  if (statusEl) {
    statusEl.innerHTML = '<span class="status-indicator offline" style="background-color: var(--color-danger); box-shadow: 0 0 8px var(--color-danger);"></span><span class="text-danger" style="font-weight: 600;">Backend Disconnected</span>';
  }
  return false;
}


// ==========================================================================
// SPA Router & Navigation
// ==========================================================================
function initNavigation() {
  const navItems = document.querySelectorAll('.sidebar-nav .nav-item');
  
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const targetView = item.getAttribute('data-view');
      switchView(targetView);
    });
  });

  // Handle Hash change if directly navigated
  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.replace('#', '');
    if (hash) switchView(hash);
  });
}

function switchView(viewName) {
  state.activeView = viewName;
  
  // Update Nav links
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    if (item.getAttribute('data-view') === viewName) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Update View Panels
  document.querySelectorAll('.view-panel').forEach(panel => {
    panel.classList.remove('active');
  });

  const activePanel = document.getElementById(`view-${viewName}`);
  if (activePanel) {
    activePanel.classList.add('active');
  }

  // Update Header Title
  const titleMap = {
    'dashboard': { title: 'Executive Dashboard', subtitle: 'PAIMANA Infrastructure Risk Portfolio & Early Warning Intelligence' },
    'explorer': { title: 'Project Explorer', subtitle: 'Search and filter 3,589 monitored PAIMANA infrastructure projects' },
    'risk-intelligence': { title: 'Risk & Trajectory Intelligence', subtitle: 'SHAP driver breakdown, trajectory analysis, and prescriptive interventions' },
    'early-warning': { title: 'Early Warning Matrix', subtitle: 'Prioritized risk escalation queue based on calibrated cutoff T* = 0.28' },
    'documents': { title: 'RAG Knowledge Search', subtitle: 'Search 331,206 vector-indexed PAIMANA monthly report chunks' }
  };

  const meta = titleMap[viewName] || titleMap['dashboard'];
  document.getElementById('page-title').textContent = meta.title;
  document.getElementById('page-subtitle').textContent = meta.subtitle;

  // View specific data trigger
  if (viewName === 'early-warning') {
    renderFullEarlyWarningMatrix();
  }
}

// ==========================================================================
// Drawers (Citation Evidence & AI Assistant)
// ==========================================================================
function initDrawers() {
  // Evidence Drawer
  const evidenceDrawer = document.getElementById('evidence-drawer');
  document.getElementById('close-evidence-drawer').addEventListener('click', () => {
    evidenceDrawer.classList.remove('open');
  });
  evidenceDrawer.querySelector('.drawer-backdrop').addEventListener('click', () => {
    evidenceDrawer.classList.remove('open');
  });

  // Assistant Drawer
  const assistantDrawer = document.getElementById('assistant-drawer');
  const toggleBtn = document.getElementById('toggle-assistant-btn');
  const closeBtn = document.getElementById('close-assistant-drawer');

  toggleBtn.addEventListener('click', () => {
    assistantDrawer.classList.add('open');
  });
  closeBtn.addEventListener('click', () => {
    assistantDrawer.classList.remove('open');
  });
  assistantDrawer.querySelector('.drawer-backdrop').addEventListener('click', () => {
    assistantDrawer.classList.remove('open');
  });
}

function openEvidenceDrawer(evidenceData) {
  document.getElementById('ev-project-code').textContent = evidenceData.project_code || 'N/A';
  document.getElementById('ev-source-file').textContent = evidenceData.source_file || 'N/A';
  document.getElementById('ev-doc-type').textContent = evidenceData.document_type || 'PDF Chunk';
  document.getElementById('ev-month').textContent = evidenceData.reporting_month || 'N/A';
  document.getElementById('ev-page').textContent = evidenceData.page_number ? `Page ${evidenceData.page_number}` : 'N/A';
  document.getElementById('ev-score').textContent = evidenceData.relevance_score ? `${(evidenceData.relevance_score * 100).toFixed(1)}% Match` : 'Grounded';
  document.getElementById('ev-chunk-text').textContent = evidenceData.chunk_text || 'No raw text available';

  document.getElementById('evidence-drawer-title').textContent = `Citation Evidence ${evidenceData.tag || '[E]'}`;
  document.getElementById('evidence-drawer').classList.add('open');
}

// ==========================================================================
// 1. Executive Dashboard Logic
// ==========================================================================
async function loadDashboardData() {
  try {
    // Fetch Portfolio KPIs
    const kpiRes = await fetch(`${API_BASE}/analytics/portfolio_kpis`);
    if (kpiRes.ok) {
      const kpiData = await kpiRes.json();
      state.portfolioKPIs = kpiData;
      renderKPIs(kpiData);
    }

    // Fetch Early Warning Priority Matrix
    const ewRes = await fetch(`${API_BASE}/risk/early_warnings?limit=15`);
    if (ewRes.ok) {
      const ewData = await ewRes.json();
      state.earlyWarnings = Array.isArray(ewData) ? ewData : (ewData.prioritized_projects || []);
      renderDashboardEarlyWarnings(state.earlyWarnings);
      const ewBadge = document.getElementById('nav-ew-count');
      if (ewBadge) {
        ewBadge.textContent = state.earlyWarnings.length;
      }
    }
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
}

function renderKPIs(data) {
  document.getElementById('kpi-total-projects').textContent = (data.total_projects || 0).toLocaleString();
  document.getElementById('kpi-high-risk-count').textContent = (data.high_critical_risk_count || 0).toLocaleString();
  document.getElementById('kpi-high-risk-pct').textContent = `${(data.high_risk_percentage || 0).toFixed(1)}% of portfolio`;
  document.getElementById('kpi-avg-cost-expansion').textContent = `${(data.avg_cost_expansion || 1.0).toFixed(2)}x`;
  document.getElementById('kpi-avg-schedule-slippage').textContent = (data.avg_schedule_slippage || 0).toFixed(2);
}

function renderDashboardEarlyWarnings(warnings) {
  const tbody = document.getElementById('dashboard-ew-tbody');
  tbody.innerHTML = '';

  if (!warnings || warnings.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-4">No early warning projects active</td></tr>';
    return;
  }

  warnings.slice(0, 8).forEach(item => {
    const tr = document.createElement('tr');
    const categoryBadge = getCategoryBadgeHTML(item.risk_category);
    const scoreVal = (item.risk_score || 0).toFixed(1);
    const projName = item.project_name || `Project ${item.project_code}`;
    const driverVal = item.primary_risk_driver || (item.urgency_reason ? item.urgency_reason.split('|')[0].trim() : 'Schedule / Cost Risk');
    const urgencyVal = item.urgency_level || item.trajectory_trend || (item.risk_score >= 40 ? 'CRITICAL' : 'HIGH');

    tr.innerHTML = `
      <td><code>${item.project_code}</code></td>
      <td><strong>${projName}</strong></td>
      <td><span class="text-muted">${item.state || 'N/A'}</span> / ${item.sector || item.agency || 'N/A'}</td>
      <td><strong class="text-danger">${scoreVal}</strong></td>
      <td>${categoryBadge}</td>
      <td><span class="badge badge-warning">${driverVal}</span></td>
      <td><span class="badge badge-danger">${urgencyVal}</span></td>
      <td>
        <button class="btn btn-sm btn-outline view-project-btn" data-code="${item.project_code}">
          Analyze
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach event handlers
  tbody.querySelectorAll('.view-project-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.getAttribute('data-code');
      analyzeProjectRisk(code);
      switchView('risk-intelligence');
    });
  });
}


// ==========================================================================
// 2. Project Explorer Logic
// ==========================================================================
async function loadProjectExplorerData() {
  const stateFilter = document.getElementById('filter-state').value;
  const sectorFilter = document.getElementById('filter-sector').value;
  const riskFilter = document.getElementById('filter-risk').value;
  const searchFilter = document.getElementById('filter-search').value;

  const offset = (state.currentPage - 1) * state.pageSize;
  let url = `${API_BASE}/projects?limit=${state.pageSize}&offset=${offset}`;

  if (stateFilter) url += `&state=${encodeURIComponent(stateFilter)}`;
  if (sectorFilter) url += `&sector=${encodeURIComponent(sectorFilter)}`;
  if (riskFilter) url += `&risk_category=${encodeURIComponent(riskFilter)}`;

  try {
    const res = await fetch(url);
    if (res.ok) {
      const data = await res.json();
      state.projects = Array.isArray(data) ? data : (data.projects || []);
      state.totalProjectsCount = Array.isArray(data) ? 3589 : (data.total_count || state.projects.length);

      renderExplorerTable(state.projects);
      updatePaginationControls();
      populateFilterDropdowns(data.available_states, data.available_sectors);

    }
  } catch (err) {
    console.error('Failed to load project explorer:', err);
  }
}

function renderExplorerTable(projects) {
  const tbody = document.getElementById('explorer-tbody');
  tbody.innerHTML = '';

  if (!projects || projects.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted p-4">No matching projects found</td></tr>';
    return;
  }

  projects.forEach(p => {
    const tr = document.createElement('tr');
    const categoryBadge = getCategoryBadgeHTML(p.risk_category || 'MODERATE');
    const projName = p.project_name || p.name || `Project ${p.project_code}`;
    
    let costExpVal = '1.00x';
    if (p.cost_expansion_ratio != null) {
      costExpVal = `${p.cost_expansion_ratio.toFixed(2)}x`;
    } else if (p.anticipated_cost && p.original_cost && p.original_cost > 0) {
      costExpVal = `${(p.anticipated_cost / p.original_cost).toFixed(2)}x`;
    }

    let schedSlVal = '0.00';
    if (p.schedule_slippage_ratio != null) {
      schedSlVal = p.schedule_slippage_ratio.toFixed(2);
    } else if (p.schedule_risk_index != null) {
      schedSlVal = p.schedule_risk_index.toFixed(2);
    }

    const scoreNum = p.risk_score != null ? p.risk_score.toFixed(1) : '--';

    tr.innerHTML = `
      <td><code>${p.project_code}</code></td>
      <td><strong>${projName}</strong></td>
      <td>${p.state || 'N/A'}</td>
      <td>${p.sector || 'N/A'}</td>
      <td>${costExpVal}</td>
      <td>${schedSlVal}</td>
      <td><strong>${scoreNum}</strong></td>
      <td>${categoryBadge}</td>
      <td>
        <button class="btn btn-sm btn-secondary view-project-btn" data-code="${p.project_code}">
          <i class="fa-solid fa-chart-line"></i> View
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });


  tbody.querySelectorAll('.view-project-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.getAttribute('data-code');
      analyzeProjectRisk(code);
      switchView('risk-intelligence');
    });
  });
}

function populateFilterDropdowns(states, sectors) {
  const stateSelect = document.getElementById('filter-state');
  const sectorSelect = document.getElementById('filter-sector');

  if (!states && state.projects.length > 0) {
    states = Array.from(new Set(state.projects.map(p => p.state).filter(Boolean))).sort();
  }
  if (!sectors && state.projects.length > 0) {
    sectors = Array.from(new Set(state.projects.map(p => p.sector).filter(Boolean))).sort();
  }

  if (states && stateSelect && stateSelect.children.length <= 1) {
    states.forEach(s => {
      if (s) {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        stateSelect.appendChild(opt);
      }
    });
  }

  if (sectors && sectorSelect && sectorSelect.children.length <= 1) {
    sectors.forEach(sec => {
      if (sec) {
        const opt = document.createElement('option');
        opt.value = sec;
        opt.textContent = sec;
        sectorSelect.appendChild(opt);
      }
    });
  }
}


function updatePaginationControls() {
  const totalPages = Math.ceil(state.totalProjectsCount / state.pageSize) || 1;
  document.getElementById('page-indicator').textContent = `Page ${state.currentPage} of ${totalPages}`;
  document.getElementById('explorer-count-label').textContent = `Showing ${(state.currentPage - 1) * state.pageSize + 1} - ${Math.min(state.currentPage * state.pageSize, state.totalProjectsCount)} of ${state.totalProjectsCount} projects`;
  
  document.getElementById('prev-page-btn').disabled = state.currentPage <= 1;
  document.getElementById('next-page-btn').disabled = state.currentPage >= totalPages;
}

function initFilters() {
  document.getElementById('apply-filters-btn').addEventListener('click', () => {
    state.currentPage = 1;
    loadProjectExplorerData();
  });

  document.getElementById('reset-filters-btn').addEventListener('click', () => {
    document.getElementById('filter-state').value = '';
    document.getElementById('filter-sector').value = '';
    document.getElementById('filter-risk').value = '';
    document.getElementById('filter-search').value = '';
    state.currentPage = 1;
    loadProjectExplorerData();
  });

  document.getElementById('prev-page-btn').addEventListener('click', () => {
    if (state.currentPage > 1) {
      state.currentPage--;
      loadProjectExplorerData();
    }
  });

  document.getElementById('next-page-btn').addEventListener('click', () => {
    state.currentPage++;
    loadProjectExplorerData();
  });
}

// ==========================================================================
// 3. Risk & Trajectory View Logic
// ==========================================================================
function initRiskLookup() {
  document.getElementById('risk-analyze-btn').addEventListener('click', () => {
    const code = document.getElementById('risk-project-input').value.trim();
    if (code) {
      analyzeProjectRisk(code);
    }
  });

  document.getElementById('generate-briefing-btn').addEventListener('click', () => {
    if (state.selectedProjectCode) {
      loadExecutiveBriefing(state.selectedProjectCode);
    }
  });
}

async function analyzeProjectRisk(projectCode) {
  state.selectedProjectCode = projectCode;
  document.getElementById('risk-project-input').value = projectCode;

  try {
    const res = await fetch(`${API_BASE}/risk/intelligence/${projectCode}`);
    if (!res.ok) {
      alert(`Project ${projectCode} not found or failed risk computation.`);
      return;
    }

    const data = await res.json();
    state.activeRiskIntelligence = data;
    renderRiskIntelligenceView(data);
    loadExecutiveBriefing(projectCode);
  } catch (err) {
    console.error('Failed to load risk intelligence:', err);
  }
}

function renderRiskIntelligenceView(data) {
  const meta = data.project_metadata || {};
  const risk = data.risk_assessment || {};
  const trajectory = data.risk_trajectory || {};
  const shap = data.risk_decomposition || {};
  const recs = data.prescriptive_recommendations || [];

  // Banner Header
  document.getElementById('rd-project-code').textContent = data.project_code || 'N/A';
  document.getElementById('rd-project-name').textContent = meta.name || `Project ${data.project_code}`;
  document.getElementById('rd-project-meta').textContent = `${meta.state || 'N/A'} | Sector: ${meta.sector || 'N/A'} | Agency: ${meta.agency || 'N/A'}`;

  // Risk Score Box
  const scoreVal = (risk.risk_score || 0).toFixed(1);
  document.getElementById('rd-score-value').textContent = scoreVal;
  document.getElementById('rd-category-badge').outerHTML = getCategoryBadgeHTML(risk.risk_category || 'MODERATE');
  document.getElementById('rd-probability-text').textContent = `Risk Prob: ${((risk.risk_probability || 0) * 100).toFixed(1)}%`;

  // Banner Stats
  document.getElementById('rd-cost-original').textContent = `₹${(meta.original_cost || 0).toFixed(1)} Cr`;
  document.getElementById('rd-cost-latest').textContent = `₹${(meta.latest_sanctioned_cost || meta.original_cost || 0).toFixed(1)} Cr`;
  document.getElementById('rd-cost-expansion').textContent = `${(risk.cost_risk_index || 1.0).toFixed(2)}x`;
  document.getElementById('rd-schedule-slippage').textContent = (risk.schedule_risk_index || 0).toFixed(2);
  document.getElementById('rd-progress-rate').textContent = `${(meta.milestone_progress_rate || 0).toFixed(1)}%`;

  // Trajectory Card
  document.getElementById('rd-trend-classification').textContent = trajectory.trajectory_classification || 'N/A';
  document.getElementById('rd-trend-badge').textContent = trajectory.trajectory_classification || 'STABLE';
  document.getElementById('rd-trend-slope').textContent = trajectory.slope != null ? trajectory.slope.toFixed(4) : 'N/A';
  document.getElementById('rd-trend-variance').textContent = trajectory.variance != null ? trajectory.variance.toFixed(2) : 'N/A';

  const trajTbody = document.getElementById('rd-trajectory-tbody');
  trajTbody.innerHTML = '';
  const historyList = trajectory.historical_points || [];

  if (historyList.length === 0) {
    trajTbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No historical reporting months available</td></tr>';
  } else {
    historyList.forEach(pt => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${pt.reporting_month}</code></td>
        <td>${pt.model_version || 'RiskEngine-v1.0'}</td>
        <td><strong>${(pt.risk_score || 0).toFixed(1)}</strong></td>
        <td>${((pt.risk_probability || 0) * 100).toFixed(1)}%</td>
        <td>${getCategoryBadgeHTML(pt.risk_category || 'LOW')}</td>
      `;
      trajTbody.appendChild(tr);
    });
  }

  // SHAP Drivers & Protective Factors
  renderSHAPList('rd-risk-drivers-list', shap.risk_drivers || [], 'risk');
  renderSHAPList('rd-protective-factors-list', shap.protective_factors || [], 'protective');

  // Recommendations
  renderRecommendationsList(recs);
}

function renderSHAPList(elementId, items, type) {
  const container = document.getElementById(elementId);
  container.innerHTML = '';

  if (!items || items.length === 0) {
    container.innerHTML = `<p class="text-muted text-xs p-2">No ${type === 'risk' ? 'adverse risk drivers' : 'protective factors'} identified.</p>`;
    return;
  }

  items.forEach(item => {
    const div = document.createElement('div');
    div.className = 'shap-item';

    const barClass = type === 'risk' ? 'risk' : 'protective';
    const valPct = Math.min(Math.abs(item.contribution || 0) * 200, 100);

    div.innerHTML = `
      <div class="shap-item-header">
        <strong>${item.feature_description || item.feature_name}</strong>
        <span><code>${item.value || 'N/A'}</code> (${(item.contribution * 100).toFixed(1)}%)</span>
      </div>
      <div class="shap-bar-bg">
        <div class="shap-bar-fill ${barClass}" style="width: ${valPct}%;"></div>
      </div>
    `;
    container.appendChild(div);
  });
}

function renderRecommendationsList(recs) {
  const container = document.getElementById('rd-recommendations-list');
  container.innerHTML = '';

  if (!recs || recs.length === 0) {
    container.innerHTML = '<p class="text-muted p-3">No specific policy triggers violated for this project.</p>';
    return;
  }

  recs.forEach(r => {
    const card = document.createElement('div');
    const priorityClass = (r.priority || 'medium').toLowerCase();
    card.className = `recommendation-card ${priorityClass}`;

    card.innerHTML = `
      <div class="rec-header">
        <span class="rec-title">${r.title}</span>
        <span class="badge badge-${priorityClass === 'urgent' ? 'danger' : 'warning'}">${r.priority}</span>
      </div>
      <p class="rec-details mb-2">${r.action_details}</p>
      <div class="text-xs text-muted"><strong>Policy Rule:</strong> ${r.trigger_condition}</div>
    `;
    container.appendChild(card);
  });
}

async function loadExecutiveBriefing(projectCode) {
  const briefingBox = document.getElementById('rd-briefing-content');
  briefingBox.textContent = 'Generating automated executive briefing...';

  try {
    const res = await fetch(`${API_BASE}/risk/briefing/${projectCode}`);
    if (res.ok) {
      const data = await res.json();
      briefingBox.textContent = data.briefing || data.executive_briefing || 'Briefing generated successfully.';
    } else {
      briefingBox.textContent = 'Briefing synthesis unavailable for this project.';
    }
  } catch (err) {
    briefingBox.textContent = 'Failed to load executive briefing document.';
  }
}

// ==========================================================================
// 4. Early Warning Matrix View Logic
// ==========================================================================
function renderFullEarlyWarningMatrix() {
  const tbody = document.getElementById('full-ew-tbody');
  tbody.innerHTML = '';

  if (!state.earlyWarnings || state.earlyWarnings.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted p-4">Loading portfolio early warning matrix...</td></tr>';
    return;
  }

  state.earlyWarnings.forEach(item => {
    const tr = document.createElement('tr');
    const projName = item.project_name || `Project ${item.project_code}`;
    const driverVal = item.primary_risk_driver || (item.urgency_reason ? item.urgency_reason.split('|')[0].trim() : 'Schedule / Cost Risk');
    const urgencyVal = item.urgency_level || item.trajectory_trend || (item.risk_score >= 40 ? 'CRITICAL' : 'HIGH');
    const urgencyReason = item.urgency_rationale || item.urgency_reason || 'High calibrated risk probability cutoff exceeded';

    tr.innerHTML = `
      <td><span class="badge badge-danger">${urgencyVal}</span></td>
      <td><code>${item.project_code}</code></td>
      <td><strong>${projName}</strong></td>
      <td>${item.state || 'N/A'} / ${item.sector || item.agency || 'N/A'}</td>
      <td><strong class="text-danger">${(item.risk_score || 0).toFixed(1)}</strong></td>
      <td><span class="badge badge-warning">${driverVal}</span></td>
      <td class="text-xs">${urgencyReason}</td>
      <td>
        <button class="btn btn-sm btn-outline view-project-btn" data-code="${item.project_code}">
          Analyze
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });


  tbody.querySelectorAll('.view-project-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.getAttribute('data-code');
      analyzeProjectRisk(code);
      switchView('risk-intelligence');
    });
  });
}

// ==========================================================================
// 5. RAG Knowledge Search View Logic
// ==========================================================================
function initRAGSearch() {
  document.getElementById('rag-search-btn').addEventListener('click', executeRAGSearch);
  document.getElementById('rag-query-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') executeRAGSearch();
  });
}

async function executeRAGSearch() {
  const query = document.getElementById('rag-query-input').value.trim();
  if (!query) return;

  const projFilter = document.getElementById('rag-filter-project').value.trim();
  const monthFilter = document.getElementById('rag-filter-month').value.trim();
  const docTypeFilter = document.getElementById('rag-filter-doctype').value.trim();

  let url = `${API_BASE}/documents/search?query=${encodeURIComponent(query)}&top_k=8`;
  if (projFilter) url += `&project_code=${encodeURIComponent(projFilter)}`;
  if (monthFilter) url += `&reporting_month=${encodeURIComponent(monthFilter)}`;
  if (docTypeFilter) url += `&document_type=${encodeURIComponent(docTypeFilter)}`;

  const resultsContainer = document.getElementById('rag-results-list');
  resultsContainer.innerHTML = '<p class="text-center text-muted p-4"><i class="fa-solid fa-circle-notch fa-spin"></i> Retrieving PAIMANA document chunks...</p>';

  try {
    const res = await fetch(url);
    if (!res.ok) {
      resultsContainer.innerHTML = '<p class="text-danger p-4">RAG search request failed.</p>';
      return;
    }

    const data = await res.json();
    const chunks = data.results || data.chunks || [];
    renderRAGResults(chunks, query);
  } catch (err) {
    resultsContainer.innerHTML = '<p class="text-danger p-4">Error executing RAG search.</p>';
  }
}

function renderRAGResults(chunks, query) {
  const resultsContainer = document.getElementById('rag-results-list');
  resultsContainer.innerHTML = '';

  document.getElementById('rag-results-count').textContent = `Retrieved ${chunks.length} verified PAIMANA document chunks for "${query}"`;

  if (chunks.length === 0) {
    resultsContainer.innerHTML = '<p class="text-muted p-4 text-center">No document chunks found matching the search criteria.</p>';
    return;
  }

  chunks.forEach((c, idx) => {
    const card = document.createElement('div');
    card.className = 'rag-result-card';
    const scorePct = c.score ? (c.score * 100).toFixed(1) : '90.0';

    card.innerHTML = `
      <div class="rag-result-header">
        <div>
          <span class="badge badge-outline">Project ${c.project_code || 'N/A'}</span>
          <span class="badge badge-secondary ml-2">${c.document_type || 'Monthly Report'}</span>
          <span class="text-muted text-xs px-2">${c.reporting_month || 'N/A'} | Page ${c.page_number || 'N/A'}</span>
        </div>
        <span class="badge badge-success">${scorePct}% Relevance</span>
      </div>
      <div class="chunk-text mb-2">${c.chunk_text || c.text || ''}</div>
      <div class="flex justify-between items-center text-xs text-muted">
        <span><strong>Source:</strong> <code>${c.source_file || 'PAIMANA PDF'}</code></span>
        <button class="btn btn-sm btn-outline open-ev-btn" data-idx="${idx}">
          <i class="fa-solid fa-quote-left"></i> View Citation [E${idx + 1}]
        </button>
      </div>
    `;
    resultsContainer.appendChild(card);

    // Save evidence chunk to state map
    state.activeEvidenceMap[`E${idx + 1}`] = {
      tag: `[E${idx + 1}]`,
      project_code: c.project_code,
      source_file: c.source_file,
      document_type: c.document_type,
      reporting_month: c.reporting_month,
      page_number: c.page_number,
      relevance_score: c.score,
      chunk_text: c.chunk_text || c.text
    };
  });

  resultsContainer.querySelectorAll('.open-ev-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = btn.getAttribute('data-idx');
      const tag = `E${parseInt(idx) + 1}`;
      if (state.activeEvidenceMap[tag]) {
        openEvidenceDrawer(state.activeEvidenceMap[tag]);
      }
    });
  });
}

// ==========================================================================
// 6. Global AI Assistant Logic
// ==========================================================================
function initAssistant() {
  const sendBtn = document.getElementById('send-assistant-btn');
  const inputEl = document.getElementById('assistant-input');

  sendBtn.addEventListener('click', () => {
    const text = inputEl.value.trim();
    if (text) {
      sendAssistantMessage(text);
      inputEl.value = '';
    }
  });

  inputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const text = inputEl.value.trim();
      if (text) {
        sendAssistantMessage(text);
        inputEl.value = '';
      }
    }
  });

  // Quick prompt chips
  document.querySelectorAll('.chip-btn').forEach(chip => {
    chip.addEventListener('click', () => {
      const promptText = chip.getAttribute('data-prompt');
      document.getElementById('assistant-drawer').classList.add('open');
      sendAssistantMessage(promptText);
    });
  });
}

async function sendAssistantMessage(promptText) {
  const container = document.getElementById('assistant-messages');

  // Append User Message Bubble
  const userMsgDiv = document.createElement('div');
  userMsgDiv.className = 'message user-msg';
  userMsgDiv.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
    <div class="msg-bubble"><p>${escapeHTML(promptText)}</p></div>
  `;
  container.appendChild(userMsgDiv);

  // Append Assistant Loading Indicator
  const botMsgDiv = document.createElement('div');
  botMsgDiv.className = 'message assistant-msg';
  botMsgDiv.innerHTML = `
    <div class="msg-avatar"><i class="fa-solid fa-robot"></i></div>
    <div class="msg-bubble"><p><i class="fa-solid fa-circle-notch fa-spin"></i> Routing query & gathering evidence...</p></div>
  `;
  container.appendChild(botMsgDiv);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/assistant/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: promptText })
    });

    if (!res.ok) {
      botMsgDiv.querySelector('.msg-bubble').innerHTML = '<p class="text-danger">Assistant service error. Please try again.</p>';
      return;
    }

    const data = await res.json();
    renderAssistantResponse(botMsgDiv, data);
  } catch (err) {
    botMsgDiv.querySelector('.msg-bubble').innerHTML = '<p class="text-danger">Network error connecting to AI Assistant.</p>';
  }
}

function renderAssistantResponse(msgDiv, responseData) {
  const bubble = msgDiv.querySelector('.msg-bubble');
  const text = responseData.response || responseData.answer || 'No response text returned.';
  const citations = responseData.citations || [];

  // Save Citations to Evidence Map
  citations.forEach(cit => {
    const tagKey = cit.tag ? cit.tag.replace('[', '').replace(']', '') : `E${cit.citation_id}`;
    state.activeEvidenceMap[tagKey] = {
      tag: cit.tag || `[${tagKey}]`,
      project_code: cit.project_code,
      source_file: cit.source_file,
      document_type: cit.document_type,
      reporting_month: cit.reporting_month,
      page_number: cit.page_number,
      chunk_text: cit.chunk_text || cit.text || 'Citation evidence chunk'
    };
  });

  // Format HTML & Render Citation Tags
  let formattedHTML = formatMarkdownText(text);

  // Add intent & grounded meta
  const intentBadge = responseData.intent ? `<span class="badge badge-secondary mb-2">${responseData.intent}</span>` : '';
  const metaText = `<div class="text-xs text-muted mt-2"><strong>Source:</strong> ${responseData.grounded ? 'Verified Grounded Data' : 'General'} | <strong>Confidence:</strong> ${((responseData.confidence || 0.95) * 100).toFixed(0)}%</div>`;

  bubble.innerHTML = `${intentBadge}<div>${formattedHTML}</div>${metaText}`;

  // Attach citation tag click handlers
  bubble.querySelectorAll('.citation-tag').forEach(tagEl => {
    tagEl.addEventListener('click', () => {
      const tagKey = tagEl.getAttribute('data-tag');
      if (state.activeEvidenceMap[tagKey]) {
        openEvidenceDrawer(state.activeEvidenceMap[tagKey]);
      }
    });
  });

  const container = document.getElementById('assistant-messages');
  container.scrollTop = container.scrollHeight;
}

// Helpers
function getCategoryBadgeHTML(category) {
  const cat = (category || 'LOW').toUpperCase();
  if (cat === 'CRITICAL') return '<span class="badge badge-danger">CRITICAL</span>';
  if (cat === 'HIGH') return '<span class="badge badge-warning">HIGH</span>';
  if (cat === 'MODERATE') return '<span class="badge badge-info">MODERATE</span>';
  return '<span class="badge badge-success">LOW</span>';
}

function initGlobalSearch() {
  const searchInput = document.getElementById('global-project-search');
  const searchBtn = document.getElementById('global-search-btn');

  const doSearch = () => {
    const code = searchInput.value.trim();
    if (code) {
      analyzeProjectRisk(code);
      switchView('risk-intelligence');
    }
  };

  searchBtn.addEventListener('click', doSearch);
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') doSearch();
  });
}

function formatMarkdownText(text) {
  if (!text) return '';
  let str = escapeHTML(text);

  // Format bold
  str = str.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Format code
  str = str.replace(/`(.*?)`/g, '<code>$1</code>');
  // Format Citation Tags e.g. [E1], [E2]
  str = str.replace(/\[E(\d+)\]/g, (match, p1) => {
    const tagKey = `E${p1}`;
    return `<span class="citation-tag" data-tag="${tagKey}"><i class="fa-solid fa-quote-left"></i> [E${p1}]</span>`;
  });
  // Format newlines
  str = str.replace(/\n/g, '<br>');
  return str;
}

function escapeHTML(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
