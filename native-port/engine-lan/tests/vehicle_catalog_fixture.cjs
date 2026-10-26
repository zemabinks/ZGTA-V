'use strict';
const a=require('node:assert/strict'),path=require('node:path'),root=process.argv[2];
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.value='';this.textContent='';this.disabled=false;}
 append(...items){this.children.push(...items);}replaceChildren(...items){this.children=[...items];}
 get src(){return this._src;}set src(value){this._src=value;if(this.tag==='img')a.equal(this.crossOrigin,'anonymous','CORS mode must be set before requesting any image under COEP');}
 setAttribute(k,v){this[k]=v;}removeAttribute(k){if(k==='src')delete this._src;else delete this[k];}
}
global.document={createElement:tag=>new Element(tag)};
const C=require(path.join(root,'vehicle-catalog.js')),UI=require(path.join(root,'vehicle-ui.js'));
const walk=e=>[e,...e.children.flatMap(walk)];
let selected=[];const container=new Element('div');
const ui=UI.mount(container,{select:(...v)=>selected.push(v),loadedPacks:[{vehicleModels:['customcar']}]});
const input=walk(container).find(e=>e.type==='search'),filter=walk(container).find(e=>e.type==='checkbox');
const button=model=>walk(container).find(e=>e.tag==='button'&&e['aria-label']?.endsWith(' · '+model));
a.equal(C.vehicles.length,876);a.equal(C.vehicles.filter(v=>v.base).length,298);
a.equal(new Set(C.vehicles.map(v=>v.model)).size,C.vehicles.length);
a.equal(walk(container).filter(e=>e.tag==='details').length,24+1);
a.ok(walk(container).filter(e=>e.tag==='details').every(e=>!e.open));a.equal(selected.length,0);
const preview=walk(container).find(e=>e['aria-label']==='Vehicle preview'),picture=walk(preview).find(e=>e.tag==='img'),notice=walk(preview).find(e=>e.role==='status');
a.ok(preview.hidden);a.equal(picture.src,undefined,'No eager image downloads');a.equal(picture.crossOrigin,'anonymous');
a.equal(C.thumbnailURL({model:'customcar',kind:'mod'}),null);a.equal(C.thumbnailURL({model:'../secret',kind:'vehicle'}),null);
a.equal(C.thumbnailURL({model:'casup',kind:'mod'}),'/zema-lab/mod-vehicle-casup.png');
a.equal(C.thumbnailURL({model:'casup',kind:'vehicle'}),null);
a.match(C.thumbnailCredit({model:'casup',kind:'mod'}),/original Supra mod page/);
a.equal(C.thumbnailURL({model:'constructor',kind:'mod'}),null);
a.equal(C.thumbnailURL(C.vehicles.find(v=>v.model==='buzzard')),'https://docs-backend.fivem.net/vehicles/buzzard.webp');
button('sultan').onfocus();a.equal(preview.hidden,false);a.match(picture.src,/\/sultan\.webp$/);a.equal(selected.length,0,'Preview must not queue a selection or spawn');
const staleLoad=picture.onload;button('buzzard').onpointerenter({pointerType:'mouse'});a.match(picture.src,/\/buzzard\.webp$/);
button('sultan').onblur();a.equal(preview.hidden,false,'Old row blur must not hide the new row preview');
staleLoad();a.match(notice.textContent,/Loading/,'Ignore the previous model completion');picture.onerror();a.ok(picture.hidden);a.match(notice.textContent,/unavailable/);
button('buzzard').onpointerleave();a.ok(preview.hidden);a.equal(picture.src,undefined,'Cancel image load on leaving');
input.value='BMX';input.oninput();a.ok(button('bmx'));a.equal(walk(container).filter(e=>e.tag==='details').length,1);
a.ok(walk(container).find(e=>e.tag==='details').open);button('bmx').onclick();a.deepEqual(selected,[['bmx','BMX']]);
input.value='helicopters';input.oninput();a.ok(button('buzzard'));a.ok(!button('sultan'));
input.value='';filter.checked=false;filter.onchange();a.ok(button('sultan'));a.ok(!button('oppressor2'));
a.ok(button('freight').disabled);button('freight').onclick();a.equal(selected.length,1);
ui.setMods({packs:[{enabled:true,vehicleModels:['customcar','customcar','nextcar','bad<script>']},{enabled:false,vehicleModels:['disabledcar']},{enabled:true,models:['pedonly','textureonly']}]});
a.ok(button('customcar'));a.equal(button('customcar').disabled,false);a.equal(button('nextcar').disabled,true);a.ok(!button('disabledcar'));a.ok(!button('pedonly'));a.ok(!button('bad<script>'));
button('nextcar').onclick();a.equal(selected.length,1);button('customcar').onclick();a.equal(selected.length,2);a.equal(picture.src,undefined);a.match(notice.textContent,/No reference picture/);a.ok(!preview.hidden);walk(preview).find(e=>e.tag==='button').onclick();a.ok(preview.hidden);
// A mod overriding an official model must never inherit the official picture.
ui.setMods({packs:[{enabled:true,vehicleModels:['sultan']}]});
ui.setMods({packs:[{enabled:true,vehicleModels:['sultan','casup']}]});
const beforePreview=selected.length;button('casup').onfocus();
a.equal(picture.src,'/zema-lab/mod-vehicle-casup.png');a.equal(selected.length,beforePreview);
a.ok(walk(preview).some(e=>e.textContent==='Image supplied from the original Supra mod page.'));
picture.onload();a.equal(notice.textContent,'');button('casup').onblur();a.ok(preview.hidden);
const sultans=walk(container).filter(e=>e.tag==='button'&&e['aria-label']?.endsWith(' · sultan'));
a.equal(sultans.length,2);sultans[0].onfocus();a.match(picture.src,/\/sultan\.webp$/);sultans[1].onfocus();a.equal(picture.src,undefined);a.match(notice.textContent,/No reference picture/);
sultans[1].onblur();a.ok(preview.hidden);
button('bmx').onclick();a.ok(!preview.hidden);button('bmx').onblur();button('bmx').onpointerleave();a.ok(!preview.hidden,'Pinned touch/click preview survives leaving its row');
const bicycles=walk(container).find(e=>e.tag==='details'&&walk(e).includes(button('bmx')));
bicycles.open=false;bicycles.ontoggle();a.ok(preview.hidden,'Collapsing a category dismisses the preview');
input.value='bmx';input.oninput();button('bmx').onclick();const searchGroup=walk(container).find(e=>e.tag==='details');searchGroup.open=false;searchGroup.ontoggle();a.ok(preview.hidden,'Search does not keep a collapsed category preview pinned');input.value='';input.oninput();
ui.setMods({packs:[]});a.ok(button('customcar'),'Keep the running snapshot after next-launch removal');a.ok(!button('nextcar'));
const lan=new Element('div');UI.mount(lan,{mode:()=> 'lan',select:()=>a.fail('LAN imported mod selected'),loadedPacks:[{vehicleModels:['customcar']}]}).setMods({packs:[{enabled:true,vehicleModels:['customcar']}]});
const mod=walk(lan).find(e=>e['aria-label']==='Select customcar · customcar');a.ok(mod.disabled);mod.onclick();
console.log('PASS full catalog, category/search selection, special trains, installed vehicle-only discovery, immutable loaded-pack and LAN boundaries');

let state='checking';const marked=new Element('div');const markedUI=UI.mount(marked,{select:()=>a.fail('missing model selected'),availability:()=>state});
const markedSearch=walk(marked).find(e=>e.type==='search');markedSearch.value='oppressor2';markedSearch.oninput();
const markedRow=walk(marked).find(e=>e.tag==='button'&&e['aria-label']?.endsWith(' · oppressor2'));a.ok(markedRow);a.equal(markedRow.disabled,false);
state='missing';markedUI.refreshAvailability();a.equal(markedRow.disabled,true);a.ok(walk(markedRow).some(e=>e.textContent==='×  Files unavailable'));markedRow.onclick();
state='unknown';markedUI.refreshAvailability();a.equal(markedRow.disabled,false,'unknown is not missing');
a.equal(walk(marked).find(e=>e===markedRow),markedRow,'availability never rebuilds or collapses rows');
