'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
if(!globalThis.crypto)globalThis.crypto=require('node:crypto').webcrypto;
const S=require('../browser-saves.js');
const bytes=new Uint8Array([0,1,2,255,0,128]);
async function browser(mode,path='/userdata/Documents/Rockstar Games/GTA V/Profiles/12345678/SGTA50000'){
 return S.archive(mode,[{path,data:bytes,mtime:123}]);
}
async function main(){
 const story=await S.nativeArchive('story',await browser('story'));
 const sandbox=await S.nativeArchive('sandbox',await browser('sandbox'));
 const phone={schema:1,created:story.created,entries:[...story.entries,...sandbox.entries]};
 for(const mode of ['story','sandbox']){
  const entries=await S.validate(phone,mode);
  assert.equal(entries.length,1);assert.deepEqual(entries[0].data,bytes);
  assert.equal(entries[0].path,'/userdata/Documents/Rockstar Games/GTA V/Profiles/12345678/SGTA50000');
 }
 assert(Math.abs(story.created+978307200-Date.now()/1000)<5,'Swift Date epoch');
 assert.equal(story.entries[0].path.slice(0,9),'userdata/');
 assert.equal(sandbox.entries[0].path.slice(0,8),'sandbox/');
 await assert.rejects(S.validate(sandbox,'story'),/no Story files/);
 await assert.rejects(S.validate(await browser('story'),'sandbox'));
 for(const path of ['userdata/Documents/../outside','userdata/Documents/a\\b','userdata/Documents/settings.xml','userdata/Documents/a\u0085b','/userdata/Documents/a','sandbox/../userdata/Documents/a','userdata/Documents/','elsewhere/Documents/a']){
  const invalid=structuredClone(phone);invalid.entries[0].path=path;
  await assert.rejects(S.validate(invalid,'story'));
 }
 // Even an unselected profile must pass checksum/path validation.
 const corrupt=structuredClone(phone);corrupt.entries[1].sha256='0'.repeat(64);
 await assert.rejects(S.validate(corrupt,'story'),/checksum/);
 const duplicate=structuredClone(phone);duplicate.entries.push(duplicate.entries[0]);
 await assert.rejects(S.validate(duplicate,'story'),/duplicate/);
 for(const value of [null,{},[],{...phone,schema:2},{...phone,created:'bad'},{...phone,entries:[null]},{...phone,entries:[]}])await assert.rejects(S.validate(value,'story'));
 const ambiguous=await S.archive('story',[{path:'/userdata/Documents/A',data:bytes},{path:'/userdata/Documents/a',data:bytes}]);
 await assert.rejects(S.nativeArchive('story',ambiguous),/differ only/);
 const unicode=await S.archive('story',[{path:'/userdata/Documents/é',data:bytes},{path:'/userdata/Documents/e\u0301',data:bytes}]);
 await assert.rejects(S.nativeArchive('story',unicode),/differ only/);
 for(const [first,second]of [['σ','ς'],['ss','ß'],['ff','ﬀ'],['A','a'],['é','e\u0301']]){
  const archive=await S.archive('story',[{path:'/userdata/Documents/'+first,data:bytes},{path:'/userdata/Documents/'+second,data:bytes}]);
  assert.equal((await S.validate(archive,'story')).length,2,'Browser-only case-sensitive paths remain valid');
  await assert.rejects(S.nativeArchive('story',archive),/differ only/);
  const phoneAliases={schema:1,created:0,entries:archive.entries.map(e=>({...e,path:e.path.slice(1)}))};
  await assert.rejects(S.validate(phoneAliases,'story'),/duplicate/,'Native-input aliases must reject before profile selection/writes');
 }
 await assert.rejects(S.nativeArchive('story',await browser('story','/userdata/Documents/'+'é'.repeat(600))),/too long/);
 const megabyte=new Uint8Array(1024*1024).fill(255),big=await S.archive('story',[{path:'/userdata/Documents/big',data:megabyte}]);
 assert.deepEqual((await S.validate(big,'story'))[0].data,megabyte,'large valid base64 must not exhaust the regex stack');
 for(const data of ['A','A===','AA=A','AAAA=','AAAA====','AA!A','====']){
  const invalid=structuredClone(phone);invalid.entries[0].data=data;await assert.rejects(S.validate(invalid,'story'),/Invalid save/);
 }
 const large={schema:1,created:0,entries:[{path:'userdata/Documents/large',data:Buffer.alloc(16*1024*1024+1).toString('base64'),sha256:'0'.repeat(64)}]};
 await assert.rejects(S.validate(large,'story'),/too large|Invalid save/);
 if(process.argv[2]==='emit')fs.writeFileSync(process.argv[3],JSON.stringify(phone));
 if(process.argv[2]==='verify-native'){
  const native=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
  for(const mode of ['story','sandbox']){
   const entries=await S.validate(native,mode);assert.equal(entries.length,1);assert.deepEqual(entries[0].data,bytes);
  }
 }
 console.log('PASS: native/browser binary save interoperability, profile isolation, Swift Date epoch, whole-archive validation, checksum/size/path/duplicate rejection.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
