/* Desktop composition: move the existing controls; never copy a save or launch form. */
(function(root){'use strict';
 function mount({getSettings,selectSolo,showPage,showSettings,lobbyUI}){
  const by=id=>document.getElementById(id),make=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;};
  const media=matchMedia('(min-width: 1000px) and (hover: hover) and (pointer: fine)');
  const solo=document.querySelector('[data-page="solo"]'),friends=document.querySelector('[data-page="friends"]'),preferences=by('preferences');
  const anchors=new Map();let active=false,lastPage='solo';
  function move(node,target){if(!anchors.has(node)){const marker=document.createComment('desktop return point');node.before(marker);anchors.set(node,marker);}target.append(node);}
  function restore(node){const marker=anchors.get(node);if(marker)marker.after(node);}
  function button(text,cls,action){const b=make('button',cls,text);b.type='button';b.addEventListener('click',action);return b;}
  const nav=make('nav','desktop-nav');nav.setAttribute('aria-label','Launcher');
  const soloMenu=make('div','desktop-mode-menu'),soloToggle=button('Story mode','desktop-nav-item',()=>{const open=soloToggle.getAttribute('aria-expanded')==='true';setMenu(!open);if(!open)soloOptions.querySelector('button').focus();});
  soloToggle.id='desktop-solo-toggle';soloToggle.setAttribute('aria-expanded','false');soloToggle.setAttribute('aria-controls','desktop-solo-options');
  const soloOptions=make('div','desktop-mode-options');soloOptions.id='desktop-solo-options';soloOptions.hidden=true;
  for(const [mode,title]of [['story','Story mode'],['sandbox','Free roam']]){const b=button(title,'',()=>{selectSolo(mode);showPage('solo');setMenu(false);soloToggle.focus();});b.dataset.soloMode=mode;soloOptions.append(b);}
  function setMenu(open){soloToggle.setAttribute('aria-expanded',String(open));soloOptions.hidden=!open;}
  soloMenu.append(soloToggle,soloOptions);nav.append(soloMenu);
  const multiplayer=button('Multiplayer','desktop-nav-item',()=>showPage('friends'));nav.append(multiplayer);
  for(const [tab,title]of [['tools','Mods'],['saves','Saves'],['device','Support']])nav.append(button(title,'desktop-nav-item',()=>{setMenu(false);showSettings(tab);}));
  document.querySelector('.topbar .brand').after(nav);
  document.addEventListener('click',event=>{if(!soloMenu.contains(event.target))setMenu(false);});
  soloMenu.addEventListener('keydown',event=>{if(event.key==='Escape'){setMenu(false);soloToggle.focus();}if(event.key==='ArrowDown'&&event.target===soloToggle){event.preventDefault();setMenu(true);soloOptions.querySelector('button').focus();}});
  soloOptions.addEventListener('focusout',event=>{if(event.relatedTarget&&!soloMenu.contains(event.relatedTarget))setMenu(false);});

  const art=make('figure','desktop-story-art'),image=make('img');image.src='/zema-lab/desktop-city.png';image.alt='Sunset city artwork';image.width=1672;image.height=941;
  const caption=make('figcaption');art.append(image,caption);by('home-game').before(art);
  function setup(title){const panel=make('aside','desktop-setup'),heading=make('h2','',title),fields=make('div','desktop-quick-fields'),links=make('div','desktop-setup-links');
   for(const [tab,text]of [['graphics','Graphics'],['controls','Controls']])links.append(button(text,'desktop-link',()=>showSettings(tab)));
   const input=make('div','desktop-input-summary'),inputLabel=make('span','','Input'),inputValue=make('span');input.append(inputLabel,inputValue);
   panel.append(heading,fields,input,links);return {panel,fields,links,inputValue};
  }
  const soloSetup=setup('Launch setup');solo.querySelector('.solo-layout').append(soloSetup.panel);
  const friendsGrid=make('div','desktop-friends-grid'),directoryPanel=make('section','desktop-directory'),multiSetup=setup('Join or create');multiSetup.panel.querySelector('h2').id='desktop-multiplayer-title';
  directoryPanel.setAttribute('aria-label','Lobby browser');friendsGrid.append(directoryPanel,multiSetup.panel);friends.append(friendsGrid);
  const inlineSetup=make('div','desktop-lobby-setup');multiSetup.panel.querySelector('h2').after(inlineSetup);
  const footer=make('footer','desktop-footer');document.querySelector('.shell').append(footer);
  const quickRows=['preset','height','fps'].map(id=>by(id).closest('.row'));
  function syncQuickRows(){if(!active)return;const target=preferences.open?document.querySelector('[data-section="graphics"]'):(lastPage==='friends'?multiSetup:soloSetup).fields;
   if(preferences.open){for(const row of quickRows)restore(row);}else for(const row of quickRows)move(row,target);
  }
  preferences.addEventListener('close',syncQuickRows);
  function pageChanged(page){if(!active)return;setMenu(false);lastPage=page==='friends'?'friends':'solo';syncQuickRows();lobbyUI.activateDesktop(page==='friends');refresh();}
  function refresh(){if(!active)return;const s=getSettings(),isFriends=document.body.dataset.currentPage==='friends';
   const mode=s.mode==='lan'?soloToggle.dataset.lastMode||'story':s.mode;soloToggle.dataset.lastMode=mode;soloToggle.textContent=(mode==='sandbox'?'Free roam':'Story mode')+' ▾';
   soloToggle.toggleAttribute('aria-current',!isFriends);multiplayer.toggleAttribute('aria-current',isFriends);
   for(const b of soloOptions.children)b.setAttribute('aria-pressed',String(b.dataset.soloMode===mode));
   by('solo-title').textContent=mode==='sandbox'?'Free roam':'Story mode';caption.textContent=mode==='sandbox'?'Explore Los Santos at your pace.':'Play the story using your saves.';
   by('friends-title').textContent='Private multiplayer';
   if(s.mode==='story')by('play').querySelector('span').textContent=s.newgame?'Start New Story':'Play Story Mode';
   const status=by('status');if(!by('play').disabled&&!status.classList.contains('error'))status.textContent='';
   const input=s.keyboardMouse?(s.controller?'Keyboard, mouse & controller':'Keyboard & mouse'):(s.controller?'Controller':'No input selected');soloSetup.inputValue.textContent=multiSetup.inputValue.textContent=input;
   document.querySelector('.skip').href=isFriends?'#friends-title':'#solo-title';
  }
  function setActive(enabled){if(active===enabled)return;active=enabled;document.body.classList.toggle('desktop-launcher',active);setMenu(false);
   if(active){
    const heading=friends.querySelector('.subpage-heading');move(by('servers-dialog'),directoryPanel);move(heading,directoryPanel);directoryPanel.prepend(heading);
    move(by('lobby-dialog'),inlineSetup);move(by('friends-launch'),multiSetup.panel);move(by('home-host'),multiSetup.panel);move(by('file-readiness'),footer);
    lobbyUI.setDesktop(true);
    const page=document.body.dataset.currentPage;
    if(page==='home'){let mode='story';try{const saved=localStorage.getItem('zema-solo-mode-v1');if(['story','sandbox'].includes(saved))mode=saved;}catch(_){}selectSolo(mode);showPage('solo');}
    else pageChanged(page);
   }else{
    lobbyUI.setDesktop(false);for(const row of quickRows)restore(row);
    for(const id of ['servers-dialog','lobby-dialog','friends-launch','home-host','file-readiness'])restore(by(id));
    restore(directoryPanel.querySelector('.subpage-heading'));restore(by('launch-panel'));
    by('solo-title').textContent='On my own';by('friends-title').textContent='With friends';showPage(document.body.dataset.currentPage);refresh();
    document.querySelector('.skip').href='#home-title';
   }
  }
  // Returning from a settings sheet or resizing keeps the one real launch panel.
  const launch=by('launch-panel'),launchAnchor=document.createComment('launch panel original');launch.before(launchAnchor);anchors.set(launch,launchAnchor);
  function placeLaunch(){if(active){const page=document.body.dataset.currentPage;move(launch,page==='friends'?by('friends-launch'):soloSetup.panel);}}
  const publicPage=page=>{pageChanged(page);placeLaunch();};
  media.addEventListener('change',()=>{setActive(media.matches);placeLaunch();});
  document.querySelector('.brand').addEventListener('click',event=>{if(active){event.preventDefault();selectSolo(soloToggle.dataset.lastMode||'story');showPage('solo');}});
  setActive(media.matches);if(active)pageChanged(document.body.dataset.currentPage);placeLaunch();
  return {get active(){return active;},refresh,showSettings:()=>{if(active)for(const row of quickRows)restore(row);},pageChanged:publicPage};
 }
 root.ZemaDesktopLauncher={mount};
})(globalThis);
