'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const listeners=new Map(),timers=new Map();let serial=0,releases=0;
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.hidden=false;this.disabled=false;this.attributes={};this.listeners={};}
 append(...children){this.children.push(...children);}setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,f){this.listeners[k]=f;}
 remove(){this.removed=true;}focus(){document.activeElement=this;}
 querySelectorAll(){return walk(this).filter(n=>['button','summary'].includes(n.tag));}
}
const walk=n=>[n,...n.children.flatMap(walk)],document={body:new Element('body'),createElement:t=>new Element(t),activeElement:null,exitPointerLock(){},addEventListener(k,f){listeners.set(k,f);},removeEventListener(k,f){if(listeners.get(k)===f)listeners.delete(k);},dispatchEvent:e=>listeners.get(e.type)?.(e)};
const context={document,CustomEvent:class{constructor(type,value){this.type=type;this.detail=value.detail;}},setTimeout:f=>(timers.set(++serial,f),serial),clearTimeout:id=>timers.delete(id),ZemaGameInput:{release(){releases++;}},module:{exports:{}}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
const ui=context.module.exports.mount({room:'<test-room>',connection:'LAN',relay:'ws://127.0.0.1:47540/engine-lan',lobbyRole:'join'}),button=text=>walk(ui.root).find(n=>n.tag==='button'&&n.textContent===text);
assert.equal(ui.detail.textContent,'Room: <test-room>\nHost: ws://127.0.0.1:47540/engine-lan');assert.equal(timers.size,1);
ui.show();assert.equal(context.ZemaInputSuspended,true);ui.show();ui.hide();assert.equal(context.ZemaInputSuspended,false,'Repeated opening must not steal input ownership');assert.equal(releases,1);
context.ZemaInputSuspended=true;ui.show();ui.hide();assert.equal(context.ZemaInputSuspended,true,'Pre-existing input suspension belongs to its owner');context.ZemaInputSuspended=false;
let recoveredRestarts=0;ui.reconnect.onclick=()=>recoveredRestarts++;ui.render('recovered');ui.show();button('Reconnect').onclick();ui.hide();assert.equal(recoveredRestarts,1);assert.equal(context.ZemaInputSuspended,false,'Reconnect while already open must preserve input ownership');ui.render('restarting');assert(button('Reconnect').disabled);
ui.show();document.dispatchEvent(new context.CustomEvent('zema-ui-panel-open',{detail:'mod-manager'}));assert.equal(context.ZemaInputSuspended,false);assert.equal(ui.root.children.find(n=>n.tag==='section').hidden,true);
let resumes=0;ui.reconnect.onclick=()=>resumes++;ui.render('disconnected');button('Reconnect').onclick();assert.equal(resumes,1);assert.equal(timers.size,0);
ui.render('connected');assert.equal(timers.size,1);const dismiss=walk(ui.root).find(n=>n.attributes['aria-label']==='Dismiss connection notification');dismiss.onclick();assert.equal(walk(ui.root).find(n=>n.className==='connection-notice').hidden,true);
ui.render('profile-error');button('Details').onclick();assert.equal(walk(ui.root).find(n=>n.tag==='details').open,true);
ui.destroy();assert.equal(context.ZemaInputSuspended,false);assert.equal(timers.size,0);assert.equal(listeners.size,0);assert.equal(ui.root.removed,true);ui.show();assert.equal(context.ZemaInputSuspended,false);
console.log('PASS connection panel: input ownership/repeated-open/other-panel, safe text, explicit action, notification timer and teardown');
