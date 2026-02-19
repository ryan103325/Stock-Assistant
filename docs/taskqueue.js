/**
 * TaskQueue — 分析任務排隊面板
 *
 * 每次觸發基本面/籌碼面分析時，呼叫 TaskQueue.add() 登記任務。
 * 面板顯示各任務的進度，完成後可點擊直接跳到對應頁籤+載入結果。
 *
 * 任務物件結構：
 * {
 *   id:        string  (uid)
 *   stockId:   string  ('2330')
 *   stockName: string  ('台積電')
 *   type:      'chip' | 'fundamental'
 *   status:    'pending' | 'running' | 'done' | 'error'
 *   pct:       number  (0-100)
 *   label:     string  (目前步驟文字)
 *   runId:     number | null
 *   createdAt: string  (ISO)
 *   doneAt:    string | null
 *   result:    object | null  (原始分析 JSON)
 * }
 */

const TaskQueue = (() => {
    const LS_KEY = 'tq_tasks';
    const MAX_TASKS = 20;
    let _tasks = [];
    let _panelVisible = false;

    // ── localStorage ────────────────────────────────────────────
    function _load() {
        try {
            _tasks = JSON.parse(localStorage.getItem(LS_KEY) || '[]');
        } catch {
            _tasks = [];
        }
    }

    function _save() {
        // 只保留最新 MAX_TASKS 筆
        if (_tasks.length > MAX_TASKS) {
            _tasks = _tasks.slice(_tasks.length - MAX_TASKS);
        }
        try {
            localStorage.setItem(LS_KEY, JSON.stringify(_tasks));
        } catch { }
    }

    function _uid() {
        return `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    }

    // ── 公開 API ────────────────────────────────────────────────
    function add({ stockId, stockName, type }) {
        _load();
        const task = {
            id: _uid(),
            stockId,
            stockName: stockName || stockId,
            type,           // 'chip' | 'fundamental'
            status: 'pending',
            pct: 0,
            label: '等待排隊...',
            runId: null,
            createdAt: new Date().toISOString(),
            doneAt: null,
            result: null,
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

    function getActiveCount() {
        _load();
        return _tasks.filter(t => t.status === 'running' || t.status === 'pending').length;
    }

    // ── 渲染 ─────────────────────────────────────────────────────
    function _showPanel() {
        _panelVisible = true;
        const panel = document.getElementById('tqPanel');
        if (panel) panel.classList.add('tq-visible');
    }

    function _togglePanel() {
        _panelVisible = !_panelVisible;
        const panel = document.getElementById('tqPanel');
        if (panel) panel.classList.toggle('tq-visible', _panelVisible);
    }

    function _render() {
        _load();
        const list = document.getElementById('tqList');
        if (!list) return;

        if (_tasks.length === 0) {
            list.innerHTML = '<div class="tq-empty">尚無排隊任務</div>';
        } else {
            // 最新的排在最上面
            list.innerHTML = [..._tasks].reverse().map(_taskHtml).join('');
        }
        _updateBadge();
    }

    function _renderTask(task) {
        const el = document.getElementById(`tq-${task.id}`);
        if (!el) {
            _render(); // 找不到就全部重繪
            return;
        }
        el.outerHTML = _taskHtml(task);
    }

    function _taskHtml(task) {
        const typeIcon = task.type === 'chip' ? '📊' : '🔬';
        const typeLabel = task.type === 'chip' ? '籌碼面' : '基本面';
        const timeStr = _fmtTime(task.createdAt);

        let statusIcon, statusClass, barClass;
        switch (task.status) {
            case 'pending': statusIcon = '⏳'; statusClass = 'tq-pending'; barClass = ''; break;
            case 'running': statusIcon = '🔄'; statusClass = 'tq-running'; barClass = 'tq-bar-running'; break;
            case 'done': statusIcon = '✅'; statusClass = 'tq-done'; barClass = 'tq-bar-done'; break;
            case 'error': statusIcon = '❌'; statusClass = 'tq-error'; barClass = 'tq-bar-error'; break;
        }

        const clickable = task.status === 'done' && task.result;
        const clickAttr = clickable
            ? `onclick="TaskQueue.jumpTo('${task.id}')" style="cursor:pointer;"`
            : '';
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
        const active = getActiveCount();
        badge.textContent = active > 0 ? active : '';
        badge.style.display = active > 0 ? 'inline-flex' : 'none';
    }

    function _fmtTime(iso) {
        try {
            const d = new Date(iso);
            return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        } catch { return ''; }
    }

    // ── 跳頁 ─────────────────────────────────────────────────────
    function jumpTo(id) {
        _load();
        const task = _tasks.find(t => t.id === id);
        if (!task || !task.result) return;

        // 1. 切到目標股票
        const inputEl = document.getElementById('stockInput');
        if (inputEl) {
            inputEl.value = task.stockId;
            document.getElementById('searchBtn')?.click();
        }

        // 2. 切換頁籤
        const tab = task.type === 'chip' ? 'chip' : 'fundamental';
        const tabBtn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
        if (tabBtn) tabBtn.click();

        // 3. 延遲渲染結果（等頁籤切換完）
        setTimeout(() => {
            if (task.type === 'chip' && typeof renderChipResult === 'function') {
                renderChipResult(task.result);
                document.getElementById('chipResult').style.display = 'block';
                updateChipStatus('✅ 已從佇列載入結果', 'success', null);
            } else if (task.type === 'fundamental' && typeof renderFundamentalResult === 'function') {
                renderFundamentalResult(task.result);
                document.getElementById('fundResult').style.display = 'block';
                updateStatusUI('✅ 已從佇列載入結果', 'success', null);
            }
        }, 300);
    }

    // ── 清除完成任務 ──────────────────────────────────────────────
    function clearDone() {
        _load();
        _tasks = _tasks.filter(t => t.status !== 'done' && t.status !== 'error');
        _save();
        _render();
    }

    // ── 初始化（頁面載入時呼叫）──────────────────────────────────
    function init() {
        _load();
        _render();
        // 如果有進行中的任務，自動展開面板
        if (getActiveCount() > 0) _showPanel();
    }

    return { add, update, jumpTo, clearDone, init, togglePanel: _togglePanel };
})();

document.addEventListener('DOMContentLoaded', () => TaskQueue.init());
