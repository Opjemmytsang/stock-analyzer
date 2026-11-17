// Run: node tests/signal-engine.test.js
const assert=require('node:assert/strict');
require('../signal-engine.js');
const e=globalThis.OptionRadarEngine;
for(const symbol of ['SPY','QQQ','NVDA','TSLA','AMD']){
 const result=e.analyze(e.demoCandles(symbol));
 assert.equal(result.dataStatus,'DEMO');
 assert.equal(result.isTradeSignal,false);
 assert.ok(result.score>=0&&result.score<=100);
 assert.ok(result.vwap>0);
 assert.ok(result.rvol>=0);
 assert.ok(Number.isFinite(result.rangeHigh));
}
assert.throws(()=>e.analyze([]),/20/);
const bad=e.demoCandles('SPY');bad[0].volume=-1;
assert.throws(()=>e.analyze(bad),/無效/);
console.log('Signal engine tests passed');
