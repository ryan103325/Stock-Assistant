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
                let color = d.close > prevClose ? '#ef5350' : d.close < prevClose ? '#26a69a' : '#757575';
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
