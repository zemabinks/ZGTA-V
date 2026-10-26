'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const helper=require(path.join(process.argv[2],'script_bank.js'));
const aux=Uint8Array.from(JSON.parse(fs.readFileSync(process.argv[3],'utf8')));
let status=2,mode='normal',calls=[],notes=[],typed;
const other=helper.callbacks(()=>7,()=>2);
const callbacks=helper.callbacks((bank,network,players)=>{
 calls.push(['request',bank,network,players]);
 assert.equal(other.bank_loading_status(128n,bank),2,'Worker scopes must remain independent');
 if(mode==='throw-request')throw Error('request failure');
 if(mode==='nested'&&bank===10){
  assert.equal(typed.script_bank_request(11,network,players),0);
  assert.equal(typed.bank_loading_status(128n,bank),0,'Inner request must not clear outer depth');
 }
 return typed.bank_loading_status(128n,bank);
},(slot,bank)=>{
 calls.push(['status',slot,bank]);
 if(mode==='throw-status')throw Error('status failure');
 return status;
},bank=>notes.push(bank));
typed=new WebAssembly.Instance(new WebAssembly.Module(aux),{zema:callbacks}).exports;
assert.equal(typed.bank_loading_status(128n,4328),2,'Failed banks outside script requests stay failed');
assert.deepEqual(notes,[]);
assert.equal(typed.script_bank_request(4328,1,8),0);
assert.deepEqual(notes,[4328]);
assert.deepEqual(calls.slice(-2),[['request',4328,1,8],['status',128n,4328]]);
assert.equal(typed.bank_loading_status(128n,4328),2);
for(const value of [0,1,3,7]){status=value;assert.equal(typed.script_bank_request(4328,0,1),value);assert.equal(typed.bank_loading_status(128n,4328),value);}
status=2;mode='nested';assert.equal(typed.script_bank_request(10,1,8),0);assert.equal(typed.bank_loading_status(128n,10),2);
mode='throw-request';assert.throws(()=>typed.script_bank_request(4328,0,1),/request failure/);mode='normal';assert.equal(typed.bank_loading_status(128n,4328),2);
mode='throw-status';assert.throws(()=>typed.script_bank_request(4328,0,1),/status failure/);mode='normal';assert.equal(typed.bank_loading_status(128n,4328),2);
const originalReturn=helper.callbacks(()=>37,()=>2);assert.equal(originalReturn.script_bank_request(1,0,0),37,'Request return must remain original');
assert.deepEqual(notes,[4328],'Only the first actual conversion emits a diagnostic');
let guarded,observerCalls=0;guarded=helper.callbacks(()=>guarded.bank_loading_status(128n,99),()=>2,bank=>{observerCalls++;assert.equal(bank,99);throw Error('observer failure');});
assert.equal(guarded.script_bank_request(99,0,1),0);assert.equal(guarded.script_bank_request(100,0,1),0);assert.equal(observerCalls,1);assert.equal(guarded.bank_loading_status(128n,99),2);
assert.throws(()=>helper.callbacks(null,()=>0),/originals/);
assert.throws(()=>helper.callbacks(()=>0,()=>0,3),/observer/);
assert.throws(()=>typed.bank_loading_status(128,4328),TypeError,'WASM i64 ABI requires BigInt');
console.log(JSON.stringify({result:'SCRIPT_BANK_SCOPED_FAILURE_TYPED_PASS',gtaInstantiated:false,gameplayVerified:false}));
