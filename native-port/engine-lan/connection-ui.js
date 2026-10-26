/* Connection presentation only: no profiles, sockets, game commands or automatic retry. */
(function(root){'use strict';
 function mount(settings){
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const scope=el('aside',undefined,'zgta-connection');scope.id='zema-lan-status';
  const style=el('style');style.textContent=`
  #zema-lan-status{--mint:#46e7c2;--ink:#091119;position:fixed;inset:0;z-index:2190;pointer-events:none;font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#f4f7fb;color-scheme:dark}
  #zema-lan-status *{box-sizing:border-box}#zema-lan-status [hidden]{display:none!important}
  #zema-lan-status button{font:inherit;cursor:pointer;touch-action:manipulation}#zema-lan-status button:disabled{opacity:.5;cursor:default}#zema-lan-status button:focus-visible,#zema-lan-status summary:focus-visible{outline:2px solid var(--mint);outline-offset:4px}
  #zema-lan-status .connection-toggle{position:absolute;right:max(84px,env(safe-area-inset-right));top:max(56px,env(safe-area-inset-top));width:52px;height:52px;display:grid;place-items:center;pointer-events:auto;border:1px solid #d7e6eb38;border-radius:50%;background:#0911194d;backdrop-filter:blur(18px);color:#eff7fa}
  #zema-lan-status .connection-toggle svg{width:24px;height:24px}#zema-lan-status .connection-dot{position:absolute;right:7px;top:7px;width:7px;height:7px;border-radius:50%;background:var(--mint);box-shadow:0 0 0 3px #101923}
  #zema-lan-status[data-state=disconnected] .connection-dot,#zema-lan-status[data-state=error] .connection-dot{background:#f4b469}#zema-lan-status[data-state=connecting] .connection-dot{background:#dce7ed}
  #zema-lan-status .connection-notice{position:absolute;left:50%;top:max(18px,env(safe-area-inset-top));transform:translateX(-50%);width:min(430px,calc(100vw - 36px));padding:15px 17px;display:flex;gap:12px;align-items:center;pointer-events:auto;border:1px solid #d7e6eb24;border-radius:18px;background:#0810194d;backdrop-filter:blur(22px);box-shadow:0 10px 40px #0002}
  #zema-lan-status .connection-copy{min-width:0;flex:1}#zema-lan-status .connection-title{display:block;font-size:14px;font-weight:650;letter-spacing:.01em}#zema-lan-status .connection-message{display:block;font-size:12px;color:#d8e2e9;margin-top:3px;line-height:1.45}
  #zema-lan-status .connection-primary{flex:none;min-height:38px;border:0;border-radius:10px;padding:9px 13px;background:var(--mint);color:var(--ink);font-weight:650}
  #zema-lan-status .connection-dismiss{border:0;background:none;color:#dce8ec;padding:4px;font-size:20px;line-height:1}
  #zema-lan-status .connection-panel{position:absolute;right:max(20px,env(safe-area-inset-right));top:118px;pointer-events:auto;width:min(360px,calc(100vw - 40px));max-height:calc(100dvh - 142px);overflow:auto;overscroll-behavior:contain;padding:23px;border:1px solid #d7e6eb24;border-radius:22px;background:#0c141de8;backdrop-filter:blur(24px);box-shadow:0 20px 70px #0005}
  #zema-lan-status .connection-header{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:18px}#zema-lan-status h2{font-size:19px;letter-spacing:-.025em;margin:0}#zema-lan-status .connection-close{border:0;background:#ffffff0d;color:#e6f0f6;border-radius:50%;height:30px;width:30px;font-size:20px}
  #zema-lan-status .connection-room{margin:0;color:#f7fafc;font-size:16px;font-weight:600;overflow-wrap:anywhere}#zema-lan-status .connection-kind{margin:3px 0 20px;color:#a9bac6;font-size:12px}#zema-lan-status .connection-actions{display:flex;flex-wrap:wrap;gap:9px;margin:18px 0}
  #zema-lan-status .connection-secondary{padding:9px 12px;min-height:38px;border:1px solid #d6e9f026;border-radius:10px;background:#ffffff08;color:#e4edf2}
  #zema-lan-status .connection-help{font-size:13px;color:#c1cfd9;margin:10px 0 18px}#zema-lan-status .connection-help strong{display:block;color:#eff5f8;font-weight:600;margin-bottom:5px}
  #zema-lan-status details{border-top:1px solid #d5e5f018;padding-top:16px;font-size:12px;color:#9db0bd}#zema-lan-status summary{cursor:pointer;color:#c7d5df;list-style:none}#zema-lan-status summary::after{content:'+';float:right;font-size:16px}#zema-lan-status details[open] summary::after{content:'−'}
  #zema-lan-status .connection-detail{display:block;margin:12px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}#zema-lan-status .connection-host{margin-top:16px;font-size:12px;color:#b8c9d5;white-space:pre-wrap}
  @media(max-width:600px){#zema-lan-status .connection-notice{top:auto;bottom:max(20px,env(safe-area-inset-bottom));width:calc(100vw - 32px)}#zema-lan-status .connection-panel{top:118px;right:16px;width:calc(100vw - 32px);max-height:calc(100dvh - 138px)}}
  @media(prefers-reduced-motion:no-preference){#zema-lan-status .connection-notice{animation:zgta-connection-in .18s ease-out}@keyframes zgta-connection-in{from{opacity:0;translate:0 -4px}to{opacity:1;translate:0 0}}}
  `;
  const toggle=el('button',undefined,'connection-toggle');toggle.type='button';toggle.title='Connection';toggle.setAttribute('aria-label','Connection');toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls','zema-connection-panel');
  toggle.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M3 8.5a14 14 0 0 1 18 0M6.5 12a9 9 0 0 1 11 0M10 15.5a3.5 3.5 0 0 1 4 0"/><circle cx="12" cy="19" r="1" fill="currentColor" stroke="none"/></svg>';
  toggle.append(el('span',undefined,'connection-dot'));
  const notice=el('div',undefined,'connection-notice'),copy=el('div',undefined,'connection-copy'),title=el('span','Connected to host','connection-title'),message=el('span',settings.room,'connection-message');copy.setAttribute('role','status');copy.setAttribute('aria-live','polite');copy.append(title,message);
  const quick=el('button','Reconnect','connection-primary'),dismiss=el('button','×','connection-dismiss');quick.type=dismiss.type='button';dismiss.setAttribute('aria-label','Dismiss connection notification');notice.append(copy,quick,dismiss);
  const panel=el('section',undefined,'connection-panel');panel.id='zema-connection-panel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Connection');
  const header=el('div',undefined,'connection-header'),close=el('button','×','connection-close');close.type='button';close.setAttribute('aria-label','Close connection');header.append(el('h2','Connection'),close);
  const room=el('p',settings.room,'connection-room'),kind=el('p',(settings.connection||'LAN')+' multiplayer','connection-kind'),actions=el('div',undefined,'connection-actions');
  const reconnect=el('button','Reconnect','connection-primary'),rejoin=el('button','Restart game','connection-secondary');reconnect.type=rejoin.type='button';rejoin.hidden=true;actions.append(reconnect,rejoin);
  const help=el('p',undefined,'connection-help');help.hidden=true;help.append(el('strong','Continue in GTA'),el('span','Pause → Online → Find New Session → Public Session. Confirm in GTA to return to this lobby.'));
  const details=el('details'),summary=el('summary','Connection details'),detail=el('small','Room: '+settings.room+'\nHost: '+settings.relay,'connection-detail'),live=el('output','Connected to host','connection-detail'),saveOutput=el('small',undefined,'connection-detail');saveOutput.setAttribute('role','status');details.append(summary,detail,live,saveOutput);
  const inputOutput=el('small',undefined,'connection-detail');details.append(inputOutput);
  const hostRegion=el('div'),hostDetails=el('small',undefined,'connection-host'),hostButton=el('button','Refresh lobby','connection-secondary'),stopHost=el('button','Stop hosting','connection-secondary'),hostActions=el('div',undefined,'connection-actions');hostButton.type=stopHost.type='button';hostRegion.hidden=settings.lobbyRole!=='host';hostActions.append(hostButton,stopHost);hostRegion.append(hostActions,hostDetails);
  panel.append(header,room,kind,help,actions,hostRegion,details);scope.append(style,toggle,notice,panel);document.body.append(scope);
  let closed=false,hideTimer=null,previousSuspended=false,phase='connected',lastNotice='';
  function hide(){if(panel.hidden)return;panel.hidden=true;root.ZemaInputSuspended=previousSuspended;toggle.setAttribute('aria-expanded','false');toggle.focus?.();}
  function show(){if(closed||!panel.hidden)return;document.dispatchEvent(new CustomEvent('zema-ui-panel-open',{detail:'connection'}));previousSuspended=!!root.ZemaInputSuspended;root.ZemaInputSuspended=true;root.ZemaGameInput?.release();document.exitPointerLock?.();panel.hidden=false;toggle.setAttribute('aria-expanded','true');close.focus?.();}
  toggle.onclick=()=>panel.hidden?show():hide();close.onclick=hide;dismiss.onclick=()=>notice.hidden=true;
  panel.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();hide();}else if(event.key==='Tab'){const all=Array.from(panel.querySelectorAll('button,summary')).filter(n=>!n.disabled&&!n.hidden&&!n.closest?.('[hidden]'));if(!all.length)return;const first=all[0],last=all[all.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
  const otherPanel=event=>{if(event.detail!=='connection')hide();};document.addEventListener('zema-ui-panel-open',otherPanel);
  function render(state,{technical='',showGuide=false}={}){
   if(closed)return;phase=state;scope.setAttribute('data-state',state);if(technical)live.textContent=technical;help.hidden=!showGuide;
   const presentation={connected:['Connected to host',settings.room],restarting:['Rejoining your lobby','GTA is restarting your session. Keep the game open.'],connecting:['Reconnecting…','Keep your game open while the host returns.'],disconnected:['Connection lost','Reconnect to return to '+settings.room+'.'],recovered:['Host connection restored','Reconnect to restart your GTA session in this lobby.'],error:['Couldn’t reconnect','Check that the same host is running, then try again.'],saving:['Saving your character','Keep this tab open until the save finishes.'],'profile-error':['Character save needs attention','Keep your game open and check Connection details.']}[state]||['Connection',settings.room];
   title.textContent=presentation[0];message.textContent=presentation[1];quick.textContent=state==='profile-error'?'Details':'Reconnect';quick.disabled=state==='connecting'||state==='saving'||state==='restarting';quick.hidden=state==='connected';
   const key=state+'|'+showGuide;if(key!==lastNotice){lastNotice=key;notice.hidden=false;if(hideTimer)clearTimeout(hideTimer);hideTimer=null;if(state==='connected')hideTimer=setTimeout(()=>{notice.hidden=true;hideTimer=null;},3500);}
  }
  quick.onclick=()=>{if(phase==='profile-error'){show();if(phase==='profile-error')details.open=true;}else reconnect.onclick?.();};
  function destroy(){if(closed)return;hide();closed=true;if(hideTimer)clearTimeout(hideTimer);document.removeEventListener('zema-ui-panel-open',otherPanel);scope.remove();}
  render('connected');
  return {root:scope,reconnect,rejoin,live,saveOutput,hostDetails,hostButton,stopHost,hostRegion,detail,inputStatus:text=>{inputOutput.textContent=text;},render,show,hide,destroy};
 }
 root.ZemaConnectionUI={mount};if(typeof module==='object')module.exports=root.ZemaConnectionUI;
})(globalThis);
