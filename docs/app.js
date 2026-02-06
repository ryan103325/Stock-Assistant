/**
 * 台股技術分析圖表 - 前端應用
 * 使用 TradingView Lightweight Charts
 */

// === 全域狀態 ===
let stockList = [];
let stockMap = {};  // id -> name
let nameMap = {};   // name -> id
let currentStock = null;
let currentTimeframe = 'D';
let mainChart = null;
let volumeChart = null;
let candleSeries = null;
let volumeSeries = null;

// === 初始化 ===
document.addEventListener('DOMContentLoaded', async () => {
    await loadStockList();
    initCharts();
    initEventListeners();

    // 預設載入台積電
    loadStock('2330');
});

// === 載入股票清單 ===
async function loadStockList() {
    try {
        const resp = await fetch('./data/stock_list.json');
        stockList = await resp.json();

        stockList.forEach(stock => {
            stockMap[stock.id] = stock.name;
            nameMap[stock.name] = stock.id;
        });

        console.log(`✅ 載入 ${stockList.length} 檔股票`);
    } catch (e) {
        console.error('❌ 載入股票清單失敗:', e);
    }
}

// === 初始化圖表 ===
function initCharts() {
    const chartOptions = {
        layout: {
            background: { type: 'solid', color: '#161b22' },
            textColor: '#8b949e',
        },
        grid: {
            vertLines: { color: '#21262d' },
            horzLines: { color: '#21262d' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#30363d',
        },
        timeScale: {
            borderColor: '#30363d',
            timeVisible: true,
        },
    };

    // 主圖表 (K線)
    mainChart = LightweightCharts.createChart(document.getElementById('chart'), {
        ...chartOptions,
        height: 400,
    });

    candleSeries = mainChart.addCandlestickSeries({
        upColor: '#f85149',      // 紅漲
        downColor: '#3fb950',    // 綠跌
        borderUpColor: '#f85149',
        borderDownColor: '#3fb950',
        wickUpColor: '#f85149',
        wickDownColor: '#3fb950',
    });

    // 成交量圖表
    volumeChart = LightweightCharts.createChart(document.getElementById('volumeChart'), {
        ...chartOptions,
        height: 120,
    });

    volumeSeries = volumeChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: '',
    });

    volumeChart.priceScale('').applyOptions({
        scaleMargins: { top: 0.1, bottom: 0 },
    });

    // 同步時間軸
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) volumeChart.timeScale().setVisibleLogicalRange(range);
    });

    volumeChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) mainChart.timeScale().setVisibleLogicalRange(range);
    });

    // 響應式調整
    window.addEventListener('resize', () => {
        mainChart.applyOptions({ width: document.getElementById('chart').clientWidth });
        volumeChart.applyOptions({ width: document.getElementById('volumeChart').clientWidth });
    });
}

// === 事件監聽 ===
function initEventListeners() {
    const input = document.getElementById('stockInput');
    const searchBtn = document.getElementById('searchBtn');
    const suggestions = document.getElementById('suggestions');

    // 搜尋按鈕
    searchBtn.addEventListener('click', () => handleSearch(input.value));

    // Enter 鍵
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch(input.value);
    });

    // 輸入自動補全
    input.addEventListener('input', () => {
        const query = input.value.trim().toUpperCase();
        if (!query) {
            suggestions.classList.remove('show');
            return;
        }

        const matches = stockList.filter(s =>
            s.id.includes(query) || s.name.toUpperCase().includes(query)
        ).slice(0, 10);

        if (matches.length > 0) {
            suggestions.innerHTML = matches.map(s =>
                `<div class="suggestion-item" data-id="${s.id}">
                    <span class="id">${s.id}</span>
                    <span class="name">${s.name}</span>
                </div>`
            ).join('');

            // 定位
            const rect = input.getBoundingClientRect();
            suggestions.style.top = `${rect.bottom + 4}px`;
            suggestions.style.left = `${rect.left}px`;
            suggestions.style.width = `${rect.width}px`;
            suggestions.classList.add('show');
        } else {
            suggestions.classList.remove('show');
        }
    });

    // 點擊建議
    suggestions.addEventListener('click', (e) => {
        const item = e.target.closest('.suggestion-item');
        if (item) {
            const id = item.dataset.id;
            input.value = id;
            suggestions.classList.remove('show');
            loadStock(id);
        }
    });

    // 點擊其他地方關閉建議
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box') && !e.target.closest('.suggestions')) {
            suggestions.classList.remove('show');
        }
    });

    // 日線/週線切換
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTimeframe = btn.dataset.tf;
            if (currentStock) loadStock(currentStock);
        });
    });
}

// === 處理搜尋 ===
function handleSearch(query) {
    query = query.trim();
    if (!query) return;

    // 嘗試匹配
    let stockId = query.toUpperCase();

    // 如果輸入的是名稱，轉換為代碼
    if (nameMap[query]) {
        stockId = nameMap[query];
    }

    loadStock(stockId);
}

// === 載入股票資料 ===
async function loadStock(stockId) {
    try {
        const resp = await fetch(`./data/${stockId}.json`);
        if (!resp.ok) throw new Error('找不到股票');

        const stockData = await resp.json();
        currentStock = stockId;

        // 處理週線
        let data = stockData.data;
        if (currentTimeframe === 'W') {
            data = convertToWeekly(data);
        }

        // 更新圖表
        updateCharts(data);

        // 更新資訊欄
        updateStockInfo(stockId, stockData.name, data);

    } catch (e) {
        console.error('❌ 載入失敗:', e);
        alert(`找不到股票: ${stockId}`);
    }
}

// === 轉換為週線 ===
function convertToWeekly(dailyData) {
    const weeklyData = [];
    let currentWeek = null;

    dailyData.forEach(d => {
        const date = new Date(d.time);
        // 取得該週的週五日期
        const weekDay = date.getDay();
        const friday = new Date(date);
        friday.setDate(date.getDate() + (5 - weekDay + 7) % 7);
        const weekKey = friday.toISOString().split('T')[0];

        if (!currentWeek || currentWeek.time !== weekKey) {
            if (currentWeek) weeklyData.push(currentWeek);
            currentWeek = {
                time: weekKey,
                open: d.open,
                high: d.high,
                low: d.low,
                close: d.close,
                volume: d.volume,
            };
        } else {
            currentWeek.high = Math.max(currentWeek.high, d.high);
            currentWeek.low = Math.min(currentWeek.low, d.low);
            currentWeek.close = d.close;
            currentWeek.volume += d.volume;
        }
    });

    if (currentWeek) weeklyData.push(currentWeek);
    return weeklyData;
}

// === 更新圖表 ===
function updateCharts(data) {
    // K線資料
    const candleData = data.map(d => ({
        time: d.time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
    }));

    // 成交量資料 (顏色根據漲跌 - 台灣紅漲綠跌)
    const volumeData = data.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(248, 81, 73, 0.6)' : 'rgba(63, 185, 80, 0.6)',
    }));

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

    // 自適應顯示範圍
    mainChart.timeScale().fitContent();
    volumeChart.timeScale().fitContent();
}

// === 更新股票資訊 ===
function updateStockInfo(stockId, stockName, data) {
    const last = data[data.length - 1];
    const prev = data[data.length - 2] || last;

    const price = last.close;
    const change = price - prev.close;
    const changePct = (change / prev.close * 100).toFixed(2);

    document.getElementById('stockId').textContent = stockId;
    document.getElementById('stockName').textContent = stockName;
    document.getElementById('stockPrice').textContent = price.toFixed(1);

    const changeEl = document.getElementById('stockChange');
    const sign = change >= 0 ? '+' : '';
    changeEl.textContent = `${sign}${change.toFixed(1)} (${sign}${changePct}%)`;
    changeEl.className = 'stock-change ' + (change > 0 ? 'up' : change < 0 ? 'down' : 'flat');
}
