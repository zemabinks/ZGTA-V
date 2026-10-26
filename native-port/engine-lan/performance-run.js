/* Presented-frame samples from this launch only. No uploads or persisted history. */
(function(root){'use strict';
 const counters=new Set(['resourceBytesReleased','resourceBytesReused','resourceReclaimFailures','memoryBudgetClamps']);
 const gauges=new Set(['appFootprintBytes','availableMemoryBytes','thermalState','thermalScale','requestedRenderWidth','requestedRenderHeight','canvasWidth','canvasHeight', 'requestedFrameInterval', 'secondsSinceWorldReady']);
 class Run {
  constructor(){this.state='idle';this.samples=[];this.reason='';}
  start(now,context={},durationSeconds=30){if(![30,180].includes(durationSeconds))throw Error('Invalid duration');if(!Number.isFinite(now))throw Error('Invalid clock');this.measurementMS=durationSeconds*1000;this.state='running';this.started=now;this.last=now;this.samples=[];this.conditions={};this.latestGauges={};this.timeline=[];this.lastConditionTime=null;this.reason='';this.context={...context};this.result=null;}
  get endsAt(){return this.started+2000+this.measurementMS;}
  cancel(reason='Measurement cancelled.'){if(this.state==='running'){this.state='cancelled';this.reason=reason;this.result=null;}}
  tick(now){if(this.state==='running'&&(!Number.isFinite(now)||now<this.last||now-this.last>1500))this.cancel('Frame samples stopped. Start another measurement.');return this.state;}
  wantsConditions(now){return this.state==='running'&&Number.isFinite(now)&&now>=this.started+2000&&now<=this.endsAt&&(this.lastConditionTime===null||now-this.lastConditionTime>=1000);}
  observeConditions(values,now){
   if(!this.wantsConditions(now))return;this.lastConditionTime=now;
   for(const [name,value] of Object.entries(values)){
    if((!counters.has(name)&&!gauges.has(name))||!Number.isFinite(value)||value<0)continue;
    if(gauges.has(name))this.latestGauges[name]=value;
    const m=this.conditions[name];
    if(m){m.counterReset=m.counterReset||(counters.has(name)&&value<m.last);m.last=value;m.minimum=Math.min(m.minimum,value);m.maximum=Math.max(m.maximum,value);m.observations++;if(counters.has(name)&&!m.counterReset)m.delta=value-m.first;else delete m.delta;}
    else this.conditions[name]={first:value,last:value,minimum:value,maximum:value,observations:1,counterReset:false};
   }
  }
  comparisonWarnings(){
   const c=this.conditions,w=[];
   if(c.thermalState?.maximum>=2)w.push('iOS reported serious or critical heat during this check.');
   if(c.thermalState&&c.thermalState.minimum!==c.thermalState.maximum)w.push('Thermal state changed during this check.');
   if(['requestedRenderWidth','requestedRenderHeight','canvasWidth','canvasHeight'].some(k=>c[k]&&c[k].minimum!==c[k].maximum))w.push('Render dimensions changed during this check.');
   if(c.requestedFrameInterval&&c.requestedFrameInterval.minimum!==c.requestedFrameInterval.maximum)w.push('Requested engine frame limit changed during this check.');
   if(Object.values(c).some(m=>m.counterReset))w.push('A cumulative counter reset; its delta is unavailable.');
   if(!Object.keys(c).length)w.push('Run conditions were unavailable.');return w;
  }
  sample(fps,now){
   if(this.state!=='running')return;this.tick(now);if(this.state!=='running')return;
   if(!Number.isFinite(fps)||fps<0||fps>1000){this.cancel('Invalid frame sample.');return;}
   const previous=this.last;this.last=now;const begin=this.started+2000,end=this.endsAt;
   const weight=Math.max(0,Math.min(now,end)-Math.max(previous,begin));
   if(weight>0)this.samples.push({fps,ms:weight});
   if(weight>0&&(!this.timeline.length||Math.min(now,end)-begin-this.timeline[this.timeline.length-1].elapsedMS>=1000))this.timeline.push({elapsedMS:Math.min(now,end)-begin,fps,conditions:{...this.latestGauges}});
   if(this.samples.length>this.measurementMS/1000*6){this.cancel('Too many frame samples.');return;}
   if(now>=end){
    const duration=this.samples.reduce((n,s)=>n+s.ms,0);
    if(duration<this.measurementMS-500||this.samples.length<Math.floor(this.measurementMS/1500)){this.cancel('Not enough fresh frame samples.');return;}
    const sorted=this.samples.map(s=>s.fps).sort((a,b)=>a-b);
    this.result={format:'zgta-performance-v2',context:this.context,durationMS:duration,samples:this.samples.length,
     averageFPS:this.samples.reduce((n,s)=>n+s.fps*s.ms,0)/duration,
     medianWindowFPS:sorted[Math.floor(sorted.length/2)],slowestWindowFPS:sorted[0],
     conditions:this.conditions,comparisonWarnings:this.comparisonWarnings(),timeline:this.timeline,
     note:'Presented FPS averaged over sampling windows; not a per-frame 1% low. Match position, view, weather, settings and device temperature when comparing.'};
    this.state='complete';
   }
  }
 }
 root.ZemaPerformanceRun={Run};if(typeof module==='object')module.exports={Run};
 if(typeof window==='undefined')return;
 root.ZemaFPSChannel='zema-fps-'+crypto.randomUUID();
 const run=new Run();let channel,timer;
 addEventListener('DOMContentLoaded',()=>{
  const panel=document.getElementById('zema-mod-manager');if(!panel)return;
  const title=document.createElement('h3');title.textContent='Performance check';
  const note=document.createElement('p');note.textContent='Choose a 30-second check or a 3-minute check with an FPS timeline. Keep the game visible, stay in the same place and avoid opening the pause menu. Results stay on this device.';
  const button=document.createElement('button');button.type='button';button.textContent='Measure 30s FPS';
  const sustained=document.createElement('button');sustained.type='button';sustained.textContent='Measure 3min FPS';
  const status=document.createElement('output');status.style.cssText='display:block;white-space:pre-wrap;margin:12px 0';status.textContent='No measurement yet.';
  const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel measurement';cancel.hidden=true;
  const download=document.createElement('button');download.type='button';download.textContent='Save performance report';download.hidden=true;
  const badge=document.createElement('output');badge.hidden=true;badge.style.cssText='position:fixed;right:20px;top:16px;z-index:2202;background:#172923;color:#e6f9ed;padding:10px;border-radius:8px;font:14px system-ui;pointer-events:none';
  function refresh(){
   run.tick(performance.now());button.disabled=run.state==='running'||!root.ZemaGameReady;sustained.disabled=button.disabled;cancel.hidden=run.state!=='running';download.hidden=run.state!=='complete';
   if(run.state!=='running'&&timer){clearInterval(timer);timer=null;}
   if(run.state==='running'){const left=Math.max(0,Math.ceil((run.endsAt-performance.now())/1000));status.textContent=performance.now()<run.started+2000?'Warming up…':`Measuring FPS · ${left}s left`;badge.hidden=false;badge.textContent=status.textContent;}
   else if(run.state==='complete'){status.textContent=`Average ${run.result.averageFPS.toFixed(1)} FPS\nMedian sample ${run.result.medianWindowFPS.toFixed(1)} FPS · slowest sample ${run.result.slowestWindowFPS.toFixed(1)} FPS`+(run.result.comparisonWarnings.length?'\n'+run.result.comparisonWarnings.join('\n'):'');badge.textContent=`${run.measurementMS/1000}s average: ${run.result.averageFPS.toFixed(1)} FPS`;}
   else {badge.hidden=true;status.textContent=run.reason||'No measurement yet.';}
  }
  const start=duration=>{if(!root.ZemaGameReady||document.hidden)return;const s=root.ZemaRuntime.settings;run.start(performance.now(),{platform:'browser',engineSHA:root.ZemaBenchmarkEngine,mode:s.mode,preset:s.preset,height:s.height,fpsCap:s.fps,cores:s.cores,viewport:[innerWidth,innerHeight],renderDimensionsSource:'DOM canvas backing dimensions; not GPU timing',startedAt:new Date().toISOString()},duration);panel.hidden=true;root.ZemaInputSuspended=false;timer=setInterval(refresh,250);refresh();};
  button.onclick=()=>start(30);sustained.onclick=()=>start(180);
  cancel.onclick=()=>{run.cancel();refresh();};
  download.onclick=()=>{if(!run.result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(run.result,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='ZGTA-performance.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  channel=new BroadcastChannel(root.ZemaFPSChannel);channel.onmessage=e=>{if(run.state==='running'){const now=performance.now();if(run.wantsConditions(now)){const canvas=document.getElementById('canvas');run.observeConditions(canvas?{canvasWidth:canvas.width,canvasHeight:canvas.height}:{},now);}run.sample(e.data?.fps,now);refresh();}else if(button.disabled&&root.ZemaGameReady)refresh();};
  addEventListener('visibilitychange',()=>{if(document.hidden){run.cancel('The game was hidden. Start another measurement.');refresh();}});
  addEventListener('keydown',e=>{if(e.code==='Escape'||e.code==='KeyP'){run.cancel('Measurement interrupted by a menu key.');refresh();}},true);
  for(const b of [button,sustained,cancel,download])b.style.cssText='padding:10px 14px;margin:4px 6px 4px 0;background:#acdfbb;border:0;border-radius:8px;color:#10291b;font:inherit;cursor:pointer';
  panel.append(title,note,button,sustained,cancel,status,download);document.body.append(badge);refresh();
 });
 addEventListener('pagehide',()=>{clearInterval(timer);channel?.close();run.cancel('Game closed.');},{once:true});
})(globalThis);
