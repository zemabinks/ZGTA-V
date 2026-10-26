'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const api=require('../browser.js'),rows=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
class NoSocket { constructor(){throw Error('Endpoint validation must not open a connection');} }
for(const row of rows){
  if(row.valid){
    const client=new api.Client(row.url,'fixture','Fixture',new api.SharedLan(),NoSocket);
    assert.equal(client.socket,null);assert.equal(client.resume,null);
    const parsed=new URL(api.localURL(row.url));
    assert.equal(parsed.hostname,new URL(row.url).hostname);
    assert.equal(parsed.pathname,'/engine-lan');
  }else{
    assert.throws(()=>api.localURL(row.url),undefined,row.url);
    assert.throws(()=>new api.Client(row.url,'fixture','Fixture',new api.SharedLan(),NoSocket),undefined,row.url);
  }
}
console.log('BROWSER_LAN_TAILSCALE_ENDPOINT_BOUNDARIES_NO_CONNECT_PASS '+rows.length);
