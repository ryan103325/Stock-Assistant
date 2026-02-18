/**
 * 基本面分析模組 — GitHub Actions 版
 * 前端觸發 GitHub workflow → polling 結果 JSON → 渲染
 */

// === 設定 ===
const GITHUB_OWNER = 'ryan103325';
const GITHUB_REPO = 'Stock-Assistant';
const WORKFLOW_FILE = 'step_fundamental_master.yml';
const RESULT_BASE_URL = `https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/main/docs/data/fundamental`;

// === 頁籤切換 ===
document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tfBtns = document.getElementById('timeframeBtns');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;

            // 更新按鈕狀態
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // 切換頁籤
            document.querySelectorAll('.tab-content').forEach(el => {
                el.classList.remove('active');
            });
            document.getElementById(`${tab}-tab`).classList.add('active');

            // 技術分析才顯示日線/週線切換
            tfBtns.style.display = tab === 'technical' ? 'flex' : 'none';
        });
    });

    // 開始分析按鈕
    document.getElementById('startAnalysis').addEventListener('click', startFundamentalAnalysis);

    // Token 設定按鈕
    document.getElementById('configToken').addEventListener('click', configureToken);
});

// === GitHub Token 管理 ===
function getToken() {
    return localStorage.getItem('github_pat') || '';
}

function configureToken() {
    const current = getToken();
    const token = prompt(
        'GitHub Personal Access Token (PAT)\n\n' +
        '需要 workflow (read & write) 權限的 Fine-grained token\n' +
        '建立方式: GitHub → Settings → Developer settings → Fine-grained tokens\n\n' +
        '目前' + (current ? '已設定' : '未設定'),
        current
    );

    if (token !== null) {
        if (token.trim()) {
            localStorage.setItem('github_pat', token.trim());
            showAnalysisStatus('✅ Token 已儲存', 'success');
        } else {
            localStorage.removeItem('github_pat');
            showAnalysisStatus('🗑️ Token 已移除', 'warning');
        }
    }
}

// === 分析觸發 ===
async function startFundamentalAnalysis() {
    const stockId = document.getElementById('stockId').textContent;
    if (!stockId || stockId === '--') {
        showAnalysisStatus('⚠️ 請先查詢一檔股票', 'warning');
        return;
    }

    // 先檢查是否有快取結果
    showAnalysisStatus('🔍 檢查是否有已存在的分析結果...', 'loading');
    const cached = await fetchCachedResult(stockId);
    if (cached) {
        const cacheTime = new Date(cached.timestamp);
        const now = new Date();
        const hoursDiff = (now - cacheTime) / (1000 * 60 * 60);

        // 顯示快取結果
        renderFundamentalResult(cached);
        showAnalysisStatus(
            `📋 顯示快取結果 (${formatTimeAgo(cacheTime)})。點擊「重新分析」可更新。`,
            'success'
        );
        showRefreshBtn(stockId);
        return;
    }

    // 沒有快取，觸發新分析
    await triggerAnalysis(stockId);
}

async function triggerAnalysis(stockId) {
    const token = getToken();
    if (!token) {
        showAnalysisStatus(
            '🔑 需要設定 GitHub Token 才能觸發分析。請點擊右側 ⚙️ 設定。',
            'warning'
        );
        return;
    }

    const btn = document.getElementById('startAnalysis');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = '觸發中...';
    btn.querySelector('.btn-icon').textContent = '⏳';

    try {
        // 觸發 GitHub Actions workflow
        showAnalysisStatus('🚀 觸發 GitHub Actions 分析...', 'loading');

        const res = await fetch(
            `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
            {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Accept': 'application/vnd.github.v3+json',
                },
                body: JSON.stringify({
                    ref: 'main',
                    inputs: {
                        stock_id: stockId,
                        force_mode: 'true',
                        no_telegram: 'true',
                    }
                })
            }
        );

        if (res.status === 204) {
            showAnalysisStatus('✅ 已觸發分析！正在等待結果 (預計 2~3 分鐘)...', 'loading');
            btn.querySelector('.btn-text').textContent = '等待結果中...';

            // 開始 polling
            await pollForResult(stockId);
        } else if (res.status === 401 || res.status === 403) {
            showAnalysisStatus('❌ Token 無效或權限不足。請重新設定 Token (⚙️)', 'error');
        } else if (res.status === 422) {
            showAnalysisStatus('❌ Workflow 不存在或參數錯誤', 'error');
        } else {
            const err = await res.json().catch(() => ({}));
            showAnalysisStatus(`❌ 觸發失敗: ${res.status} ${err.message || ''}`, 'error');
        }
    } catch (e) {
        showAnalysisStatus(`❌ 網路錯誤: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').textContent = '開始基本面分析';
        btn.querySelector('.btn-icon').textContent = '🔬';
    }
}

// === Polling ===
async function pollForResult(stockId, maxMinutes = 5) {
    const startTime = Date.now();
    const maxMs = maxMinutes * 60 * 1000;
    const interval = 15000; // 每 15 秒

    let dots = 0;
    while (Date.now() - startTime < maxMs) {
        await sleep(interval);

        dots = (dots + 1) % 4;
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        showAnalysisStatus(
            `⏳ 等待分析結果${'.'.repeat(dots + 1)} (已等待 ${elapsed} 秒)`,
            'loading'
        );

        const result = await fetchCachedResult(stockId);
        if (result) {
            const resultTime = new Date(result.timestamp);
            // 確認是新結果 (在觸發之後產生的)
            if (resultTime.getTime() > startTime - 60000) {
                renderFundamentalResult(result);
                showAnalysisStatus('✅ 分析完成！', 'success');
                return;
            }
        }
    }

    showAnalysisStatus('⏰ 等待超時。請到 GitHub Actions 查看執行狀態。', 'warning');
}

async function fetchCachedResult(stockId) {
    try {
        // 加 timestamp 防止瀏覽器快取
        const url = `${RESULT_BASE_URL}/${stockId}.json?t=${Date.now()}`;
        const res = await fetch(url, { cache: 'no-store' });
        if (res.ok) {
            return await res.json();
        }
    } catch (e) {
        // 檔案不存在
    }
    return null;
}

// === UI Helpers ===
function showAnalysisStatus(message, type) {
    const el = document.getElementById('analysisStatus');
    el.textContent = message;
    el.className = `analysis-status ${type}`;
}

function showRefreshBtn(stockId) {
    const el = document.getElementById('analysisStatus');
    const refreshBtn = document.createElement('button');
    refreshBtn.textContent = '🔄 重新分析';
    refreshBtn.className = 'refresh-btn';
    refreshBtn.onclick = () => triggerAnalysis(stockId);
    el.appendChild(refreshBtn);
}

function formatTimeAgo(date) {
    const now = new Date();
    const diff = now - date;
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (mins < 60) return `${mins} 分鐘前`;
    if (hours < 24) return `${hours} 小時前`;
    return `${days} 天前`;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// === 渲染結果 ===
function renderFundamentalResult(data) {
    document.getElementById('fundResult').style.display = 'block';

    // Z-Score
    const zScore = data.scores?.z_score;
    if (zScore) {
        document.getElementById('zScoreValue').textContent =
            zScore.value != null ? zScore.value.toFixed(2) : 'N/A';
        const badge = document.getElementById('zScoreBadge');
        badge.textContent = zScore.rating || '--';
        badge.className = `score-badge ${getZoneClass(zScore.rating)}`;
    }

    // F-Score
    const fScore = data.scores?.f_score;
    if (fScore) {
        document.getElementById('fScoreValue').textContent =
            fScore.value != null ? `${fScore.value}/9` : 'N/A';
        const badge = document.getElementById('fScoreBadge');
        const level = fScore.value >= 8 ? '強勢' : fScore.value >= 4 ? '中性' : '惡化';
        badge.textContent = level;
        badge.className = `score-badge ${fScore.value >= 8 ? 'good' : fScore.value >= 4 ? 'neutral' : 'bad'}`;
    }

    // M-Score
    const mScore = data.scores?.m_score;
    if (mScore) {
        document.getElementById('mScoreValue').textContent =
            mScore.value != null ? mScore.value.toFixed(2) : 'N/A';
        const badge = document.getElementById('mScoreBadge');
        const isPASS = mScore.probability?.includes('PASS') || mScore.probability?.includes('✅');
        badge.textContent = isPASS ? 'PASS' : 'FAIL';
        badge.className = `score-badge ${isPASS ? 'good' : 'bad'}`;
    }

    // ROIC
    const roic = data.scores?.roic;
    document.getElementById('roicValue').textContent =
        roic != null ? `${roic.toFixed(1)}%` : 'N/A';
    const roicBadge = document.getElementById('roicBadge');
    if (roic != null) {
        roicBadge.textContent = roic > 25 ? '優異' : roic > 15 ? '良好' : roic > 10 ? '一般' : '偏低';
        roicBadge.className = `score-badge ${roic > 15 ? 'good' : roic > 10 ? 'neutral' : 'bad'}`;
    }

    // Lynch
    const lynch = data.scores?.lynch;
    document.getElementById('lynchValue').textContent = lynch || '--';
    const lynchDetail = data.scores?.lynch_detail;
    if (lynchDetail?.eps_cagr != null) {
        document.getElementById('lynchBadge').textContent = `CAGR ${lynchDetail.eps_cagr.toFixed(1)}%`;
        document.getElementById('lynchBadge').className = 'score-badge neutral';
    }

    // Earnings Yield
    const eyData = data.scores?.earnings_yield;
    document.getElementById('eyValue').textContent =
        eyData != null ? `${eyData.toFixed(1)}%` : 'N/A';
    const eyBadge = document.getElementById('eyBadge');
    if (eyData != null) {
        eyBadge.textContent = eyData > 10 ? '極具吸引力' : eyData > 6 ? '合理' : eyData > 3 ? '偏高' : '過高';
        eyBadge.className = `score-badge ${eyData > 6 ? 'good' : eyData > 3 ? 'neutral' : 'bad'}`;
    }

    // 財務比率
    renderRatios(data.ratios);

    // AI 分析
    const aiEl = document.getElementById('aiSummary');
    const aiData = data.ai_analysis;
    if (aiData?.summary) {
        let html = `<p>${aiData.summary.replace(/\n/g, '<br>')}</p>`;
        if (aiData.overall_score != null) {
            html += `<div class="ai-score">綜合評分: <strong>${aiData.overall_score}/10</strong></div>`;
        }
        if (aiData.recommendation) {
            html += `<div class="ai-recommendation">${aiData.recommendation}</div>`;
        }
        aiEl.innerHTML = html;
    }

    // Lynch 策略提示
    if (lynchDetail?.strategy) {
        const strategyEl = document.createElement('div');
        strategyEl.className = 'ai-recommendation';
        strategyEl.textContent = `🎯 Lynch 策略: ${lynchDetail.strategy}`;
        document.getElementById('aiSummary').appendChild(strategyEl);
    }
}

function renderRatios(ratios) {
    if (!ratios) return;
    const grid = document.getElementById('ratioGrid');

    const items = [
        { key: 'pe', label: '本益比', fmt: v => v?.toFixed(1) },
        { key: 'pb', label: '股價淨值比', fmt: v => v?.toFixed(2) },
        { key: 'roe', label: 'ROE', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'roa', label: 'ROA', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'gross_margin', label: '毛利率', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'operating_margin', label: '營業利益率', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'net_margin', label: '稅後淨利率', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'current_ratio', label: '流動比率', fmt: v => v?.toFixed(2) },
        { key: 'debt_ratio', label: '負債比率', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'dividend_yield', label: '殖利率', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
        { key: 'revenue_growth', label: '營收成長率', fmt: v => v != null ? `${v.toFixed(1)}%` : null },
    ];

    grid.innerHTML = items.map(({ key, label, fmt }) => {
        const val = ratios[key];
        const display = val != null ? fmt(val) : 'N/A';
        return `<div class="ratio-item">
            <span class="ratio-label">${label}</span>
            <span class="ratio-value">${display}</span>
        </div>`;
    }).join('');
}

function getZoneClass(rating) {
    if (!rating) return '';
    if (rating.includes('Safe') || rating.includes('🟢')) return 'good';
    if (rating.includes('Grey') || rating.includes('🟡')) return 'neutral';
    if (rating.includes('Distress') || rating.includes('🔴')) return 'bad';
    return '';
}
