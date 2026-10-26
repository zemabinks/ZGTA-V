/* Physical controllers publish native engine pad values; PC input stays separate. */
(function(root){'use strict';
 function install(memory,block,canvas,size,startMode,settings,features){
  if(!features||!root.ZemaBrowserFeatures||!root.ZemaTrainer)throw Error('Native analog controller bridge unavailable');
  const keys=new Uint8Array(memory.buffer,block,256),w=new Int32Array(memory.buffer,block+256,10),text=new Uint16Array(memory.buffer,block+296,64),ext=new Int32Array(memory.buffer,block+424,4);
  const physical=new Set(),vk={Backspace:8,Tab:9,Enter:13,NumpadEnter:253,Escape:27,Space:32,ArrowLeft:37,ArrowUp:38,ArrowRight:39,ArrowDown:40,ShiftLeft:160,ShiftRight:161,ControlLeft:162,ControlRight:163,AltLeft:164,AltRight:165,Backquote:192};
  for(let i=0;i<26;i++)vk['Key'+String.fromCharCode(65+i)]=65+i;for(let i=0;i<10;i++){vk['Digit'+i]=48+i;vk['Numpad'+i]=96+i;}Object.assign(vk,{Minus:189,Equal:187,BracketLeft:219,BracketRight:221,Backslash:220,Semicolon:186,Quote:222,Comma:188,Period:190,Slash:191,Delete:46,Home:36,End:35,PageUp:33,PageDown:34,Insert:45});for(let i=1;i<=24;i++)vk['F'+i]=111+i;
  Object.assign(vk,{Pause:19,CapsLock:20,PrintScreen:44,MetaLeft:91,MetaRight:92,ContextMenu:93,NumpadMultiply:106,NumpadAdd:107,NumpadSubtract:109,NumpadDecimal:110,NumpadDivide:111,NumLock:144,ScrollLock:145,IntlBackslash:226});
  const alias={KeyI:'Numpad8',KeyK:'Numpad2',KeyJ:'Numpad4',KeyL:'Numpad6',KeyU:'Numpad7',KeyO:'Numpad9'};
  let mouse=0,closed=false,raf,lookX=0,lookY=0,wheelAccum=0;
  const accepting=()=>!closed&&!root.ZemaInputSuspended&&document.hasFocus()&&!document.hidden;
  let wasAccepting=accepting(),wasLocked=document.pointerLockElement===canvas;
  function motion(dx,dy){lookX+=dx;lookY+=dy;const x=Math.trunc(lookX),y=Math.trunc(lookY);lookX-=x;lookY-=y;Atomics.add(w,2,x);Atomics.add(w,3,y);}
  function sync(){const all=new Set(accepting()&&settings.keyboardMouse?physical:[]);for(const [src,dst] of Object.entries(alias))if(all.has(src))all.add(dst);for(const [code,value]of Object.entries(vk))Atomics.store(keys,value,all.has(code)?128:0);Atomics.store(w,5,accepting()&&settings.keyboardMouse?mouse:0);}
  function release(){physical.clear();mouse=0;lookX=lookY=wheelAccum=0;sync();for(const index of [2,3,4])Atomics.exchange(w,index,0);Atomics.store(w,6,accepting()?1:0);root.ZemaBrowserFeatures.publish(features.pad,null,settings);root.ZemaTrainer.cancel(features.trainer);}
  function requestLock(){
   if(!canvas.requestPointerLock)return;
   const fallback=()=>{try{Promise.resolve(canvas.requestPointerLock()).catch(()=>{});}catch(_){}};
   try{Promise.resolve(canvas.requestPointerLock({unadjustedMovement:true})).catch(fallback);}catch(_){fallback();}
  }
  function type(char){const head=Atomics.load(w,8);if(((head-Atomics.load(w,9))>>>0)<64){text[head&63]=char;Atomics.store(w,8,(head+1)|0);}}
  function pass(e){return e.code==='Equal'||e.code==='F11'||e.code==='F12'||e.code==='F5'||e.metaKey||(e.ctrlKey&&e.shiftKey);}
  addEventListener('keydown',e=>{if(!settings.keyboardMouse||!accepting()||pass(e))return;e.preventDefault();physical.add(e.code);sync();if(e.key.length===1&&!e.ctrlKey&&!e.metaKey)type(e.key.charCodeAt(0));else if(e.code==='Backspace'||e.code==='Enter')type(e.code==='Enter'?13:8);});
  addEventListener('keyup',e=>{physical.delete(e.code);sync();});
  canvas.addEventListener('mousedown',e=>{if(!settings.keyboardMouse||!accepting())return;requestLock();mouse|=1<<[0,2,1,3,4][e.button];sync();e.preventDefault();});
  addEventListener('mouseup',e=>{mouse&=~(1<<[0,2,1,3,4][e.button]);sync();});
  addEventListener('mousemove',e=>{if(!settings.keyboardMouse||!accepting())return;const locked=document.pointerLockElement===canvas;if(locked){motion(e.movementX*settings.mouseSpeed,e.movementY*settings.mouseSpeed*(settings.invertY?-1:1));Atomics.store(w,0,Math.max(0,Math.min(size[0]-1,Atomics.load(w,0)+e.movementX)));Atomics.store(w,1,Math.max(0,Math.min(size[1]-1,Atomics.load(w,1)+e.movementY)));}else {const r=canvas.getBoundingClientRect(),x=Math.max(0,Math.min(size[0]-1,Math.round((e.clientX-r.left)*size[0]/r.width))),y=Math.max(0,Math.min(size[1]-1,Math.round((e.clientY-r.top)*size[1]/r.height)));Atomics.add(w,2,x-Atomics.load(w,0));Atomics.add(w,3,y-Atomics.load(w,1));Atomics.store(w,0,x);Atomics.store(w,1,y);}});
  addEventListener('wheel',e=>{if(settings.keyboardMouse&&accepting()){wheelAccum+=-e.deltaY/(e.deltaMode===0?100:e.deltaMode===1?3:1);const n=Math.trunc(wheelAccum);if(n){wheelAccum-=n;Atomics.add(w,4,n);}e.preventDefault();}},{passive:false});canvas.addEventListener('contextmenu',e=>e.preventDefault());
  function focus(){if(!accepting())release();Atomics.store(w,6,accepting()?1:0);}
  addEventListener('blur',()=>{release();Atomics.store(w,6,0);});addEventListener('focus',focus);document.addEventListener('visibilitychange',focus);
  document.addEventListener('pointerlockchange',()=>{const locked=document.pointerLockElement===canvas;if(wasLocked&&!locked)release();wasLocked=locked;Atomics.store(w,7,locked?1:0);});
  Atomics.store(ext,2,size[0]);Atomics.store(ext,3,size[1]);if(startMode)Atomics.store(new Int32Array(memory.buffer,block+440,1),0,startMode);Atomics.store(w,6,accepting()?1:0);Atomics.store(w,0,size[0]>>1);Atomics.store(w,1,size[1]>>1);
  const badge=document.createElement('aside');badge.id='zema-controller';badge.hidden=true;badge.style.cssText='position:fixed;right:20px;top:16px;z-index:1000;background:#0911194d;backdrop-filter:blur(18px);color:#e6f0f6;padding:9px 13px;border:1px solid #d7e6eb24;border-radius:12px;font:12px system-ui;pointer-events:none';document.body.append(badge);
  const status=document.createElement('output');badge.append(status);let lastPad=null,noticeUntil=0;
  function tick(){if(closed)return;const active=accepting();if(wasAccepting&&!active)release();wasAccepting=active;Atomics.store(w,6,active?1:0);let pad,observedPad=lastPad;try{if(settings.controller&&active){pad=Array.from(navigator.getGamepads?.()||[]).find(p=>p?.connected&&p.mapping==='standard');observedPad=!!pad;}else if(!settings.controller)observedPad=false;}catch(_){}
   root.ZemaBrowserFeatures.publish(features.pad,pad,settings);Atomics.store(w,7,document.pointerLockElement===canvas?1:0);sync();const hasPad=observedPad;if(hasPad!==null&&hasPad!==lastPad){if(hasPad||lastPad===true)noticeUntil=Date.now()+3500;status.textContent=hasPad?'Controller connected':'Controller disconnected';root.ZemaConnectionPanel?.inputStatus?.(hasPad?'Controller connected':settings.keyboardMouse?'Keyboard and mouse':'No controller connected');lastPad=hasPad;}badge.hidden=!!root.ZemaConnectionPanel||Date.now()>=noticeUntil;raf=requestAnimationFrame(tick);
  }raf=requestAnimationFrame(tick);addEventListener('pagehide',()=>{closed=true;cancelAnimationFrame(raf);release();});return {release};
 }
 root.ZemaController={install};if(typeof module==='object')module.exports=root.ZemaController;
})(globalThis);
