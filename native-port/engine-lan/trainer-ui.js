/* One tools panel: offline cheat codes, plus vehicle/waypoint tools in private LAN. */
(function(root){'use strict';
 function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
 function mount(container,{runtime=null,mode=()=> 'sandbox'}={}){
  const note=el('p',runtime?'Vehicle and waypoint tools work in offline play and Engine LAN. Cheat codes remain offline only.':'Preview the tools here. Actions become available after the game world loads.');note.className='note';
  const output=el('output',runtime?'Waiting for the world and engine hook…':'No action is queued automatically.'),select=el('select');select.setAttribute('aria-label','Cheat action');
  const groups=new Map();for(const item of ZemaTrainer.catalog){let group=groups.get(item.category);if(!group){group=el('optgroup');group.label=item.category;groups.set(item.category,group);select.append(group);}const option=el('option',item.label+' · '+item.code);option.value=item.code;group.append(option);}
  const apply=el('button','Apply cheat'),cancel=el('button','Cancel current action'),model=el('input'),spawn=el('button','Spawn vehicle'),waypoint=el('button','Spawn to waypoint'),selection=el('p','Selected: Sultan · sultan');model.setAttribute('aria-label','Custom vehicle model');model.placeholder='Custom model, e.g. sultan';model.maxLength=128;model.value='sultan';
  for(const b of [apply,cancel,spawn,waypoint]){b.type='button';b.className='subtle';b.disabled=true;b.style.cssText='padding:12px 16px;border-radius:10px;border:1px solid #638c79;background:#294b3b;color:#e6f9ed;font:inherit;cursor:pointer';}
  for(const field of [select,model])field.style.cssText='width:100%;max-width:100%;min-width:0;padding:9px;background:#0d1618;color:#e9f5ef;border:1px solid #476256;border-radius:8px;box-sizing:border-box;font:inherit';
  const controls=el('div'),vehicleList=el('div');controls.className='trainer-actions';controls.style.cssText='display:grid;gap:12px;margin:16px 0';controls.append(el('label','Vehicle model'),model,selection,spawn,vehicleList,el('p','Select a waypoint on the pause map before teleporting. Your current vehicle moves only when you are its driver and have control.'),waypoint,el('label','Cheat action · offline only'),select,apply,cancel);
  const vehicles=ZemaVehicleUI.mount(vehicleList,{mode,availability:value=>runtime&&root.ZemaGameReady&&typeof ZemaTrainer.availability==='function'?ZemaTrainer.availability(runtime.features.trainer,value):'unknown',loadedPacks:runtime?(root.ZemaLoadedVehiclePacks||[]):null,select:(value,name)=>{model.value=value;selection.textContent='Selected: '+name+' · '+value;spawn.focus?.();}});
  model.oninput=()=>selection.textContent='Custom model: '+model.value;
  let admissionNotice=null;
  const actionLabel=command=>command.type==='waypoint'?'Waypoint teleport':command.type==='spawn'?'Vehicle spawn':'Cheat action';
  function request(command){try{if(!runtime||!root.ZemaGameReady)throw Error('Wait until your character is in the game world.');if(command.type==='cheat'&&mode()==='lan')throw Error('Cheat codes remain disabled in multiplayer.');ZemaTrainer.request(runtime.features.trainer,command);admissionNotice=null;output.textContent=actionLabel(command)+': queued for the engine thread…';}catch(e){admissionNotice={sequence:runtime?ZemaTrainer.status(runtime.features.trainer).sequence:0,text:actionLabel(command)+' not queued: '+e.message};output.textContent=admissionNotice.text;}}
  apply.onclick=()=>request({type:'cheat',code:select.value});spawn.onclick=()=>request({type:'spawn',model:model.value.trim()});waypoint.onclick=()=>request({type:'waypoint'});cancel.onclick=()=>{if(runtime){admissionNotice=null;ZemaTrainer.cancel(runtime.features.trainer);}};container.append(note,controls,output);
  container.append(el('p','Models must exist in the base game or a loaded DLC pack. Import packs before launching; multiplayer players need matching packs. Cheat codes remain offline only.'));
  function refresh(){
   if(!runtime)return;vehicles.refreshAvailability();const s=ZemaTrainer.status(runtime.features.trainer),allowed=root.ZemaGameReady&&s.ready,busy=s.result===1||s.sequence!==s.ack||s.cleanupPending||s.replacementPending;
   const selectedAvailability=typeof ZemaTrainer.availability==='function'?ZemaTrainer.availability(runtime.features.trainer,model.value.trim()):'unknown';
   spawn.disabled=!allowed||(busy&&s.type!==2)||selectedAvailability==='missing'||selectedAvailability==='unsupported';waypoint.disabled=!allowed||busy;apply.disabled=!allowed||busy||mode()==='lan';select.disabled=mode()==='lan';cancel.disabled=!allowed||!busy;
   const messages={[-13]:'Required vehicle files are missing or not loaded in this game.',0:'Queued…',1:({1:'Loading vehicle model…',2:'Loading waypoint area and checking ground…',3:'Waiting for a running game script…',4:'Waiting for the multiplayer freemode script…'})[s.phase]||'Running on the engine thread…',2:s.type===2?'Vehicle created; check visibility on the other client.':s.type===3?'Moved to waypoint.':'Cheat sequence delivered; verify its effect in game.',[-1]:'Invalid command.',[-2]:'This action is not available in multiplayer.',[-3]:'An engine command is unavailable or failed.',[-4]:s.type===3?'Waypoint area did not finish loading. Your position was preserved.':'Model/action timed out. Check the model name and loaded DLC.',[-5]:'Action cancelled.',[-6]:'No waypoint selected. Set one on the map first.',[-7]:'No safe position or ground found. Choose a nearby open road.',[-8]:'Your character or vehicle is not under local control. Exit the vehicle or take the driver seat.',[-9]:'Your character or vehicle changed. Try again after it is ready.',[-10]:'Another scene is loading. Wait before teleporting.',[-11]:'Your character is not ready. Wait until you are in the world.',[-12]:s.type===2?'The engine rejected vehicle creation after the model loaded. This is not a model-download error.':'Unexpected engine result. No vehicle spawn was requested by this action.'};
   const label=actionLabel({type:s.type===3?'waypoint':s.type===2?'spawn':'cheat'});
   output.textContent=admissionNotice&&admissionNotice.sequence===s.sequence?admissionNotice.text:s.replacementPending?'Switching to your latest vehicle choice…':s.cleanupPending?'Releasing the previous model/scene request…':!allowed?'Waiting for the world and engine hook…':s.sequence?label+' #'+s.sequence+': '+(messages[s.result]||'Waiting…'):'Ready. No action queued.';
  }
  let timer;if(runtime){timer=setInterval(refresh,200);refresh();addEventListener('pagehide',()=>clearInterval(timer),{once:true});}
  return {refresh,setMods:vehicles.setMods};
 }
 if(typeof window!=='undefined')addEventListener('DOMContentLoaded',()=>{
  if(!root.ZemaRuntime)return;
  const panel=el('section');panel.id='zema-mod-manager';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Mod Manager');
  panel.style.cssText='position:fixed;right:20px;top:118px;z-index:2200;background:#172923f5;color:#e6f9ed;border:1px solid #638c79;border-radius:18px;padding:24px;width:min(480px,calc(100vw - 88px));max-height:65vh;overflow:auto;font:15px/1.5 system-ui;box-shadow:0 12px 50px #0008';
  const header=el('div'),title=el('h2','Mod Manager'),close=el('button','Done');header.style.cssText='display:flex;justify-content:space-between;align-items:center;gap:12px';title.style.margin='0';close.type='button';close.style.cssText='padding:8px 12px;border:0;border-radius:8px;background:#294b3b;color:#a5ecd4;font:inherit';header.append(title,close);
  const tabs=el('nav'),playTab=el('button','Play tools'),filesTab=el('button','Installed mods'),play=el('div'),files=el('div'),fileStatus=el('output');tabs.setAttribute('aria-label','Mod Manager sections');tabs.style.cssText='display:flex;gap:10px;margin:18px 0';files.hidden=true;
  for(const button of [playTab,filesTab]){button.type='button';button.style.cssText='flex:1;padding:12px;border-radius:10px;border:1px solid #638c79;background:#243e33;color:#e6f9ed;font:inherit';tabs.append(button);}
  const tools=mount(play,{runtime:root.ZemaRuntime,mode:()=>root.ZemaRuntime.settings.mode});files.append(fileStatus);
  const mods=root.ZemaModsUI.mount(files,{mode:()=>root.ZemaRuntime.settings.mode,changed:tools.setMods});
  function selectFiles(selected){play.hidden=selected;files.hidden=!selected;playTab.setAttribute('aria-pressed',String(!selected));filesTab.setAttribute('aria-pressed',String(selected));if(selected)mods.refresh().catch(error=>fileStatus.textContent=error.message);}
  playTab.onclick=()=>selectFiles(false);filesTab.onclick=()=>selectFiles(true);selectFiles(false);
  panel.append(header,tabs,play,files);
  const button=el('button');button.type='button';button.setAttribute('aria-label','Mod Manager');button.title='Mod Manager';
  button.innerHTML='<svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true"><path fill="currentColor" d="M20 13h-2a3 3 0 1 0 0 6h2v3H2v-7h2a3 3 0 1 0 0-6H2V2h7v2a3 3 0 1 0 6 0V2h5z"/></svg>';
  button.style.cssText='position:fixed;right:20px;top:56px;z-index:2201;width:52px;height:52px;display:grid;place-items:center;background:#172923d9;border:1px solid #a8c6b680;border-radius:50%;color:#dff4e8;cursor:pointer';
  let wasSuspended=false;
  function hide(){panel.hidden=true;root.ZemaInputSuspended=wasSuspended;button.setAttribute('aria-expanded','false');button.focus();}
  button.setAttribute('aria-controls',panel.id);button.setAttribute('aria-expanded','false');
  button.onclick=()=>{if(!panel.hidden){hide();return;}document.dispatchEvent(new CustomEvent('zema-ui-panel-open',{detail:'mod-manager'}));wasSuspended=!!root.ZemaInputSuspended;root.ZemaInputSuspended=true;document.exitPointerLock?.();root.ZemaGameInput?.release();panel.hidden=false;button.setAttribute('aria-expanded','true');close.focus();if(root.ZemaRuntime.settings.mode!=='lan')mods.refresh().catch(error=>fileStatus.textContent=error.message);};close.onclick=hide;
  panel.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();hide();}});
  document.addEventListener('zema-ui-panel-open',event=>{if(event.detail!=='mod-manager'&&!panel.hidden)hide();});
  document.body.append(panel,button);
 });
 root.ZemaTrainerUI={mount};
})(globalThis);
