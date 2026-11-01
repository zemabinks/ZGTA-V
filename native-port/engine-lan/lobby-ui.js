/* Configure first, launch through the green button; live rooms and explicit favorites. */
(function(root){'use strict';
 const M=root.ZemaLobbyModel;
 function mount({getSettings,change,api,storage=localStorage,nameEdited=()=>{}}){
  const by=id=>document.getElementById(id),node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const button=(title,cls,fn)=>{const e=node('button',title,cls);e.type='button';e.onclick=fn;return e;};
  const note=text=>node('p',text,'note');
  const dialog=by('lobby-dialog'),content=by('lobby-content'),servers=by('servers-dialog'),directory=by('servers-content');
  let activePlayerInput=null,activePlayerDirty=false,desktop=false,desktopVisible=false,pendingSetup=null,searchTerm='';
  let owned=null,hostBusy=false,launching=false,catalogBusy=false,closed=false,mode='LAN',networks={},discovered=[],catalogGeneration=0,discoveryGeneration=0,serverTimer,hostTimer,discoveryNote='';
  const saved=()=>M.read(storage),favorites=()=>M.favorites(storage),remember=x=>{try{M.remember(storage,x);}catch(_){/* A full preferences store must not block play. */}};
  function show(sheet){if(!sheet.open){if(desktop)sheet.show();else sheet.showModal();}}
  function close(sheet){if(sheet.open&&!desktop)sheet.close();}
  function directoryActive(){return servers.open&&(!desktop||desktopVisible);}
  const hostBox=by('home-host'),hostTitle=node('strong'),hostNote=note(''),hostFeedback=node('output'),hostButtons=node('div',undefined,'button-row'),inviteText=node('div','', 'invite-text');inviteText.hidden=true;hostFeedback.setAttribute('role','status');
  const copy=button('Share invite','subtle',async()=>{
   if(!owned?.running)return;try{const target={relay:owned.remote||owned.lan,room:owned.room};inviteText.textContent=M.invite(target);inviteText.hidden=false;await navigator.clipboard.writeText(inviteText.textContent);hostFeedback.textContent='Invite copied. Send it to your friend; they can paste it into Join a lobby.';}catch(_){hostFeedback.textContent='Copy the invite shown below and send it to your friend.';}
  });
  const stop=button('Stop hosting','subtle danger-button',async()=>{
   if(hostBusy||!owned)return;if(owned.running&&!confirm('Stop this lobby? Connected players will disconnect.'))return;
   hostBusy=true;copy.disabled=stop.disabled=true;hostFeedback.textContent=owned.running?'Stopping your lobby…':'Starting your lobby again…';
   try{renderHost(await api(owned.running?'host/stop':'host/restart',{id:owned.id}));hostFeedback.textContent=owned.running?'Lobby is running again. Reconnect on each game device.':'Lobby stopped. Your saved characters are kept.';}
   catch(e){hostFeedback.textContent=e.message;}finally{hostBusy=false;copy.disabled=!owned?.running;stop.disabled=!owned;}
  });hostButtons.append(copy,stop);hostBox.append(hostTitle,hostNote,hostButtons,hostFeedback,inviteText);
  function renderHost(state){
   const previous=owned&&(owned.remote||owned.lan)+'\n'+owned.room;
   owned=state.owned&&(state.running||state.can_restart)?state:null;hostBox.hidden=!owned;if(!owned)return;
   hostTitle.textContent=state.running?'Your lobby is running':'Your lobby is stopped';hostNote.textContent=state.room+' · '+state.connection+(state.running?' · '+state.peers+' connected':'')+'\n'+(state.remote||state.lan||'');hostNote.style.whiteSpace='pre-line';stop.textContent=state.running?'Stop hosting':'Start hosting again';copy.disabled=hostBusy||!state.running;stop.disabled=hostBusy;if(previous!==(state.remote||state.lan)+'\n'+state.room){inviteText.hidden=true;if(state.running)remember({relay:state.remote||state.lan,room:state.room});}
   if(state.running&&state.connection==='LAN'&&['error','unavailable'].includes(state.discovery?.state))hostNote.textContent+='\n'+state.discovery.message;
  }
  async function readHost(){if(closed||hostBusy||document.hidden)return;try{const state=await api('host/status',{});if(!closed&&!hostBusy)renderHost(state);}catch(_){if(!closed&&owned){hostFeedback.textContent='Hosting status is unavailable. Check the local launcher.';copy.disabled=stop.disabled=true;}}}
  function field(form,title,help,value,limit){const wrap=node('label',undefined,'field'),caption=node('span',title),input=node('input');input.type='text';input.value=value||'';input.maxLength=limit;input.autocomplete='off';if(help)input.title=help;wrap.append(caption,input);if(help)wrap.append(node('small',help));form.append(wrap);return {wrap,input};}
  function connectionBar(current,onChange){const bar=node('div',undefined,'segmented'),buttons=[];for(const name of ['LAN','Remote']){const b=button(name==='LAN'?'Same Wi-Fi / LAN':'Remote / Tailscale','',()=>onChange(name));buttons.push(b);bar.append(b);}bar.setAttribute('aria-label','Connection type');bar.sync=value=>buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(['LAN','Remote'][i]===value)));bar.sync(current);return bar;}
  function openJoin(role='join',target=null,bookmark=false){
   if(launching)return;change({mode:'lan',...(desktop?{lobbyRole:role}:{})});const s=getSettings();let selected=target?.connection||s.connection;
   dialog.dataset.setup=bookmark?'favorite':role;const desktopTitle=by('desktop-multiplayer-title');if(desktopTitle)desktopTitle.textContent=bookmark?'Save favorite':'Join or create';
   by('lobby-title').textContent=bookmark?'Save a favorite':role==='host'?'Create a lobby':'Join a friend';content.replaceChildren();
   const form=node('form'),feedback=node('output','', 'lobby-feedback');feedback.setAttribute('role','status');
   if(desktop){const roles=node('div',undefined,'segmented desktop-role-options');roles.setAttribute('aria-label','Multiplayer setup');for(const [value,title]of [['join','Join a friend'],['host','Create a lobby']]){const b=button(title,'',()=>openJoin(value));b.setAttribute('aria-pressed',String(role===value&&!bookmark));roles.append(b);}form.append(roles);}
   const guidance=node('div','', 'help-box');
   const bar=connectionBar(selected,value=>{selected=value;bar.sync(value);updateGuidance();if(!target){const bank=value==='Remote'?'remote':'lan';address.input.value=s[bank+'Relay']||'';room.input.value=s[bank+'Room']||'LOS-SANTOS';}if(desktop){mode=value;discovered=[];++discoveryGeneration;directoryModeBar?.sync(mode);++catalogGeneration;catalogBusy=false;refreshServers();if(mode==='LAN')discoverLAN();}});
   form.append(bar,guidance);
   const address=field(form,'Host address or invite','Paste your friend’s invite, full address, or IP address.',target?.relay||s[(selected==='Remote'?'remote':'lan')+'Relay']||'',1024);address.input.placeholder=selected==='Remote'?'100.x.x.x or zgtav://join?…':'192.168.x.x or zgtav://join?…';address.wrap.hidden=role==='host';
   const room=field(form,'Room name',role==='host'?'Give your lobby a name. Your invite includes this.':'Use the same room name as your friend.',target?.room||s[(selected==='Remote'?'remote':'lan')+'Room']||s.room||'LOS-SANTOS',64);
   const player=field(form,'Your player name','This name updates your saved multiplayer name. Appearance and progress stay intact.',s.player,16);player.wrap.hidden=bookmark;activePlayerInput=player.input;activePlayerDirty=false;player.input.addEventListener('input',()=>{activePlayerDirty=true;nameEdited();});
   const submit=node('button',bookmark?'Save favorite':'Use this setup','primary lobby-submit'+(bookmark?' bookmark-submit':''));submit.type='submit';form.append(submit,feedback);content.append(form);
   function updateGuidance(){guidance.textContent=selected==='Remote'?'Play from different networks. Connect Tailscale on every device first. The host must keep its game or relay open.':'Play on the same Wi-Fi or local network. The host must keep its game or relay open.';}updateGuidance();
   address.input.addEventListener('input',()=>{if(!address.input.value.trim().startsWith('zgtav:'))return;try{const t=M.target(address.input.value,room.input.value);room.input.value=t.room;selected=t.connection;bar.sync(selected);updateGuidance();if(desktop&&mode!==selected){mode=selected;directoryModeBar?.sync(mode);++catalogGeneration;catalogBusy=false;refreshServers();}feedback.textContent='Invite detected. Host, connection and room are filled in.';}catch(_){feedback.textContent='Keep pasting the complete invite.';}});
   function configure(){
     let chosen=role==='host'?{room:M.room(room.input.value),connection:selected}:M.target(address.input.value,room.input.value);
     if(!/^[\x20-\x7e]{1,16}$/.test(player.input.value)||!player.input.value.trim())throw Error('Use a player name of 1–16 English characters.');
     selected=chosen.connection;bar.sync(selected);updateGuidance();
     const bank=selected==='Remote'?'remote':'lan',patch={mode:'lan',lobbyRole:role,connection:selected,room:chosen.room,player:player.input.value};
     patch[bank+'Room']=chosen.room;
     if(role==='join'){patch.relay=chosen.relay;patch[bank+'Relay']=chosen.relay;remember(chosen);}change(patch);
     feedback.textContent='';return chosen;
   }
   pendingSetup=()=>{feedback.textContent='';if(bookmark)throw Error('Save this favorite, or choose Join a friend / Create a lobby before launching.');return configure();};
   form.onsubmit=async event=>{event.preventDefault();if(launching)return;
    try{
     if(bookmark){const chosen=M.target(address.input.value,room.input.value);M.setFavorite(storage,chosen,true);onlyFavorites=true;close(dialog);openServers(chosen.connection);if(desktop)openJoin('join',chosen);return;}
     configure();
     close(dialog);by('play').focus(); // Configuration never starts the relay or game.

    }catch(error){feedback.className='lobby-feedback error';feedback.textContent=error.message;launching=false;for(const control of form.querySelectorAll('button,input'))control.disabled=false;}
   };
   dialog.oncancel=e=>{if(launching||desktop)e.preventDefault();};close(servers);show(dialog);if(desktop&&selected!==mode){mode=selected;directoryModeBar?.sync(mode);++catalogGeneration;catalogBusy=false;refreshServers();}setTimeout(()=>{if(dialog.open&&!desktop)(role==='join'?address.input:room.input).focus();},0);
  }
  let directoryModeBar,directoryFeedback,list,refreshButton,discoverButton;
  async function discoverLAN(){
   if(closed||!directoryActive()||mode!=='LAN'||discoverButton.disabled)return;discoverButton.disabled=true;const generation=discoveryGeneration;discoveryNote='';directoryFeedback.textContent='Looking for nearby ZGTA 5 hosts…';
   try{const found=await api('lobbies/discover',{});if(!servers.open||mode!=='LAN'||generation!==discoveryGeneration)return;discovered=found.addresses||[];if(!found.available)discoveryNote=found.message||'Automatic discovery is unavailable. Add your friend’s invite instead.';catalogBusy=false;await refreshServers();}catch(e){directoryFeedback.textContent=e.message;}finally{discoverButton.disabled=false;}
  }
  let onlyFavorites=false,latest={hosts:[],checkedAt:0},favoriteTabs=[];
  function seeds(){
   const s=getSettings(),entries=[...favorites(),...saved()];
   for(const connection of ['LAN','Remote']){const bank=connection==='Remote'?'remote':'lan';if(s[bank+'Relay'])try{entries.push(M.target(s[bank+'Relay'],s[bank+'Room']||s.room));}catch(_){} }
   if(owned?.running)try{entries.push(M.target(owned.remote||owned.lan,owned.room));}catch(_){}
   for(const key of ['lan','remote'])if(networks[key])try{entries.push(M.target(networks[key]+':47540','LOS-SANTOS'));}catch(_){}
   for(const relay of discovered)try{entries.push(M.target(relay,'LOS-SANTOS'));}catch(_){}
   const seen=new Set();return entries.filter(x=>{if(x.connection!==mode||seen.has(x.relay))return false;seen.add(x.relay);return true;}).slice(0,64);
  }
  function renderCatalog(){
   favoriteTabs.forEach((b,i)=>b.setAttribute('aria-pressed',String(onlyFavorites===(i===1))));
   const all=M.visible({...latest,favorites:favorites(),mode,onlyFavorites}),term=searchTerm.trim().toLowerCase(),cards=all.filter(card=>!term||[card.room,card.label,card.relay].some(value=>String(value||'').toLowerCase().includes(term)));
   list.replaceChildren();for(const card of cards)renderServer(card);
   if(!cards.length){const empty=node('div',undefined,'empty-state');empty.append(node('h3',term?'No matching lobbies':onlyFavorites?'No favorites yet':'No online lobbies found'),note(term?'Try a different room name or host address.':onlyFavorites?'Save an invite or choose the heart on an online lobby. Favorites stay here when offline.':'Refresh or join a friend using their invite. Only online advertised rooms appear here.'));if(!desktop)empty.append(button('Add a friend’s invite','subtle',()=>openJoin('join',null,true)));list.append(empty);}
  }
  async function refreshServers(){
   if(catalogBusy||closed||!directoryActive()||document.hidden)return;catalogBusy=true;const generation=++catalogGeneration;refreshButton.disabled=true;renderCatalog();directoryFeedback.textContent='Checking hosts on your '+(mode==='LAN'?'local network':'Tailscale network')+'…';
   const entries=seeds();
   try{
    // The backend caps each private-host request at 12. Check all favorites,
    // including those beyond the recent-host list, without dropping any.
    const batches=[];for(let i=0;i<entries.length;i+=12)batches.push(entries.slice(i,i+12));
    const results=await Promise.all(batches.map(rows=>api('lobbies/probe',{addresses:rows.map(x=>x.relay)})));
    if(closed||generation!==catalogGeneration||!servers.open)return;
    latest={hosts:results.flatMap(x=>x.hosts),checkedAt:Date.now()};renderCatalog();
    directoryFeedback.textContent=M.visible({...latest,favorites:favorites(),mode}).length+' online room(s) · Checked just now'+(discoveryNote?' · '+discoveryNote:'');
   }catch(e){if(generation===catalogGeneration){latest={hosts:[],checkedAt:0};renderCatalog();directoryFeedback.textContent=e.message;}}finally{if(generation===catalogGeneration){catalogBusy=false;refreshButton.disabled=false;}}
  }
  function renderServer(card){
   const row=node('article',undefined,'server-card'),top=node('div',undefined,'server-top'),title=node('div'),pill=node('span',card.state==='online'?'Online':card.state==='unadvertised'?'Host online · room not advertised':card.state==='unchecked'?'Not checked':card.state==='incompatible'?'Different version':card.state==='room-missing'?'Room unavailable':'Offline','state-pill '+(card.state==='online'?'':card.state==='incompatible'?'incompatible':'offline'));
   title.append(node('h3',card.room),node('p',(card.label||'ZGTA 5 lobby').replace(/^ZGTA V lobby$/,'ZGTA 5 lobby'),'server-caption'));top.append(title,pill);row.append(top,node('p',card.relay,'server-caption'));
   const meta=node('div',undefined,'server-meta');
   if(card.state==='online'||card.state==='unadvertised'){meta.append(node('span',card.verifiedRoom?card.players+' / '+card.capacity+' players':card.total+' connected on host'),node('span',card.latency+' ms response'),node('span',card.connection));if(!card.verifiedRoom)meta.append(node('span','Room is checked when joining'));if(card.slots>=card.capacity)meta.append(node('span','Full or players reconnecting'));}
   else meta.append(node('span',card.state==='room-missing'?'Your saved room is no longer advertised by this host.':card.message||'Open the host game/relay and check your connection.'));
   row.append(meta);const actions=node('div',undefined,'server-actions'),join=button('Join lobby','primary',()=>openJoin('join',card));join.disabled=!M.canJoin(card);actions.append(join);
   actions.append(button('Copy invite','subtle',async()=>{try{await navigator.clipboard.writeText(M.invite(card));directoryFeedback.textContent='Invite copied.';}catch(_){directoryFeedback.textContent=M.invite(card);}}));
   const heart=button(card.favorite?'♥ Saved':'♡ Favorite','subtle',()=>{try{M.setFavorite(storage,card,!card.favorite);renderCatalog();}catch(e){directoryFeedback.textContent=e.message;}});heart.setAttribute('aria-pressed',String(!!card.favorite));heart.setAttribute('aria-label',(card.favorite?'Remove favorite ':'Save favorite ')+card.room);actions.append(heart);
   row.append(actions);list.append(row);
  }
  function openServers(selected){
   if(launching)return;++catalogGeneration;catalogBusy=false;mode=selected||getSettings().connection;++discoveryGeneration;discovered=[];discoveryNote='';latest={hosts:[],checkedAt:0};directory.replaceChildren();
   const toolbar=node('div',undefined,'lobby-toolbar');
   directoryModeBar=connectionBar(mode,value=>{mode=value;discovered=[];++discoveryGeneration;directoryModeBar.sync(mode);discoverButton.hidden=mode!=='LAN';++catalogGeneration;catalogBusy=false;discoveryNote='';refreshServers();if(mode==='LAN')discoverLAN();});directoryModeBar.className='segmented directory-connection';
   refreshButton=button('Refresh','subtle',()=>mode==='LAN'?discoverLAN():refreshServers());discoverButton=button('Search LAN','subtle discover-lan',discoverLAN);discoverButton.hidden=mode!=='LAN';
   const tabs=node('div',undefined,'segmented');favoriteTabs=[button(desktop?'Find lobby':'Online','',()=>{onlyFavorites=false;renderCatalog();}),button('♥ Favorites','',()=>{onlyFavorites=true;renderCatalog();})];tabs.setAttribute('aria-label','Lobby list');tabs.append(...favoriteTabs);
   toolbar.append(directoryModeBar,tabs);
   if(desktop){const search=node('input',undefined,'lobby-search');search.type='search';search.placeholder='Search lobbies';search.setAttribute('aria-label','Search lobbies');search.value=searchTerm;search.addEventListener('input',()=>{searchTerm=search.value;renderCatalog();});toolbar.append(search);}
   toolbar.append(refreshButton,discoverButton,button(desktop?'Add favorite':'Add invite','subtle',()=>openJoin('join',null,true)));
   directoryFeedback=node('output','', 'directory-status');directoryFeedback.setAttribute('role','status');list=node('div',undefined,'server-list');directory.append(toolbar);
   if(!desktop)directory.append(note('Online lists advertised rooms checked just now. Favorites are saved only when you choose the heart or Add invite. Each device must use a reachable local or private VPN address.'));
   directory.append(directoryFeedback,list);close(dialog);show(servers);refreshServers();if(mode==='LAN')discoverLAN();
  }
  by('configure-lobby').onclick=()=>{
   by('lobby-title').textContent='Join or create';content.replaceChildren();const choices=node('div',undefined,'role-choices');
   choices.append(button('Join a friend','action-tile',()=>openJoin('join')),button('Create a lobby','action-tile',()=>openJoin('host')));content.append(note('Choose your setup. The game starts only after you press the green button on With friends.'),choices);show(dialog);
  };by('browse-lobbies').onclick=()=>{onlyFavorites=false;openServers();};
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&directoryActive()){renderCatalog();refreshServers();}});
  servers.addEventListener('close',()=>{if(!servers.open){++catalogGeneration;++discoveryGeneration;catalogBusy=false;}});
  root.addEventListener('pagehide',()=>{closed=true;++catalogGeneration;++discoveryGeneration;clearInterval(serverTimer);clearInterval(hostTimer);});
  function poll(){hostTimer=setInterval(readHost,10000);serverTimer=setInterval(()=>{if(directoryActive()&&!document.hidden){if(mode==='LAN')discoverLAN();else refreshServers();}},15000);}
  root.addEventListener('pageshow',event=>{if(!event.persisted)return;closed=false;poll();readHost();if(directoryActive())refreshServers();});
  poll();
  api('launcher/status',{}).then(info=>{if(closed)return;networks=info.networks||{};by('file-readiness').textContent=info.files_available?'Game files available · Ready when you are':'Game files are unavailable. Open Files & Support for help.';}).catch(()=>{by('file-readiness').textContent='The local launcher is unavailable. Check Files & Support.';});readHost();
  return {setDesktop:value=>{if(desktop===value)return;for(const sheet of [dialog,servers])if(sheet.open)sheet.close();desktop=value;desktopVisible=false;pendingSetup=null;if(!desktop)searchTerm='';for(const sheet of [dialog,servers])sheet.setAttribute('role',desktop?'region':'dialog');dialog.setAttribute('aria-labelledby',desktop?'desktop-multiplayer-title':'lobby-title');servers.setAttribute('aria-labelledby',desktop?'friends-title':'servers-title');},activateDesktop:visible=>{desktopVisible=visible;if(desktop&&visible){if(!servers.open)openServers();if(!dialog.open)openJoin(getSettings().lobbyRole||'join');}},prepareLaunch:()=>{if(desktop){if(!pendingSetup)throw Error('Choose Join a friend or Create a lobby first.');return pendingSetup();}},join:openJoin,browse:openServers,readHost,restorePlayerName:value=>{if(dialog.open&&activePlayerInput&&!activePlayerDirty)activePlayerInput.value=value;},resetLaunch:()=>{launching=false;},hostState:()=>owned};
 }
 root.ZemaLobbyUI={mount};
})(globalThis);
