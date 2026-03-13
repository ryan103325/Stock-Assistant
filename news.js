/**
 * 新聞面分析模組
 * 讀取 sentiment_ranking.json / market_summary.json 並渲染到 UI
 */
(function () {
    const DATA_BASE = 'data/news';

    // ===== 工具函數 =====
    function scoreColor(score) {
        if (score >= 0.5) return '#22c55e';
        if (score >= 0.2) return '#86efac';
        if (score > -0.2) return '#94a3b8';
        if (score > -0.5) return '#fca5a5';
        return '#ef4444';
    }

    function labelBadge(label) {
        const map = {
            'Bullish': ['🟢', '#22c55e20', '#22c55e'],
            'Somewhat-Bullish': ['🟢', '#86efac20', '#86efac'],
            'Neutral': ['⚪', '#94a3b820', '#94a3b8'],
            'Somewhat-Bearish': ['🔴', '#fca5a520', '#fca5a5'],
            'Bearish': ['🔴', '#ef444420', '#ef4444'],
        };
        const [icon, bg, color] = map[label] || ['⚪', '#94a3b820', '#94a3b8'];
        return `<span style="background:${bg};color:${color};padding:2px 8px;border-radius:12px;font-size:0.8em">${icon} ${label}</span>`;
    }

    function formatTime(iso) {
        if (!iso) return '--';
        const d = new Date(iso);
        return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    }

    // ===== 載入資料 =====
    async function loadData(file) {
        try {
            const res = await fetch(`${DATA_BASE}/${file}?t=${Date.now()}`);
            if (!res.ok) return null;
            return await res.json();
        } catch {
            return null;
        }
    }

    // ===== 渲染：個股情緒總覽 =====
    function renderOverview(summary) {
        const el = document.getElementById('newsOverview');
        const wrapper = document.getElementById('newsContentWrapper');
        const emptyState = document.getElementById('newsEmptyState');

        if (!summary) {
            wrapper.style.display = 'none';
            emptyState.style.display = 'block';
            emptyState.innerHTML = '尚無該股票的新聞情緒資料。請輸入代碼並點擊「搜尋個股新聞」。';
            return;
        }

        wrapper.style.display = 'block';
        emptyState.style.display = 'none';

        // 標題與時間
        document.getElementById('newsStockTitle').textContent = `${summary.stock_id} 消息面分析`;
        document.getElementById('newsAnalysisDate').textContent = `最後分析：${formatTime(summary.updated_at)}`;

        const avgColor = scoreColor(summary.weighted_score);
        const avgLabel = summary.weighted_score >= 0.2 ? '偏多' :
            summary.weighted_score <= -0.2 ? '偏空' : '中性';

        el.innerHTML = `
            <div class="news-stats-grid">
                <div class="news-stat-card">
                    <div class="news-stat-value">${summary.news_count}</div>
                    <div class="news-stat-label">近${summary.period_days}天相關新聞數</div>
                </div>
                <div class="news-stat-card">
                    <div class="news-stat-value" style="color:${avgColor}">${(summary.weighted_score >= 0 ? '+' : '') + summary.weighted_score.toFixed(3)}</div>
                    <div class="news-stat-label">加權情緒分數 (${avgLabel})</div>
                </div>
            </div>
        `;
    }

    // ===== 渲染：情緒分佈 =====
    function renderDistribution(summary) {
        const el = document.getElementById('sentimentDistribution');
        if (!summary || !summary.sentiment_distribution) {
            el.innerHTML = '<div class="news-empty">無分佈資料</div>';
            return;
        }

        const dist = summary.sentiment_distribution;
        const order = ['Bullish', 'Somewhat-Bullish', 'Neutral', 'Somewhat-Bearish', 'Bearish'];
        const labels = { 'Bullish': '看多', 'Somewhat-Bullish': '偏多', 'Neutral': '中性', 'Somewhat-Bearish': '偏空', 'Bearish': '看空' };
        const colors = { 'Bullish': '#22c55e', 'Somewhat-Bullish': '#86efac', 'Neutral': '#94a3b8', 'Somewhat-Bearish': '#fca5a5', 'Bearish': '#ef4444' };

        const total = summary.news_count || Object.values(dist).reduce((a, b) => a + b, 0) || 1;

        let html = '<div class="sentiment-bars">';
        for (const key of order) {
            const count = dist[key] || 0;
            const pct = ((count / total) * 100).toFixed(1);
            html += `
                <div class="sentiment-bar-row">
                    <span class="sentiment-bar-label">${labels[key] || key}</span>
                    <div class="sentiment-bar-track">
                        <div class="sentiment-bar-fill" style="width:${pct}%;background:${colors[key]}"></div>
                    </div>
                    <span class="sentiment-bar-value">${count} (${pct}%)</span>
                </div>
            `;
        }
        html += '</div>';
        el.innerHTML = html;
    }

    // ===== 渲染：最新新聞 =====
    function renderRecentNews(summary) {
        const el = document.getElementById('recentNews');
        if (!summary || !summary.news || summary.news.length === 0) {
            el.innerHTML = '<div class="news-empty">尚無相關新聞</div>';
            return;
        }

        let html = '';
        for (const news of summary.news) {
            const sColor = scoreColor(news.score || 0);
            html += `
                <div class="recent-news-item">
                    <div class="recent-news-header">
                        <a href="${news.url}" target="_blank" rel="noopener" class="recent-news-title">${news.title}</a>
                        <span class="recent-news-score" style="color:${sColor}">${news.score != null ? ((news.score >= 0 ? '+' : '') + news.score.toFixed(2)) : '--'}</span>
                    </div>
                    <div class="recent-news-meta">
                        <span class="recent-news-source">${news.source}</span>
                        <span class="recent-news-time">${formatTime(news.publish_time)}</span>
                        ${news.label ? labelBadge(news.label) : ''}
                    </div>
                    ${news.summary ? `<div class="recent-news-summary">${news.summary}</div>` : ''}
                </div>
            `;
        }
        el.innerHTML = html;
    }

    // ===== 主載入 =====
    async function loadNewsTab() {
        const newsInput = document.getElementById('newsSearchInput');
        const stockInput = document.getElementById('stockInput');

        // 優先讀取專屬搜尋列，若無則讀取全域搜尋列
        let stockId = newsInput && newsInput.value.trim() ? newsInput.value.trim() : (stockInput ? stockInput.value.trim() : '');

        if (!stockId || !/^\d{4,5}$/.test(stockId)) {
            renderOverview(null); // Show empty state
            return;
        }

        // 確保兩邊輸入框同步顯示
        if (newsInput && newsInput.value !== stockId) newsInput.value = stockId;
        if (stockInput && stockInput.value !== stockId) stockInput.value = stockId;

        renderOverview(null); // 先清空或顯示 loading (其實可以直接等 fetch 完)
        const summary = await loadData(`${stockId}.json`);

        renderOverview(summary);
        if (summary) {
            renderDistribution(summary);
            renderRecentNews(summary);
        }
    }

    // ===== News Search Dispatch =====
    const NEWS_WORKFLOW_FILE = 'step_news_search.yml';
    const NEWS_STEP_PROGRESS = {
        'Checkout code': { pct: 10, label: '📥 下載程式碼...' },
        'Set up Python': { pct: 20, label: '🐍 設定 Python 環境...' },
        'Install dependencies': { pct: 30, label: '📦 安裝套件...' },
        'Search & Analyze': { pct: 70, label: '🔍 搜尋新聞並分析中...' },
        'Commit & Push': { pct: 90, label: '💾 儲存結果...' },
    };

    function updateNewsStatus(msg, cls) {
        const el = document.getElementById('newsSearchStatus');
        if (el) {
            el.textContent = msg;
            el.className = 'analysis-status' + (cls ? ' ' + cls : '');
        }
    }

    async function startNewsSearch() {
        const input = document.getElementById('newsSearchInput');
        const stockId = (input?.value || '').trim();
        if (!stockId || !/^\d{4,5}$/.test(stockId)) {
            updateNewsStatus('⚠️ 請輸入有效的股票代碼 (4-5 碼數字)', 'warning');
            return;
        }

        // 觸發搜尋時，同步更新右上角全域輸入框
        const globalInput = document.getElementById('stockInput');
        if (globalInput) globalInput.value = stockId;

        const token = getToken();
        if (!token) {
            updateNewsStatus('🔑 需要設定 GitHub Token。請點擊 ⚙️ 設定。', 'warning');
            return;
        }

        const btn = document.getElementById('startNewsSearch');
        btn.disabled = true;
        btn.querySelector('.btn-icon').textContent = '⏳';
        btn.querySelector('.btn-text').textContent = '搜尋中...';

        try {
            const triggerTime = new Date().toISOString();
            updateNewsStatus('🚀 觸發 Tavily 新聞搜尋...', 'loading');

            const triggerRes = await ghFetch(
                `${GITHUB_API}/actions/workflows/${NEWS_WORKFLOW_FILE}/dispatches`,
                token,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        ref: 'main',
                        inputs: { stock_id: stockId },
                    }),
                }
            );

            if (triggerRes.status === 204) {
                const tqId = typeof TaskQueue !== 'undefined'
                    ? TaskQueue.add({ stockId, stockName: stockId, type: 'news' })
                    : null;
                if (tqId) {
                    TaskQueue.track(tqId, {
                        token, triggerTime,
                        workflowFile: NEWS_WORKFLOW_FILE,
                        stepProgress: NEWS_STEP_PROGRESS,
                        stockId, type: 'news',
                        onComplete: () => {
                            // 完成後重新載入新聞面資料
                            newsLoaded = false;
                            loadNewsTab();
                            newsLoaded = true;
                        }
                    });
                }
                updateNewsStatus(`✅ 已觸發 ${stockId} 新聞搜尋，請稍候`, 'success');
            } else {
                updateNewsStatus(`❌ 觸發失敗 (HTTP ${triggerRes.status})`, 'error');
            }
        } catch (err) {
            updateNewsStatus(`❌ ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.querySelector('.btn-icon').textContent = '🔍';
            btn.querySelector('.btn-text').textContent = '搜尋個股新聞';
        }
    }

    // 監聽 tab 切換，首次進入新聞面時載入
    let newsLoaded = false;
    document.addEventListener('DOMContentLoaded', () => {
        // Tab 切換
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.dataset.tab === 'news' && !newsLoaded) {
                    newsLoaded = true;
                    loadNewsTab();
                }
            });
        });

        // 監聽 taskqueue 觸發的 reload
        window.addEventListener('news-reload', () => {
            loadNewsTab();
        });

        // 搜尋按鈕
        document.getElementById('startNewsSearch')?.addEventListener('click', startNewsSearch);
        document.getElementById('configNewsToken')?.addEventListener('click', configureToken);

        // Enter 鍵觸發搜尋
        document.getElementById('newsSearchInput')?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') startNewsSearch();
        });

        // 自動填入目前選的股票
        const mainInput = document.getElementById('stockInput');
        const newsInput = document.getElementById('newsSearchInput');
        if (mainInput && newsInput) {
            const observer = new MutationObserver(() => {
                const id = document.getElementById('stockId')?.textContent;
                if (id && id !== '--') newsInput.value = id;
            });
            const stockIdEl = document.getElementById('stockId');
            if (stockIdEl) observer.observe(stockIdEl, { childList: true, characterData: true, subtree: true });
        }
    });
})();
