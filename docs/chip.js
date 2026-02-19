/**
 * 籌碼面分析模組
 * 架構與 fundamental.js 相同：觸發 GitHub Actions → 追蹤進度 → 讀取 JSON → 渲染
 */

const CHIP_WORKFLOW_FILE = 'step_chip_analysis.yml';
const CHIP_STEP_PROGRESS = {
    'Checkout code': { pct: 10, label: '📥 下載程式碼...' },
    'Set up Python': { pct: 20, label: '🐍 設定 Python 環境...' },
    'Install Python dependencies': { pct: 35, label: '📦 安裝套件...' },
    'Run Chip Analysis': { pct: 70, label: '🔍 抓取籌碼資料並評分中...' },
    'Commit outputs': { pct: 90, label: '💾 儲存結果...' },
};

// 儲存最新的 raw_data 供分點週期切換用
let _chipRawData = null;

// === 初始化 ===
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('startChipAnalysis').addEventListener('click', startChipAnalysis);
    document.getElementById('configChipToken').addEventListener('click', configureToken);
});

// === 主流程 ===
async function startChipAnalysis() {
    const stockId = document.getElementById('stockId').textContent;
    if (!stockId || stockId === '--') {
        updateChipStatus('⚠️ 請先查詢一檔股票', 'warning', null);
        return;
    }

    const token = getToken();
    if (!token) {
        updateChipStatus('🔑 需要設定 GitHub Token 才能觸發分析。請點擊 ⚙️ 設定。', 'warning', null);
        return;
    }

    await triggerChipAndTrack(stockId, token);
}

// === 觸發 + 追蹤 ===
async function triggerChipAndTrack(stockId, token) {
    const btn = document.getElementById('startChipAnalysis');
    btn.disabled = true;
    btn.querySelector('.btn-text').textContent = '分析中...';
    btn.querySelector('.btn-icon').textContent = '⏳';

    try {
        const triggerTime = new Date().toISOString();

        updateChipStatus('🚀 觸發 GitHub Actions...', 'loading', null);
        const triggerRes = await ghFetch(
            `${GITHUB_API}/actions/workflows/${CHIP_WORKFLOW_FILE}/dispatches`,
            token,
            {
                method: 'POST',
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

        if (triggerRes.status === 204) {
            updateChipProgress(0, '⏳ 等待 GitHub 排隊...', '正在排入佇列');
            const runId = await waitForChipRun(token, triggerTime);

            if (runId) {
                const success = await trackChipRunProgress(runId, token);
                if (success) {
                    updateChipProgress(95, '📥 讀取籌碼分析結果...', '下載結果 JSON');
                    let result = null;
                    for (let i = 0; i < 5; i++) {
                        await sleep(1500);
                        result = await fetchChipResult(stockId, token);
                        if (result) break;
                    }
                    if (result) {
                        updateChipProgress(100, '✅ 分析完成！', '完成');
                        renderChipResult(result);
                        await sleep(1000);
                        updateChipStatus('✅ 分析完成！', 'success', { stockId, token });
                    } else {
                        updateChipStatus('⚠️ 分析已完成但無法讀取結果，請稍後重試', 'warning', null);
                    }
                }
            } else {
                updateChipStatus('⏰ 無法找到 workflow run，請到 GitHub Actions 頁面查看', 'warning', null);
            }
        } else if (triggerRes.status === 401 || triggerRes.status === 403) {
            updateChipStatus('❌ Token 無效或權限不足。請重新設定 (⚙️)', 'error', null);
        } else {
            const err = await triggerRes.json().catch(() => ({}));
            updateChipStatus(`❌ 觸發失敗: ${triggerRes.status} ${err.message || ''}`, 'error', null);
        }
    } catch (e) {
        updateChipStatus(`❌ ${e.message}`, 'error', null);
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').textContent = '開始籌碼面分析';
        btn.querySelector('.btn-icon').textContent = '📊';
    }
}

// === 等待 Workflow Run ===
async function waitForChipRun(token, triggerTime, maxWait = 30000) {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
        await sleep(3000);
        const res = await ghFetch(
            `${GITHUB_API}/actions/workflows/${CHIP_WORKFLOW_FILE}/runs?per_page=1&created=>${triggerTime.slice(0, 19)}`,
            token
        );
        if (res.ok) {
            const data = await res.json();
            if (data.workflow_runs?.length > 0) return data.workflow_runs[0].id;
        }
    }
    return null;
}

// === 追蹤進度 ===
async function trackChipRunProgress(runId, token) {
    const maxMs = 10 * 60 * 1000;
    const start = Date.now();

    while (Date.now() - start < maxMs) {
        await sleep(5000);

        const runRes = await ghFetch(`${GITHUB_API}/actions/runs/${runId}`, token);
        if (!runRes.ok) continue;
        const run = await runRes.json();

        if (run.status === 'completed') {
            if (run.conclusion === 'success') return true;
            updateChipStatus(`❌ 分析失敗 (${run.conclusion})。請到 GitHub Actions 查看錯誤日誌。`, 'error', null);
            return false;
        }

        const jobRes = await ghFetch(`${GITHUB_API}/actions/runs/${runId}/jobs`, token);
        if (!jobRes.ok) continue;
        const jobData = await jobRes.json();

        if (jobData.jobs?.length > 0) {
            const steps = jobData.jobs[0].steps || [];
            let currentPct = 5, currentLabel = '⏳ 排隊中...', currentStep = '等待開始';

            for (const step of steps) {
                const mapped = CHIP_STEP_PROGRESS[step.name];
                if (step.status === 'completed' && mapped) {
                    currentPct = mapped.pct;
                    currentLabel = `✅ ${step.name}`;
                    currentStep = step.name;
                }
                if (step.status === 'in_progress' && mapped) {
                    currentPct = mapped.pct;
                    currentLabel = mapped.label;
                    currentStep = step.name;
                    break;
                }
            }
            const elapsed = Math.floor((Date.now() - start) / 1000);
            updateChipProgress(currentPct, currentLabel, `${currentStep} (${elapsed}s)`);
        }
    }

    updateChipStatus('⏰ 等待超時 (10 分鐘)。請到 GitHub Actions 查看。', 'warning', null);
    return false;
}

// === 讀取結果 JSON ===
async function fetchChipResult(stockId, token) {
    try {
        const res = await ghFetch(
            `${GITHUB_API}/contents/docs/data/chip/${stockId}.json?ref=main`,
            token
        );
        if (res.ok) {
            const fileData = await res.json();
            const binaryString = atob(fileData.content.replace(/\n/g, ''));
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
            return JSON.parse(new TextDecoder('utf-8').decode(bytes));
        }
    } catch (e) { /* 檔案不存在 */ }
    return null;
}

// === 渲染結果 ===
function renderChipResult(data) {
    const resultEl = document.getElementById('chipResult');
    resultEl.style.display = 'block';

    const total = data.total_score ?? 0;
    const rating = data.rating ?? '--';
    const ratingEn = data.rating_en ?? '';

    // 總分儀表
    document.getElementById('chipTotalScore').textContent = total;
    document.getElementById('chipRating').textContent = rating;
    document.getElementById('chipRatingEn').textContent = ratingEn;

    const ratingEl = document.getElementById('chipRatingBadge');
    ratingEl.className = 'chip-rating-badge ' + (
        total > 80 ? 'strong-buy' : total >= 60 ? 'bullish' : 'neutral'
    );

    // 總分進度條
    const bar = document.getElementById('chipScoreBar');
    bar.style.width = `${total}%`;
    bar.className = 'chip-score-bar-fill ' + (
        total > 80 ? 'bar-strong' : total >= 60 ? 'bar-bullish' : 'bar-neutral'
    );

    // 分析日期
    const dateEl = document.getElementById('chipAnalysisDate');
    const rawDate = data.raw_data?.ownership?.data_date || data.analysis_date || '--';
    if (dateEl) dateEl.textContent = `資料日期：${rawDate}`;

    // 儲存 raw_data
    _chipRawData = data.raw_data || {};

    // 四維度卡片
    const dims = data.dimensions || {};
    renderDimCard('dimInstitutional', '法人動能', dims.institutional, 30);
    renderDimCard('dimOwnership', '股東結構', dims.ownership, 30);
    renderBrokerCard(dims.broker, data.raw_data);
    renderDimCard('dimSentiment', '市場情緒', dims.sentiment, 20);

    // 亮點
    const highlightsEl = document.getElementById('chipHighlights');
    if (data.highlights?.length) {
        highlightsEl.innerHTML = data.highlights.map(h =>
            `<div class="chip-highlight-item">✅ ${h}</div>`
        ).join('');
    } else {
        highlightsEl.innerHTML = '<div class="chip-highlight-item">無特別亮點</div>';
    }

    // 風險警示
    const risksEl = document.getElementById('chipRisks');
    const risksSection = document.getElementById('chipRisksSection');
    if (data.risks?.length) {
        risksSection.style.display = 'block';
        risksEl.innerHTML = data.risks.map(r =>
            `<div class="chip-risk-item">${r}</div>`
        ).join('');
    } else {
        risksSection.style.display = 'none';
    }

    // 策略建議
    document.getElementById('chipStrategy').textContent = data.strategy || '--';

    // 低成交量警示
    const lowVolEl = document.getElementById('chipLowVolWarning');
    if (lowVolEl) lowVolEl.style.display = data.low_volume_penalty ? 'block' : 'none';

    // 原始資料（可折疊）
    renderRawData(data.raw_data);
}

function renderDimCard(elId, label, dim, maxScore) {
    const el = document.getElementById(elId);
    if (!el || !dim) return;

    const score = dim.score ?? 0;
    const pct = (score / maxScore) * 100;
    const cls = pct >= 70 ? 'dim-good' : pct >= 40 ? 'dim-mid' : 'dim-low';

    el.innerHTML = `
        <div class="dim-label">${label}</div>
        <div class="dim-score">${score} <span class="dim-max">/ ${maxScore}</span></div>
        <div class="dim-bar-bg">
            <div class="dim-bar-fill ${cls}" style="width:${pct}%"></div>
        </div>
        <div class="dim-notes">
            ${dim.trust_note ? `<div class="dim-note">• ${dim.trust_note}</div>` : ''}
            ${dim.trust_turning ? `<div class="dim-note dim-warning">• ${dim.trust_turning}</div>` : ''}
            ${dim.foreign_note ? `<div class="dim-note">• ${dim.foreign_note}</div>` : ''}
            ${dim.align_note ? `<div class="dim-note">• ${dim.align_note}</div>` : ''}
            ${dim.dealer_5d != null ? `<div class="dim-note">• 自營商近5日：${dim.dealer_5d > 0 ? '買超' : '賣超'} ${Math.abs(dim.dealer_5d).toLocaleString()} 張</div>` : ''}
            ${dim.whale_note ? `<div class="dim-note">• ${dim.whale_note}</div>` : ''}
            ${dim.whale_warning ? `<div class="dim-note dim-warning">• ${dim.whale_warning}</div>` : ''}
            ${dim.holders_note ? `<div class="dim-note">• ${dim.holders_note}</div>` : ''}
            ${dim.avg_note ? `<div class="dim-note">• ${dim.avg_note}</div>` : ''}
            ${dim.margin_note ? `<div class="dim-note">• ${dim.margin_note}</div>` : ''}
            ${dim.squeeze_note ? `<div class="dim-note">• ${dim.squeeze_note}</div>` : ''}
        </div>
    `;
}

// === 分點卡片（含週期切換）===
function renderBrokerCard(dim, raw) {
    const el = document.getElementById('dimBroker');
    if (!el) return;

    const score = dim?.score ?? 0;
    const maxScore = 20;
    const pct = (score / maxScore) * 100;
    const cls = pct >= 70 ? 'dim-good' : pct >= 40 ? 'dim-mid' : 'dim-low';

    el.innerHTML = `
        <div class="dim-label">關鍵分點</div>
        <div class="dim-score">${score} <span class="dim-max">/ ${maxScore}</span></div>
        <div class="dim-bar-bg">
            <div class="dim-bar-fill ${cls}" style="width:${pct}%"></div>
        </div>
        <div class="dim-notes">
            ${dim?.intent_label ? `<div class="dim-note" style="font-weight:600;">${dim.intent_label}</div>` : ''}
            ${dim?.long_note ? `<div class="dim-note">• ${dim.long_note}</div>` : ''}
            ${dim?.exit_note ? `<div class="dim-note">${dim.exit_note.startsWith('⚠') ? '' : '• '}${dim.exit_note}</div>` : ''}
            ${dim?.period_note ? `<div class="dim-note">• ${dim.period_note}</div>` : ''}
        </div>
        <div class="broker-period-switcher">
            <button class="broker-period-btn active" data-period="1d" onclick="switchBrokerPeriod('1d')">1日</button>
            <button class="broker-period-btn" data-period="5d" onclick="switchBrokerPeriod('5d')">5日</button>
            <button class="broker-period-btn" data-period="10d" onclick="switchBrokerPeriod('10d')">10日</button>
            <button class="broker-period-btn" data-period="20d" onclick="switchBrokerPeriod('20d')">20日</button>
            <button class="broker-period-btn" data-period="60d" onclick="switchBrokerPeriod('60d')">60日</button>
        </div>
        <div id="brokerPeriodDetail" class="dim-notes"></div>
    `;

    // 預設顯示 1 日
    switchBrokerPeriod('1d');
}

function switchBrokerPeriod(period) {
    const raw = _chipRawData;
    if (!raw) return;

    // 切換按鈕 active 狀態
    document.querySelectorAll('.broker-period-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === period);
    });

    const brokerRaw = raw.broker || {};
    const pd = brokerRaw[`broker_${period}`] || {};
    const buyList = pd.buy_brokers || [];
    const sellList = pd.sell_brokers || [];

    const fmtNet = (b) => {
        const net = parseInt(String(b.net || '0').replace(/,/g, ''), 10);
        return isNaN(net) ? 'N/A' : Math.abs(net).toLocaleString();
    };

    const detail = document.getElementById('brokerPeriodDetail');
    if (detail) {
        const top5Buy = buyList.slice(0, 5).map((b, i) =>
            `<div class="dim-note">• 買超#${i + 1}：<strong>${b.broker}</strong>（${fmtNet(b)} 張）</div>`
        ).join('');
        const top5Sell = sellList.slice(0, 5).map((b, i) =>
            `<div class="dim-note">• 賣超#${i + 1}：<strong>${b.broker}</strong>（${fmtNet(b)} 張）</div>`
        ).join('');
        detail.innerHTML = `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;">
                <div>${top5Buy || '<div class="dim-note">無資料</div>'}</div>
                <div>${top5Sell || '<div class="dim-note">無資料</div>'}</div>
            </div>
        `;
    }
}

function renderRawData(raw) {
    const el = document.getElementById('chipRawData');
    if (!el || !raw) return;

    const inst = raw.institutional || {};
    const own = raw.ownership || {};
    const bkr = raw.broker || {};
    const sent = raw.sentiment || {};

    const fmt = (v, suffix = '') => v != null ? `${typeof v === 'number' ? v.toLocaleString() : v}${suffix}` : 'N/A';

    const sections = [
        {
            title: '📊 法人動態',
            items: [
                ['投信近5日買賣超', fmt(inst.trust_buy_5d, ' 張')],
                ['投信連續買超天數', fmt(inst.trust_consecutive_days, ' 天')],
                ['外資近5日買賣超', fmt(inst.foreign_buy_5d, ' 張')],
                ['外資連續買超天數', fmt(inst.foreign_consecutive_days, ' 天')],
                ['自營商近5日買賣超', fmt(inst.dealer_buy_5d, ' 張')],
            ]
        },
        {
            title: '👥 股東結構',
            items: [
                ['大戶持股（本週）', fmt(own.whale_pct_this, '%')],
                ['大戶持股（上週）', fmt(own.whale_pct_last, '%')],
                ['總股東人數', fmt(own.total_holders_this, ' 人')],
                ['平均張數/人', fmt(own.avg_shares_this, ' 張')],
                ['資料日期', fmt(own.data_date)],
            ]
        },
        {
            title: '🏢 分點主力',
            items: [
                ['主力近5日淨買超', fmt(bkr.main_force_net_5d, ' 張')],
                ['主力連續買超天數', fmt(bkr.main_force_consecutive, ' 天')],
                ...['1d', '5d', '10d', '20d', '60d'].map(p => {
                    const pd = bkr[`broker_${p}`] || {};
                    return [`近${p}買超第一`, pd.top_buy_broker ? `${pd.top_buy_broker}（${fmt(pd.top_buy_net, ' 張')}）` : 'N/A'];
                }),
            ]
        },
        {
            title: '📈 市場情緒',
            items: [
                ['融資近5日增減', fmt(sent.margin_change, ' 張')],
                ['券資比', fmt(sent.short_ratio, '%')],
            ]
        },
    ];

    el.innerHTML = sections.map(s => `
        <div class="raw-section">
            <div class="raw-section-title">${s.title}</div>
            ${s.items.map(([label, val]) =>
        `<div class="raw-item"><span class="raw-label">${label}</span><span class="raw-value">${val}</span></div>`
    ).join('')}
        </div>
    `).join('');
}

// === UI 更新 ===
function updateChipStatus(message, type, refreshInfo) {
    const container = document.getElementById('chipAnalysisStatus');
    const existing = document.getElementById('chipProgressContainer');
    if (existing) existing.remove();

    container.innerHTML = '';
    container.textContent = message;
    container.className = `analysis-status ${type}`;

    if (refreshInfo) {
        const btn = document.createElement('button');
        btn.textContent = '🔄 重新分析';
        btn.className = 'refresh-btn';
        btn.onclick = () => triggerChipAndTrack(refreshInfo.stockId, refreshInfo.token);
        container.appendChild(btn);
    }
}

function updateChipProgress(pct, label, stepName) {
    let container = document.getElementById('chipProgressContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'chipProgressContainer';
        container.className = 'progress-container';
        document.getElementById('chipAnalysisStatus').innerHTML = '';
        document.getElementById('chipAnalysisStatus').className = 'analysis-status';
        document.getElementById('chipAnalysisStatus').appendChild(container);
    }
    container.innerHTML = `
        <div class="progress-label">${label}</div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: ${pct}%"></div>
        </div>
        <div class="progress-detail">${stepName} — ${pct}%</div>
    `;
}
