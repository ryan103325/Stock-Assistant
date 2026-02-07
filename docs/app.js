/**
 * 台股技術分析圖表 - 前端應用
 * 使用 TradingView Lightweight Charts
 */

// === 顏色設定 ===
const COLORS = {
    up: '#FF5252',
    down: '#00C853',
    ma5: '#FFA500',
    ma10: '#1E90FF',
    ma20: '#0000CD',
    ma50: '#DC143C',
    bb: '#455A64',
    rsi6: '#FFA500',
    rsi12: '#9370DB',
    rsiLine: '#787B86',
};

// 隱藏價格線和標籤的通用設定
const hidePriceLine = {
    lastValueVisible: false,
    priceLineVisible: false,
};

// === 全域狀態 ===
let stockList = [];
let stockMap = {};
let nameMap = {};
let currentStock = null;
let currentTimeframe = 'D';
let mainChart = null;
let volumeChart = null;
let rsiChart = null;
let candleSeries = null;
let volumeSeries = null;
let rsiSeries6 = null;
let rsiSeries12 = null;
let maSeries = {};
let bbSeries = {};
let volMaSeries = {};

// === 初始化 ===
document.addEventListener('DOMContentLoaded', async () => {
    await loadStockList();
    initCharts();
    initEventListeners();
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
            vertLine: { visible: false },
            horzLine: { visible: false },
        },
        rightPriceScale: { borderColor: '#30363d' },
        timeScale: { borderColor: '#30363d', timeVisible: true },
    };

    // === 主圖表 ===
    mainChart = LightweightCharts.createChart(document.getElementById('chart'), {
        ...chartOptions,
        height: 400,
    });

    candleSeries = mainChart.addCandlestickSeries({
        upColor: COLORS.up,
        downColor: COLORS.down,
        borderUpColor: COLORS.up,
        borderDownColor: COLORS.down,
        wickUpColor: COLORS.up,
        wickDownColor: COLORS.down,
    });

    // MA 均線 (關閉價格標籤和水平線)
    maSeries.ma5 = mainChart.addLineSeries({ color: COLORS.ma5, lineWidth: 1, ...hidePriceLine });
    maSeries.ma10 = mainChart.addLineSeries({ color: COLORS.ma10, lineWidth: 1, ...hidePriceLine });
    maSeries.ma20 = mainChart.addLineSeries({ color: COLORS.ma20, lineWidth: 1, ...hidePriceLine });
    maSeries.ma50 = mainChart.addLineSeries({ color: COLORS.ma50, lineWidth: 1, ...hidePriceLine });

    // 布林通道
    bbSeries.upper = mainChart.addLineSeries({ color: COLORS.bb, lineWidth: 1, lineStyle: 2, ...hidePriceLine });
    bbSeries.lower = mainChart.addLineSeries({ color: COLORS.bb, lineWidth: 1, lineStyle: 2, ...hidePriceLine });

    // === 成交量圖表 ===
    volumeChart = LightweightCharts.createChart(document.getElementById('volumeChart'), {
        ...chartOptions,
        height: 100,
    });

    volumeSeries = volumeChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        ...hidePriceLine,
    });
    volumeChart.priceScale('').applyOptions({ scaleMargins: { top: 0.1, bottom: 0 } });

    // 均量線
    volMaSeries.ma5 = volumeChart.addLineSeries({ color: COLORS.ma5, lineWidth: 1, priceScaleId: '', ...hidePriceLine });
    volMaSeries.ma10 = volumeChart.addLineSeries({ color: COLORS.ma10, lineWidth: 1, priceScaleId: '', ...hidePriceLine });
    volMaSeries.ma20 = volumeChart.addLineSeries({ color: COLORS.ma20, lineWidth: 1, priceScaleId: '', ...hidePriceLine });

    // === RSI 圖表 ===
    rsiChart = LightweightCharts.createChart(document.getElementById('rsiChart'), {
        ...chartOptions,
        height: 120,
    });

    // RSI 使用左側價格軸避免衝突
    rsiChart.priceScale('left').applyOptions({
        visible: true,
        autoScale: true,
        scaleMargins: { top: 0.1, bottom: 0.1 },
    });
    rsiChart.priceScale('right').applyOptions({ visible: false });

    rsiSeries6 = rsiChart.addLineSeries({
        color: COLORS.rsi6,
        lineWidth: 2,
        priceScaleId: 'left',
        ...hidePriceLine,
    });

    rsiSeries12 = rsiChart.addLineSeries({
        color: COLORS.rsi12,
        lineWidth: 2,
        priceScaleId: 'left',
        ...hidePriceLine,
    });

    // RSI 水平線 (70, 50, 30)
    const rsiLineOpts = { lineWidth: 1, lineStyle: 2, priceScaleId: 'left', ...hidePriceLine };
    const rsi70 = rsiChart.addLineSeries({ ...rsiLineOpts, color: COLORS.rsiLine });
    const rsi50 = rsiChart.addLineSeries({ ...rsiLineOpts, color: COLORS.rsiLine, lineStyle: 1 });
    const rsi30 = rsiChart.addLineSeries({ ...rsiLineOpts, color: COLORS.rsiLine });

    // 水平線設一個很長的時間範圍
    const startTime = '2000-01-01';
    const endTime = '2030-12-31';
    rsi70.setData([{ time: startTime, value: 70 }, { time: endTime, value: 70 }]);
    rsi50.setData([{ time: startTime, value: 50 }, { time: endTime, value: 50 }]);
    rsi30.setData([{ time: startTime, value: 30 }, { time: endTime, value: 30 }]);

    // === 同步時間軸 ===
    const syncTimeScale = (source, targets) => {
        source.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (range) targets.forEach(t => t.timeScale().setVisibleLogicalRange(range));
        });
    };
    syncTimeScale(mainChart, [volumeChart, rsiChart]);
    syncTimeScale(volumeChart, [mainChart, rsiChart]);
    syncTimeScale(rsiChart, [mainChart, volumeChart]);

    // 響應式
    window.addEventListener('resize', () => {
        mainChart.applyOptions({ width: document.getElementById('chart').clientWidth });
        volumeChart.applyOptions({ width: document.getElementById('volumeChart').clientWidth });
        rsiChart.applyOptions({ width: document.getElementById('rsiChart').clientWidth });
    });
}

// === 事件監聽 ===
function initEventListeners() {
    const input = document.getElementById('stockInput');
    const searchBtn = document.getElementById('searchBtn');
    const suggestions = document.getElementById('suggestions');

    searchBtn.addEventListener('click', () => handleSearch(input.value));
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch(input.value);
    });

    input.addEventListener('input', () => {
        const query = input.value.trim().toUpperCase();
        if (!query) { suggestions.classList.remove('show'); return; }

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
            const rect = input.getBoundingClientRect();
            suggestions.style.top = `${rect.bottom + 4}px`;
            suggestions.style.left = `${rect.left}px`;
            suggestions.style.width = `${rect.width}px`;
            suggestions.classList.add('show');
        } else {
            suggestions.classList.remove('show');
        }
    });

    suggestions.addEventListener('click', (e) => {
        const item = e.target.closest('.suggestion-item');
        if (item) {
            input.value = item.dataset.id;
            suggestions.classList.remove('show');
            loadStock(item.dataset.id);
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-box') && !e.target.closest('.suggestions')) {
            suggestions.classList.remove('show');
        }
    });

    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTimeframe = btn.dataset.tf;
            if (currentStock) loadStock(currentStock);
        });
    });
}

function handleSearch(query) {
    query = query.trim();
    if (!query) return;
    let stockId = query.toUpperCase();
    if (nameMap[query]) stockId = nameMap[query];
    loadStock(stockId);
}

// === 載入股票資料 ===
async function loadStock(stockId) {
    try {
        const resp = await fetch(`./data/${stockId}.json`);
        if (!resp.ok) throw new Error('找不到股票');

        const stockData = await resp.json();
        currentStock = stockId;

        let data = stockData.data;
        if (currentTimeframe === 'W') {
            data = convertToWeekly(data);
        }

        const indicators = calculateIndicators(data);
        updateCharts(data, indicators);
        updateStockInfo(stockId, stockData.name, data);
        updateIndicatorLabels(data, indicators);

    } catch (e) {
        console.error('❌ 載入失敗:', e);
        alert(`找不到股票: ${stockId}`);
    }
}

// === 計算技術指標 ===
function calculateIndicators(data) {
    const closes = data.map(d => d.close);
    const highs = data.map(d => d.high);
    const lows = data.map(d => d.low);
    const volumes = data.map(d => d.volume);

    return {
        ma5: calcMA(closes, 5),
        ma10: calcMA(closes, 10),
        ma20: calcMA(closes, 20),
        ma50: calcMA(closes, 50),
        bb: calcBollingerBands(closes, 20, 2),
        volMa5: calcMA(volumes, 5),
        volMa10: calcMA(volumes, 10),
        volMa20: calcMA(volumes, 20),
        rsi6: calcRSI(closes, 6),
        rsi12: calcRSI(closes, 12),
        divergences: detectRSIDivergence(lows, highs, calcRSI(closes, 6), 5, 5),
    };
}

// === 計算 MA ===
function calcMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0);
            result.push(sum / period);
        }
    }
    return result;
}

// === 計算布林通道 ===
function calcBollingerBands(data, period, mult) {
    const ma = calcMA(data, period);
    const upper = [], lower = [];

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1 || ma[i] === null) {
            upper.push(null);
            lower.push(null);
        } else {
            const slice = data.slice(i - period + 1, i + 1);
            const variance = slice.reduce((sum, val) => sum + Math.pow(val - ma[i], 2), 0) / period;
            const std = Math.sqrt(variance);
            upper.push(ma[i] + mult * std);
            lower.push(ma[i] - mult * std);
        }
    }
    return { upper, lower };
}

// === 計算 RSI (Wilder's RMA) ===
function calcRSI(closes, period) {
    const rsi = [];
    const alpha = 1 / period;
    let avgGain = 0, avgLoss = 0;

    for (let i = 0; i < closes.length; i++) {
        if (i === 0) { rsi.push(null); continue; }

        const change = closes[i] - closes[i - 1];
        const gain = change > 0 ? change : 0;
        const loss = change < 0 ? -change : 0;

        if (i < period) {
            avgGain += gain;
            avgLoss += loss;
            rsi.push(null);
        } else if (i === period) {
            avgGain = avgGain / period;
            avgLoss = avgLoss / period;
            avgGain = alpha * gain + (1 - alpha) * avgGain;
            avgLoss = alpha * loss + (1 - alpha) * avgLoss;
            rsi.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
        } else {
            avgGain = alpha * gain + (1 - alpha) * avgGain;
            avgLoss = alpha * loss + (1 - alpha) * avgLoss;
            rsi.push(avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss));
        }
    }
    return rsi;
}

// === RSI 背離偵測 ===
function detectRSIDivergence(lows, highs, rsi, lbL, lbR) {
    const divergences = [];
    const minRange = 5, maxRange = 60;

    function isPivotLow(data, left, right, idx) {
        if (idx < left || idx >= data.length - right) return false;
        for (let i = idx - left; i < idx; i++) if (data[i] <= data[idx]) return false;
        for (let i = idx + 1; i <= idx + right; i++) if (data[i] < data[idx]) return false;
        return true;
    }

    function isPivotHigh(data, left, right, idx) {
        if (idx < left || idx >= data.length - right) return false;
        for (let i = idx - left; i < idx; i++) if (data[i] >= data[idx]) return false;
        for (let i = idx + 1; i <= idx + right; i++) if (data[i] > data[idx]) return false;
        return true;
    }

    for (let i = lbL; i < rsi.length - lbR; i++) {
        if (rsi[i] === null) continue;

        if (isPivotLow(rsi, lbL, lbR, i)) {
            for (let j = i - minRange; j >= Math.max(0, i - maxRange); j--) {
                if (rsi[j] !== null && isPivotLow(rsi, lbL, lbR, j)) {
                    if (lows[i] < lows[j] && rsi[i] > rsi[j]) {
                        divergences.push({ type: 'bull', index: i });
                    }
                    break;
                }
            }
        }

        if (isPivotHigh(rsi, lbL, lbR, i)) {
            for (let j = i - minRange; j >= Math.max(0, i - maxRange); j--) {
                if (rsi[j] !== null && isPivotHigh(rsi, lbL, lbR, j)) {
                    if (highs[i] > highs[j] && rsi[i] < rsi[j]) {
                        divergences.push({ type: 'bear', index: i });
                    }
                    break;
                }
            }
        }
    }
    return divergences;
}

// === 轉換為週線 ===
function convertToWeekly(dailyData) {
    const weeklyData = [];
    let currentWeek = null;

    dailyData.forEach(d => {
        const date = new Date(d.time);
        const friday = new Date(date);
        friday.setDate(date.getDate() + (5 - date.getDay() + 7) % 7);
        const weekKey = friday.toISOString().split('T')[0];

        if (!currentWeek || currentWeek.time !== weekKey) {
            if (currentWeek) weeklyData.push(currentWeek);
            currentWeek = { time: weekKey, open: d.open, high: d.high, low: d.low, close: d.close, volume: d.volume };
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
function updateCharts(data, indicators) {
    // K線
    candleSeries.setData(data.map(d => ({
        time: d.time, open: d.open, high: d.high, low: d.low, close: d.close,
    })));

    // 成交量
    volumeSeries.setData(data.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(255, 82, 82, 0.6)' : 'rgba(0, 200, 83, 0.6)',
    })));

    // MA
    const setLineData = (series, values) => {
        series.setData(data.map((d, i) => values[i] !== null ? { time: d.time, value: values[i] } : null).filter(Boolean));
    };

    setLineData(maSeries.ma5, indicators.ma5);
    setLineData(maSeries.ma10, indicators.ma10);
    setLineData(maSeries.ma20, indicators.ma20);
    setLineData(maSeries.ma50, indicators.ma50);
    setLineData(bbSeries.upper, indicators.bb.upper);
    setLineData(bbSeries.lower, indicators.bb.lower);
    setLineData(volMaSeries.ma5, indicators.volMa5);
    setLineData(volMaSeries.ma10, indicators.volMa10);
    setLineData(volMaSeries.ma20, indicators.volMa20);

    // RSI
    setLineData(rsiSeries6, indicators.rsi6);
    setLineData(rsiSeries12, indicators.rsi12);

    // RSI 背離標記
    if (indicators.divergences.length > 0) {
        rsiSeries6.setMarkers(indicators.divergences.map(d => ({
            time: data[d.index].time,
            position: d.type === 'bull' ? 'belowBar' : 'aboveBar',
            color: d.type === 'bull' ? '#00C853' : '#FF5252',
            shape: d.type === 'bull' ? 'arrowUp' : 'arrowDown',
            text: d.type === 'bull' ? 'Bull' : 'Bear',
        })));
    } else {
        rsiSeries6.setMarkers([]);
    }

    mainChart.timeScale().fitContent();
    volumeChart.timeScale().fitContent();
    rsiChart.timeScale().fitContent();
}

// === 格式化成交量 (加逗點) ===
function formatVol(vol) {
    if (vol === null || isNaN(vol)) return '-';
    return Math.round(vol).toLocaleString('en-US') + '張';
}

// === 更新指標標籤 ===
function updateIndicatorLabels(data, indicators) {
    const last = data.length - 1;

    // 成交量標籤
    document.getElementById('volValues').innerHTML = `
        <span style="color:${COLORS.up}">${formatVol(data[last].volume)}</span>
        <span style="color:${COLORS.ma5}">MA5:${formatVol(indicators.volMa5[last])}</span>
        <span style="color:${COLORS.ma10}">MA10:${formatVol(indicators.volMa10[last])}</span>
        <span style="color:${COLORS.ma20}">MA20:${formatVol(indicators.volMa20[last])}</span>
    `;

    // RSI 標籤
    const rsi6 = indicators.rsi6[last];
    const rsi12 = indicators.rsi12[last];
    document.getElementById('rsiValues').innerHTML = `
        <span style="color:${COLORS.rsi6}">RSI6:${rsi6 !== null ? rsi6.toFixed(1) : '-'}</span>
        <span style="color:${COLORS.rsi12}">RSI12:${rsi12 !== null ? rsi12.toFixed(1) : '-'}</span>
    `;
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
