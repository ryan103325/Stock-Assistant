// ===================================================================
// RS Chart Fix - Separate Charts, Single Container, Correct Colors
// ===================================================================

// K-bar colors (matching the main chart)
const RS_COLORS = {
    up: '#ef5350',      // Red for up
    down: '#00C853',    // Green for down (matching K-bar)
    neutral: '#757575'  // Gray for unchanged
};

// Prevent duplicate containers
let rsContainerCreated = false;

// Fixed container creation - only one container
function createRSChartContainerFixed() {
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
        <h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 14px;">MTF-RS Hybrid (Mansfield/IBD)</h3>
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
            color = RS_COLORS.down;    // #00C853 (green, matches K-bar)
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
