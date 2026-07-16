/**
 * Calculates Simple Moving Average (SMA) lines based on given candle data.
 * @param {Array} data - Array of candles like [{time, close}, ...]
 * @param {number} period - Moving average window period (e.g., 5, 20, 60)
 * @returns {Array} - Array of SMA data like [{time, value: number|undefined}]
 */
export function calculateSMA(data, period) {
  if (!data || data.length === 0) return [];
  const smaData = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      smaData.push({ time: data[i].time, value: undefined });
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j].close;
      }
      smaData.push({ time: data[i].time, value: sum / period });
    }
  }
  return smaData;
}

/**
 * Determines the volume bar color based on candle open/close and previous candle close.
 * @param {Object} candle - Current candle data
 * @param {Object|null} prevCandle - Previous candle data
 * @returns {string} - HEX color code
 */
export function getVolumeColor(candle, prevCandle) {
  const currentClose = candle.close ?? 0;
  const currentOpen = candle.open ?? 0;
  
  if (currentClose > currentOpen) {
    return '#10b981'; // Bullish green
  } else if (currentClose < currentOpen) {
    return '#ef4444'; // Bearish red
  }
  
  // Compare with previous candle if open and close are equal
  if (prevCandle && currentClose < (prevCandle.close ?? 0)) {
    return '#ef4444';
  }
  return '#10b981';
}
