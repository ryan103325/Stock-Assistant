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
let currentData = [];
let currentIndicators = {};
let mainChart, volumeChart, rsiChart;
let candleSeries, volumeSeries, rsiSeries6, rsiSeries12;
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

function initCharts() {
    const priceScaleWidth = 80;

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
            vertLine: { width: 1, color: '#758696', style: LightweightCharts.LineStyle.Dashed },
            horzLine: { visible: true },
        },
        rightPriceScale: {
            borderColor: '#30363d',
            minimumWidth: priceScaleWidth,
        },
        timeScale: {
            borderColor: '#30363d',
            timeVisible: true,
            rightOffset: 5,
        },
    };

    // === 主圖表 ===
    mainChart = LightweightCharts.createChart(document.getElementById('chart'), {
        ...chartOptions,
        height: 380,
    });

    candleSeries = mainChart.addCandlestickSeries({
        upColor: COLORS.up,
        downColor: COLORS.down,
        borderUpColor: COLORS.up,
        borderDownColor: COLORS.down,
        wickUpColor: COLORS.up,
        wickDownColor: COLORS.down,
        lastValueVisible: false,
        priceLineVisible: false,
    });

    // MA 均線
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
        height: 130,
    });

    volumeSeries = volumeChart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'right',
        ...hidePriceLine,
    });
    volumeChart.priceScale('right').applyOptions({
        scaleMargins: { top: 0.05, bottom: 0 },
        minimumWidth: priceScaleWidth,
    });

    volMaSeries.ma5 = volumeChart.addLineSeries({ color: COLORS.ma5, lineWidth: 1, priceScaleId: 'right', ...hidePriceLine });
    volMaSeries.ma10 = volumeChart.addLineSeries({ color: COLORS.ma10, lineWidth: 1, priceScaleId: 'right', ...hidePriceLine });
    volMaSeries.ma20 = volumeChart.addLineSeries({ color: COLORS.ma20, lineWidth: 1, priceScaleId: 'right', ...hidePriceLine });

    // === RSI 圖表 ===
    rsiChart = LightweightCharts.createChart(document.getElementById('rsiChart'), {
        ...chartOptions,
        height: 130,
    });

    rsiChart.priceScale('right').applyOptions({
        autoScale: true,
        scaleMargins: { top: 0.02, bottom: 0.02 },
        minimumWidth: priceScaleWidth,
    });

    const rsiLineOpts = {
        lineWidth: 2,
        priceScaleId: 'right',
        ...hidePriceLine,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
    };

    rsiSeries6 = rsiChart.addLineSeries({ ...rsiLineOpts, color: COLORS.rsi6 });
    rsiSeries12 = rsiChart.addLineSeries({ ...rsiLineOpts, color: COLORS.rsi12 });

    const hLineOpts = {
        lineWidth: 1, lineStyle: 2, priceScaleId: 'right', ...hidePriceLine,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
    };
    window.rsi70 = rsiChart.addLineSeries({ ...hLineOpts, color: COLORS.rsiLine });
    window.rsi50 = rsiChart.addLineSeries({ ...hLineOpts, color: COLORS.rsiLine, lineStyle: 1 });
    window.rsi30 = rsiChart.addLineSeries({ ...hLineOpts, color: COLORS.rsiLine });

    // === 時間軸同步 ===
    const syncTimeScale = (source, targets) => {
        source.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (range) targets.forEach(t => t.timeScale().setVisibleLogicalRange(range));
        });
    };
    syncTimeScale(mainChart, [volumeChart, rsiChart]);
    syncTimeScale(volumeChart, [mainChart, rsiChart]);
    syncTimeScale(rsiChart, [mainChart, volumeChart]);

    // === 十字線同步 + 浮動資訊面板 ===
    const syncCrosshair = (sourceChart, sourceSeries, targetCharts) => {
        sourceChart.subscribeCrosshairMove(param => {
            targetCharts.forEach(({ chart, series }) => {
                if (param.time) {
                    chart.setCrosshairPosition(NaN, series, param.time);
                } else {
                    chart.clearCrosshairPosition();
                }
            });
            // 更新浮動資訊面板
            updateTooltip(param);
        });
    };

    syncCrosshair(mainChart, candleSeries, [
        { chart: volumeChart, series: volumeSeries },
        { chart: rsiChart, series: rsiSeries6 },
    ]);
    syncCrosshair(volumeChart, volumeSeries, [
        { chart: mainChart, series: candleSeries },
        { chart: rsiChart, series: rsiSeries6 },
    ]);
    syncCrosshair(rsiChart, rsiSeries6, [
        { chart: mainChart, series: candleSeries },
        { chart: volumeChart, series: volumeSeries },
    ]);

    window.addEventListener('resize', () => {
        mainChart.applyOptions({ width: document.getElementById('chart').clientWidth });
        volumeChart.applyOptions({ width: document.getElementById('volumeChart').clientWidth });
        rsiChart.applyOptions({ width: document.getElementById('rsiChart').clientWidth });
    });
}

// === 浮動資訊面板 ===
const tooltip = document.getElementById('tooltip');

function updateTooltip(param) {
    if (!param.time || currentData.length === 0) {
        tooltip.classList.remove('show');
        return;
    }

    const idx = currentData.findIndex(d => d.time === param.time);
    if (idx < 0) {
        tooltip.classList.remove('show');
        return;
    }

    const bar = currentData[idx];
    const prevClose = idx > 0 ? currentData[idx - 1].close : bar.open;
    const change = bar.close - prevClose;
    const changePct = ((change / prevClose) * 100).toFixed(2);
    const sign = change >= 0 ? '+' : '';
    const changeClass = change > 0 ? 'up' : change < 0 ? 'down' : 'neutral';

    const getClass = (val) => val > prevClose ? 'up' : val < prevClose ? 'down' : 'neutral';

    // 指標數值
    const ma5 = currentIndicators.ma5[idx];
    const ma10 = currentIndicators.ma10[idx];
    const ma20 = currentIndicators.ma20[idx];
    const ma50 = currentIndicators.ma50[idx];
    const bbU = currentIndicators.bb.upper[idx];
    const bbL = currentIndicators.bb.lower[idx];
    const rsi6 = currentIndicators.rsi6[idx];
    const rsi12 = currentIndicators.rsi12[idx];
    const vol = bar.volume;
    const volMa5 = currentIndicators.volMa5[idx];
    const volMa10 = currentIndicators.volMa10[idx];
    const volMa20 = currentIndicators.volMa20[idx];

    const fmtPrice = (v) => v !== null ? v.toFixed(1) : '-';
    const fmtVol = (v) => v !== null ? Math.round(v).toLocaleString('en-US') : '-';

    tooltip.innerHTML = `
        <div class="tooltip-date">${bar.time}</div>
        <div class="tooltip-row"><span class="tooltip-label">開盤</span><span class="tooltip-value ${getClass(bar.open)}">${bar.open.toFixed(1)}</span></div>
        <div class="tooltip-row"><span class="tooltip-label">最高</span><span class="tooltip-value ${getClass(bar.high)}">${bar.high.toFixed(1)}</span></div>
        <div class="tooltip-row"><span class="tooltip-label">最低</span><span class="tooltip-value ${getClass(bar.low)}">${bar.low.toFixed(1)}</span></div>
        <div class="tooltip-row"><span class="tooltip-label">收盤</span><span class="tooltip-value ${getClass(bar.close)}">${bar.close.toFixed(1)}</span></div>
        <div class="tooltip-row"><span class="tooltip-label">漲跌</span><span class="tooltip-value ${changeClass}">${sign}${change.toFixed(1)} (${sign}${changePct}%)</span></div>
        ${ma5 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#FFA500">MA5</span><span class="tooltip-value">${fmtPrice(ma5)}</span></div>` : ''}
        ${ma10 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#1E90FF">MA10</span><span class="tooltip-value">${fmtPrice(ma10)}</span></div>` : ''}
        ${ma20 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#0000CD">MA20</span><span class="tooltip-value">${fmtPrice(ma20)}</span></div>` : ''}
        ${ma50 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#DC143C">MA50</span><span class="tooltip-value">${fmtPrice(ma50)}</span></div>` : ''}
        ${bbU !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#455A64">BB_U</span><span class="tooltip-value">${fmtPrice(bbU)}</span></div>` : ''}
        ${bbL !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#455A64">BB_D</span><span class="tooltip-value">${fmtPrice(bbL)}</span></div>` : ''}
        <div class="tooltip-sep"></div>
        <div class="tooltip-row"><span class="tooltip-label">成交量</span><span class="tooltip-value">${fmtVol(vol)}張</span></div>
        ${volMa5 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#FFA500">Vol MA5</span><span class="tooltip-value">${fmtVol(volMa5)}</span></div>` : ''}
        ${volMa10 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#1E90FF">Vol MA10</span><span class="tooltip-value">${fmtVol(volMa10)}</span></div>` : ''}
        ${volMa20 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#0000CD">Vol MA20</span><span class="tooltip-value">${fmtVol(volMa20)}</span></div>` : ''}
        <div class="tooltip-sep"></div>
        ${rsi6 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#FFA500">RSI6</span><span class="tooltip-value">${rsi6.toFixed(1)}</span></div>` : ''}
        ${rsi12 !== null ? `<div class="tooltip-row"><span class="tooltip-label" style="color:#9370DB">RSI12</span><span class="tooltip-value">${rsi12.toFixed(1)}</span></div>` : ''}
    `;

    // 位置計算 - 跟隨滑鼠
    const x = param.point?.x ?? 0;
    const y = param.point?.y ?? 0;
    const chartRect = document.getElementById('chart').getBoundingClientRect();

    let left = chartRect.left + x + 20;
    let top = chartRect.top + y - 20;

    // 避免超出視窗
    if (left + 220 > window.innerWidth) {
        left = chartRect.left + x - 230;
    }
    if (top + 300 > window.innerHeight) {
        top = window.innerHeight - 320;
    }
    if (top < 10) top = 10;

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    tooltip.classList.add('show');
}

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

        currentData = data;
        currentIndicators = calculateIndicators(data);

        updateCharts(data, currentIndicators);
        updateStockInfo(stockId, stockData.name, data);

    } catch (e) {
        console.error('❌ 載入失敗:', e);
        alert(`找不到股票: ${stockId}`);
    }
}

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
                        divergences.push({ type: 'bull', index: i, value: rsi[i] });
                    }
                    break;
                }
            }
        }

        if (isPivotHigh(rsi, lbL, lbR, i)) {
            for (let j = i - minRange; j >= Math.max(0, i - maxRange); j--) {
                if (rsi[j] !== null && isPivotHigh(rsi, lbL, lbR, j)) {
                    if (highs[i] > highs[j] && rsi[i] < rsi[j]) {
                        divergences.push({ type: 'bear', index: i, value: rsi[i] });
                    }
                    break;
                }
            }
        }
    }
    return divergences;
}

// 用 ISO Week 分組，自動處理假日
function convertToWeekly(dailyData) {
    if (!dailyData.length) return [];

    // 取得 ISO Week Key (年-週)
    const getWeekKey = (dateStr) => {
        const d = new Date(dateStr);
        d.setHours(0, 0, 0, 0);
        const dayNum = d.getDay() || 7; // 週日=7
        d.setDate(d.getDate() + 4 - dayNum); // 調整到該週的週四
        const yearStart = new Date(d.getFullYear(), 0, 1);
        const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
        return `${d.getFullYear()}-W${String(weekNo).padStart(2, '0')}`;
    };

    const weeklyMap = new Map();

    dailyData.forEach(day => {
        const weekKey = getWeekKey(day.time);

        if (!weeklyMap.has(weekKey)) {
            weeklyMap.set(weekKey, {
                time: day.time,  // 用該週第一個交易日的日期
                open: day.open,
                high: day.high,
                low: day.low,
                close: day.close,
                volume: day.volume
            });
        } else {
            const w = weeklyMap.get(weekKey);
            w.high = Math.max(w.high, day.high);
            w.low = Math.min(w.low, day.low);
            w.close = day.close;  // 用該週最後一天的收盤
            w.volume += day.volume;
        }
    });

    return Array.from(weeklyMap.values());
}

function updateCharts(data, indicators) {
    candleSeries.setData(data.map(d => ({
        time: d.time, open: d.open, high: d.high, low: d.low, close: d.close,
    })));

    volumeSeries.setData(data.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(255, 82, 82, 0.6)' : 'rgba(0, 200, 83, 0.6)',
    })));

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

    // RSI 水平線
    const rsiHLineData = (value) => data.map(d => ({ time: d.time, value }));
    window.rsi70.setData(rsiHLineData(70));
    window.rsi50.setData(rsiHLineData(50));
    window.rsi30.setData(rsiHLineData(30));

    // RSI 背離標記
    if (indicators.divergences.length > 0) {
        rsiSeries6.setMarkers(indicators.divergences.map(d => ({
            time: data[d.index].time,
            position: d.type === 'bull' ? 'belowBar' : 'aboveBar',
            color: d.type === 'bull' ? '#00C853' : '#FF5252',
            shape: 'circle',
            size: 1,
        })));
    } else {
        rsiSeries6.setMarkers([]);
    }

    // 預設顯示最近 100 筆 - 三個圖表同時設定
    const totalBars = data.length;
    const visibleBars = Math.min(100, totalBars);
    const range = { from: totalBars - visibleBars, to: totalBars };
    mainChart.timeScale().setVisibleLogicalRange(range);
    volumeChart.timeScale().setVisibleLogicalRange(range);
    rsiChart.timeScale().setVisibleLogicalRange(range);
}

function formatVol(vol) {
    if (vol === null || isNaN(vol)) return '-';
    return Math.round(vol).toLocaleString('en-US') + '張';
}

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
