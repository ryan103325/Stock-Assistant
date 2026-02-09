// ===================================================================
// RS 圖表整合與初始化
// ===================================================================

/**
 * 創建 RS 圖表容器（如果不存在）
 */
function createRSChartContainer() {
    // 檢查是否已存在
    if (document.getElementById('rsChartContainer')) return;

    // 找到 RSI 容器後面插入
    const rsiContainer = document.querySelector('.rsi-container') || document.querySelector('[id*="rsi"]')?.parentElement;

    if (!rsiContainer) {
        console.warn('找不到 RSI 容器，RS 圖表將添加到 body 末尾');
    }

    // 創建 RS 容器
    const rsContainer = document.createElement('div');
    rsContainer.className = 'rs-container';
    rsContainer.innerHTML = `
        <h3 style="margin: 0 0 8px 0; color: #e0e0e0; font-size: 14px;">MTF-RS 混合版 (Mansfield/IBD)</h3>
        <div id="rsChart" style="width: 100%; height: 200px;"></div>
    `;

    // 插入到適當位置
    if (rsiContainer && rsiContainer.nextSibling) {
        rsiContainer.parentNode.insertBefore(rsContainer, rsiContainer.nextSibling);
    } else {
        document.body.appendChild(rsContainer);
    }

    // 添加 CSS 樣式
    const style = document.createElement('style');
    style.textContent = `
        .rs-container {
            background: var(--bg-secondary, #1e222d);
            border-radius: 12px;
            padding: 16px;
            margin-top: 8px;
        }
        #rsChart {
            width: 100%;
            height: 200px;
        }
    `;
    document.head.appendChild(style);
}

/**
 * 初始化 RS 圖表
 */
let rsChart = null;
let mansfieldSeries = null;
let rs10dSeries = null;
let rs3dSeries = null;

function initializeRSChart() {
    createRSChartContainer();

    const container = document.getElementById('rsChart');
    if (!container) {
        console.error('RS 圖表容器不存在');
        return;
    }

    // 創建圖表
    rsChart = LightweightCharts.createChart(container, {
        layout: {
            background: { color: '#1e222d' },
            textColor: '#d1d4dc',
        },
        grid: {
            vertLines: { color: '#2b2b43' },
            horzLines: { color: '#2b2b43' },
        },
        width: container.clientWidth,
        height: 200,
        timeScale: {
            borderColor: '#485c7b',
        },
        rightPriceScale: {
            borderColor: '#485c7b',
        },
    });

    // Mansfield 柱狀圖
    mansfieldSeries = rsChart.addHistogramSeries({
        priceFormat: {
            type: 'price',
            precision: 2,
        },
    });

    // 10日 RS 線（橙色）
    rs10dSeries = rsChart.addLineSeries({
        color: '#ff9800',
        lineWidth: 2,
        title: '10日RS',
    });

    // 3日 RS 線（藍色）
    rs3dSeries = rsChart.addLineSeries({
        color: '#42a5f5',
        lineWidth: 1,
        title: '3日RS',
    });

    // 零軸線
    rsChart.applyOptions({
        priceScale: {
            mode: 0,  // Normal mode
        },
    });

    console.log('RS 圖表已初始化');
}

/**
 * 更新 RS 圖表數據
 * @param {Array} stockData - 股票數據
 */
async function updateRSChart(stockData) {
    if (!taiexData) {
        console.warn('TAIEX 資料尚未載入，無法計算 RS');
        return;
    }

    if (!rsChart) {
        initializeRSChart();
    }

    // 計算 RS 指標
    const rsData = calculateMansfieldRS(stockData, taiexData);

    // 準備 Mansfield 柱狀圖數據
    const mansfieldData = rsData
        .filter(d => d.mansfield !== null)
        .map(d => ({
            time: d.time,
            value: d.mansfield,
            color: d.color
        }));

    // 準備 RS 線數據
    const rs10Data = rsData
        .filter(d => d.rs10d !== null)
        .map(d => ({
            time: d.time,
            value: d.rs10d
        }));

    const rs3Data = rsData
        .filter(d => d.rs3d !== null)
        .map(d => ({
            time: d.time,
            value: d.rs3d
        }));

    // 設置數據
    mansfieldSeries.setData(mansfieldData);
    rs10dSeries.setData(rs10Data);
    rs3dSeries.setData(rs3Data);

    console.log('RS 圖表已更新:', rsData.length, '筆數據');
}

// ===================================================================
// 成交量顏色整合
// ===================================================================

/**
 * 包裝原有的股票載入函數，添加成交量顏色和 RS 計算
 */
function wrapLoadStockFunction() {
    // 保存原始的 loadStock 函數（如果存在）
    if (typeof window.originalLoadStock === 'undefined' && typeof loadStock === 'function') {
        window.originalLoadStock = loadStock;

        // 重寫 loadStock
        window.loadStock = async function (stockId) {
            // 呼叫原始函數
            const result = await window.originalLoadStock(stockId);

            // 如果有成交量序列，更新顏色
            if (typeof volumeSeries !== 'undefined' && volumeSeries && currentData) {
                const volumeData = currentData.map((d, i) => {
                    const prevClose = i > 0 ? currentData[i - 1].close : d.close;
                    let color;
                    if (d.close > prevClose) {
                        color = '#ef5350';  // 紅色
                    } else if (d.close < prevClose) {
                        color = '#26a69a';  // 綠色
                    } else {
                        color = '#757575';  // 灰色
                    }
                    return {
                        time: d.time,
                        value: d.volume,
                        color: color
                    };
                });

                volumeSeries.setData(volumeData);
                console.log('成交量顏色已更新');
            }

            // 更新 RS 圖表
            if (currentData && currentData.length > 0) {
                await updateRSChart(currentData);
            }

            return result;
        };

        console.log('loadStock 函數已包裝，添加成交量顏色和 RS 計算');
    }
}

// ===================================================================
// 自動初始化
// ===================================================================

// 等待頁面和 TAIEX 資料載入完成後初始化
if (typeof window !== 'undefined') {
    window.addEventListener('load', async () => {
        // 等待 TAIEX 載入
        await initializeTAIEX();

        // 初始化 RS 圖表
        setTimeout(() => {
            initializeRSChart();
            wrapLoadStockFunction();
            console.log('✅ RS 指標系統已初始化');
        }, 1000);
    });
}
