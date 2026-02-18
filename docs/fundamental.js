/**
 * 基本面分析模組 — GitHub Actions 版 v2
 * 用 GitHub API 追蹤 workflow run 進度 + 視覺進度條
 */

// === 設定 ===
const GITHUB_OWNER = 'ryan103325';
const GITHUB_REPO = 'Stock-Assistant';
const WORKFLOW_FILE = 'step_fundamental_master.yml';
const GITHUB_API = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}`;

// === Workflow 步驟進度對照 ===
const STEP_PROGRESS = {
    'Checkout code': { pct: 5, label: '📥 下載程式碼...' },
    'Set up Python': { pct: 15, label: '🐍 設定 Python 環境...' },
    'Install system dependencies': { pct: 25, label: '📦 安裝系統依賴...' },
    'Install Python dependencies': { pct: 35, label: '📦 安裝 Python 套件...' },
    'Install Playwright browsers': { pct: 45, label: '🌐 安裝瀏覽器...' },
    'Run Fundamental Analysis': { pct: 60, label: '🔬 執行基本面分析中...' },
    'Commit outputs': { pct: 90, label: '💾 儲存結果...' },
};

// === 頁籤切換 ===
document.addEventListener('DOMContentLoaded', () => {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tfBtns = document.getElementById('timeframeBtns');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById(`${tab}-tab`).classList.add('active');
            tfBtns.style.display = tab === 'technical' ? 'flex' : 'none';
        });
    });

    document.getElementById('startAnalysis').addEventListener('click', startFundamentalAnalysis);
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
        '需要 Actions (read & write) + Contents (read) 權限\n' +
        '建立: GitHub → Settings → Developer settings → Fine-grained tokens\n\n' +
        '目前' + (current ? '已設定' : '未設定'),
        current
    );

    if (token !== null) {
        if (token.trim()) {
            localStorage.setItem('github_pat', token.trim());
            updateStatusUI('✅ Token 已儲存', 'success', null);
        } else {
            localStorage.removeItem('github_pat');
            updateStatusUI('🗑️ Token 已移除', 'warning', null);
        }
    }
}

// === 主流程 ===
async function startFundamentalAnalysis() {
    const stockId = document.getElementById('stockId').textContent;
    if (!stockId || stockId === '--') {
        updateStatusUI('⚠️ 請先查詢一檔股票', 'warning', null);
        return;
    }

    const token = getToken();
    if (!token) {
        updateStatusUI('🔑 需要設定 GitHub Token 才能觸發分析。請點擊 ⚙️ 設定。', 'warning', null);
        return;
    }

    // 先檢查快取
    updateStatusUI('🔍 檢查已存在的分析結果...', 'loading', null);
    const cached = await fetchResult(stockId, token);
    if (cached) {
        renderFundamentalResult(cached);
        const cacheTime = new Date(cached.timestamp);
        updateStatusUI(
            `📋 顯示快取結果 (${formatTimeAgo(cacheTime)})`,
            'success',
            { stockId, token }
        );
        return;
    }

    await triggerAndTrack(stockId, token);
}

// === 觸發 + 追蹤 ===
async function triggerAndTrack(stockId, token) {
    const btn = document.getElementById('startAnalysis');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = '分析中...';
    btn.querySelector('.btn-icon').textContent = '⏳';

    try {
        // 1. 記錄觸發時間
        const triggerTime = new Date().toISOString();

        // 2. 觸發 workflow
        updateStatusUI('🚀 觸發 GitHub Actions...', 'loading', null);
        const triggerRes = await ghFetch(
            `${GITHUB_API}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
            token,
            {
                method: 'POST',
                body: JSON.stringify({
                    ref: 'main',
                    inputs: {
                        stock_id: stockId,
                        force_mode: 'true',
                        no_telegram: 'true',
                        web_only: 'true',
                    }
                })
            }
        );

        if (triggerRes.status === 204) {
            // 3. 等待 workflow run 出現
            updateProgressUI(0, '⏳ 等待 GitHub 排隊...', '正在排入佇列');
            const runId = await waitForRun(token, triggerTime);

            if (runId) {
                // 4. 追蹤進度
                const success = await trackRunProgress(runId, token);

                if (success) {
                    // 5. 讀取結果
                    updateProgressUI(95, '📥 讀取分析結果...', '下載結果 JSON');
                    await sleep(5000); // 等 GitHub commit 傳播
                    const result = await fetchResult(stockId, token);
                    if (result) {
                        updateProgressUI(100, '✅ 分析完成！', '完成');
                        renderFundamentalResult(result);
                        await sleep(1000);
                        updateStatusUI('✅ 分析完成！', 'success', { stockId, token });
                    } else {
                        updateStatusUI('⚠️ 分析已完成但無法讀取結果，請稍後重試', 'warning', null);
                    }
                }
            } else {
                updateStatusUI('⏰ 無法找到 workflow run，請到 GitHub Actions 頁面查看', 'warning', null);
            }
        } else if (triggerRes.status === 401 || triggerRes.status === 403) {
            updateStatusUI('❌ Token 無效或權限不足。請重新設定 (⚙️)', 'error', null);
        } else {
            const err = await triggerRes.json().catch(() => ({}));
            updateStatusUI(`❌ 觸發失敗: ${triggerRes.status} ${err.message || ''}`, 'error', null);
        }
    } catch (e) {
        updateStatusUI(`❌ ${e.message}`, 'error', null);
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').textContent = '開始基本面分析';
        btn.querySelector('.btn-icon').textContent = '🔬';
    }
}

// === 等待 Workflow Run 出現 ===
async function waitForRun(token, triggerTime, maxWait = 30000) {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
        await sleep(3000);
        const res = await ghFetch(
            `${GITHUB_API}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=1&created=>${triggerTime.slice(0, 19)}`,
            token
        );
        if (res.ok) {
            const data = await res.json();
            if (data.workflow_runs?.length > 0) {
                return data.workflow_runs[0].id;
            }
        }
    }
    return null;
}

// === 追蹤 Run 進度 ===
async function trackRunProgress(runId, token) {
    const maxMinutes = 10;
    const start = Date.now();
    const maxMs = maxMinutes * 60 * 1000;

    while (Date.now() - start < maxMs) {
        await sleep(5000);

        // 取得 run 狀態
        const runRes = await ghFetch(`${GITHUB_API}/actions/runs/${runId}`, token);
        if (!runRes.ok) continue;
        const run = await runRes.json();

        if (run.status === 'completed') {
            if (run.conclusion === 'success') {
                return true;
            } else {
                updateStatusUI(
                    `❌ 分析失敗 (${run.conclusion})。請到 GitHub Actions 查看錯誤日誌。`,
                    'error', null
                );
                return false;
            }
        }

        // 取得 job 步驟
        const jobRes = await ghFetch(`${GITHUB_API}/actions/runs/${runId}/jobs`, token);
        if (!jobRes.ok) continue;
        const jobData = await jobRes.json();

        if (jobData.jobs?.length > 0) {
            const job = jobData.jobs[0];
            const steps = job.steps || [];

            // 找到目前進行中的步驟
            let currentPct = 5;
            let currentLabel = '⏳ 排隊中...';
            let currentStep = '等待開始';

            for (const step of steps) {
                const mapped = STEP_PROGRESS[step.name];
                if (step.status === 'completed' && mapped) {
                    currentPct = mapped.pct;
                    currentLabel = `✅ ${step.name}`;
                    currentStep = step.name;
                }
                if (step.status === 'in_progress' && mapped) {
                    currentPct = mapped.pct;
                    currentLabel = mapped.label;
                    currentStep = step.name;
                    break; // 當前步驟
                }
            }

            const elapsed = Math.floor((Date.now() - start) / 1000);
            updateProgressUI(currentPct, currentLabel, `${currentStep} (${elapsed}s)`);
        }
    }

    updateStatusUI('⏰ 等待超時 (10 分鐘)。請到 GitHub Actions 查看。', 'warning', null);
    return false;
}

// === 取得結果 JSON ===
async function fetchResult(stockId, token) {
    try {
        // 用 GitHub API 而非 raw.githubusercontent.com (避免 CDN 快取)
        const res = await ghFetch(
            `${GITHUB_API}/contents/docs/data/fundamental/${stockId}.json?ref=main`,
            token
        );
        if (res.ok) {
            const fileData = await res.json();
            // content 是 base64 encoded — 需要正確處理 UTF-8
            const binaryString = atob(fileData.content.replace(/\n/g, ''));
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            const content = new TextDecoder('utf-8').decode(bytes);
            return JSON.parse(content);
        }
    } catch (e) {
        // 檔案不存在
    }
    return null;
}

// === UI 更新 ===
function updateStatusUI(message, type, refreshInfo) {
    const container = document.getElementById('analysisStatus');
    // 移除進度條 (如果有)
    const existing = document.getElementById('progressContainer');
    if (existing) existing.remove();

    container.innerHTML = '';
    container.textContent = message;
    container.className = `analysis-status ${type}`;

    if (refreshInfo) {
        const refreshBtn = document.createElement('button');
        refreshBtn.textContent = '🔄 重新分析';
        refreshBtn.className = 'refresh-btn';
        refreshBtn.onclick = () => triggerAndTrack(refreshInfo.stockId, refreshInfo.token);
        container.appendChild(refreshBtn);
    }
}

function updateProgressUI(pct, label, stepName) {
    let container = document.getElementById('progressContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'progressContainer';
        container.className = 'progress-container';
        document.getElementById('analysisStatus').innerHTML = '';
        document.getElementById('analysisStatus').className = 'analysis-status';
        document.getElementById('analysisStatus').appendChild(container);
    }

    container.innerHTML = `
        <div class="progress-label">${label}</div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: ${pct}%"></div>
        </div>
        <div class="progress-detail">${stepName} — ${pct}%</div>
    `;
}

// === GitHub API Helper ===
async function ghFetch(url, token, options = {}) {
    return fetch(url, {
        ...options,
        headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'application/vnd.github.v3+json',
            ...(options.headers || {}),
        }
    });
}

// === Utils ===
function formatTimeAgo(date) {
    const diff = Date.now() - date.getTime();
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
        if (mScore.value == null) {
            badge.textContent = '資料不足';
            badge.className = 'score-badge neutral';
        } else {
            const isPASS = mScore.probability?.includes('PASS') || mScore.probability?.includes('✅');
            badge.textContent = isPASS ? 'PASS' : 'FAIL';
            badge.className = `score-badge ${isPASS ? 'good' : 'bad'}`;
        }
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
            html += `<div class="ai-recommendation">🎯 建議: ${aiData.recommendation}</div>`;
        }
        if (aiData.key_monitoring) {
            html += `<div class="ai-recommendation">👁️ 關注: ${aiData.key_monitoring}</div>`;
        }
        aiEl.innerHTML = html;
    } else {
        aiEl.innerHTML = '<p>AI 分析尚無結果</p>';
    }

    if (lynchDetail?.strategy) {
        const el = document.createElement('div');
        el.className = 'ai-recommendation';
        el.textContent = `🎯 Lynch 策略: ${lynchDetail.strategy}`;
        document.getElementById('aiSummary').appendChild(el);
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
