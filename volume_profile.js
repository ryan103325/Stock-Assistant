// === Volume Profile (LuxAlgo style) ===
// 動態 Volume Profile - 隨著視窗縮放/移動自動更新

const VP_ROWS = 25;  // 25 個價格區間
const VP_GRADIENT_COLORS = [
    '#1E152A', '#1F182C', '#201B2F', '#211E32', '#222135', '#242438', '#25273B', '#262B3E',
    '#272E41', '#283144', '#2A3447', '#2B374A', '#2C3A4D', '#2D3D50', '#2E4153', '#304455',
    '#314758', '#324A5B', '#334D5E', '#355061', '#365464', '#375767', '#385A6A', '#395D6D',
    '#3B6070'
];

function updateVolumeProfile() {
    const canvas = document.getElementById('vpCanvas');
    const chartDiv = document.getElementById('chart');
    if (!canvas || !chartDiv || !currentData || currentData.length === 0) return;
    if (!candleSeries) return;

    const ctx = canvas.getContext('2d');
    const chartRect = chartDiv.getBoundingClientRect();

    // 使用 timeScale().width() 取得實際圖表區域寬度
    const chartAreaWidth = mainChart.timeScale().width();
    if (!chartAreaWidth || chartAreaWidth <= 0) return;

    canvas.width = chartAreaWidth;
    canvas.height = chartRect.height;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 取得可見範圍
    const visibleRange = mainChart.timeScale().getVisibleLogicalRange();
    if (!visibleRange) return;

    const startIdx = Math.max(0, Math.floor(visibleRange.from));
    const endIdx = Math.min(currentData.length - 1, Math.ceil(visibleRange.to));
    if (endIdx <= startIdx) return;

    // 取得可見範圍內的數據
    const visibleData = currentData.slice(startIdx, endIdx + 1);

    // 計算價格範圍
    let minPrice = Infinity, maxPrice = -Infinity;
    visibleData.forEach(d => {
        minPrice = Math.min(minPrice, d.low);
        maxPrice = Math.max(maxPrice, d.high);
    });

    if (minPrice === maxPrice) return;

    // 建立 25 個價格區間
    const levels = [];
    for (let i = 0; i <= VP_ROWS; i++) {
        levels.push(minPrice + (i / VP_ROWS) * (maxPrice - minPrice));
    }

    // 計算每個區間的成交量（K線穿過該區間就累加）
    const sumv = new Array(VP_ROWS).fill(0);
    visibleData.forEach(d => {
        for (let j = 0; j < VP_ROWS; j++) {
            if (d.high > levels[j] && d.low < levels[j + 1]) {
                sumv[j] += d.volume;
            }
        }
    });

    const maxVol = Math.max(...sumv);
    if (maxVol === 0) return;

    // 繪製 VP 條形
    sumv.forEach((vol, i) => {
        if (vol === 0) return;

        const priceTop = levels[i + 1];
        const priceBottom = levels[i];

        // 將價格轉換成圖表 Y 座標
        const yTop = candleSeries.priceToCoordinate(priceTop);
        const yBottom = candleSeries.priceToCoordinate(priceBottom);

        if (yTop === null || yBottom === null) return;

        const barHeight = Math.abs(yBottom - yTop);
        const y = Math.min(yTop, yBottom);

        const ratio = vol / maxVol;
        const width = ratio * canvas.width;

        // 漸變色（根據成交量比例）
        const colorIndex = Math.min(VP_ROWS - 1, Math.floor(ratio * VP_ROWS));
        ctx.fillStyle = VP_GRADIENT_COLORS[colorIndex] + '80';  // 加上透明度

        // 從左側向右繪製
        ctx.fillRect(0, y, width, barHeight - 0.5);
    });
}

// 監聽圖表縮放/移動事件，動態更新 VP
function setupVolumeProfileListeners() {
    if (!mainChart) return;

    // 監聽 visible range 變化
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(() => {
        requestAnimationFrame(updateVolumeProfile);
    });

    // 初始繪製
    setTimeout(updateVolumeProfile, 100);
}

// 當頁面載入完成後，延遲初始化 VP（確保 mainChart 已存在）
if (typeof window !== 'undefined') {
    const initVP = () => {
        if (typeof mainChart !== 'undefined' && mainChart) {
            setupVolumeProfileListeners();
        } else {
            setTimeout(initVP, 200);
        }
    };
    setTimeout(initVP, 500);
}
