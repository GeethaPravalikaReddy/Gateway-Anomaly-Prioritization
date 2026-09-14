"""Interactive Web Dashboard Route for Gateway Anomaly Prioritization."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Dashboard"])

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Gateway Anomaly Prioritization — Radio Network Anomaly & Dispatch Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
  <style>
    :root {
      --bg-base: #0a0e17;
      --bg-surface: #111827;
      --bg-surface-elevated: #1a2234;
      --bg-card: rgba(17, 24, 39, 0.75);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(56, 189, 248, 0.3);
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      --primary: #38bdf8;
      --primary-hover: #0284c7;
      --accent: #818cf8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --card-radius: 16px;
      --transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-base);
      color: var(--text-main);
      line-height: 1.5;
      min-height: 100vh;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.07) 0%, transparent 45%),
        radial-gradient(circle at 85% 75%, rgba(129, 140, 248, 0.06) 0%, transparent 45%);
      background-attachment: fixed;
    }

    .container {
      max-width: 1360px;
      margin: 0 auto;
      padding: 32px 24px 64px 24px;
    }

    /* Header */
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 32px;
      flex-wrap: wrap;
      gap: 16px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .brand-icon {
      width: 44px;
      height: 44px;
      background: linear-gradient(135deg, #0284c7, #6366f1);
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 16px rgba(56, 189, 248, 0.3);
    }

    .brand-icon svg {
      width: 24px;
      height: 24px;
      fill: #ffffff;
    }

    .brand-title {
      font-size: 1.4rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(to right, #ffffff, #93c5fd);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-subtitle {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 500;
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .nav-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      font-size: 0.85rem;
      font-weight: 500;
      color: var(--text-main);
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      text-decoration: none;
      transition: var(--transition);
      cursor: pointer;
    }

    .nav-btn:hover {
      background: var(--bg-surface-elevated);
      border-color: var(--border-accent);
      color: var(--primary);
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: 9999px;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--success);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--success);
    }

    /* KPI Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }

    .kpi-card {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--card-radius);
      padding: 20px 24px;
      transition: var(--transition);
      position: relative;
      overflow: hidden;
    }

    .kpi-card::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--primary), transparent);
      opacity: 0;
      transition: var(--transition);
    }

    .kpi-card:hover {
      transform: translateY(-2px);
      border-color: var(--border-accent);
    }

    .kpi-card:hover::before {
      opacity: 1;
    }

    .kpi-label {
      font-size: 0.8rem;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 8px;
    }

    .kpi-value {
      font-size: 1.8rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #ffffff;
    }

    .kpi-desc {
      font-size: 0.78rem;
      color: var(--text-dim);
      margin-top: 6px;
    }

    /* Control Panel */
    .control-panel {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--card-radius);
      padding: 20px 24px;
      margin-bottom: 28px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }

    .control-group {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
    }

    .form-item {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .form-label {
      font-size: 0.85rem;
      color: var(--text-muted);
      font-weight: 500;
    }

    select, input[type="text"] {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 9px 14px;
      border-radius: 10px;
      font-size: 0.88rem;
      font-family: inherit;
      outline: none;
      transition: var(--transition);
    }

    select:focus, input[type="text"]:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
    }

    .btn-primary {
      background: linear-gradient(135deg, #0284c7, #2563eb);
      color: #ffffff;
      border: none;
      padding: 9px 18px;
      border-radius: 10px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: var(--transition);
      box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
    }

    .btn-primary:hover {
      background: linear-gradient(135deg, #0369a1, #1d4ed8);
      transform: translateY(-1px);
    }

    .btn-primary:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
    }

    /* Table Container */
    .table-container {
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-color);
      border-radius: var(--card-radius);
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    }

    .table-header-bar {
      padding: 18px 24px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }

    .table-title {
      font-size: 1.1rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .count-tag {
      font-size: 0.75rem;
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      padding: 3px 10px;
      border-radius: 9999px;
      font-weight: 600;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }

    thead th {
      background: var(--bg-surface);
      color: var(--text-muted);
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 14px 20px;
      font-weight: 600;
      border-bottom: 1px solid var(--border-color);
    }

    tbody tr {
      border-bottom: 1px solid var(--border-color);
      transition: var(--transition);
    }

    tbody tr:hover {
      background: rgba(255, 255, 255, 0.02);
    }

    tbody td {
      padding: 14px 20px;
      font-size: 0.9rem;
      vertical-align: middle;
    }

    /* Badges & Elements */
    .rank-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.85rem;
      background: var(--bg-surface-elevated);
      color: var(--text-muted);
    }

    .rank-1 { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
    .rank-2 { background: rgba(148, 163, 184, 0.2); color: #e2e8f0; border: 1px solid rgba(148, 163, 184, 0.4); }
    .rank-3 { background: rgba(217, 119, 6, 0.2); color: #f97316; border: 1px solid rgba(217, 119, 6, 0.4); }

    .gateway-code {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.88rem;
      font-weight: 600;
      color: #67e8f9;
      background: rgba(6, 182, 212, 0.1);
      padding: 4px 8px;
      border-radius: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .score-badge {
      display: inline-flex;
      align-items: baseline;
      gap: 4px;
      font-weight: 700;
      font-size: 1.05rem;
      color: #f87171;
    }

    .score-sub {
      font-size: 0.72rem;
      color: var(--text-dim);
      font-weight: 500;
    }

    .reason-text {
      font-size: 0.82rem;
      color: var(--text-muted);
      max-width: 480px;
    }

    .action-btn {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 6px 12px;
      border-radius: 8px;
      font-size: 0.8rem;
      font-weight: 500;
      cursor: pointer;
      transition: var(--transition);
    }

    .action-btn:hover {
      background: var(--bg-surface-elevated);
      border-color: var(--border-accent);
      color: var(--primary);
    }

    /* Modal */
    .modal-backdrop {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(8px);
      z-index: 100;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }

    .modal {
      background: var(--bg-surface);
      border: 1px solid var(--border-accent);
      border-radius: var(--card-radius);
      max-width: 640px;
      width: 100%;
      padding: 28px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
      position: relative;
    }

    .modal-close {
      position: absolute;
      top: 20px;
      right: 20px;
      background: none;
      border: none;
      color: var(--text-dim);
      font-size: 1.4rem;
      cursor: pointer;
      line-height: 1;
    }

    .modal-close:hover {
      color: #ffffff;
    }

    .breakdown-card {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px;
      margin-top: 14px;
    }

    .breakdown-row {
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 0.85rem;
    }

    .breakdown-row:last-child {
      border-bottom: none;
    }

    /* Loader */
    .spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #ffffff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      border: 1px solid var(--primary);
      padding: 12px 20px;
      border-radius: 10px;
      color: #ffffff;
      font-size: 0.9rem;
      display: none;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      z-index: 200;
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header>
      <div class="brand">
        <div class="brand-icon">
          <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
        </div>
        <div>
          <h1 class="brand-title">Gateway Anomaly Prioritization Analytics</h1>
          <div class="brand-subtitle">LPDG Radio Network Anomaly Detection & Dispatch Prioritization</div>
        </div>
      </div>

      <div class="nav-actions">
        <div class="status-badge" id="serviceStatus">
          <span class="status-dot"></span>
          <span>API Online</span>
        </div>
        <a href="/docs" target="_blank" class="nav-btn">
          <span>Interactive Swagger UI</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </a>
        <a href="/redoc" target="_blank" class="nav-btn">
          <span>ReDoc</span>
        </a>
        <a href="/health" target="_blank" class="nav-btn">
          <span>Health JSON</span>
        </a>
      </div>
    </header>

    <!-- KPI Grid -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Fleet Monitored</div>
        <div class="kpi-value" id="kpiTotalGateways">332</div>
        <div class="kpi-desc">Registered master gateways across utilities</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Telemetry Ingested</div>
        <div class="kpi-value" id="kpiTelemetryRows">1,433,387</div>
        <div class="kpi-desc">Hourly time-series telemetry events</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Weekly Dispatch Limit</div>
        <div class="kpi-value">15 Sites</div>
        <div class="kpi-desc">Hard operations crew physical visit cap</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Ranking Model</div>
        <div class="kpi-value" style="font-size: 1.35rem; padding-top: 6px;">3-Sigma Dynamic</div>
        <div class="kpi-desc">28-day rolling window baseline per gateway</div>
      </div>
    </div>

    <!-- Control Panel -->
    <div class="control-panel">
      <div class="control-group">
        <div class="form-item">
          <label class="form-label" for="weekSelect">Target Week (Monday):</label>
          <select id="weekSelect">
            <option value="2026-02-02" selected>2026-02-02 (Week 1)</option>
            <option value="2026-02-09">2026-02-09 (Week 2)</option>
            <option value="2026-02-16">2026-02-16 (Week 3)</option>
            <option value="2026-02-23">2026-02-23 (Week 4)</option>
            <option value="2026-03-02">2026-03-02 (Week 5)</option>
            <option value="2026-03-09">2026-03-09 (Week 6)</option>
            <option value="2026-03-16">2026-03-16 (Week 7)</option>
            <option value="2026-03-23">2026-03-23 (Week 8)</option>
          </select>
        </div>

        <div class="form-item">
          <label class="form-label" for="limitSelect">Limit:</label>
          <select id="limitSelect">
            <option value="15" selected>15 dispatches (Standard)</option>
            <option value="5">Top 5</option>
            <option value="10">Top 10</option>
            <option value="25">Top 25</option>
            <option value="50">Top 50</option>
          </select>
        </div>

        <div class="form-item">
          <input type="text" id="searchInput" placeholder="Filter Gateway ID / Reason..." />
        </div>
      </div>

      <div class="control-group">
        <button id="btnRunPipeline" class="btn-primary">
          <span>Trigger Live Pipeline Run</span>
        </button>
      </div>
    </div>

    <!-- Table Container -->
    <div class="table-container">
      <div class="table-header-bar">
        <div class="table-title">
          <span>Prioritized Technician Site Visits</span>
          <span class="count-tag" id="tableCountTag">15 Dispatches</span>
        </div>
        <div>
          <a id="rawJsonLink" href="/predictions/2026-02-02?limit=15" target="_blank" class="nav-btn" style="padding: 6px 12px; font-size: 0.8rem;">
            View Endpoint JSON
          </a>
        </div>
      </div>

      <table id="recommendationsTable">
        <thead>
          <tr>
            <th style="width: 80px;">Rank</th>
            <th style="width: 190px;">Gateway ID</th>
            <th style="width: 140px;">Anomaly Score</th>
            <th>Primary Breach & Failure Reason</th>
            <th style="width: 140px; text-align: right;">Drill-down</th>
          </tr>
        </thead>
        <tbody id="tableBody">
          <tr>
            <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-muted);">
              <span class="spinner"></span> Loading recommendations...
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Detail Modal -->
  <div class="modal-backdrop" id="detailModal">
    <div class="modal">
      <button class="modal-close" id="modalCloseBtn">&times;</button>
      <h2 style="font-size: 1.25rem; font-weight: 700; margin-bottom: 4px;">Gateway Anomaly Analysis</h2>
      <div id="modalSub" style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 16px;"></div>
      
      <div id="modalBody">
        <div style="text-align: center; padding: 20px;"><span class="spinner"></span> Loading telemetry metrics...</div>
      </div>
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    let currentData = [];
    const weekSelect = document.getElementById('weekSelect');
    const limitSelect = document.getElementById('limitSelect');
    const searchInput = document.getElementById('searchInput');
    const tableBody = document.getElementById('tableBody');
    const tableCountTag = document.getElementById('tableCountTag');
    const rawJsonLink = document.getElementById('rawJsonLink');
    const btnRunPipeline = document.getElementById('btnRunPipeline');
    const detailModal = document.getElementById('detailModal');
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const toast = document.getElementById('toast');

    function showToast(message) {
      toast.textContent = message;
      toast.style.display = 'block';
      setTimeout(() => { toast.style.display = 'none'; }, 3500);
    }

    async function loadHealth() {
      try {
        const res = await fetch('/health');
        if (res.ok) {
          const data = await res.json();
          document.getElementById('kpiTotalGateways').textContent = data.total_registered_gateways.toLocaleString();
          document.getElementById('kpiTelemetryRows').textContent = data.telemetry_row_count.toLocaleString();
        }
      } catch (err) {
        console.error('Health load error:', err);
      }
    }

    async function loadRecommendations() {
      const week = weekSelect.value;
      const limit = limitSelect.value;
      rawJsonLink.href = `/predictions/${week}?limit=${limit}`;
      
      tableBody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-muted);">
            <span class="spinner"></span> Computing 3-sigma anomaly ranking for ${week}...
          </td>
        </tr>
      `;

      try {
        const res = await fetch(`/predictions/${week}?limit=${limit}`);
        if (!res.ok) {
          const err = await res.json();
          tableBody.innerHTML = `<tr><td colspan="5" style="color: var(--danger); text-align: center; padding: 30px;">Error: ${err.detail || 'Could not fetch data'}</td></tr>`;
          return;
        }

        const data = await res.json();
        currentData = data.recommendations || [];
        renderTable();
      } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="5" style="color: var(--danger); text-align: center; padding: 30px;">Network Error: ${err.message}</td></tr>`;
      }
    }

    function renderTable() {
      const filter = (searchInput.value || '').trim().toUpperCase();
      const filtered = currentData.filter(item => 
        item.gateway_id.toUpperCase().includes(filter) ||
        item.reason.toUpperCase().includes(filter)
      );

      tableCountTag.textContent = `${filtered.length} Dispatches`;

      if (filtered.length === 0) {
        tableBody.innerHTML = `
          <tr>
            <td colspan="5" style="text-align: center; padding: 40px; color: var(--text-muted);">
              No gateways matching filter.
            </td>
          </tr>
        `;
        return;
      }

      tableBody.innerHTML = filtered.map(row => {
        let rankClass = 'rank-badge';
        if (row.rank === 1) rankClass += ' rank-1';
        else if (row.rank === 2) rankClass += ' rank-2';
        else if (row.rank === 3) rankClass += ' rank-3';

        return `
          <tr>
            <td><span class="${rankClass}">#${row.rank}</span></td>
            <td>
              <span class="gateway-code">${row.gateway_id}</span>
            </td>
            <td>
              <span class="score-badge">
                ${row.score}
                <span class="score-sub">hours &gt; 3σ</span>
              </span>
            </td>
            <td>
              <div class="reason-text">${escapeHtml(row.reason)}</div>
            </td>
            <td style="text-align: right;">
              <button class="action-btn" onclick="inspectGateway('${row.gateway_id}', '${row.week_start}')">
                Breakdown
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    async function inspectGateway(gwId, week) {
      document.getElementById('modalSub').textContent = `Gateway ID: ${gwId} • Week: ${week}`;
      document.getElementById('modalBody').innerHTML = `
        <div style="text-align: center; padding: 30px;"><span class="spinner"></span> Ingesting telemetry breakdown...</div>
      `;
      detailModal.style.display = 'flex';

      try {
        const res = await fetch(`/predictions/${week}/gateway/${gwId}`);
        if (!res.ok) {
          const err = await res.json();
          document.getElementById('modalBody').innerHTML = `<p style="color: var(--danger);">Failed: ${err.detail}</p>`;
          return;
        }
        const data = await res.json();

        let breakdownHtml = `
          <div style="margin-bottom: 16px; font-size: 0.88rem; color: var(--text-muted);">
            <div><strong>Overall Anomaly Score:</strong> ${data.score} flagged hours</div>
            <div><strong>First Breach Metric:</strong> <span style="color: var(--primary);">${data.first_breach_metric || 'None'}</span></div>
            <div><strong>Baseline Hours Observed:</strong> ${data.baseline_total_hours_observed} hrs (trailing 28 days)</div>
            <div><strong>Recent Hours Observed:</strong> ${data.recent_total_hours_observed} hrs (trailing 7 days)</div>
          </div>
          <h3 style="font-size: 0.95rem; font-weight: 600; margin-top: 14px;">Metric 3-Sigma Rolling Baselines:</h3>
        `;

        if (data.metric_breakdown && data.metric_breakdown.length > 0) {
          breakdownHtml += data.metric_breakdown.map(m => `
            <div class="breakdown-card">
              <div style="font-weight: 600; font-size: 0.9rem; color: var(--primary); margin-bottom: 8px;">
                ${m.metric_name}
              </div>
              <div class="breakdown-row">
                <span style="color: var(--text-muted);">Baseline Mean (μ):</span>
                <span>${Number(m.mean).toFixed(3)}</span>
              </div>
              <div class="breakdown-row">
                <span style="color: var(--text-muted);">Standard Dev (σ):</span>
                <span>${Number(m.std).toFixed(3)}</span>
              </div>
              <div class="breakdown-row">
                <span style="color: var(--text-muted);">3-Sigma Threshold (μ + 3σ):</span>
                <span style="font-weight: 600; color: #fbbf24;">${Number(m.threshold_3sigma).toFixed(3)}</span>
              </div>
              <div class="breakdown-row">
                <span style="color: var(--text-muted);">Breaches in Recent 7 Days:</span>
                <span style="font-weight: 700; color: ${m.recent_breaches_count > 0 ? '#ef4444' : '#10b981'};">
                  ${m.recent_breaches_count} hours
                </span>
              </div>
            </div>
          `).join('');
        }

        document.getElementById('modalBody').innerHTML = breakdownHtml;
      } catch (err) {
        document.getElementById('modalBody').innerHTML = `<p style="color: var(--danger);">Network Error: ${err.message}</p>`;
      }
    }

    async function runPipeline() {
      btnRunPipeline.disabled = true;
      btnRunPipeline.innerHTML = '<span class="spinner"></span> Running Batch Pipeline...';

      try {
        const res = await fetch('/pipeline/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ output_path: 'predictions.csv' })
        });

        if (res.ok) {
          const data = await res.json();
          showToast(`Pipeline complete! Generated ${data.total_predictions_generated} records to ${data.output_path}`);
          loadRecommendations();
        } else {
          const err = await res.json();
          showToast(`Error: ${err.detail || 'Pipeline failed'}`);
        }
      } catch (err) {
        showToast(`Failed: ${err.message}`);
      } finally {
        btnRunPipeline.disabled = false;
        btnRunPipeline.innerHTML = '<span>Trigger Live Pipeline Run</span>';
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    weekSelect.addEventListener('change', loadRecommendations);
    limitSelect.addEventListener('change', loadRecommendations);
    searchInput.addEventListener('input', renderTable);
    btnRunPipeline.addEventListener('click', runPipeline);
    modalCloseBtn.addEventListener('click', () => { detailModal.style.display = 'none'; });
    detailModal.addEventListener('click', (e) => {
      if (e.target === detailModal) detailModal.style.display = 'none';
    });

    // Initial load
    loadHealth();
    loadRecommendations();
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def get_dashboard() -> HTMLResponse:
    """Serve the Gateway Anomaly Prioritization interactive operations and analytics dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML, status_code=200)
