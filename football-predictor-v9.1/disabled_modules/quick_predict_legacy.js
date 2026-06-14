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
