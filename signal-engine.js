/* OptionRadar research engine. No market-data feed; no investment recommendations. */
(function(global){
'use strict';
function analyze(candles){
 if(!Array.isArray(candles)||candles.length<20)throw Error('至少需要 20 根有效 K 線');
 let pv=0,volume=0;
 for(const c of candles){
  if(![c.open,c.high,c.low,c.close,c.volume].every(Number.isFinite)||c.high<Math.max(c.open,c.close,c.low)||c.low>Math.min(c.open,c.close)||c.volume<0)throw Error('K 線數據無效');
  const typical=(c.high+c.low+c.close)/3;pv+=typical*c.volume;volume+=c.volume;
 }
 if(volume<=0)throw Error('成交量不可全為零');
 const last=candles[candles.length-1],prior=candles.slice(-21,-1),first15=candles.slice(0,15);
 const vwap=pv/volume,avgVol=prior.reduce((a,c)=>a+c.volume,0)/prior.length;
 const rvol=avgVol?last.volume/avgVol:0;
 const rangeHigh=Math.max(...first15.map(c=>c.high)),rangeLow=Math.min(...first15.map(c=>c.low));
 const above=last.close>vwap,breakout=last.close>rangeHigh,breakdown=last.close<rangeLow;
 const reasons=[],risks=[];
 if(above)reasons.push('價格高於 VWAP');else reasons.push('價格低於或等於 VWAP');
 if(breakout)reasons.push('突破首 15 根 K 線高位');
 if(breakdown)reasons.push('跌穿首 15 根 K 線低位');
 if(rvol>=1.5)reasons.push('最新成交量為近期平均的 '+rvol.toFixed(2)+' 倍');
 if(rvol<1)risks.push('成交量低於近期平均');
 if(!breakout&&!breakdown)risks.push('尚未突破觀察區間');
 const score=(above?20:0)+(breakout?30:0)+(rvol>=1.5?25:rvol>=1?10:0)+(last.close>last.open?15:0)+(last.close>prior[prior.length-1].close?10:0);
 const state=breakout&&above&&rvol>=1.5?'觀察向上突破':breakdown&&!above?'觀察向下跌破':'等待確認';
 return {state,score,vwap,rvol,rangeHigh,rangeLow,last:last.close,reasons,risks,dataStatus:'DEMO',isTradeSignal:false};
}
function demoCandles(symbol){
 const seeds={SPY:600,NVDA:190,TSLA:320,AMD:165,QQQ:520};
 const base=seeds[symbol]||100,idx=Object.keys(seeds).indexOf(symbol)+1;
 const out=[];
 for(let i=0;i<30;i++){
  const wave=Math.sin((i+idx)*.75)*.0025,trend=(i-15)*.0005*(idx%2?1:-1);
  const close=base*(1+wave+trend),open=base*(1+Math.sin((i+idx-1)*.75)*.0025+(i-16)*.0005*(idx%2?1:-1));
  out.push({open,close,high:Math.max(open,close)*1.0015,low:Math.min(open,close)*.9985,volume:Math.round(80000+Math.abs(Math.sin(i+idx))*25000+(i===29?65000:0))});
 }
 return out;
}
global.OptionRadarEngine={analyze,demoCandles};
})(typeof globalThis!=='undefined'?globalThis:this);
