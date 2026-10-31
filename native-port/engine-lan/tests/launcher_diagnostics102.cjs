'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),P=require('../browser-performance.js');
const identity={build:102,browser_revision:'102',source_revision:'a'.repeat(40),stage_manifest_sha256:'b'.repeat(64),module_metadata_sha256:'c'.repeat(64)};
const dirty={...identity,path:'/private/owner/location',url:'http://name:secret@example.test/'};
assert.deepEqual(P.hostIdentity(dirty),identity,'Only bounded build/hash fields survive');
for(const bad of [null,[],{}, {...identity,source_revision:'/private/path'}, {...identity,build:true}, {...identity,browser_revision:'../102'}, {...identity,module_metadata_sha256:'credential'}, {...identity,build:101}])assert.equal(P.hostIdentity(bad),null);
const source=fs.readFileSync(path.join(root,'launcher.js'),'utf8'),start=source.indexOf('download.onclick='),end=source.indexOf('\nconst preferences=',start);assert(start>0&&end>start);
async function run(value,unavailable=false){
 const blobs=[],downloads=[],events=[],download={disabled:false};
 const context={download,S:{normalize:s=>({...s})},settings:{preset:'performance'},crossOriginIsolated:true,navigator:{gpu:{},deviceMemory:8,hardwareConcurrency:8},
 ZemaModsUI:{api:async(route,body)=>{assert.equal(route,'launcher/status');assert.equal(JSON.stringify(body),'{}');if(unavailable)throw Error('Offline');return {identity:value};}},ZemaBrowserPerformance:P,
 URL:{createObjectURL:blob=>{blobs.push(blob);return 'blob:fixture';},revokeObjectURL:url=>events.push(url)},Blob,JSON,
 element:tag=>{assert.equal(tag,'a');const link={click:()=>downloads.push(link)};return link;},setTimeout:fn=>fn()};
 vm.runInNewContext(source.slice(start,end),context);await download.onclick();
 assert.equal(download.disabled,false);assert.equal(downloads.length,1);assert.equal(downloads[0].download,'zema-browser-launcher.json');assert.deepEqual(events,['blob:fixture']);
 return JSON.parse(await blobs[0].text());
}
(async()=>{const report=await run(dirty);assert.equal(report.format,'zema-browser-launch-diagnostic-v1');assert.deepEqual(report.hostIdentity,identity);assert.equal(JSON.stringify(report).includes('secret'),false);assert.equal(JSON.stringify(report).includes('/private/'),false);assert.equal((await run({})).hostIdentity,null);assert.equal((await run(null,true)).hostIdentity,null);console.log('PASS actual launcher diagnostic handler records bounded host identity, strips extras, preserves download on unavailable/legacy host.');})().catch(error=>{console.error(error);process.exitCode=1;});
