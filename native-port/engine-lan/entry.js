/* Launcher owns configuration; runtime only admits the saved selection. */
(function(){'use strict';
  let resolveReady,rejectReady,closed=false,network=null,profile=null,recoveryTimer=null,hostTimer=null,restartTimer=null;
  const pending=new Set();
  let profileOwnerReady=false,checkpointSequence=0;
  function checkpointProfile(){
    if(closed||!profileOwnerReady||!profile)return 0;
    const id=++checkpointSequence;try{profile.postMessage({type:'checkpoint',id});return id;}catch{return 0;}
  }
  document.addEventListener('visibilitychange',()=>{if(document.hidden)checkpointProfile();});
  const ready=new Promise((resolve,reject)=>{resolveReady=resolve;rejectReady=reject;});
  ready.catch(()=>{}); // Runtime owns the visible failure path; never start a game after failure.
  window.ZemaLanReady=ready;
  const base='/b/8b0b5899ed/';
  const args=['-disableDebugPadButtons','-disallowdebugpad','-lan','-StraightIntoFreemode','-netMpSkipCloudFileRequirements','-sc_noOnlinePolicy','-netshoptransactionnull','-netGameTransactionsNoToken','-nocatalog','-wasmstartchoice=1'];
  window.ZemaLabLaunch=async function(worker,message,transfer){
    const context=await ready;
    if(window.ZemaRuntime)context.features=window.ZemaRuntime.features;
    message.remoteLog=true;message.engineLan=context;message.keepThreads=(message.keepThreads||0)|6;
    message.args=message.args.filter(x=>x!=='-nonetwork'&&!x.startsWith('-wasmstartchoice='));message.args.push(...args);
    worker.postMessage(message,transfer);
  };
  function expect(worker,type,message){return new Promise((resolve,reject)=>{
    let settled=false;
    const finish=(error,context)=>{if(settled)return;settled=true;clearTimeout(timer);pending.delete(cancel);worker.onerror=null;worker.onmessage=null;if(error)reject(error);else resolve(context);};
    const cancel=()=>finish(Error('Startup cancelled.'));
    const timer=setTimeout(()=>finish(Error('Startup timed out; no game was started.')),30000);pending.add(cancel);
    worker.onerror=()=>finish(Error('Experimental worker could not start.'));
    worker.onmessage=event=>{const m=event.data;if(m.type==='error')finish(Error(m.message));else if(m.type===type)finish(null,m.context);};
    try{worker.postMessage(message);}catch(error){finish(error);}
  });}
  addEventListener('DOMContentLoaded',async()=>{
    const settings=window.ZemaRuntime?.settings;
    function failed(error){
      if(closed)return;
      if(profile)profile.terminate();if(network)network.terminate();profile=network=null;
      const message=String(error.message||error).slice(0,300);
      try{sessionStorage.setItem('zema-browser-lan-error-v1',JSON.stringify({message,relay:settings?.relay||'',at:Date.now()}));}catch(_){}
      rejectReady(Error(message));window.location.replace('/?'+new URLSearchParams({lan:'failed',...(settings||{mode:'lan'})}));
    }
    if(!settings||settings.mode!=='lan'||!window.ZemaRuntimeAdmission){failed(Error('Choose multiplayer from the launcher before pressing Play.'));return;}
    // No side worker or profile access before GPU and exclusive-game admission.
    if(!await window.ZemaRuntimeAdmission||closed)return;
    try{
      if(!crossOriginIsolated||typeof SharedArrayBuffer==='undefined')throw Error('Open the local lab server in Chrome; isolated shared memory is required.');
      ZemaEngineLan.localURL(settings.relay);
      const room=settings.room;if(!room.trim()||new TextEncoder().encode(room).length>64||/[\x00-\x1f\x7f-\x9f]/.test(room))throw Error('Enter a room of 1–64 bytes without control characters.');
      const name=settings.player;if(!/^[\x20-\x7e]{1,16}$/.test(name)||!name.trim())throw Error('Use a name of 1–16 English characters.');
      profile=new Worker(ZemaLaunchChannels.url(base+'profile-worker.js'));
      const profileContext=await expect(profile,'ready',{buffer:new SharedArrayBuffer(4096+8*1024*1024+36),name});
      profileOwnerReady=true;
      let saveStatus={state:'checking'},saveOutput=null,onSaveStatus=()=>{};
      const showSave=()=>{if(!saveOutput)return;saveOutput.textContent=saveStatus.state==='error'?'LAN profile save failed. Keep this tab open; check browser storage before restarting.':saveStatus.state==='pending'?'Saving LAN profile…':saveStatus.state!=='saved'?'Checking stored character data…':!saveStatus.characterFiles?'Profile stored; the game has not saved a character file yet.':saveStatus.characterReads?'Character save stored and read by the game.':'Character save stored; not yet read by the game.';};
      profile.onmessage=event=>{if(closed)return;if(event.data.type==='profile-status'){saveStatus=event.data;showSave();onSaveStatus();if(saveStatus.state==='error')window.ZemaConnectionPanel?.render('profile-error');}};
      profile.onerror=()=>{if(closed)return;saveStatus={state:'error'};showSave();onSaveStatus();window.ZemaConnectionPanel?.render('profile-error');};
      network=new Worker(ZemaLaunchChannels.url(base+'network-worker.js'));
      const context=await expect(network,'joined',{type:'connect',url:settings.relay,room,name:profileContext.name});
      if(closed)return;context.profile=profileContext;
      const connectionUI=ZemaConnectionUI.mount(settings);
      window.ZemaConnectionPanel=connectionUI;
      const {live,reconnect,rejoin,hostDetails,hostButton,stopHost}=connectionUI;
      saveOutput=connectionUI.saveOutput;showSave();
      if(saveStatus.state==='error')connectionUI.render('profile-error');
      let refreshHost=()=>{};
      if(settings.lobbyRole==='host'){
        const hostAPI=async(path,body)=>{const response=await fetch('/zema-lab/host/'+path,{method:'POST',headers:{'X-Zema-Lab':'1','Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw Error(value.error||'Lobby action failed');return value;};
        let hostBusy=false,hostState=null;
        const matching=state=>state.owned&&state.join===settings.relay&&state.room===settings.room&&state.connection===settings.connection;
        const showHost=state=>{
          hostState=matching(state)?state:null;
          stopHost.disabled=hostBusy||!hostState||(!state.running&&!state.can_restart);
          stopHost.textContent=hostState&&!state.running?'Start hosting again':'Stop hosting';
          hostDetails.textContent=!hostState?'This game’s hosted lobby is no longer available.':state.running?'Hosting on this computer · '+state.peers+' player(s)\nRoom: '+state.room+'\nJoin address: '+(state.remote||state.lan):'Hosting stopped. Start hosting again to reopen this room at the same address. Your character is preserved.';
        };
        const refresh=async()=>{if(closed||hostBusy)return;hostBusy=true;try{const state=await hostAPI('status',{});if(!closed)showHost(state);}catch(error){if(!closed){hostState=null;hostDetails.textContent='Lobby status unavailable. '+error.message;}}finally{hostBusy=false;if(!closed)stopHost.disabled=!hostState||(!hostState.running&&!hostState.can_restart);}};
        // Refresh after admission and periodically; a pre-admission snapshot
        // otherwise stays at zero until the owner clicks Lobby details.
        // One timer and one in-flight request; background tabs do no polling.
        refreshHost=()=>{if(!closed&&!document.hidden)return refresh();};
        hostTimer=setInterval(refreshHost,5000);
        hostButton.onclick=refresh;
        stopHost.onclick=async()=>{
          if(hostBusy)return;hostBusy=true;hostButton.disabled=stopHost.disabled=true;
          try{
            const state=await hostAPI('status',{});showHost(state);
            if(!hostState)throw Error('This game’s hosted lobby is no longer available. Another lobby was left running.');
            if(state.running){if(confirm('Stop your lobby and disconnect its players?'))showHost(await hostAPI('stop',{id:state.id}));}
            else if(state.can_restart){
              const restarted=await hostAPI('restart',{id:state.id});showHost(restarted);
              if(!hostState||!restarted.running)throw Error('The lobby could not restart at this game’s address.');
              live.textContent='Lobby restarted. Reconnecting to the relay…';reconnect.disabled=true;network.postMessage({type:'resume'});
            }
          }catch(error){hostDetails.textContent=error.message;}
          finally{hostBusy=false;hostButton.disabled=false;stopHost.disabled=!hostState||(!hostState.running&&!hostState.can_restart);}
        };

        refreshHost();
      }
      let rejoinRequested=false,transportRecovered=false,wantsRestart=false,transportState='connected',restartActive=false;
      const restartSession=()=>{
        if(closed||restartActive)return;
        const shared=window.ZemaRuntime?.features?.pad;
        if(!shared||!window.ZemaGameReady){live.textContent='Wait until your character enters the world, then reconnect.';connectionUI.render('error',{technical:live.textContent});return;}
        if(!ZemaSessionRestart.request(shared))return;
        wantsRestart=false;restartActive=true;reconnect.disabled=true;connectionUI.hide();connectionUI.render('restarting');
        restartTimer=setInterval(()=>{if(closed)return;const status=ZemaSessionRestart.status(shared);if(status<=0||status===4){clearInterval(restartTimer);restartTimer=null;restartActive=false;reconnect.disabled=false;rejoin.hidden=status===4;live.textContent=status===4?'Returned to the GTA session.':'GTA could not finish the restart (status '+status+'). Use Find New Session → Public Session manually, or retry.';transportRecovered=status!==4;connectionUI.render(status===4?'connected':'error',{technical:live.textContent,showGuide:status!==4});}},250);
      };
      const recoveredMessage='The host is connected. Reconnect restarts your GTA session in the same lobby.';

      const finishRejoin=()=>{
        if(!rejoinRequested||closed)return;
        if(saveStatus.state==='saved'&&saveStatus.characterFiles>0){
          rejoinRequested=false;clearTimeout(recoveryTimer);recoveryTimer=null;
          live.textContent='Rejoining the server with your saved character…';window.location.reload();
        }else if(saveStatus.state==='error'||(saveStatus.state==='saved'&&!saveStatus.characterFiles)){
          rejoinRequested=false;clearTimeout(recoveryTimer);recoveryTimer=null;reconnect.disabled=false;rejoin.disabled=false;reconnect.textContent='Reconnect';
          live.textContent=saveStatus.state==='error'?'Character storage needs attention. Keep this tab open before rejoining.':'The game has not saved a character yet. Wait for a character save before rejoining.';
          connectionUI.render('profile-error',{technical:live.textContent});
        }
      };
      const requestRejoin=()=>{
        if(rejoinRequested)return;rejoinRequested=true;reconnect.disabled=rejoin.disabled=true;reconnect.textContent='Rejoining…';
        live.textContent='Waiting for the current character save before rejoining…';
        recoveryTimer=setTimeout(()=>{if(!rejoinRequested)return;rejoinRequested=false;reconnect.disabled=rejoin.disabled=false;reconnect.textContent='Reconnect';live.textContent='The profile is still saving. Keep this tab open and retry after the save completes.';connectionUI.render('profile-error',{technical:live.textContent});},8000);
        connectionUI.render('saving',{technical:live.textContent});
        finishRejoin();
      };
      rejoin.onclick=requestRejoin;
      onSaveStatus=finishRejoin;
      network.onmessage=event=>{const m=event.data;
        if(m.type==='status'){
          transportState=m.state;live.textContent=m.message;reconnect.disabled=restartActive||m.state==='connecting';rejoin.disabled=m.state==='connecting';
          if(m.state==='connected'){if(transportRecovered)live.textContent=recoveredMessage;rejoin.hidden=!transportRecovered;reconnect.textContent='Reconnect';}
        }else if(m.type==='resumed'){
          transportState='connected';transportRecovered=true;
          live.textContent=recoveredMessage;reconnect.disabled=true;rejoin.hidden=false;rejoin.disabled=false;reconnect.textContent='Reconnect';
          refreshHost();if(wantsRestart)restartSession();
        }else if(m.type==='error'){
          if(m.operation==='resume'){
            rejoin.hidden=!transportRecovered&&!['address-in-use','identity-changed'].includes(m.code);rejoin.disabled=false;
            live.textContent=rejoin.hidden?m.message:m.message+' The host could not restore this session. Retry, or use Rejoin with saved character to reload the game.';reconnect.disabled=false;reconnect.textContent='Reconnect';
          }
          else{live.textContent=m.message;reconnect.disabled=false;}
        }
        const state=m.type==='resumed'||(m.type==='status'&&m.state==='connected'&&transportRecovered)?'recovered':m.type==='error'?'error':m.state==='connecting'?'connecting':m.state==='disconnected'?'disconnected':'connected';
        connectionUI.render(restartActive?'restarting':state,{technical:live.textContent,showGuide:transportRecovered&&!restartActive});
      };
      reconnect.onclick=()=>{
        if(restartActive)return;if(transportState==='connected'){restartSession();return;}wantsRestart=true;
        reconnect.disabled=true;
        rejoin.disabled=true;live.textContent='Reconnecting to the same session…';connectionUI.render('connecting',{technical:live.textContent});network.postMessage({type:'resume'});
      };
      resolveReady(context);
    }catch(error){failed(error);}
  });
  addEventListener('pagehide',()=>{
    if(closed)return;const id=checkpointProfile(),owner=profile;closed=true;
    if(recoveryTimer)clearTimeout(recoveryTimer);if(hostTimer)clearInterval(hostTimer);if(restartTimer)clearInterval(restartTimer);for(const cancel of pending)cancel();rejectReady(Error('Startup cancelled.'));if(network)network.terminate();
    if(owner&&id){
      // Best effort only: a closing browser can terminate workers regardless.
      // Give an already-ready owner a bounded chance to finish its transaction.
      let ended=false;const finish=()=>{if(ended)return;ended=true;clearTimeout(deadline);owner.terminate();};
      const deadline=setTimeout(finish,1500);
      owner.onmessage=event=>{const m=event.data;if(m?.type==='profile-checkpoint'&&m.state==='saved'&&m.id>=id)finish();};
      owner.onerror=()=>{}; // No late UI errors after the game has closed.
    }else if(owner)owner.terminate();
    window.ZemaConnectionPanel?.destroy();
  });
})();
