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
let currentRSData = [];  // 儲存 RS 數據供 tooltip 使用

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
    const chartEl = document.getElementById('chart');
    mainChart = LightweightCharts.createChart(chartEl, {
        ...chartOptions,
        height: chartEl.clientHeight || 380,
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
    const volumeEl = document.getElementById('volumeChart');
    volumeChart = LightweightCharts.createChart(volumeEl, {
        ...chartOptions,
        height: volumeEl.clientHeight || 130,
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
    const rsiEl = document.getElementById('rsiChart');
    rsiChart = LightweightCharts.createChart(rsiEl, {
        ...chartOptions,
        height: rsiEl.clientHeight || 130,
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
    // 全局同步函數，讓所有圖表對齊（包含後續加入的 rsChartV2）
    window.syncAllChartsTimeScale = (range, source) => {
        if (!range) return;
        const charts = [mainChart, volumeChart, rsiChart];
        if (typeof rsChartV2 !== 'undefined' && rsChartV2) charts.push(rsChartV2);
        charts.forEach(chart => {
            if (chart && chart !== source) {
                chart.timeScale().setVisibleLogicalRange(range);
            }
        });
    };

    const setupChartSync = (chart) => {
        chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            window.syncAllChartsTimeScale(range, chart);
        });
    };
    setupChartSync(mainChart);
    setupChartSync(volumeChart);
    setupChartSync(rsiChart);

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

    // === ResizeObserver：寬度 + 高度同時自適應 ===
    const chartEntries = [
        { el: chartEl, chart: () => mainChart },
        { el: volumeEl, chart: () => volumeChart },
        { el: rsiEl, chart: () => rsiChart },
    ];
    const ro = new ResizeObserver(entries => {
        for (const entry of entries) {
            const match = chartEntries.find(c => c.el === entry.target);
            if (match) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0) {
                    match.chart().applyOptions({ width, height });
                }
            }
        }
        // 同時處理 RS 圖表（如果存在）
        if (typeof rsChartV2 !== 'undefined' && rsChartV2) {
            const rsEl = document.getElementById('rsChart');
            if (rsEl) rsChartV2.applyOptions({ width: rsEl.clientWidth, height: rsEl.clientHeight });
        }
    });
    chartEntries.forEach(c => ro.observe(c.el));
}

// === 浮動資訊面板 ===
const tooltip = document.getElementById('tooltip');

// 取得 RS 數據的 tooltip 內容
function getRSTooltip(idx) {
    if (!currentRSData || currentRSData.length === 0 || idx < 0 || idx >= currentRSData.length) {
        return '';
    }
    const rs = currentRSData[idx];
    if (!rs) return '';

    const fmtRS = (v) => v !== null && v !== undefined ? v.toFixed(2) : '-';
    const getColor = (v) => v > 0 ? '#ef5350' : v < 0 ? '#26a69a' : '#8b949e';

    let html = '<div class="tooltip-sep"></div>';
    if (rs.mansfield !== null) {
        const rsColor = rs.color || '#8b949e';  // 使用柱狀圖顏色
        html += `<div class="tooltip-row"><span class="tooltip-label">RS</span><span class="tooltip-value" style="color:${rsColor}">${fmtRS(rs.mansfield)}%</span></div>`;
    }
    if (rs.rs3d !== null) {
        html += `<div class="tooltip-row"><span class="tooltip-label" style="color:#42a5f5">3d RS</span><span class="tooltip-value" style="color:${getColor(rs.rs3d)}">${fmtRS(rs.rs3d)}%</span></div>`;
    }
    if (rs.rs10d !== null) {
        html += `<div class="tooltip-row"><span class="tooltip-label" style="color:#ff9800">10d RS</span><span class="tooltip-value" style="color:${getColor(rs.rs10d)}">${fmtRS(rs.rs10d)}%</span></div>`;
    }
    return html;
}

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
        ${getRSTooltip(idx)}
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

    volumeSeries.setData(data.map((d, i) => {
        const prevClose = i > 0 ? data[i - 1].close : d.close;
        let color = d.close > prevClose ? '#ef5350' : d.close < prevClose ? '#00C853' : '#757575';
        return { time: d.time, value: d.volume, color: color };
    }));

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
    if (typeof rsChartV2 !== 'undefined' && rsChartV2) {
        rsChartV2.timeScale().setVisibleLogicalRange(range);
    }
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
// ===================================================================
// Volume Color & MTF-RS Indicator Integration
// ===================================================================

// Volume Color Calculation
function addVolumeColors(candleData, volumeData) {
    return volumeData.map((v, i) => {
        const currentClose = candleData[i].close;
        const prevClose = i > 0 ? candleData[i - 1].close : currentClose;

        let color;
        if (currentClose > prevClose) {
            color = '#ef5350';
        } else if (currentClose < prevClose) {
            color = '#26a69a';
        } else {
            color = '#757575';
        }

        return { ...v, color: color };
    });
}

// SMA Calculation
function calculateSMA(data, period) {
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

// Standard Deviation Calculation
function calculateStdev(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);
        } else {
            const slice = data.slice(i - period + 1, i + 1);
            const mean = slice.reduce((a, b) => a + b, 0) / period;
            const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period;
            result.push(Math.sqrt(variance));
        }
    }
    return result;
}

// Mansfield RS Calculation
function calculateMansfieldRS(stockData, indexData) {
    // 建立 TAIEX 日期索引
    const indexMap = new Map(indexData.map(d => [d.time, d]));

    // 用 stockData 的日期為基準，匹配對應的 TAIEX 數據（缺失時用前一天的值）
    let lastValidIndex = null;
    const alignedData = stockData.map(s => {
        const idx = indexMap.get(s.time);
        if (idx) {
            lastValidIndex = idx;
            return { stock: s, index: idx };
        } else {
            // 缺失時用前一天的值
            return { stock: s, index: lastValidIndex };
        }
    });

    const rsRatio = alignedData.map(d =>
        d.index ? (d.stock.close / d.index.close) * 100 : null
    );

    // 計算 SMA 時忽略 null 值
    const rsBaseline = [];
    for (let i = 0; i < rsRatio.length; i++) {
        if (i < 49) {
            rsBaseline.push(null);
        } else {
            const window = rsRatio.slice(i - 49, i + 1).filter(v => v !== null);
            rsBaseline.push(window.length > 0 ? window.reduce((a, b) => a + b, 0) / window.length : null);
        }
    }

    const mansfield = rsRatio.map((ratio, i) =>
        ratio !== null && rsBaseline[i] !== null && rsBaseline[i] !== 0
            ? ((ratio - rsBaseline[i]) / rsBaseline[i]) * 100
            : null
    );

    const sigma = calculateStdev(mansfield.map(m => m || 0), 21);

    const strengthLevel = mansfield.map((m, i) => {
        if (m === null || sigma[i] === null) return null;
        const neutralThreshold = 0.7 * sigma[i];
        const extremeThreshold = 1.5 * sigma[i];
        if (m > extremeThreshold) return 5;
        if (m > neutralThreshold) return 4;
        if (m > -neutralThreshold) return 3;
        if (m > -extremeThreshold) return 2;
        return 1;
    });

    const momentum = mansfield.map((m, i) =>
        i > 0 && m !== null && mansfield[i - 1] !== null ? m - mansfield[i - 1] : null
    );
    const isAccelerating = momentum.map(m => m !== null && m > 0);

    // 10種顏色：5個強度等級 × 加速/減速，使用更有區分度的配色
    const colors = mansfield.map((m, i) => {
        const level = strengthLevel[i];
        const accel = isAccelerating[i];
        if (level === null) return null;
        // Level 5: 極強 - 深紅/粉紅
        if (level === 5) return accel ? '#B71C1C' : '#f79696ff';
        // Level 4: 強 - 橙色/淺橙
        if (level === 4) return accel ? '#E65100' : '#f3c786ff';
        // Level 3: 中性 - 灰色/淺灰
        if (level === 3) return accel ? '#616161' : '#d6d6d6ff';
        // Level 2: 弱 - 青綠/淺青
        if (level === 2) return accel ? '#3cff00aa' : '#b9ffa4aa';
        // Level 1: 極弱 - 深藍/天藍
        return accel ? '#0077ffff' : '#77d0f9ff';
    });

    const rs3d = alignedData.map((d, i) => {
        if (i < 3 || !d.index) return null;
        const prev = alignedData[i - 3];
        if (!prev || !prev.index) return null;
        const stockChange = (d.stock.close / prev.stock.close - 1) * 100;
        const indexChange = (d.index.close / prev.index.close - 1) * 100;
        return stockChange - indexChange;
    });

    const rs10d = alignedData.map((d, i) => {
        if (i < 10 || !d.index) return null;
        const prev = alignedData[i - 10];
        if (!prev || !prev.index) return null;
        const stockChange = (d.stock.close / prev.stock.close - 1) * 100;
        const indexChange = (d.index.close / prev.index.close - 1) * 100;
        return stockChange - indexChange;
    });

    return stockData.map((s, i) => ({
        time: s.time,
        mansfield: mansfield[i],
        color: colors[i],
        level: strengthLevel[i],
        isAccelerating: isAccelerating[i],
        rs3d: rs3d[i],
        rs10d: rs10d[i]
    }));
}

// Load TAIEX Data
async function loadTAIEXData() {
    try {
        const response = await fetch('data/TAIEX.json');
        const json = await response.json();
        return json.data;
    } catch (error) {
        console.error('Failed to load TAIEX data:', error);
        return null;
    }
}

let taiexData = null;
let rsChart = null;
let mansfieldSeries = null;
let rs10dSeries = null;
let rs3dSeries = null;

async function initializeTAIEX() {
    taiexData = await loadTAIEXData();
    if (taiexData) {
        console.log('TAIEX data loaded:', taiexData.length, 'bars');
    }
}

function createRSChartContainer() {
    return; // Disabled - using V2 version only
    if (document.getElementById('rsChartContainer')) return;
    const rsiContainer = document.querySelector('.rsi-container') || document.querySelector('[id*="rsi"]')?.parentElement;
    const rsContainer = document.createElement('div');
    rsContainer.className = 'rs-container';
    rsContainer.innerHTML = '<h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 14px;">相對強度</h3><div id="rsChart" style="width: 100%; height: 200px;"></div>';
    if (rsiContainer && rsiContainer.nextSibling) {
        rsiContainer.parentNode.insertBefore(rsContainer, rsiContainer.nextSibling);
    } else {
        document.body.appendChild(rsContainer);
    }
    const style = document.createElement('style');
    style.textContent = '.rs-container { background: var(--bg-secondary, #1e222d); border-radius: 12px; padding: 16px; margin-top: 8px; } #rsChart { width: 100%; height: 200px; }';
    document.head.appendChild(style);
}

function initializeRSChart() {
    return; // Disabled - using V2 version only
    createRSChartContainer();
    const container = document.getElementById('rsChart');
    if (!container) return;
    rsChart = LightweightCharts.createChart(container, {
        layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
        width: container.clientWidth,
        height: 200,
        timeScale: { borderColor: '#485c7b' },
        rightPriceScale: { borderColor: '#485c7b' }
    });
    mansfieldSeries = rsChart.addHistogramSeries({ priceFormat: { type: 'price', precision: 2 } });
    rs10dSeries = rsChart.addLineSeries({ color: '#ff9800', lineWidth: 2, title: '10d RS' });
    rs3dSeries = rsChart.addLineSeries({ color: '#42a5f5', lineWidth: 1, title: '3d RS' });
    console.log('RS chart initialized');
}

async function updateRSChart(stockData) {
    if (!taiexData) return;
    if (!rsChart) initializeRSChart();
    const rsData = calculateMansfieldRS(stockData, taiexData);
    mansfieldSeries.setData(rsData.filter(d => d.mansfield !== null).map(d => ({ time: d.time, value: d.mansfield, color: d.color })));
    rs10dSeries.setData(rsData.filter(d => d.rs10d !== null).map(d => ({ time: d.time, value: d.rs10d })));
    rs3dSeries.setData(rsData.filter(d => d.rs3d !== null).map(d => ({ time: d.time, value: d.rs3d })));
    console.log('RS chart updated:', rsData.length, 'bars');
}

function wrapLoadStockFunction() {
    if (typeof window.originalLoadStock === 'undefined' && typeof loadStock === 'function') {
        window.originalLoadStock = loadStock;
        window.loadStock = async function (stockId) {
            const result = await window.originalLoadStock(stockId);

            // 更新成交量顏色
            if (typeof volumeSeries !== 'undefined' && volumeSeries && currentData) {
                const volumeData = currentData.map((d, i) => {
                    const prevClose = i > 0 ? currentData[i - 1].close : d.close;
                    let color = d.close > prevClose ? '#ef5350' : d.close < prevClose ? '#00C853' : '#757575';
                    return { time: d.time, value: d.volume, color: color };
                });
                volumeSeries.setData(volumeData);
                console.log('Volume colors updated');
            }

            // 更新 RS 指標 (使用 V2 版本)
            if (currentData && currentData.length > 0 && typeof updateRSChartV2 === 'function') {
                await updateRSChartV2(currentData);
            }

            // 確保所有圖表顯示最近 100 筆
            if (currentData && currentData.length > 0) {
                const totalBars = currentData.length;
                const visibleBars = Math.min(100, totalBars);
                const range = { from: totalBars - visibleBars, to: totalBars };

                if (mainChart) mainChart.timeScale().setVisibleLogicalRange(range);
                if (volumeChart) volumeChart.timeScale().setVisibleLogicalRange(range);
                if (rsiChart) rsiChart.timeScale().setVisibleLogicalRange(range);
                if (typeof rsChartV2 !== 'undefined' && rsChartV2) {
                    rsChartV2.timeScale().setVisibleLogicalRange(range);
                }
            }

            return result;
        };
        console.log('loadStock function wrapped');
    }
}

if (typeof window !== 'undefined') {
    window.addEventListener('load', async () => {
        await initializeTAIEX();
        setTimeout(() => {
            // initializeRSChart(); // 已棄用，改用 V2 版本
            wrapLoadStockFunction();
            console.log('RS indicator system initialized');
        }, 1000);
    });
}
// ===================================================================
// RS Chart Auto-Update System - Alternative Approach
// ===================================================================

// Store last data hash to detect changes
let lastDataHash = '';

function getDataHash(data) {
    if (!data || data.length === 0) return '';
    return data.length + '_' + data[0].time + '_' + data[data.length - 1].time;
}

// Check for data changes and update RS chart
function checkAndUpdateRS() {
    if (typeof currentData === 'undefined' || !currentData || currentData.length === 0) return;

    const newHash = getDataHash(currentData);
    if (newHash !== lastDataHash) {
        lastDataHash = newHash;

        // Update volume colors
        if (typeof volumeSeries !== 'undefined' && volumeSeries) {
            const volumeData = currentData.map((d, i) => {
                const prevClose = i > 0 ? currentData[i - 1].close : d.close;
                let color = d.close > prevClose ? '#ef5350' : d.close < prevClose ? '#00C853' : '#757575';
                return { time: d.time, value: d.volume, color: color };
            });
            volumeSeries.setData(volumeData);
            console.log('Volume colors updated');
        }

        // Update RS chart
        if (taiexData && currentData.length > 0) {
            updateRSChart(currentData);
        }
    }
}

// Global function for manual refresh
window.refreshRS = function () {
    if (typeof currentData !== 'undefined' && currentData && currentData.length > 0) {
        lastDataHash = ''; // Force update
        checkAndUpdateRS();
        console.log('RS chart manually refreshed');
    } else {
        console.log('No stock data loaded yet');
    }
};

// Start checking for data changes
if (typeof window !== 'undefined') {
    window.addEventListener('load', () => {
        // Check every 500ms for data changes
        setInterval(checkAndUpdateRS, 500);
        console.log('RS auto-update system started');
    });
}
// ===================================================================
// RS Chart Fix - Separate Charts, Single Container, Correct Colors
// ===================================================================

// K-bar colors (matching the main chart)
const RS_COLORS = {
    up: '#ef5350',      // Red for up
    down: '#00C853',    // Green for down
    neutral: '#757575'  // Gray for unchanged
};

// Prevent duplicate containers
let rsContainerCreated = false;

// Fixed container creation - only one container
function createRSChartContainerFixed() {
    return; // Disabled - using V2 version only
    // Check if already created
    if (rsContainerCreated) return;
    if (document.getElementById('rsChartContainer')) {
        rsContainerCreated = true;
        return;
    }

    // Find insertion point
    const rsiContainer = document.querySelector('.rsi-container');

    // Create container with TWO chart divs
    const rsContainer = document.createElement('div');
    rsContainer.id = 'rsChartContainer';
    rsContainer.className = 'rs-container';
    rsContainer.innerHTML = `
        <h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 14px;">相對強度</h3>
        <div id="mansfieldChart" style="width: 100%; height: 120px;"></div>
        <div id="rsLineChart" style="width: 100%; height: 100px; margin-top: 4px;"></div>
    `;

    // Insert after RSI container
    if (rsiContainer && rsiContainer.nextSibling) {
        rsiContainer.parentNode.insertBefore(rsContainer, rsiContainer.nextSibling);
    } else if (rsiContainer) {
        rsiContainer.parentNode.appendChild(rsContainer);
    } else {
        document.body.appendChild(rsContainer);
    }

    // Add styles
    const style = document.createElement('style');
    style.id = 'rs-styles';
    style.textContent = `
        .rs-container {
            background: var(--bg-secondary, #1e222d);
            border-radius: 12px;
            padding: 16px;
            margin-top: 8px;
        }
    `;
    if (!document.getElementById('rs-styles')) {
        document.head.appendChild(style);
    }

    rsContainerCreated = true;
    console.log('RS container created (fixed version)');
}

// Separate charts for histogram and lines
let mansfieldChart = null;
let rsLineChart = null;
let mansfieldHistogram = null;
let rs10dLine = null;
let rs3dLine = null;

function initializeRSChartsFixed() {
    return; // Disabled - using V2 version only
    createRSChartContainerFixed();

    const mansfieldContainer = document.getElementById('mansfieldChart');
    const lineContainer = document.getElementById('rsLineChart');

    if (!mansfieldContainer || !lineContainer) return;

    // Mansfield Histogram Chart
    mansfieldChart = LightweightCharts.createChart(mansfieldContainer, {
        layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
        width: mansfieldContainer.clientWidth,
        height: 120,
        timeScale: { borderColor: '#485c7b', visible: false },
        rightPriceScale: { borderColor: '#485c7b' }
    });

    mansfieldHistogram = mansfieldChart.addHistogramSeries({
        priceFormat: { type: 'price', precision: 2 }
    });

    // RS Lines Chart
    rsLineChart = LightweightCharts.createChart(lineContainer, {
        layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
        width: lineContainer.clientWidth,
        height: 100,
        timeScale: { borderColor: '#485c7b' },
        rightPriceScale: { borderColor: '#485c7b' }
    });

    rs10dLine = rsLineChart.addLineSeries({ color: '#ff9800', lineWidth: 2, title: '10d RS' });
    rs3dLine = rsLineChart.addLineSeries({ color: '#42a5f5', lineWidth: 1, title: '3d RS' });

    // Sync time scales
    mansfieldChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) rsLineChart.timeScale().setVisibleLogicalRange(range);
    });
    rsLineChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) mansfieldChart.timeScale().setVisibleLogicalRange(range);
    });

    console.log('RS charts initialized (fixed - separate histogram and lines)');
}

// Fixed update function
async function updateRSChartsFixed(stockData) {
    if (!taiexData) {
        console.log('Waiting for TAIEX data...');
        return;
    }

    if (!mansfieldChart || !rsLineChart) {
        initializeRSChartsFixed();
    }

    const rsData = calculateMansfieldRS(stockData, taiexData);

    // Update Mansfield histogram
    const histogramData = rsData
        .filter(d => d.mansfield !== null)
        .map(d => ({ time: d.time, value: d.mansfield, color: d.color }));
    mansfieldHistogram.setData(histogramData);

    // Update RS lines
    rs10dLine.setData(rsData.filter(d => d.rs10d !== null).map(d => ({ time: d.time, value: d.rs10d })));
    rs3dLine.setData(rsData.filter(d => d.rs3d !== null).map(d => ({ time: d.time, value: d.rs3d })));

    console.log('RS charts updated:', rsData.length, 'bars');
}

// Fixed volume color update with K-bar matching green
function updateVolumeColorsFixed(candleData) {
    if (typeof volumeSeries === 'undefined' || !volumeSeries) return;

    const volumeData = candleData.map((d, i) => {
        const prevClose = i > 0 ? candleData[i - 1].close : d.close;
        let color;
        if (d.close > prevClose) {
            color = RS_COLORS.up;      // #ef5350 (red)
        } else if (d.close < prevClose) {
            color = RS_COLORS.down;    // #00C853 (green)
        } else {
            color = RS_COLORS.neutral; // #757575 (gray)
        }
        return { time: d.time, value: d.volume, color: color };
    });

    volumeSeries.setData(volumeData);
    console.log('Volume colors updated (matching K-bar green)');
}

// Fixed data change detection
let lastDataHashFixed = '';

function checkAndUpdateRSFixed() {
    if (typeof currentData === 'undefined' || !currentData || currentData.length === 0) return;

    const newHash = currentData.length + '_' + currentData[0].time + '_' + currentData[currentData.length - 1].time;
    if (newHash !== lastDataHashFixed) {
        lastDataHashFixed = newHash;

        // Update volume colors
        updateVolumeColorsFixed(currentData);

        // Update RS charts
        if (taiexData) {
            updateRSChartsFixed(currentData);
        }
    }
}

// Remove old duplicate containers on load
function cleanupOldContainers() {
    const oldContainers = document.querySelectorAll('.rs-container');
    oldContainers.forEach((container, index) => {
        if (index > 0 || !container.querySelector('#mansfieldChart')) {
            container.remove();
            console.log('Removed old RS container');
        }
    });
}

// Override old functions
window.refreshRS = function () {
    lastDataHashFixed = '';
    checkAndUpdateRSFixed();
    console.log('RS manually refreshed');
};

// Initialize on load
if (typeof window !== 'undefined') {
    window.addEventListener('load', async () => {
        // Wait for TAIEX
        let attempts = 0;
        while (!taiexData && attempts < 20) {
            await new Promise(r => setTimeout(r, 250));
            attempts++;
        }

        // Cleanup old containers
        cleanupOldContainers();

        // Initialize
        initializeRSChartsFixed();

        // Start auto-update
        setInterval(checkAndUpdateRSFixed, 500);
        console.log('RS system (fixed) initialized');
    });
}
// ===================================================================
// RS Chart - Single Chart with Dual Y-Axis (Overlay Mode)
// ===================================================================

const RS_COLORS_V2 = {
    up: '#ef5350',
    down: '#00C853',    // Green for down
    neutral: '#757575'
};

let rsContainerCreatedV2 = false;
let rsChartV2 = null;
let mansfieldSeriesV2 = null;
let rs10dSeriesV2 = null;
let rs3dSeriesV2 = null;

function createRSChartContainerV2() {
    if (rsContainerCreatedV2) return;
    if (document.getElementById('rsChartContainerV2')) {
        rsContainerCreatedV2 = true;
        return;
    }

    // Remove all old containers
    document.querySelectorAll('.rs-container').forEach(c => c.remove());

    const rsiContainer = document.querySelector('.rsi-container');

    const rsContainer = document.createElement('div');
    rsContainer.id = 'rsChartContainerV2';
    rsContainer.className = 'rs-container';
    rsContainer.innerHTML = `
        <div class="indicator-label"><span>相對強度</span></div>
        <div id="rsChartV2" style="width: 100%; height: 200px;"></div>
    `;

    if (rsiContainer && rsiContainer.nextSibling) {
        rsiContainer.parentNode.insertBefore(rsContainer, rsiContainer.nextSibling);
    } else if (rsiContainer) {
        rsiContainer.parentNode.appendChild(rsContainer);
    } else {
        document.body.appendChild(rsContainer);
    }

    const style = document.createElement('style');
    style.id = 'rs-styles-v2';
    style.textContent = `.rs-container { background: var(--bg-secondary, #161b22); border-radius: 12px; padding: 16px; margin-top: 8px; }`;
    if (!document.getElementById('rs-styles-v2')) {
        document.head.appendChild(style);
    }

    rsContainerCreatedV2 = true;
}

function initializeRSChartV2() {
    createRSChartContainerV2();

    const container = document.getElementById('rsChartV2');
    if (!container) return;

    // Single chart with dual price scales
    rsChartV2 = LightweightCharts.createChart(container, {
        layout: { background: { type: 'solid', color: '#161b22' }, textColor: '#8b949e' },
        grid: { vertLines: { color: '#21262d' }, horzLines: { color: '#21262d' } },
        width: container.clientWidth,
        height: 200,
        timeScale: { borderColor: '#30363d', rightOffset: 5 },
        rightPriceScale: {
            borderColor: '#30363d',
            scaleMargins: { top: 0.1, bottom: 0.1 },
            minimumWidth: 80
        },
        leftPriceScale: {
            visible: false,  // 隱藏左側價格標籤
            borderColor: '#30363d',
            scaleMargins: { top: 0.1, bottom: 0.1 },
            minimumWidth: 80
        }
    });

    // Mansfield histogram on RIGHT price scale (hidden label)
    mansfieldSeriesV2 = rsChartV2.addHistogramSeries({
        priceScaleId: 'right',
        priceFormat: { type: 'price', precision: 2 },
        lastValueVisible: false,
        priceLineVisible: false
    });

    // RS lines on RIGHT price scale (hidden label)
    rs10dSeriesV2 = rsChartV2.addLineSeries({
        priceScaleId: 'right',
        color: '#ff9800',
        lineWidth: 2,
        lastValueVisible: false,
        priceLineVisible: false
    });

    rs3dSeriesV2 = rsChartV2.addLineSeries({
        priceScaleId: 'right',
        color: '#42a5f5',
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false
    });

    // 與其他圖表同步時間軸（使用全局同步函數）
    const syncWithOtherCharts = () => {
        if (!mainChart || !volumeChart || !rsiChart) return;

        // RS 圖表變化時，使用全局同步函數同步所有圖表
        rsChartV2.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (range && !window.rsSyncLock && window.syncAllChartsTimeScale) {
                window.rsSyncLock = true;
                window.syncAllChartsTimeScale(range, rsChartV2);
                window.rsSyncLock = false;
            }
        });

        console.log('RS chart synced with main charts');

        // 加入 crosshair 同步 (RS -> 其他圖表)
        rsChartV2.subscribeCrosshairMove(param => {
            if (param.time) {
                mainChart.setCrosshairPosition(NaN, candleSeries, param.time);
                volumeChart.setCrosshairPosition(NaN, volumeSeries, param.time);
                rsiChart.setCrosshairPosition(NaN, rsiSeries6, param.time);
            } else {
                mainChart.clearCrosshairPosition();
                volumeChart.clearCrosshairPosition();
                rsiChart.clearCrosshairPosition();
            }
        });

        // 反向同步 (其他圖表 -> RS)
        const syncToRS = (sourceChart) => {
            sourceChart.subscribeCrosshairMove(param => {
                if (rsChartV2 && mansfieldSeriesV2) {
                    if (param.time) {
                        rsChartV2.setCrosshairPosition(NaN, mansfieldSeriesV2, param.time);
                    } else {
                        rsChartV2.clearCrosshairPosition();
                    }
                }
            });
        };
        syncToRS(mainChart);
        syncToRS(volumeChart);
        syncToRS(rsiChart);
    };

    // 延遲執行確保其他圖表已初始化
    setTimeout(syncWithOtherCharts, 100);

    console.log('RS chart V2 initialized (dual Y-axis overlay)');
}

async function updateRSChartV2(stockData) {
    if (!taiexData) return;
    if (!rsChartV2) initializeRSChartV2();

    const rsData = calculateMansfieldRS(stockData, taiexData);

    // 儲存 RS 數據供 tooltip 使用（對齊 currentData 的索引）
    currentRSData = rsData;

    // 啟用同步鎖，防止 setData 觸發連鎖反應
    window.rsSyncLock = true;

    // Mansfield histogram - 保留所有日期以對齊其他圖表
    mansfieldSeriesV2.setData(
        rsData.map(d => ({
            time: d.time,
            value: d.mansfield !== null ? d.mansfield : 0,
            color: d.color || '#9E9E9E'
        }))
    );

    // RS lines - 保留所有日期
    rs10dSeriesV2.setData(rsData.map(d => ({
        time: d.time,
        value: d.rs10d !== null ? d.rs10d : 0
    })));
    rs3dSeriesV2.setData(rsData.map(d => ({
        time: d.time,
        value: d.rs3d !== null ? d.rs3d : 0
    })));

    // 同步主圖表的可見範圍到 RS 圖表
    if (mainChart) {
        const range = mainChart.timeScale().getVisibleLogicalRange();
        if (range) {
            rsChartV2.timeScale().setVisibleLogicalRange(range);
        }
    }

    // 解除同步鎖
    window.rsSyncLock = false;

    console.log('RS chart V2 updated:', rsData.length, 'bars');
}

function updateVolumeColorsV2(candleData) {
    if (typeof volumeSeries === 'undefined' || !volumeSeries) return;

    const volumeData = candleData.map((d, i) => {
        const prevClose = i > 0 ? candleData[i - 1].close : d.close;
        let color = d.close > prevClose ? RS_COLORS_V2.up : d.close < prevClose ? RS_COLORS_V2.down : RS_COLORS_V2.neutral;
        return { time: d.time, value: d.volume, color: color };
    });

    volumeSeries.setData(volumeData);
}

let lastDataHashV2 = '';

function checkAndUpdateRSV2() {
    if (typeof currentData === 'undefined' || !currentData || currentData.length === 0) return;

    const newHash = currentData.length + '_' + currentData[0].time + '_' + currentData[currentData.length - 1].time;
    if (newHash !== lastDataHashV2) {
        lastDataHashV2 = newHash;
        updateVolumeColorsV2(currentData);
        if (taiexData) updateRSChartV2(currentData);
    }
}

window.refreshRS = function () {
    lastDataHashV2 = '';
    checkAndUpdateRSV2();
};

if (typeof window !== 'undefined') {
    window.addEventListener('load', async () => {
        let attempts = 0;
        while (!taiexData && attempts < 20) {
            await new Promise(r => setTimeout(r, 250));
            attempts++;
        }

        // Remove ALL old containers
        document.querySelectorAll('.rs-container').forEach(c => c.remove());
        rsContainerCreatedV2 = false;

        initializeRSChartV2();
        setInterval(checkAndUpdateRSV2, 500);
        console.log('RS V2 (dual Y-axis) initialized');
    });
}
