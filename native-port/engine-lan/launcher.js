/* No engine or multiplayer startup before Play; management actions are explicit. */
'use strict';
const S=ZemaLaunchSettings;let settings=S.read({getItem:key=>localStorage.getItem(key)}),lastPreferences='';
const initialPlayerName=settings.player;let playerNameEdited=false;
function rememberSettings(){try{const value=JSON.stringify(S.normalize(settings));if(value!==lastPreferences){localStorage.setItem('zema-browser-launch-v1',value);lastPreferences=value;}}catch(_){/* Browsing and play still work if local preferences are unavailable. */}}
const retryQuery=new URLSearchParams(location.search);
if(retryQuery.get('lan')==='failed'){if(retryQuery.has('version'))settings=S.decode(location.search);settings.mode='lan';}
let lastSoloMode=settings.mode==='sandbox'?'sandbox':'story';
try{if(settings.mode==='lan'&&localStorage.getItem('zema-solo-mode-v1')==='sandbox')lastSoloMode='sandbox';}catch(_){}
const host=document.getElementById('sections');
function element(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function section(id,title,note){const s=element('section');s.dataset.section=id;s.hidden=id!=='graphics';s.append(element('h2',title),element('p',note,'note'));host.append(s);return s;}
function row(s,label,detail,control){const r=element('div',undefined,'row'),l=element('label',label);if(detail)l.append(element('small',detail));if(control){l.htmlFor=control.id;r.append(l,control);}else r.append(l);s.append(r);return r;}
function choice(s,key,label,detail,values){const c=element('select');c.id=key;c.name=key;for(const [value,title] of values){const o=element('option',title);o.value=String(value);c.append(o);}c.value=String(settings[key]);c.onchange=()=>{settings[key]=typeof S.defaults[key]==='number'?Number(c.value):c.value;refresh();};row(s,label,detail,c);return c;}
function toggle(s,key,label,detail){const c=element('input');c.type='checkbox';c.id=key;c.name=key;c.checked=settings[key];c.onchange=()=>{settings[key]=c.checked;refresh();};row(s,label,detail,c);}
function slider(s,key,label,detail){const c=element('input');c.type='range';c.min=.5;c.max=10;c.step=.1;c.value=settings[key];c.id=key;c.name=key;c.setAttribute('aria-label',label);const r=row(s,label,detail,c),value=element('output',settings[key]+'×');r.append(value);c.oninput=()=>{settings[key]=Number(c.value);value.textContent=c.value+'×';rememberSettings();};}
const game=document.getElementById('home-game');
const modes=element('div',undefined,'mode-grid');
for(const [value,title,symbol,caption] of [['story','Story mode','book','Continue or start a story'],['sandbox','Free roam','map','Explore Los Santos']]){
 const l=element('label'),i=element('input');i.type='radio';i.name='mode';i.value=value;i.checked=settings.mode===value;i.onchange=()=>{settings.mode=value;lastSoloMode=value;try{localStorage.setItem('zema-solo-mode-v1',value);}catch(_){}refresh();};
 const icon=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-'+symbol);icon.setAttribute('aria-hidden','true');icon.append(use);l.append(i,icon,element('span',title),element('small',caption,'mode-caption'));modes.append(l);
}game.append(modes);
toggle(game,'newgame','Start a new Story','Off: continue the newest save in this browser profile. On: skip auto-load; existing files are kept.');

const graphics=section('graphics','Graphics & frame rate','Choose a frame-rate cap and render resolution. The cap is a limit, not a guarantee. Changes apply on the next launch.');
choice(graphics,'preset','Detail preset','The same six preset definitions as the iOS app.',Object.entries(S.presets).map(([key,p])=>[key,p.title+' · '+p.height+'p']));
choice(graphics,'height','Resolution','Auto follows the preset, not Retina display resolution.',S.heights.map(h=>[h,h?h+'p':'Auto (preset)']));
toggle(graphics,'fill','Fill the screen','Match the window shape. Off uses a 16:9 render surface.');
choice(graphics,'fps','Frame rate','30 FPS is the lighter option; this is a cap, not a performance guarantee.',[[30,'30 FPS'],[60,'60 FPS'],[0,'Unlocked']]);
row(graphics,'Engine workers','Automatic. The supported four-worker budget avoids the observed two-worker startup stall.',element('span','4 workers','badge'));
const fastButton=element('button','Favor frame rate','subtle');fastButton.type='button';
const undoFast=element('button','Restore previous graphics','subtle');undoFast.type='button';undoFast.hidden=true;let previousGraphics=null;
const fastNote=element('output','Uses lower detail at 432p and a 60 FPS cap. Sharper pictures need more graphics work.');fastNote.setAttribute('role','status');
fastButton.onclick=()=>{if(!previousGraphics)previousGraphics={preset:settings.preset,height:settings.height,fps:settings.fps,cores:settings.cores};Object.assign(settings,ZemaBrowserPerformance.faster(settings));for(const key of ['preset','height','fps'])document.getElementById(key).value=String(settings[key]);undoFast.hidden=false;fastNote.textContent='Frame-rate setup selected: 432p / 60 FPS cap. Applies on the next launch; actual FPS depends on this device.';refresh();};
undoFast.onclick=()=>{if(!previousGraphics)return;Object.assign(settings,previousGraphics);previousGraphics=null;for(const key of ['preset','height','fps'])document.getElementById(key).value=String(settings[key]);undoFast.hidden=true;fastNote.textContent='Previous graphics restored.';refresh();};
const fastActions=element('div',undefined,'inline-actions');fastActions.append(fastButton,undoFast);graphics.append(fastActions,fastNote);
const gpuCheck=element('button','Check this GPU','subtle');gpuCheck.type='button';const gpuResult=element('pre','The check runs locally when selected. It does not change Chrome settings.','diagnostics');gpuResult.setAttribute('role','status');
gpuCheck.onclick=async()=>{gpuCheck.disabled=true;try{gpuResult.textContent=ZemaBrowserPerformance.text(await ZemaBrowserPerformance.inspect());}catch(e){gpuResult.textContent='GPU check failed: '+e.message;}finally{gpuCheck.disabled=false;}};
graphics.append(gpuCheck,gpuResult,element('p','For Chrome: enable graphics acceleration in Settings → System, keep the game active under Settings → Performance, and connect power. Press = in-game to toggle actual presented FPS. These browser settings are checked manually; this launcher does not silently change them.','note'));

const controls=section('controls','Keyboard & controller','Pair your Xbox / PlayStation controller in your device’s Bluetooth settings, or connect it by USB, then press a button. Standard Gamepad API mapping is required.');
toggle(controls,'keyboardMouse','Keyboard and mouse','WASD, mouse look, click to capture; Esc releases the mouse.');
slider(controls,'mouseSpeed','Mouse look speed','Relative mouse movement multiplier.');
toggle(controls,'controller','Controller input','Native engine gamepad input: analog movement, camera, steering and triggers. No manual on-foot/driving switch.');
choice(controls,'targetingMode','Targeting','The same engine preference as iPhone; applies on the engine input thread.',[[0,'Traditional lock-on'],[1,'Assisted aim'],[2,'Assisted free aim'],[3,'Free aim']]);
slider(controls,'lookSensitivity','Camera stick speed','Controller look multiplier.');slider(controls,'aimSensitivity','Aim stick speed','Controller look speed while the left trigger is held.');toggle(controls,'invertY','Invert vertical look','Applies to mouse look and the controller right stick.');
row(controls,'Controller status','Controller detection stays on this Mac; nothing is uploaded.',element('output','Press a controller button','controller-status')).querySelector('output').id='controller-status';
controls.append(element('p','The engine handles on-foot/vehicle actions automatically. Xbox and PlayStation controllers use the standard Gamepad mapping. Disconnect, focus loss and a stale input publisher release controller input. Real controller feel still needs a play test.','note'));
const saves=section('saves','Save games','Separate local browser storage for Story, Free Roam and your multiplayer character. Existing browser and phone saves stay untouched.');
row(saves,'Continue / new Story','Choose Story on Home. New Story skips auto-load without deleting saved files.');
const saveMode=element('select');saveMode.id='save-mode';for(const [value,title]of [['story','Story'],['sandbox','Free Roam']]){const o=element('option',title);o.value=value;saveMode.append(o);}row(saves,'Save profile','Manage only this launcher’s offline saves.',saveMode);
const saveActions=element('div'),saveStatus=element('output','No files have been read yet.'),saveList=element('div');saves.append(saveActions,saveStatus,saveList);
saveActions.style.cssText='display:flex;flex-wrap:wrap;gap:8px;margin:16px 0';
function downloadJson(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=element('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function saveButton(title,fn){const b=element('button',title,'subtle');b.type='button';b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){saveStatus.textContent=e.message;}finally{b.disabled=false;}};saveActions.append(b);return b;}
async function refreshSaves(){const mode=saveMode.value,files=await ZemaBrowserSaves.list(mode);if(mode!==saveMode.value)return;saveList.replaceChildren();saveStatus.textContent=files.length+' saved file(s).';for(const file of files){const b=element('button','Export','subtle');b.type='button';b.onclick=async()=>{try{downloadJson(await ZemaBrowserSaves.exportSaves(mode,file.path),'zema-'+mode+'-save.json');}catch(e){saveStatus.textContent=e.message;}};row(saveList,file.path,file.data.byteLength+' bytes',b);}}
saveMode.onchange=()=>{storyImport.hidden=storyNote.hidden=saveMode.value!=='story';saveList.replaceChildren();saveStatus.textContent='Press Refresh list to view '+(saveMode.value==='story'?'Story':'Free Roam')+' saves.';};
saveButton('Refresh list',refreshSaves);saveButton('Export all saves',async()=>{downloadJson(await ZemaBrowserSaves.exportSaves(saveMode.value),'zema-'+saveMode.value+'-backup.json');saveStatus.textContent='Backup exported.';});
saveButton('Export latest safety backup',async()=>{downloadJson(await ZemaBrowserSaves.exportSafety(saveMode.value),'zema-'+saveMode.value+'-safety-backup.json');saveStatus.textContent='Safety backup exported; import it to restore these previous files.';});
saveButton('Export for iPhone',async()=>{const mode=saveMode.value;downloadJson(await ZemaBrowserSaves.exportNative(mode),'ZGTA-V-'+mode+'.zgtasave');saveStatus.textContent='iPhone backup exported. In the app, open Save game → Import backup before starting the game.';});
const importFile=element('input');importFile.type='file';importFile.accept='.zgtasave,.mugoatsave,.json,application/json';importFile.hidden=true;saveActions.append(importFile);saveButton('Import save backup',async()=>importFile.click());
importFile.onchange=async()=>{const file=importFile.files[0],mode=saveMode.value;try{if(!file)return;if(file.size>32*1024*1024)throw Error('Backup exceeds 32 MB.');const raw=await file.text(),backup=JSON.parse(raw),entries=await ZemaBrowserSaves.validate(backup,mode),other=backup.entries.length-entries.length,label=mode==='story'?'Story':'Free Roam';if(!confirm('Restore '+entries.length+' '+label+' file(s)? Matching saves will be replaced. An atomic safety backup will be kept first.'+(other?' The '+other+' file(s) from the other iPhone profile will not be imported.':'')))return;const result=await ZemaBrowserSaves.restore(mode,raw);await refreshSaves();saveStatus.textContent=result.restored+' '+label+' file(s) restored. Safety backup retained.';}catch(e){saveStatus.textContent=e.message;}finally{importFile.value='';}};
const storyFile=element('input');storyFile.type='file';storyFile.hidden=true;storyFile.setAttribute('aria-label','Choose one SGTA5 Story save');saveActions.append(storyFile);
const storyImport=saveButton('Add a Story save',async()=>storyFile.click());
const storyNote=element('p','Add one SGTA5 file to an empty manual slot. Existing saves and autosave are kept. Close the game first. After importing, select Story and use Pause → Game → Load Game. Saves from newer GTA versions may not load in this port.','note');saves.append(storyNote);
storyFile.onchange=async()=>{const file=storyFile.files[0];if(!file)return;storyImport.disabled=true;try{
 if(file.size<65536||file.size>8*1024*1024)throw Error('Choose an SGTA5 Story save between 64 KB and 8 MB.');
 const result=await ZemaBrowserSaves.importStory(new Uint8Array(await file.arrayBuffer()),file.name);
 saveMode.value='story';storyImport.hidden=storyNote.hidden=false;await refreshSaves();
 saveStatus.textContent='Added “'+result.title+'” to manual slot '+result.slot+'. Select Story, then Pause → Game → Load Game.';
}catch(e){saveStatus.textContent=e.message;}finally{storyFile.value='';storyImport.disabled=false;}};
saves.append(element('p','Story and Free Roam backups can move between iPhone and browser. Import an iPhone backup or browser JSON; only the selected save profile is restored. Use Export for iPhone to transfer back to the app. Graphics settings are excluded. These are optional transfers; multiplayer characters still save automatically.','note'));
saves.append(element('h3','Multiplayer character · automatic saves'),element('p','Saving and loading are automatic; you do not need to select a folder. Export/import below are optional backups. Your multiplayer character is separate from pc_settings.bin and Story saves. It is saved automatically on this browser and address: '+location.origin+'. Use the same Chrome profile and address when returning. Each device should keep its own character when playing together; importing a profile moves its identity and does not merge characters.','note'));
const lanActions=element('div'),lanStatus=element('output','Automatic saves stay in Chrome. Close the running game, then refresh to inspect character files. Backups are optional.');lanStatus.id='lan-save-status';lanStatus.setAttribute('role','status');lanActions.style.cssText='display:flex;flex-wrap:wrap;gap:8px;margin:16px 0';saves.append(lanActions,lanStatus);
function lanButton(title,fn){const b=element('button',title,'subtle');b.type='button';b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){lanStatus.textContent=e.message;}finally{b.disabled=false;}};lanActions.append(b);}
async function refreshLan(){const p=await ZemaBrowserSaves.lanInfo();lanStatus.textContent=p?'Saved LAN profile: '+p.name+' · '+p.files.length+' game file(s), '+p.stats+' saved value(s), '+p.bytes+' bytes.'+(p.files.some(f=>/(?:^|[_/])char\d+\.save$/i.test(f))?'':' No character-save file has been written yet. Profile settings alone cannot restore a completed character.'):'No saved LAN profile at this browser address yet. Nothing was created or replaced.';}
function downloadLan(bytes,name){if(!bytes)throw Error('No LAN profile backup exists yet.');const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'})),a=element('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
lanButton('Refresh LAN profile',refreshLan);
lanButton('Export LAN profile',async()=>{downloadLan(await ZemaBrowserSaves.lanBytes(),'ZGTA-V-LAN-profile.zemapf');lanStatus.textContent='LAN profile exported in the same format used by iOS.';});
lanButton('Export previous LAN profile',async()=>{downloadLan(await ZemaBrowserSaves.lanBytes(true),'ZGTA-V-LAN-profile-previous.zemapf');lanStatus.textContent='Previous profile exported. Existing saves are unchanged.';});
const lanImport=element('input');lanImport.type='file';lanImport.accept='.zemapf';lanImport.hidden=true;lanActions.append(lanImport);lanButton('Import LAN profile',async()=>lanImport.click());
lanImport.onchange=async()=>{try{const f=lanImport.files[0];if(!f)return;if(f.size>8*1024*1024+36)throw Error('LAN profile exceeds 8 MB.');const bytes=new Uint8Array(await f.arrayBuffer()),p=ZemaOnline.Profile.decode(bytes);if(!confirm('Restore LAN character '+p.name+'? The current profile will be kept as the previous snapshot. Use separate characters on devices playing together.'))return;await ZemaBrowserSaves.restoreLan(bytes);await refreshLan();}catch(e){lanStatus.textContent=e.message;}finally{lanImport.value='';}};
const tools=section('tools','Mod manager','Private copies and immutable launch snapshots preserve the original game files.');
let vehicleTools;
const modsUI=ZemaModsUI.mount(tools,{mode:()=>settings.mode,changed:catalog=>vehicleTools?.setMods(catalog)});
tools.append(element('h3','Play tools'));
vehicleTools=ZemaTrainerUI.mount(tools,{mode:()=>settings.mode});
const device=section('device','Game files & support','This launcher serves your existing local mirror and makes no changes to the original Intel build folder.');
row(device,'Game files / asset server','This local launcher reads your selected game mirror. Your original files are preserved.');
row(device,'Playing with friends','Choose Join or create, or Find lobby on Home. Confirm your setup, then press the green Play Multiplayer or Host Multiplayer button. LAN needs the same Wi-Fi or local network. Remote needs Tailscale connected on every device.');
row(device,'Can’t find a lobby?','Ask the host to keep ZGTA V open and share an invite. In Find lobbies, choose Add invite. Check Local Network permission on iPhone, or Tailscale for Remote.');
row(device,'Automatic character saves','Keep using the same browser profile and launcher address. Export backups only when you want an extra copy or a character transfer. Do not share one character identity between devices playing together.');

const diagnostics=element('pre');device.append(diagnostics);const download=element('button','Download launcher diagnostics','subtle');download.type='button';device.append(download);
download.onclick=()=>{const data={format:'zema-browser-launch-diagnostic-v1',settings:S.normalize(settings),isolated:crossOriginIsolated,webgpu:!!navigator.gpu,reportedMemoryGB:navigator.deviceMemory||null,reportedCores:navigator.hardwareConcurrency||null,engineStarted:false};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=element('a');a.href=url;a.download='zema-browser-launcher.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
const preferences=document.getElementById('preferences');
function showPage(page){
 for(const panel of document.querySelectorAll('[data-page]'))panel.hidden=panel.dataset.page!==page;
 document.body.dataset.currentPage=page;
 document.getElementById(page==='friends'?'friends-launch':'solo-launch').append(document.getElementById('launch-panel'));
 if(page==='friends'){if(settings.mode!=='lan'){lastSoloMode=settings.mode;try{localStorage.setItem('zema-solo-mode-v1',lastSoloMode);}catch(_){}}settings.mode='lan';refresh();}
 if(page==='solo'&&settings.mode==='lan'){settings.mode=lastSoloMode;refresh();}
 scrollTo({top:0,behavior:'instant'});
}
for(const button of document.querySelectorAll('[data-open-page]'))button.addEventListener('click',()=>showPage(button.dataset.openPage));
function showSettings(tab){
 for(const section of host.children)section.hidden=section.dataset.section!==tab;
 for(const button of document.querySelectorAll('#tabs [data-tab]')){if(button.dataset.tab===tab)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');}
 document.getElementById('preferences-title').textContent={graphics:'Settings & Graphics',controls:'Controls',saves:'Save games',tools:'Mod Manager',device:'Files & Support'}[tab]||'Settings';
 if(!preferences.open)preferences.showModal();
 if(tab==='tools')modsUI.refresh().catch(e=>{document.getElementById('status').textContent=e.message;});
}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>showSettings(b.dataset.tab);
for(const b of document.querySelectorAll('[data-close]'))b.onclick=()=>{const sheet=document.getElementById(b.dataset.close);if(!launchBusy)sheet.close();};
let launchBusy=false;
function refresh(){
 settings=S.normalize(settings);rememberSettings();const p=S.presets[settings.preset],dims=S.size(settings,{width:innerWidth,height:innerHeight});
 document.getElementById('summary').textContent=p.title+' · '+dims.join(' × ')+' · '+(settings.fps?settings.fps+' FPS':'Unlocked');
 document.getElementById('mode-detail').textContent={story:'Story · '+(settings.newgame?'Start a new story':'Continue your saved story'),sandbox:'Free Roam · Los Santos',lan:settings.lobbyRole==='host'?'Host '+settings.room+' · '+settings.connection:settings.relay?settings.room+' · '+settings.connection:'Choose Join or create, or Find lobby above.'}[settings.mode];
 document.getElementById('newgame').closest('.row').hidden=settings.mode!=='story';
 const feedback=document.getElementById('status');if(!launchBusy&&!feedback.classList.contains('error'))feedback.textContent=settings.mode==='lan'?(settings.lobbyRole==='host'?'Press Host Multiplayer to create '+settings.room+'.':settings.relay?'Press Play Multiplayer to join '+settings.room+'.':'Choose a multiplayer option above, then press Play Multiplayer.'):'Your game starts when you press Play.';
 const play=document.getElementById('play');play.hidden=false;play.querySelector('span').textContent=settings.mode==='lan'?(settings.lobbyRole==='host'?'Host Multiplayer':'Play Multiplayer'):settings.mode==='story'?(settings.newgame?'Start a new story':'Play Story'):'Play Free Roam';
 for(const input of document.querySelectorAll('input[name="mode"]'))input.checked=input.value===settings.mode;
 diagnostics.textContent='Shared memory: '+(crossOriginIsolated?'ready':'unavailable')+'\nWebGPU API: '+(navigator.gpu?'available (adapter checked on Play)':'unavailable')+'\nReported CPU cores: '+(navigator.hardwareConcurrency||'unknown')+'\nReported memory: '+(navigator.deviceMemory?navigator.deviceMemory+' GB':'not exposed');
}
async function launch(){
 if(launchBusy)throw Error('Your game is already starting.');
 if(settings.mode==='lan'&&settings.lobbyRole==='join'&&!settings.relay.trim()){document.getElementById('status').textContent='Choose Join or create, or Find lobby above first.';document.getElementById('home-multiplayer').scrollIntoView({block:'nearest'});return false;}
 launchBusy=true;
 const status=document.getElementById('status'),play=document.getElementById('play'),selected=S.normalize(settings);play.disabled=true;status.className='';
 try{
  if(!crossOriginIsolated||!navigator.gpu)throw Error('Open this launcher in a current Chrome or Edge browser with WebGPU enabled to start the game.');
  if(selected.mode==='lan'){
   if(!selected.room.trim()||new TextEncoder().encode(selected.room).length>64)throw Error('Enter a room name of 1–64 bytes.');
   if(!/^[\x20-\x7e]{1,16}$/.test(selected.player)||!selected.player.trim())throw Error('Use a player name of 1–16 English characters.');
   if(selected.lobbyRole==='host'){
    status.textContent='Creating your lobby…';const lobby=await ZemaModsUI.api('host/start',{room:selected.room,connection:selected.connection});selected.relay=lobby.join;
   }else{
    const target=ZemaLobbyModel.target(selected.relay,selected.room);selected.relay=target.relay;selected.connection=target.connection;
    status.textContent='Checking your lobby…';const checked=await ZemaModsUI.api('lobbies/probe',{addresses:[selected.relay]});const checkedHost=checked.hosts[0];
    if(checkedHost?.state!=='online')throw Error(checkedHost?.message||'This lobby is unavailable. Open the host game or relay and check your network.');
    if(checkedHost.catalog&&checkedHost.room_policy==='hosted'&&!checkedHost.lobbies.some(r=>r.room===selected.room))throw Error('This host is using a different room. Find lobbies shows its current room.');
   }
  }
  try{localStorage.setItem('zema-browser-launch-v1',JSON.stringify(selected));}catch(_){}
  status.textContent='Getting your game ready…';const prepared=await ZemaModsUI.api('launch',{mode:selected.mode});
  if(prepared.prefix!==''&&!/^\/session\/[a-f0-9]{32}$/.test(prepared.prefix))throw Error('The launcher returned an invalid game session.');
  location.assign(prepared.prefix+S.url(selected));return true;
 }catch(error){status.className='error';status.textContent=error.message;launchBusy=false;play.disabled=false;throw error;}
}
const lobbyUI=ZemaLobbyUI.mount({getSettings:()=>settings,nameEdited:()=>{playerNameEdited=true;},change:patch=>{if(Object.prototype.hasOwnProperty.call(patch,'player'))playerNameEdited=true;settings={...settings,...patch};refresh();},api:ZemaModsUI.api});
document.getElementById('settings').onsubmit=event=>{event.preventDefault();if(event.submitter===document.getElementById('play'))launch().catch(()=>{});};
setInterval(()=>{if(document.hidden||!preferences.open||host.querySelector('[data-section="controls"]').hidden)return;let pads=[];try{pads=Array.from(navigator.getGamepads?.()||[]).filter(p=>p?.connected);}catch(_){}document.getElementById('controller-status').textContent=pads.length?pads.map(p=>p.mapping==='standard'?'Standard controller connected':'Controller mapping not supported').join(', '):'Press a controller button';},1500);
function showSavedLanProfile(profile){if(!profile)return;if(!playerNameEdited&&settings.player===initialPlayerName&&/^[\x20-\x7e]{1,16}$/.test(profile.name)){settings.player=profile.name;lobbyUI.restorePlayerName(profile.name);}document.getElementById('profile-title').textContent=profile.name;document.getElementById('profile-detail').textContent=profile.files.some(f=>/(?:^|[_/])char\d+\.save$/i.test(f))?'Your multiplayer character is saved on this browser.':'Profile found. Character creation still needs to finish.';}
ZemaBrowserSaves.lanInfo().then(showSavedLanProfile).catch(()=>{});
refresh();addEventListener('resize',refresh);
showPage(new URLSearchParams(location.search).get('lan')==='failed'?'friends':'home');
if(new URLSearchParams(location.search).get('lan')==='failed'){
 let failure;try{failure=JSON.parse(sessionStorage.getItem('zema-browser-lan-error-v1'));sessionStorage.removeItem('zema-browser-lan-error-v1');}catch(_){}
 const fresh=failure&&typeof failure.message==='string'&&Number.isFinite(failure.at)&&Date.now()-failure.at>=0&&Date.now()-failure.at<300000;
 const status=document.getElementById('status');status.className='error';status.textContent='Could not join the lobby. '+(fresh?failure.message.slice(0,300)+' ':'')+'Your character and settings are kept. Check the host, then try Join a lobby again.';
}
