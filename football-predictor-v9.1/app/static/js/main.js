/* Football Predictor V9.0 - Main JavaScript */

// ── Sidebar toggle ──────────────────────────────────────────────
document.getElementById('sidebarToggle')?.addEventListener('click', () => {
    const sidebar = document.getElementById('sidebar');
    const main = document.getElementById('main-content');
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle('show');
    } else {
        const collapsed = sidebar.style.width === '0px';
        sidebar.style.width = collapsed ? '240px' : '0px';
        main.style.marginLeft = collapsed ? '240px' : '0px';
    }
});

// ── Toast notifications ─────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const id = 'toast-' + Date.now();
    const colors = {
        success: 'text-bg-success',
        error: 'text-bg-danger',
        info: 'text-bg-info',
        warning: 'text-bg-warning',
    };
    const html = `
        <div id="${id}" class="toast align-items-center ${colors[type] || 'text-bg-secondary'} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body fw-500">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>`;
    container.insertAdjacentHTML('beforeend', html);
    const el = document.getElementById(id);
    const toast = new bootstrap.Toast(el, { delay: 4500 });
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
}

// ── Loading overlay ─────────────────────────────────────────────
function showLoading(message = 'Ejecutando simulación Monte Carlo...') {
    if (document.getElementById('loadingOverlay')) return;
    const div = document.createElement('div');
    div.id = 'loadingOverlay';
    div.className = 'spinner-overlay';
    div.innerHTML = `
        <div class="spinner-border" role="status"></div>
        <p class="mt-3">${message}</p>
        <small class="text-muted">Por favor espera...</small>`;
    document.body.appendChild(div);
}

function hideLoading() {
    document.getElementById('loadingOverlay')?.remove();
}

// ── API helper ──────────────────────────────────────────────────
async function apiCall(url, method = 'GET', body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }
    return res.json();
}

// ── Probability bar renderer ────────────────────────────────────
function renderProbBar(homeProb, drawProb, awayProb, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const h = Math.round(homeProb * 100);
    const d = Math.round(drawProb * 100);
    const a = 100 - h - d;
    el.innerHTML = `
        <div class="prob-bar-container mb-1">
            <div class="prob-bar-home" style="width:${h}%">${h > 9 ? h + '%' : ''}</div>
            <div class="prob-bar-draw" style="width:${d}%">${d > 9 ? d + '%' : ''}</div>
            <div class="prob-bar-away" style="width:${a}%">${a > 9 ? a + '%' : ''}</div>
        </div>
        <div class="d-flex justify-content-between" style="font-size:0.78rem">
            <span style="color:#58a6ff;font-weight:600">${h}% Local</span>
            <span style="color:#6e7681;font-weight:600">${d}% Empate</span>
            <span style="color:#da3633;font-weight:600">${a}% Visitante</span>
        </div>`;
}

// ── Score distribution renderer ─────────────────────────────────
function renderScoreDistribution(scoreData, containerId) {
    const el = document.getElementById(containerId);
    if (!el || !scoreData) return;
    const sorted = Object.entries(scoreData).sort((a, b) => b[1] - a[1]).slice(0, 18);
    el.innerHTML = sorted.map(([score, prob], i) => `
        <div class="score-item ${i === 0 ? 'top-score' : ''}">
            <span class="fw-700" style="font-size:0.82rem">${score}</span>
            <span class="score-prob">${(prob * 100).toFixed(1)}%</span>
        </div>`).join('');
}

// ── Variable predictions renderer ───────────────────────────────
function renderVariablePreds(varPreds, containerId) {
    const el = document.getElementById(containerId);
    if (!el || !varPreds) return;
    const labels = { xg: 'xG', elo: 'ELO', form: 'Forma', market: 'Mercado', ranking: 'Ranking' };
    el.innerHTML = Object.entries(varPreds).map(([name, data]) => `
        <div class="var-pred-card">
            <div class="var-pred-title">${labels[name] || name}</div>
            <div class="d-flex gap-1 flex-wrap mb-1">
                <span class="badge" style="background:rgba(31,111,235,0.2);color:#58a6ff">${Math.round(data.home_win_prob * 100)}% L</span>
                <span class="badge" style="background:rgba(110,118,129,0.2);color:#9ea8b5">${Math.round(data.draw_prob * 100)}% E</span>
                <span class="badge" style="background:rgba(218,54,51,0.2);color:#f85149">${Math.round(data.away_win_prob * 100)}% V</span>
            </div>
            <div class="text-muted" style="font-size:0.72rem">${(data.home_goals_exp || data.home_goals_expected || 0).toFixed(2)} - ${(data.away_goals_exp || data.away_goals_expected || 0).toFixed(2)}</div>
        </div>`).join('');
}

// ── World Cup probability list renderer ─────────────────────────
function renderWCProbList(probs, containerId, limit = 12, showFlag = false) {
    const el = document.getElementById(containerId);
    if (!el || !probs) return;
    const entries = Object.entries(probs).slice(0, limit);
    const maxVal = entries[0]?.[1] || 100;

    el.innerHTML = entries.map(([team, prob], i) => {
        const flagCode = FLAG_CODES[team] || 'un';
        const flagHtml = showFlag
            ? `<img src="https://flagcdn.com/20x15/${flagCode}.png" class="wc-team-flag" alt="${team}" onerror="this.style.display='none'">`
            : '';
        return `
        <div class="wc-team-row">
            <div class="wc-team-rank">${i + 1}</div>
            ${flagHtml}
            <div class="wc-team-name">${team}</div>
            <div class="wc-prob-bar"><div class="wc-prob-fill" style="width:${(prob/maxVal*100).toFixed(1)}%"></div></div>
            <div class="wc-prob-value">${prob}%</div>
        </div>`;
    }).join('');
}

const FLAG_CODES = {
    "Argentina": "ar", "France": "fr", "Brazil": "br", "England": "gb-eng",
    "Spain": "es", "Belgium": "be", "Portugal": "pt", "Netherlands": "nl",
    "Germany": "de", "Italy": "it", "Croatia": "hr", "Denmark": "dk",
    "Uruguay": "uy", "Morocco": "ma", "USA": "us", "Mexico": "mx",
    "Colombia": "co", "Switzerland": "ch", "Japan": "jp", "Senegal": "sn",
    "South Korea": "kr", "Ecuador": "ec", "Poland": "pl", "Ivory Coast": "ci",
    "Serbia": "rs", "Chile": "cl", "Egypt": "eg", "Iran": "ir", "IR Iran": "ir",
    "Australia": "au", "Peru": "pe", "Nigeria": "ng", "Cameroon": "cm",
    "Saudi Arabia": "sa", "Qatar": "qa", "Canada": "ca", "Algeria": "dz",
    "Ghana": "gh", "Bolivia": "bo", "Costa Rica": "cr", "Paraguay": "py",
    "Bahrain": "bh", "New Zealand": "nz", "Jamaica": "jm", "Slovenia": "si",
    "South Africa": "za", "Sweden": "se", "Ukraine": "ua", "Tunisia": "tn",
    "Venezuela": "ve", "Turkey": "tr",
};

// ── Utilities ───────────────────────────────────────────────────
function refreshData() { location.reload(); }
function pct(val) { return (val * 100).toFixed(1) + '%'; }
function fmt2(val) { return parseFloat(val).toFixed(2); }

// ── Quick predict helper (used on index page) ───────────────────
async function quickPredict() {
    const home = document.getElementById('quickHome')?.value.trim();
    const away = document.getElementById('quickAway')?.value.trim();
    if (!home || !away) { showToast('Ingresa ambos equipos', 'warning'); return; }
    showLoading('Predicción rápida...');
    try {
        const data = await apiCall('/api/predict', 'POST', { home_team: home, away_team: away });
        hideLoading();
        if (data.success) {
            const d = data.data;
            const dbBadge = (b) => b ? '<span class="badge bg-success ms-1" style="font-size:0.6rem">DB</span>' : '';
            document.getElementById('quickResult').innerHTML = `
                <div class="prediction-result">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <span class="team-name">${d.home_team}${dbBadge(d.home_from_db)}</span>
                        <span class="badge bg-warning text-dark" style="font-size:1.3rem;padding:0.5rem 1rem;letter-spacing:2px">${d.most_likely_score}</span>
                        <span class="team-name text-end">${d.away_team}${dbBadge(d.away_from_db)}</span>
                    </div>
                    <div id="qpBar" class="mb-3"></div>
                    <div class="row g-2">
                        <div class="col-4"><div class="market-badge"><div class="market-value">${(d.btts_prob*100).toFixed(1)}%</div>BTTS</div></div>
                        <div class="col-4"><div class="market-badge"><div class="market-value">${(d.over_25_prob*100).toFixed(1)}%</div>Over 2.5</div></div>
                        <div class="col-4"><div class="market-badge"><div class="market-value">${(d.confidence_score*100).toFixed(1)}%</div>Confianza</div></div>
                    </div>
                    <div class="mt-2 text-center">
                        <span class="badge bg-warning text-dark">${d.predicted_label}</span>
                        <small class="text-muted ms-2">${d.simulations_run.toLocaleString()} simulaciones</small>
                    </div>
                </div>`;
            renderProbBar(d.home_win_prob, d.draw_prob, d.away_win_prob, 'qpBar');
        }
    } catch (e) {
        hideLoading();
        showToast('Error: ' + e.message, 'error');
    }
}
