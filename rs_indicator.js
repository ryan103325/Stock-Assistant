// ===================================================================
// 成交量顏色計算（根據收盤價變化）
// ===================================================================

/**
 * 為成交量數據添加顏色
 * @param {Array} candleData - K線數據
 * @param {Array} volumeData - 成交量數據
 * @returns {Array} 帶顏色的成交量數據
 */
function addVolumeColors(candleData, volumeData) {
    return volumeData.map((v, i) => {
        const currentClose = candleData[i].close;
        const prevClose = i > 0 ? candleData[i - 1].close : currentClose;

        let color;
        if (currentClose > prevClose) {
            color = '#ef5350';  // 紅色（漲）
        } else if (currentClose < prevClose) {
            color = '#26a69a';  // 綠色（跌）
        } else {
            color = '#757575';  // 灰色（平盤）
        }

        return {
            ...v,
            color: color
        };
    });
}


// ===================================================================
// MTF-RS 混合版指標計算（v4.0）
// ===================================================================

/**
 * 計算簡單移動平均
 */
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

/**
 * 計算標準差
 */
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

/**
 * 計算 Mansfield 相對強度
 * @param {Array} stockData - 股票數據 [{time, close, ...}]
 * @param {Array} indexData - 指數數據 [{time, close, ...}]
 * @returns {Object} RS 指標數據
 */
function calculateMansfieldRS(stockData, indexData) {
    // 確保數據長度一致
    const minLength = Math.min(stockData.length, indexData.length);
    const stock = stockData.slice(-minLength);
    const index = indexData.slice(-minLength);

    // 步驟 1: 計算 RS Ratio
    const rsRatio = stock.map((s, i) => (s.close / index[i].close) * 100);

    // 步驟 2: 計算 50日移動平均基準線
    const rsBaseline = calculateSMA(rsRatio, 50);

    // 步驟 3: 計算 Mansfield 偏離值
    const mansfield = rsRatio.map((ratio, i) =>
        rsBaseline[i] !== null ? ratio - rsBaseline[i] : null
    );

    // 步驟 4: 計算 21日標準差
    const sigma = calculateStdev(mansfield.map(m => m || 0), 21);

    // 步驟 5 & 6: 統計分級（1-5）
    const strengthLevel = mansfield.map((m, i) => {
        if (m === null || sigma[i] === null) return null;

        const neutralThreshold = 0.7 * sigma[i];
        const extremeThreshold = 1.5 * sigma[i];

        if (m > extremeThreshold) return 5;      // 極強
        if (m > neutralThreshold) return 4;       // 偏強
        if (m > -neutralThreshold) return 3;      // 中立
        if (m > -extremeThreshold) return 2;      // 偏弱
        return 1;                                 // 極弱
    });

    // 步驟 7 & 8: 動能方向判斷（A/B）
    const momentum = mansfield.map((m, i) =>
        i > 0 && m !== null && mansfield[i - 1] !== null ? m - mansfield[i - 1] : null
    );

    const isAccelerating = momentum.map(m => m !== null && m > 0);

    // 顏色映射（10色系統）
    const colors = mansfield.map((m, i) => {
        const level = strengthLevel[i];
        const accel = isAccelerating[i];

        if (level === null) return null;

        if (level === 5) {
            return accel ? 'rgba(183, 28, 28, 0.8)' : 'rgba(211, 47, 47, 0.5)';  // 5A / 5B
        } else if (level === 4) {
            return accel ? 'rgba(229, 57, 53, 0.7)' : 'rgba(239, 83, 80, 0.4)';  // 4A / 4B
        } else if (level === 3) {
            return accel ? 'rgba(117, 117, 117, 0.6)' : 'rgba(158, 158, 158, 0.3)';  // 3A / 3B
        } else if (level === 2) {
            return accel ? 'rgba(102, 187, 106, 0.4)' : 'rgba(67, 160, 71, 0.7)';  // 2A / 2B
        } else {
            return accel ? 'rgba(46, 125, 50, 0.5)' : 'rgba(27, 94, 32, 0.8)';  // 1A / 1B
        }
    });

    // 計算短期 RS
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

    // 組合時間序列
    const timeData = stock.map((s, i) => ({
        time: s.time,
        mansfield: mansfield[i],
        color: colors[i],
        level: strengthLevel[i],
        isAccelerating: isAccelerating[i],
        rs3d: rs3d[i],
        rs10d: rs10d[i]
    }));

    return timeData;
}

/**
 * 載入 TAIEX 指數資料
 */
async function loadTAIEXData() {
    try {
        const response = await fetch('data/TAIEX.json');
        const json = await response.json();
        return json.data;
    } catch (error) {
        console.error('載入 TAIEX 資料失敗:', error);
        return null;
    }
}

// 全域變數存儲指數資料
let taiexData = null;

// 初始化時載入 TAIEX
async function initializeTAIEX() {
    taiexData = await loadTAIEXData();
    if (taiexData) {
        console.log('TAIEX 資料已載入:', taiexData.length, '筆');
    }
}

// 頁面載入時初始化
if (typeof window !== 'undefined') {
    window.addEventListener('load', initializeTAIEX);
}
