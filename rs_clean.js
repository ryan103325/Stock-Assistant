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
    const minLength = Math.min(stockData.length, indexData.length);
    const stock = stockData.slice(-minLength);
    const index = indexData.slice(-minLength);

    const rsRatio = stock.map((s, i) => (s.close / index[i].close) * 100);
    const rsBaseline = calculateSMA(rsRatio, 50);
    const mansfield = rsRatio.map((ratio, i) =>
        rsBaseline[i] !== null ? ratio - rsBaseline[i] : null
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

    const colors = mansfield.map((m, i) => {
        const level = strengthLevel[i];
        const accel = isAccelerating[i];
        if (level === null) return null;
        if (level === 5) return accel ? 'rgba(183, 28, 28, 0.8)' : 'rgba(211, 47, 47, 0.5)';
        if (level === 4) return accel ? 'rgba(229, 57, 53, 0.7)' : 'rgba(239, 83, 80, 0.4)';
        if (level === 3) return accel ? 'rgba(117, 117, 117, 0.6)' : 'rgba(158, 158, 158, 0.3)';
        if (level === 2) return accel ? 'rgba(102, 187, 106, 0.4)' : 'rgba(67, 160, 71, 0.7)';
        return accel ? 'rgba(46, 125, 50, 0.5)' : 'rgba(27, 94, 32, 0.8)';
    });

    const rs3d = stock.map((s, i) => {
        if (i < 3) return null;
        const stockChange = (s.close / stock[i - 3].close - 1) * 100;
        const indexChange = (index[i].close / index[i - 3].close - 1) * 100;
        return stockChange - indexChange;
    });

    const rs10d = stock.map((s, i) => {
        if (i < 10) return null;
        const stockChange = (s.close / stock[i - 10].close - 1) * 100;
        const indexChange = (index[i].close / index[i - 10].close - 1) * 100;
        return stockChange - indexChange;
    });

    return stock.map((s, i) => ({
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
    if (document.getElementById('rsChartContainer')) return;
    const rsiContainer = document.querySelector('.rsi-container') || document.querySelector('[id*="rsi"]')?.parentElement;
    const rsContainer = document.createElement('div');
    rsContainer.className = 'rs-container';
    rsContainer.innerHTML = '<h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 14px;">MTF-RS Hybrid (Mansfield/IBD)</h3><div id="rsChart" style="width: 100%; height: 200px;"></div>';
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
            if (typeof volumeSeries !== 'undefined' && volumeSeries && currentData) {
                const volumeData = currentData.map((d, i) => {
                    const prevClose = i > 0 ? currentData[i - 1].close : d.close;
                    let color = d.close > prevClose ? '#ef5350' : d.close < prevClose ? '#26a69a' : '#757575';
                    return { time: d.time, value: d.volume, color: color };
                });
                volumeSeries.setData(volumeData);
                console.log('Volume colors updated');
            }
            if (currentData && currentData.length > 0) {
                await updateRSChart(currentData);
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
            initializeRSChart();
            wrapLoadStockFunction();
            console.log('RS indicator system initialized');
        }, 1000);
    });
}
