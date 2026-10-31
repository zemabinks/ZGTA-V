/* Vehicle browsing never queues an action; Spawn remains an explicit command. */
(function(root){'use strict';
 function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
 function modEntries(catalog){
  const found=new Map();
  for(const pack of (catalog?.packs||[]).slice(0,16)){
   if(!pack.enabled)continue;
   for(const model of (pack.vehicleModels||[]).slice(0,2048)){
    if(typeof model==='string'&&/^[a-z][a-z0-9_]{0,62}$/.test(model))found.set(model,{model,name:model,category:'Installed mods',base:false,kind:'mod'});
   }
  }
  return [...found.values()];
 }
 function previewCard(container){
  const card=el('aside'),heading=el('strong'),model=el('small'),picture=el('img'),status=el('p'),credit=el('small','Reference: FiveM / Cfx.re'),close=el('button','Close preview');
  card.hidden=true;card.setAttribute('role','region');card.setAttribute('aria-label','Vehicle preview');status.setAttribute('role','status');
  card.style.cssText='position:fixed;z-index:10020;box-sizing:border-box;width:280px;max-width:calc(100vw - 24px);padding:14px;border:1px solid #698478;border-radius:16px;background:rgba(11,23,26,.96);color:#e6f9ed;box-shadow:0 12px 40px #0008';
  heading.style.cssText='display:block;font-size:18px';model.style.cssText='display:block;color:#b3c9be;margin:4px 0';
  // The game keeps COEP require-corp for shared memory. FiveM permits anonymous CORS.
  picture.crossOrigin='anonymous';
  picture.style.cssText='width:100%;height:130px;object-fit:contain;background:#ffffff09;border-radius:10px';
  status.style.cssText='font-size:13px;margin:8px 0';credit.style.cssText='display:block;color:#b3c9be;font-size:11px';
  close.type='button';close.style.cssText='margin-top:10px;border:1px solid #638c79;border-radius:8px;padding:8px 12px;background:#243e33;color:inherit';
  card.append(heading,model,picture,status,credit,close);container.append(card);
  let generation=0,pinned=false,current=null,currentRow=null;
  function hide(){generation++;card.hidden=true;pinned=false;current=null;currentRow=null;picture.onload=picture.onerror=null;picture.removeAttribute?.('src');}
  function show(v,row,pin=false){
   const url=ZemaVehicleCatalog.thumbnailURL(v),key=url||'mod:'+v.model;currentRow=row;pinned=pin;card.hidden=false;heading.textContent=v.name;model.textContent=v.model;
   credit.textContent=ZemaVehicleCatalog.thumbnailCredit(v);
   const box=row.getBoundingClientRect?.()||{left:12,right:292,top:12,bottom:60};
   const width=Math.min(280,(root.innerWidth||800)-24),height=300,screenHeight=root.innerHeight||600;
   const rightFits=box.right+12+width<=(root.innerWidth||800),leftFits=box.left>=width+24;
   const left=rightFits?box.right+12:leftFits?box.left-width-12:Math.max(12,(root.innerWidth||800)-width-12);
   const top=rightFits||leftFits?box.top:box.bottom+height+24<=screenHeight?box.bottom+12:box.top-height-12;
   card.style.left=Math.min(left,Math.max(12,(root.innerWidth||800)-width-12))+'px';
   card.style.top=Math.max(12,Math.min(top,screenHeight-height-12))+'px';card.style.maxHeight='calc(100vh - 24px)';card.style.overflow='auto';
   // A hover card must never steal the pointer and repeatedly hide/reappear over a wide row.
   card.style.pointerEvents=pin?'auto':'none';
   if(current===key)return;current=key;const token=++generation;picture.onload=picture.onerror=null;picture.removeAttribute?.('src');picture.hidden=!url;
   status.textContent=url?'Loading reference picture…':'No reference picture available for this mod vehicle.';
   if(url){picture.alt=v.name+' reference picture';picture.referrerPolicy='no-referrer';picture.decoding='async';
    picture.onload=()=>{if(token===generation)status.textContent='';};
    picture.onerror=()=>{if(token===generation){picture.hidden=true;status.textContent='Reference picture unavailable. Selection and spawning still work.';}};
    picture.src=url;
   }
  }
  close.onclick=hide;card.onkeydown=e=>{if(e.key==='Escape')hide();};
  return {show,hide,leave(row){if(!pinned&&currentRow===row)hide();}};
 }
 function mount(container,{select,mode=()=> 'sandbox',loadedPacks=null,availability=()=> 'unknown'}={}){
  const title=el('h3','Vehicle catalog'),search=el('input'),filter=el('input'),filterLabel=el('label'),count=el('p'),list=el('div');
  search.type='search';search.placeholder='Search vehicle, model or category';search.setAttribute('aria-label','Search vehicles');search.maxLength=128;
  search.style.cssText='width:100%;padding:12px;box-sizing:border-box;border:1px solid #638c79;border-radius:10px;background:#0d1618;color:#e6f9ed;font:inherit';
  filter.type='checkbox';filter.checked=true;filterLabel.append(filter,el('span',' Show DLC vehicle models'));
  filterLabel.style.cssText='display:block;margin:12px 0';count.setAttribute('role','status');
  const preview=previewCard(container);
  const open=new Set(),loadedEntries=modEntries({packs:(loadedPacks||[]).map(p=>({...p,enabled:true}))});let mods=loadedEntries;
  const loaded=new Set((loadedPacks||[]).flatMap(p=>p.vehicleModels||[]));
  let availabilityRows=[];
  function refreshAvailability(){for(const update of availabilityRows)update();}
  function render(){
   const q=search.value.trim().toLowerCase();preview.hide();availabilityRows=[];list.replaceChildren();let total=0;
   for(const c of [...ZemaVehicleCatalog.categories,{id:'Installed mods',name:'Installed mod vehicles'}]){
    const entries=(c.id==='Installed mods'?mods:ZemaVehicleCatalog.vehicles.filter(v=>v.category===c.id&&(filter.checked||v.base)))
     .filter(v=>!q||[v.name,v.model,c.name].some(s=>s.toLowerCase().includes(q)))
     .sort((a,b)=>a.name.localeCompare(b.name)||a.model.localeCompare(b.model));
    if(!entries.length&&(c.id!=='Installed mods'||q))continue;
    total+=entries.length;
    const group=el('details'),summary=el('summary',c.name+' · '+entries.length);group.open=!!q||open.has(c.id);
    group.style.cssText='border:1px solid #476256;border-radius:10px;margin:8px 0;padding:12px';summary.style.cssText='cursor:pointer;font-weight:600;padding:4px';group.append(summary);
    group.ontoggle=()=>{refreshAvailability();if(!group.open)preview.hide();if(search.value.trim())return;if(group.open)open.add(c.id);else open.delete(c.id);};
    if(!entries.length)group.append(el('p','No compatible mod vehicles detected. Import a DLC pack or refresh Installed mods.'));
    for(const v of entries){
     const row=el('button'),label=el('span',v.name),detail=el('small'),badge=el('span');row.type='button';
     const pending=v.kind==='mod'&&loadedPacks!==null&&!loaded.has(v.model);
     detail.textContent=v.model+' · '+(v.kind==='train'?'Dedicated train spawner required':v.kind==='mod'?(pending?'Available next launch':'Detected mod · matching pack must be loaded'):v.base?'Base game':'DLC · matching game files required')+(v.kind==='trailer'?' · No driving seat':'');
     row.disabled=v.kind==='train'||(v.kind==='mod'&&pending);
     row.style.cssText='display:block;text-align:left;width:100%;padding:12px;margin-top:6px;border:0;border-radius:8px;background:#243e33;color:#e6f9ed;font:inherit;cursor:pointer';
     detail.style.cssText='display:block;color:#b3c9be;margin-top:3px';if(row.disabled)row.style.opacity='.55';
     row.setAttribute('aria-label','Select '+v.name+' · '+v.model);row.append(label,badge,detail);row.onpointerenter=e=>{if(e?.pointerType!=='touch')preview.show(v,row);};row.onpointerleave=()=>preview.leave(row);row.onfocus=()=>preview.show(v,row);row.onblur=()=>preview.leave(row);
     row.onkeydown=e=>{if(e.key==='Escape')preview.hide();};row.onclick=()=>{if(!row.disabled){select(v.model,v.name);preview.show(v,row,true);}};const baseDetail=detail.textContent,blocked=row.disabled;
     const updateAvailability=()=>{
      if(group.open!==true||blocked)return;
      const state=availability(v.model),missing=state==='missing',unsupported=state==='unsupported';
      row.disabled=blocked||missing||unsupported;
      badge.textContent=missing?(v.kind==='mod'&&loaded.has(v.model)?'×  Installed pack not loaded':'×  Files unavailable'):unsupported?'×  Unsupported model':state==='checking'?'Checking…':'';
      badge.style.cssText='float:right;margin-left:10px;font-size:12px;font-weight:600;color:'+(missing||unsupported?'#ff8e99':'#b3c9be');
      row.style.opacity='1';label.style.color=missing||unsupported?'#b3c9be':'#e6f9ed';row.style.boxShadow=missing||unsupported?'inset 0 0 0 1px #ff8e9926':'';
      detail.textContent=missing?v.model+(v.kind==='mod'&&loaded.has(v.model)?' · Installed files detected; this session did not load the model':' · Required model files are missing or not loaded'):unsupported?v.model+' · Not a vehicle in this game':baseDetail;
      row.setAttribute('aria-label','Select '+v.name+' · '+v.model);row.setAttribute('aria-description',missing?'Files unavailable':unsupported?'Unsupported model':state==='checking'?'Checking game files':'');
     };availabilityRows.push(updateAvailability);updateAvailability();group.append(row);
    }
    list.append(group);
   }
   count.textContent=total+' matching model'+(total===1?'':'s')+'. Hover or focus for a picture. Choose a model, then press Spawn vehicle.';
  }
  search.oninput=filter.onchange=render;
  container.append(title,search,filterLabel,count,list,el('p','DLC entries are reference names, not downloads. Matching assets must be installed. Boats need water; aircraft need open space. New mod changes apply next launch.'));
  render();return {setMods(catalog){mods=[...new Map([...modEntries(catalog),...loadedEntries].map(v=>[v.model,v])).values()];render();},refresh:render,refreshAvailability};
 }
 root.ZemaVehicleUI={mount,modEntries};if(typeof module==='object')module.exports=root.ZemaVehicleUI;
})(globalThis);
