/* Glue 5 0db284d: memory-file pointers use raw hex, never libc's 0x prefix.
 * Explicit factory only; no startup, storage, network or engine writes outside
 * the supplied output string. The upstream u64/32-bit narrowing is preserved.
 */
(function(root){'use strict';
  const encoder=new TextEncoder(),decoder=new TextDecoder();
  const MAX_PATH=4096,MAX_CAPACITY=65536;
  function create(memory){
    if(!memory||!(memory.buffer instanceof ArrayBuffer||
      (typeof SharedArrayBuffer!=='undefined'&&memory.buffer instanceof SharedArrayBuffer)))throw Error('Explicit engine memory required');
    function view(pointer,length){
      if(typeof pointer!=='bigint'||pointer<0n||pointer>BigInt(Number.MAX_SAFE_INTEGER)||
        !Number.isSafeInteger(length)||length<0)throw Error('Memory filename range');
      const at=Number(pointer),buffer=memory.buffer;
      if(at+length>buffer.byteLength)throw Error('Memory filename range');
      return new Uint8Array(buffer,at,length);
    }
    return function memory_file_name(out,capacity,buffer,length,flag,file){
      capacity>>>=0;
      if(capacity===0)return;
      if(capacity>MAX_CAPACITY)throw Error('Memory filename capacity');
      if(out===0n)throw Error('Memory filename null output');
      const target=view(out,capacity);
      let path='';
      if(file!==0n){
        const bytes=[];
        let ended=false;
        for(let i=0;i<MAX_PATH;i++){
          const byte=view(file+BigInt(i),1)[0];
          if(byte===0){ended=true;break;}
          bytes.push(byte);
        }
        if(!ended)throw Error('Memory filename unterminated path');
        path=decoder.decode(Uint8Array.from(bytes));
      }
      const name='memory:$'+BigInt.asUintN(64,buffer).toString(16)+','+
        BigInt.asIntN(32,length).toString()+','+(flag&255)+':'+path;
      // Chromium forbids TextEncoder.encodeInto on SharedArrayBuffer views.
      // Encode into a bounded ordinary buffer, then copy only initialized bytes.
      const temporary=new Uint8Array(Math.min(capacity-1,name.length*3));
      const result=encoder.encodeInto(name,temporary);
      target.set(temporary.subarray(0,result.written));target[result.written]=0;
    };
  }
  const api={create,callback:create};root.ZemaMemoryFilename=api;
  if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
