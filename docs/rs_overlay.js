// ===================================================================
// RS Chart - Single Chart with Dual Y-Axis (Overlay Mode)
// ===================================================================

const RS_COLORS_V2 = {
    up: '#ef5350',
    down: '#00C853',
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
        <h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 14px;">MTF-RS Hybrid (Mansfield/IBD)</h3>
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
    style.textContent = `.rs-container { background: var(--bg-secondary, #1e222d); border-radius: 12px; padding: 16px; margin-top: 8px; }`;
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
        layout: { background: { color: '#1e222d' }, textColor: '#d1d4dc' },
        grid: { vertLines: { color: '#2b2b43' }, horzLines: { color: '#2b2b43' } },
        width: container.clientWidth,
        height: 200,
        timeScale: { borderColor: '#485c7b' },
        rightPriceScale: { borderColor: '#485c7b', scaleMargins: { top: 0.1, bottom: 0.1 } },
        leftPriceScale: { visible: true, borderColor: '#485c7b', scaleMargins: { top: 0.1, bottom: 0.1 } }
    });

    // Mansfield histogram on LEFT price scale
    mansfieldSeriesV2 = rsChartV2.addHistogramSeries({
        priceScaleId: 'left',
        priceFormat: { type: 'price', precision: 2 }
    });

    // RS lines on RIGHT price scale
    rs10dSeriesV2 = rsChartV2.addLineSeries({
        priceScaleId: 'right',
        color: '#ff9800',
        lineWidth: 2,
        title: '10d RS'
    });

    rs3dSeriesV2 = rsChartV2.addLineSeries({
        priceScaleId: 'right',
        color: '#42a5f5',
        lineWidth: 1,
        title: '3d RS'
    });

    console.log('RS chart V2 initialized (dual Y-axis overlay)');
}

async function updateRSChartV2(stockData) {
    if (!taiexData) return;
    if (!rsChartV2) initializeRSChartV2();

    const rsData = calculateMansfieldRS(stockData, taiexData);

    // Mansfield histogram
    mansfieldSeriesV2.setData(
        rsData.filter(d => d.mansfield !== null)
            .map(d => ({ time: d.time, value: d.mansfield, color: d.color }))
    );

    // RS lines
    rs10dSeriesV2.setData(rsData.filter(d => d.rs10d !== null).map(d => ({ time: d.time, value: d.rs10d })));
    rs3dSeriesV2.setData(rsData.filter(d => d.rs3d !== null).map(d => ({ time: d.time, value: d.rs3d })));

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
