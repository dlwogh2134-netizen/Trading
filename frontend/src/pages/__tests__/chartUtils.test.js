import assert from 'assert';
import { calculateSMA, getVolumeColor } from '../chartUtils.js';

console.log('Running chartUtils tests...');

try {
  // Test calculateSMA
  const mockCandles = [
    { time: 1000, close: 10 },
    { time: 2000, close: 12 },
    { time: 3000, close: 14 },
    { time: 4000, close: 16 },
  ];
  
  const sma3 = calculateSMA(mockCandles, 3);
  assert.strictEqual(sma3[0].value, undefined, 'Data point 0 should be undefined for period 3');
  assert.strictEqual(sma3[1].value, undefined, 'Data point 1 should be undefined for period 3');
  assert.strictEqual(sma3[2].value, 12, 'SMA of 10,12,14 should be 12');
  assert.strictEqual(sma3[3].value, 14, 'SMA of 12,14,16 should be 14');

  // Test getVolumeColor
  assert.strictEqual(getVolumeColor({ close: 15, open: 10 }, null), '#10b981');
  assert.strictEqual(getVolumeColor({ close: 8, open: 10 }, null), '#ef4444');
  assert.strictEqual(getVolumeColor({ close: 10, open: 10 }, { close: 8 }), '#10b981');
  
  console.log('All tests passed successfully!');
} catch (error) {
  console.error('Test failed:', error.message);
  process.exit(1);
}
