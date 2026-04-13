/**
 * TaskQueue v2 — 分析任務排隊面板（支援並行追蹤）
 *
 * 架構：
 *   - 觸發方（fundamental.js/chip.js）只做 dispatch，dispatch 成功後立即 return
 *   - TaskQueue.track() 記錄追蹤設定，啟動集中輪詢迴圈（setInterval）
 *   - 每 6 秒 _pollAll() 對所有 pending/running 任務同時查詢 GitHub API
 *   - 完成後儲存 result，用戶點卡片可跳頁
 *
 * 任務狀態流：
 *   pending（等待 runId）→ running（追蹤進度）→ done | error
 */

// ── GitHub API helpers（與 fundamental.js 共用，後者載入後會覆蓋 ghFetch，無影響）──
const _GITHUB_API = 'https://api.github.com/repos/ryan103325/Stock-Assistant';

function _ghFetch(url, token, options = {}) {
    return fetch(url, {
        ...options,
        headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'application/vnd.github.v3+json',
            ...(options.headers || {}),
        },
    });
}

function _sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function _fetchAnalysisResult(stockId, token, type) {
    if (type === 'news') {
        // news 類型不需要抓個股 JSON，直接回傳成功標記
        return { type: 'news', stockId, success: true };
    }
    const path = type === 'chip' ? 'chip' : 'fundamental';
    try {
        const res = await _ghFetch(
            `${_GITHUB_API}/contents/docs/data/${path}/${stockId}.json?ref=main`,
            token
        );
        if (!res.ok) return null;
        const fileData = await res.json();
        const binary = atob(fileData.content.replace(/\n/g, ''));
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return JSON.parse(new TextDecoder('utf-8').decode(bytes));
    } catch { return null; }
}

// ── TaskQueue ────────────────────────────────────────────────────────────────
const TaskQueue = (() => {
    const LS_KEY = 'tq_tasks';
    const MAX_TASKS = 20;
    const POLL_INTERVAL = 6000;   // ms
    const FIND_RUN_TIMEOUT = 5 * 60 * 1000;   // 5 min
    const TRACK_TIMEOUT = 12 * 60 * 1000;  // 12 min

    let _tasks = [];
    let _panelVisible = false;
    let _intervalId = null;
    let _polling = false;

    // 追蹤設定（不存 localStorage，含 token/functions）
    const _tracking = {}; // id → { token, triggerTime, workflowFile, stepProgress, stockId, type, runStart? }

    // ── localStorage ────────────────────────────────────────────────────────
    function _load() {
        try { _tasks = JSON.parse(localStorage.getItem(LS_KEY) || '[]'); }
        catch { _tasks = []; }
    }

    function _save() {
        if (_tasks.length > MAX_TASKS) _tasks = _tasks.slice(_tasks.length - MAX_TASKS);
        try { localStorage.setItem(LS_KEY, JSON.stringify(_tasks)); } catch { }
    }

    function _getTask(id) { return _tasks.find(t => t.id === id); }

    function _uid() { return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`; }

    // ── 公開 API ─────────────────────────────────────────────────────────────
    function add({ stockId, stockName, type }) {
        _load();
        const task = {
            id: _uid(), stockId,
            stockName: stockName || stockId, type,
            status: 'pending', pct: 0, label: '等待觸發...',
            runId: null, createdAt: new Date().toISOString(),
            doneAt: null, result: null,
        };
        _tasks.push(task);
        _save();
        _render();
        _showPanel();
        return task.id;
    }

    function update(id, patches) {
        _load();
        const idx = _tasks.findIndex(t => t.id === id);
        if (idx === -1) return;
        Object.assign(_tasks[idx], patches);
        _save();
        _renderTask(_tasks[idx]);
        _updateBadge();
    }

    /** 開始背景追蹤（由 fundamental.js/chip.js dispatch 成功後立即呼叫） */
    function track(id, config) {
        // config: { token, triggerTime, workflowFile, stepProgress, stockId, type }
        _tracking[id] = {
            ...config,
            runStart: null,
        };
        update(id, { status: 'pending', label: '等待 GitHub 排入佇列...' });
        _startPollLoop();
    }

    function clearDone() {
        _load();
        // 清除追蹤設定
        _tasks.filter(t => t.status === 'done' || t.status === 'error')
            .forEach(t => delete _tracking[t.id]);
        _tasks = _tasks.filter(t => t.status !== 'done' && t.status !== 'error');
        _save();
        _render();
    }

    function getActiveCount() {
        _load();
        return _tasks.filter(t => t.status === 'running' || t.status === 'pending').length;
    }

    // ── 輪詢迴圈 ─────────────────────────────────────────────────────────────
    function _startPollLoop() {
        if (_intervalId) return; // 已在跑
        _intervalId = setInterval(_pollAll, POLL_INTERVAL);
    }

    function _stopPollLoop() {
        if (_intervalId) { clearInterval(_intervalId); _intervalId = null; }
    }

    async function _pollAll() {
        if (_polling) return; // 防重疊
        _polling = true;
        try {
            _load();
            const active = _tasks.filter(t => t.status === 'pending' || t.status === 'running');
            if (active.length === 0) { _stopPollLoop(); return; }
            // 並行輪詢所有 active 任務
            await Promise.all(active.map(t => _pollTask(t).catch(() => { })));
        } finally {
            _polling = false;
        }
    }

    async function _pollTask(task) {
        const cfg = _tracking[task.id];
        if (!cfg) return; // 無追蹤設定（可能是頁面重整前遺留的 pending 任務）

        const { token, workflowFile, stepProgress, stockId, type, triggerTime } = cfg;
        const upd = patches => update(task.id, patches);

        if (task.status === 'pending') {
            // 超時：5 分鐘還找不到 run
            if (Date.now() - new Date(task.createdAt).getTime() > FIND_RUN_TIMEOUT) {
                upd({ status: 'error', label: '找不到 workflow run' });
                delete _tracking[task.id];
                return;
            }
            try {
                const res = await _ghFetch(
                    `${_GITHUB_API}/actions/workflows/${workflowFile}/runs?per_page=1&created=>${triggerTime.slice(0, 19)}`,
                    token
                );
                if (res.ok) {
                    const data = await res.json();
                    if (data.workflow_runs?.length > 0) {
                        const runId = data.workflow_runs[0].id;
                        cfg.runStart = Date.now();
                        upd({ status: 'running', runId, label: '開始執行...' });
                    }
                }
            } catch { }

        } else if (task.status === 'running') {
            const runId = task.runId;
            if (!runId) return;

            // 超時：12 分鐘
            if (cfg.runStart && Date.now() - cfg.runStart > TRACK_TIMEOUT) {
                upd({ status: 'error', label: '等待超時 (12 min)' });
                delete _tracking[task.id];
                return;
            }

            try {
                const runRes = await _ghFetch(`${_GITHUB_API}/actions/runs/${runId}`, token);
                if (!runRes.ok) return;
                const run = await runRes.json();

                if (run.status === 'completed') {
                    if (run.conclusion === 'success') {
                        upd({ pct: 95, label: '讀取結果中...' });
                        const result = await _fetchAnalysisResult(stockId, token, type);
                        if (result) {
                            upd({ status: 'done', pct: 100, label: '分析完成', doneAt: new Date().toISOString(), result });
                            // 呼叫 onComplete callback
                            if (typeof cfg.onComplete === 'function') {
                                try { cfg.onComplete(result); } catch (e) { console.error('onComplete error:', e); }
                            }
                        } else {
                            upd({ status: 'error', label: '無法讀取結果' });
                        }
                    } else {
                        upd({ status: 'error', label: `失敗 (${run.conclusion})` });
                    }
                    delete _tracking[task.id];
                    return;
                }

                // 還在跑 — 查步驟進度
                const jobRes = await _ghFetch(`${_GITHUB_API}/actions/runs/${runId}/jobs`, token);
                if (!jobRes.ok) return;
                const jobData = await jobRes.json();

                if (jobData.jobs?.length > 0) {
                    const steps = jobData.jobs[0].steps || [];
                    let pct = 5, label = '⏳ 排隊中...';
                    for (const step of steps) {
                        const mapped = stepProgress[step.name];
                        if (step.status === 'completed' && mapped) { pct = mapped.pct; label = `✅ ${step.name}`; }
                        if (step.status === 'in_progress' && mapped) { pct = mapped.pct; label = mapped.label; break; }
                    }
                    upd({ pct, label });
                }
            } catch { }
        }
    }

    // ── 跳頁 ─────────────────────────────────────────────────────────────────
    function jumpTo(id) {
        _load();
        const task = _tasks.find(t => t.id === id);
        if (!task || !task.result) return;

        // 切頁籤
        const tabMap = { chip: 'chip', fundamental: 'fundamental', news: 'news' };
        const tab = tabMap[task.type] || 'fundamental';
        document.querySelector(`.tab-btn[data-tab="${tab}"]`)?.click();

        if (task.type === 'news') {
            // news 完成後重新載入消息面資料
            window.dispatchEvent(new CustomEvent('news-reload'));
            return;
        }

        // 非 news 類型：切股票
        const inputEl = document.getElementById('stockInput');
        if (inputEl) { inputEl.value = task.stockId; document.getElementById('searchBtn')?.click(); }

        setTimeout(() => {
            if (task.type === 'chip' && typeof renderChipResult === 'function') {
                renderChipResult(task.result);
                document.getElementById('chipResult').style.display = 'block';
                if (typeof updateChipStatus === 'function') updateChipStatus('✅ 已從佇列載入結果', 'success', null);
            } else if (task.type === 'fundamental' && typeof renderFundamentalResult === 'function') {
                renderFundamentalResult(task.result);
                document.getElementById('fundResult').style.display = 'block';
                if (typeof updateStatusUI === 'function') updateStatusUI('✅ 已從佇列載入結果', 'success', null);
            }
        }, 300);
    }

    // ── 渲染 ─────────────────────────────────────────────────────────────────
    function _showPanel() {
        _panelVisible = true;
        document.getElementById('tqPanel')?.classList.add('tq-visible');
    }

    function togglePanel() {
        _panelVisible = !_panelVisible;
        document.getElementById('tqPanel')?.classList.toggle('tq-visible', _panelVisible);
    }

    function _render() {
        _load();
        const list = document.getElementById('tqList');
        if (!list) return;
        list.innerHTML = _tasks.length === 0
            ? '<div class="tq-empty">尚無排隊任務</div>'
            : [..._tasks].reverse().map(_taskHtml).join('');
        _updateBadge();
    }

    function _renderTask(task) {
        const el = document.getElementById(`tq-${task.id}`);
        if (!el) { _render(); return; }
        el.outerHTML = _taskHtml(task);
        _updateBadge();
    }

    function _taskHtml(task) {
        const typeIcons = { chip: '📊', fundamental: '🔬', news: '📰' };
        const typeLabels = { chip: '籌碼面', fundamental: '基本面', news: '消息面' };
        const typeIcon = typeIcons[task.type] || '🔬';
        const typeLabel = typeLabels[task.type] || '基本面';
        const timeStr = _fmtTime(task.createdAt);

        let statusIcon, statusClass, barClass;
        switch (task.status) {
            case 'pending': statusIcon = '⏳'; statusClass = 'tq-pending'; barClass = ''; break;
            case 'running': statusIcon = '🔄'; statusClass = 'tq-running'; barClass = 'tq-bar-running'; break;
            case 'done': statusIcon = '✅'; statusClass = 'tq-done'; barClass = 'tq-bar-done'; break;
            case 'error': statusIcon = '❌'; statusClass = 'tq-error'; barClass = 'tq-bar-error'; break;
        }

        const clickable = task.status === 'done' && task.result;
        const clickAttr = clickable ? `onclick="TaskQueue.jumpTo('${task.id}')" style="cursor:pointer;"` : '';
        const hintText = clickable ? '<span class="tq-hint">點擊查看結果 →</span>' : '';

        return `
        <div class="tq-item ${statusClass}" id="tq-${task.id}" ${clickAttr}>
            <div class="tq-item-header">
                <span class="tq-stock">${task.stockName} <span class="tq-sid">${task.stockId}</span></span>
                <span class="tq-type">${typeIcon} ${typeLabel}</span>
            </div>
            <div class="tq-bar-bg">
                <div class="tq-bar-fill ${barClass}" style="width:${task.pct}%"></div>
            </div>
            <div class="tq-item-footer">
                <span class="tq-label">${statusIcon} ${task.label}</span>
                <span class="tq-time">${timeStr}</span>
            </div>
            ${hintText}
        </div>`;
    }

    function _updateBadge() {
        const badge = document.getElementById('tqBadge');
        if (!badge) return;
        const n = getActiveCount();
        badge.textContent = n > 0 ? n : '';
        badge.style.display = n > 0 ? 'inline-flex' : 'none';
    }

    function _fmtTime(iso) {
        try {
            const d = new Date(iso);
            return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        } catch { return ''; }
    }

    // ── 初始化 ────────────────────────────────────────────────────────────────
    function init() {
        _load();
        // 頁面重整後，把遺留的 pending/running 標為 error（因為 _tracking 不持久化，無法繼續追蹤）
        let changed = false;
        _tasks.forEach(t => {
            if (t.status === 'pending' || t.status === 'running') {
                t.status = 'error';
                t.label = '頁面重整後中斷';
                changed = true;
            }
        });
        if (changed) _save();
        _render();
        if (getActiveCount() > 0) _showPanel();
    }

    return { add, update, track, jumpTo, clearDone, init, togglePanel, getActiveCount };
})();

document.addEventListener('DOMContentLoaded', () => TaskQueue.init());
