/* zema engine LAN: shared worker queues and explicit local WebSocket transport.
 * Engine socket layout and DATA framing follow the pinned glue5 interface.
 * No connection, timer, game patch or preference write happens on import. */
(function (root) {
  'use strict';
  const NET = 0x0a4d0000, MAX = 2048, CAP = 256, RECORD = 2064, START = 4096;
  const SIZE = START + 2 * CAP * RECORD, PROTOCOL = 'zema-engine-lan/1', BUILD = '8b0b5899ed';
  const networkError=(message,code='transport')=>Object.assign(Error(message),{code});
  const validIP = ip => Number.isInteger(ip) && ip >= 0 && ip <= 0xffffffff && (ip >>> 16) === 0x0a4d && (ip & 255) !== 0 && (ip & 255) !== 255;
  const broadcast = ip => ip === 0xffffffff || ((ip >>> 16) === 0x0a4d && (ip & 255) === 255);
  function decode(input) {
    const b = input instanceof Uint8Array ? input : new Uint8Array(input);
    if (b.length < 16 || b.length > MAX || b[0] !== 71 || b[1] !== 53 || b[2] !== 1 || b[3] !== 3) throw Error('Invalid engine datagram');
    const v = new DataView(b.buffer, b.byteOffset, b.byteLength);
    const d = {from:v.getUint32(4), srcPort:v.getUint16(8), to:v.getUint32(10), dstPort:v.getUint16(14), data:b.subarray(16)};
    if (!validIP(d.from) || !(validIP(d.to) || broadcast(d.to)) || !d.srcPort || !d.dstPort) throw Error('Invalid virtual address/port');
    return d;
  }
  function encode(from, srcPort, to, dstPort, data) {
    if (!(data instanceof Uint8Array) || data.length > MAX - 16 || !validIP(from) || !(validIP(to)||broadcast(to)) ||
        ![srcPort,dstPort].every(p=>Number.isInteger(p)&&p>0&&p<=65535)) throw Error('Datagram/address limit');
    const b = new Uint8Array(16 + data.length), v = new DataView(b.buffer);
    b.set([71,53,1,3]); v.setUint32(4,from); v.setUint16(8,srcPort);v.setUint32(10,to);v.setUint16(14,dstPort); b.set(data,16);decode(b);return b;
  }
  class SharedLan {
    constructor(buffer) {
      if (buffer === undefined) buffer = new SharedArrayBuffer(SIZE);
      if (!(buffer instanceof SharedArrayBuffer) || buffer.byteLength !== SIZE) throw Error('Shared LAN buffer mismatch');
      this.buffer=buffer;this.words=new Int32Array(buffer);this.bytes=new Uint8Array(buffer);
    }
    lock(fn) {
      const deadline=Date.now()+1000;
      while (Atomics.compareExchange(this.words,0,0,1)!==0) {
        if (Date.now()>deadline) throw Error('Shared LAN lock timeout');
        if (typeof window === 'undefined') Atomics.wait(this.words,0,1,10);
      }
      try {return fn();} finally {Atomics.store(this.words,0,0);Atomics.notify(this.words,0,1);}
    }
    get vip(){return Atomics.load(this.words,3)>>>0;}
    get connected(){return Atomics.load(this.words,2)===1;}
    configure(vip,epoch) {
      if (!validIP(vip) || typeof epoch !== 'string' || !/^[0-9a-f]{16}$/.test(epoch) || /^0+$/.test(epoch)) return false;
      const hi=parseInt(epoch.slice(0,8),16)>>>0,lo=parseInt(epoch.slice(8),16)>>>0;
      return this.lock(()=>{
        if (this.words[1] && (this.vip!==vip || (this.connected && ((this.words[4]>>>0)!==hi || (this.words[5]>>>0)!==lo)))) return false;
        this.words[1]=1;this.words[3]=vip;this.words[4]=hi;this.words[5]=lo;return true;
      });
    }
    connection(value) {
      this.lock(()=>{this.words[2]=value && this.words[1]?1:0;this.words[10]=this.words[11]=0;
        for(let i=0;i<CAP*2;i++)this.words[(START+i*RECORD)/4]=0;
        Atomics.add(this.words,9,1);});Atomics.notify(this.words,9);
    }
    ports(){const result=[];for(let i=0;i<128;i++){const at=16+i*2;if(this.words[at])result.push([this.words[at],this.words[at+1]]);}return result;}
    bind(port) {
      if (!Number.isInteger(port)||port<0||port>65535)return null;
      return this.lock(()=>{
        const ports=this.ports();if(!this.connected||ports.length>=128)return null;
        if(!port){for(let i=0;i<15536;i++){this.words[7]=this.words[7]<50000||this.words[7]===65535?50000:this.words[7]+1;
          if(!ports.some(p=>p[1]===this.words[7])){port=this.words[7];break;}}if(!port)return null;}
        if(!ports.some(p=>p[1]===port)&&new Set(ports.map(p=>p[1])).size>=32)return null;
        const known=new Set(ports.map(p=>p[0]));let handle;
        for(let i=0;i<1023;i++){this.words[6]=this.words[6]%1023+1;if(!known.has(this.words[6])){handle=this.words[6];break;}}
        if(handle===undefined)return null;
        let at=16;while(this.words[at])at+=2;
        this.words[at]=handle;this.words[at+1]=port;return {handle,port};
      });
    }
    port(handle){return this.lock(()=>{const p=this.ports().find(p=>p[0]===handle);return p?p[1]:null;});}
    close(handle){if(!Number.isInteger(handle)||handle<1||handle>1023)return false;const closed=this.lock(()=>{
      let at=16;for(;at<16+128*2;at+=2)if(this.words[at]===handle)break;
      if(at===16+128*2)return false;
      const port=this.words[at+1];this.words[at]=this.words[at+1]=0;
      if(!this.ports().some(p=>p[1]===port))for(let i=0;i<CAP;i++){
        const pos=(START+(CAP+i)*RECORD)/4;if(this.words[pos]&&this.words[pos+3]===port){this.words[pos]=0;this.words[11]--;}
      }
      Atomics.add(this.words,9,1);return true;
    });if(closed)Atomics.notify(this.words,9);return closed;}
    push(queue,frame,port) {
      if(this.words[10+queue]>=CAP)return false;
      for(let i=0;i<CAP;i++){const pos=START+(queue*CAP+i)*RECORD,at=pos/4;if(!this.words[at]){
        this.words[at]=1;this.words[at+1]=++this.words[8];this.words[at+2]=frame.length;this.words[at+3]=port;
        this.bytes.set(frame,pos+16);this.words[10+queue]++;return true;
      }}return false;
    }
    pop(queue,port) {
      let best=-1,serial=0;
      for(let i=0;i<CAP;i++){const at=(START+(queue*CAP+i)*RECORD)/4;
        if(this.words[at]&&(port===undefined||this.words[at+3]===port)&&(best<0||((this.words[at+1]-serial)|0)<0)){best=at;serial=this.words[at+1];}}
      if(best<0)return null;const pos=best*4,len=this.words[best+2];
      const data=this.bytes.slice(pos+16,pos+16+len);this.words[best]=0;this.words[10+queue]--;return data;
    }
    send(srcPort,to,dstPort,data,handle) {
      let frame;try{frame=encode(this.vip,srcPort,to,dstPort,data);}catch{return false;}
      return this.lock(()=>this.connected&&this.ports().some(p=>p[1]===srcPort&&(handle===undefined||p[0]===handle))&&this.push(0,frame,0));
    }
    takeOutgoing(){return this.lock(()=>{
      const full=this.words[10]===CAP,data=this.pop(0);
      if(data&&full){Atomics.add(this.words,9,1);Atomics.notify(this.words,9);}return data;
    });}
    deliver(frame) {
      let d;try{d=decode(frame);}catch{return false;}
      const accepted=this.lock(()=>this.connected&&d.from!==this.vip&&(d.to===this.vip||broadcast(d.to))&&
        this.ports().some(p=>p[1]===d.dstPort)&&this.push(1,new Uint8Array(frame),d.dstPort));
      if(accepted){Atomics.add(this.words,9,1);Atomics.notify(this.words,9);}return accepted;
    }
    receive(port,handle){const data=this.lock(()=>handle!==undefined&&!this.ports().some(p=>p[0]===handle&&p[1]===port)?null:this.pop(1,port));return data?decode(data):null;}
    selected(readers,writers,except) {return this.lock(()=>{
      const ports=this.ports(),known=new Set(ports.map(p=>p[0]));
      if([...readers,...writers,...except].some(h=>!known.has(h)))return null;
      if(!this.connected)return {read:[],write:[],connected:false};
      const queued=new Set();for(let i=0;i<CAP;i++){const at=(START+(CAP+i)*RECORD)/4;if(this.words[at])queued.add(this.words[at+3]);}
      const ready=new Set(ports.filter(p=>queued.has(p[1])).map(p=>p[0]));
      return {read:readers.filter(h=>ready.has(h)),write:this.words[10]<CAP?writers.slice():[],connected:true};
    });}
    hasData(handles) {return this.lock(()=>{
      const ports=new Set(this.ports().filter(p=>handles.includes(p[0])).map(p=>p[1]));
      for(let i=0;i<CAP;i++){const at=(START+(CAP+i)*RECORD)/4;if(this.words[at]&&ports.has(this.words[at+3]))return true;}return false;
    });}
  }
  class Memory {
    constructor(memory){this.memory=memory;}
    view(){return new DataView(this.memory.buffer);}
    offset(p,len){const n=Number(p);if(!Number.isSafeInteger(n)||n<0||!Number.isSafeInteger(len)||len<0||n+len>this.memory.buffer.byteLength)throw Error('Engine memory range');return n;}
    u16(p){return this.view().getUint16(this.offset(p,2),true);}
    u32(p){return this.view().getUint32(this.offset(p,4),true);}
    u64(p){return this.view().getBigUint64(this.offset(p,8),true);}
    set8(p,v){this.view().setUint8(this.offset(p,1),v);}
    set16(p,v){this.view().setUint16(this.offset(p,2),v,true);}
    set32(p,v){this.view().setUint32(this.offset(p,4),v,true);}
    set64(p,v){this.view().setBigUint64(this.offset(p,8),BigInt(v),true);}
    bytes(p,n){return new Uint8Array(this.memory.buffer,this.offset(p,n),n);}
  }
  function engineHooks(memory,lan,originals) {
    const m=new Memory(memory), originalsCall=(name,args)=>{if(typeof originals[name]!=='function')throw Error('Original hook absent: '+name);return originals[name](...args);};
    const at=(p,n)=>BigInt(p)+BigInt(n);
    // Bound diagnostics per worker. No payloads, stat values, or save contents.
    const selectNotes=new Set();let selectCalls=0;
    const selectNote=(key,text)=>{if(selectNotes.has(key)||selectNotes.size>=12)return;selectNotes.add(key);
      try{const channel=new BroadcastChannel('game-log');channel.postMessage('[online] socket select '+text);channel.close();}catch{}};
    // NativeShutdown uses an atomic64 store on the aligned engine handle.
    // Match that read across pthread workers before entering the LAN lock.
    const socketHandle=socket=>{const pos=m.offset(at(socket,8),8);
      return memory.buffer instanceof SharedArrayBuffer&&pos%8===0?Atomics.load(new BigUint64Array(memory.buffer),pos/8):m.u64(at(socket,8));};
    const clear=e=>{if(e!==0n)m.set32(e,0);};
    return {
      networkUp(){Atomics.store(new Int32Array(memory.buffer),m.offset(13346512n,4)/4,1);m.set32(13347088n,2);},
      create_socket(socket,port,protocol,blocking,family){const old=m.u32(13347088n);m.set32(13347088n,2);try{return originalsCall('create_socket',[socket,port,protocol,blocking,family]);}finally{m.set32(13347088n,old);}},
      socket_bind(socket){m.offset(socket,357);const requested=m.u16(at(socket,188)),bound=lan.port(Number(socketHandle(socket)));
        if(bound!==null)return lan.connected&&(!requested||requested===bound)?1:0;const p=lan.bind(requested);if(!p)return 0;
        m.set64(at(socket,8),p.handle);m.set32(at(socket,136),lan.vip);m.set8(at(socket,140),0);m.set16(at(socket,156),p.port);m.set8(at(socket,158),0);m.set8(at(socket,356),m.view().getUint8(m.offset(at(socket,356),1))|2);return 1;},
      socket_close(socket){const handle=Number(socketHandle(socket));originalsCall('socket_close',[socket]);lan.close(handle);},
      socket_send(socket,to,data,len,error){clear(error);len>>>=0;if(len>MAX-16)return 0;
        return lan.send(m.u16(at(socket,156)),m.u32(to),m.u16(at(to,20)),m.bytes(data,len),Number(socketHandle(socket)))?1:0;},
      socket_receive(socket,from,buffer,max,error){clear(error);max>>>=0;m.offset(buffer,max);if(from!==0n)m.offset(from,23);
        const d=lan.receive(m.u16(at(socket,156)),Number(socketHandle(socket)));if(!d)return 0;const len=Math.min(max,d.data.length);m.bytes(buffer,len).set(d.data.subarray(0,len));
        if(from!==0n){m.set32(from,d.from);m.set8(at(from,4),0);m.set16(at(from,20),d.srcPort);m.set8(at(from,22),0);}return len;},
      local_ip_address(ip){if(!lan.connected)return 0;m.offset(ip,5);m.set32(ip,lan.vip);m.set8(at(ip,4),0);return 1;},
      public_ip_address(ip){if(!lan.connected)return 0;m.offset(ip,5);m.set32(ip,lan.vip);m.set8(at(ip,4),0);return 1;},
      profiler_push(profiler,name,flag){if(name===3746537n)m.set32(13347088n,0);return originalsCall('profiler_push',[profiler,name,flag]);},
      socket_select(count,read,write,except,timeout){
        // Return actual selected-bit count. Never call libc select with virtual handles.
        const invalid=0xffffffff,call=++selectCalls,start=performance.now();
        const fail=reason=>{selectNote('reject:'+reason,'rejected: '+reason);return invalid;};
        if(!Number.isInteger(count)||count<0||count>1024)return fail('descriptor limit '+count);
        try{
          const sets=[read,write,except];for(const set of sets)if(set!==0n)m.offset(set,128);
          const handles=set=>{const result=[];if(set===0n)return result;
            for(let fd=0;fd<count;fd++)if((m.u64(at(set,Math.floor(fd/64)*8))>>BigInt(fd%64))&1n)result.push(fd);return result;};
          const readers=handles(read),writers=handles(write),exceptions=handles(except);let end=Infinity;
          if(timeout!==0n){const seconds=m.u64(timeout),micros=m.u32(at(timeout,8));if(seconds>3600n||micros>=1000000)return fail('timeout '+seconds+'/'+micros);end=performance.now()+Number(seconds)*1000+micros/1000;}
          if(call<=3)selectNote('call:'+call,'call '+call+' nfds='+count+' read='+readers.join(',')+' write='+writers.join(',')+' timeout-ms='+(Number.isFinite(end)?Math.max(0,Math.round(end-start)):'infinite'));
          let ready;
          for(;;){
            // Load sequence before deriving readiness to avoid losing a packet/disconnect wakeup.
            const seq=Atomics.load(lan.words,9);ready=lan.selected(readers,writers,exceptions);
            if(!ready)return fail('unknown handle; read='+readers.join(',')+' write='+writers.join(',')+' except='+exceptions.join(','));if(ready.read.length||ready.write.length||!ready.connected)break;
            const remaining=end-performance.now();if(remaining<=0)break;
            if(typeof window!=='undefined')throw Error('Network Select must run in a worker');
            Atomics.wait(lan.words,9,seq,remaining);
          }
          const outputs=[new Uint8Array(128),new Uint8Array(128),new Uint8Array(128)];
          for(const [row,handles]of [ready.read,ready.write].entries())for(const fd of handles)outputs[row][fd>>3]|=1<<(fd&7);
          // Refresh views after waiting so memory growth cannot leave stale output views.
          for(const set of sets)if(set!==0n)m.offset(set,128);
          sets.forEach((set,i)=>{if(set!==0n)m.bytes(set,128).set(outputs[i]);});
          if(call<=3)selectNote('done:'+call,'return '+call+' ready='+(ready.read.length+ready.write.length)+' elapsed-ms='+Math.round(performance.now()-start));
          return ready.read.length+ready.write.length;
        }catch(error){if(error.message==='Network Select must run in a worker')throw error;return fail(String(error.message||error).slice(0,100));}
      }
    };
  }
  function localURL(text) {
    // Validate the raw literal before URL() can normalize numeric shortcuts,
    // credentials, backslashes, escapes or an unexpected path into an allowed URL.
    const match=typeof text==='string'&&/^ws:\/\/((?:[0-9]{1,3}\.){3}[0-9]{1,3})(?::([0-9]{1,5}))?\/engine-lan$/.exec(text);
    const error=()=>Error('Use a LAN or Tailscale ws://IPv4:port/engine-lan endpoint');
    if(!match||match[0]!==text)throw error();
    const octets=match[1].split('.');
    const ipv4=octets.every(x=>Number(x)<=255&&String(Number(x))===x);
    const [a,b]=octets.map(Number);const local=ipv4&&(a===127||a===10||(a===192&&b===168)||(a===172&&b>=16&&b<=31)||(a===169&&b===254)||(a===100&&b>=64&&b<=127));
    if(!local||(match[2]!==undefined&&(!(Number(match[2])>=1&&Number(match[2])<=65535)||String(Number(match[2]))!==match[2])))throw error();
    return new URL(text).href;
  }
  class Client {
    constructor(url,room,name,lan,Socket=root.WebSocket) {
      this.url=localURL(url);this.room=room;this.name=name;this.lan=lan;this.Socket=Socket;this.socket=null;this.resume=null;this.timer=null;this.deadline=null;this.generation=0;this.status=null;this.rejectJoin=null;
    }
    connect(timeoutMs=15000) {
      if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>15000)throw Error('Invalid admission timeout');
      if(this.socket)throw Error('Already connected or connecting');const generation=++this.generation;
      return new Promise((resolve,reject)=>{
        const clock=()=>root.performance.now();
        const socket=new this.Socket(this.url);this.socket=socket;this.rejectJoin=reject;socket.binaryType='arraybuffer';let admitted=false,recoveryAttempted=false,recoveryEpoch=null,lastPing=clock(),lastInbound=lastPing,blocked=null;
        const current=()=>this.socket===socket&&this.generation===generation;
        const fail=error=>{if(current()){const reason=typeof error==='string'?error:error.message,code=typeof error==='string'?'transport':error.code||'protocol';this.disconnect(reason,code);}};
        const connectionFailure=cause=>admitted?'LAN disconnected: '+cause+'. Check the host device and reconnect promptly to the same session.':this.resume?'LAN resume failed: '+cause+'. Check that the same host is running, then retry Reconnect. Your running game is kept.':'Local engine-LAN connection failed: '+cause+'. Check that the host relay is running. An iPhone host must keep ZGTA V open. Verify the shared Wi-Fi or private VPN address.';
        this.deadline=setTimeout(()=>fail(connectionFailure('admission timed out')),timeoutMs);
        socket.onopen=()=>{if(!current())return;const join={type:'join',protocol:PROTOCOL,build:BUILD,room:this.room,name:this.name};if(this.resume)join.resume=this.resume;try{socket.send(JSON.stringify(join));}catch(_){fail(connectionFailure('join send failed'));}};
        socket.onmessage=event=>{if(!current())return;try{
          if(typeof event.data==='string'){
            const message=JSON.parse(event.data);if(message.type==='pong'){if(admitted)lastInbound=clock();return;}
            if(!admitted&&message.protocol===PROTOCOL&&message.build===BUILD){
              if(message.type==='rejoin-unavailable'&&recoveryAttempted)throw networkError('LAN resume failed: your original game address is occupied. Retry when that slot is free, or rejoin with your saved character.','address-in-use');
              if(message.type==='resume-unavailable'&&this.resume&&this.lan.vip&&!recoveryAttempted&&message.recovery==='same-address-v1'&&typeof message.epoch==='string'&&/^[0-9a-f]{16}$/.test(message.epoch)&&!/^0+$/.test(message.epoch)){
                recoveryAttempted=true;recoveryEpoch=message.epoch;socket.send(JSON.stringify({type:'join',protocol:PROTOCOL,build:BUILD,room:this.room,name:this.name,rejoin:{vip:this.lan.vip,epoch:message.epoch}}));return;
              }
            }
            if(admitted||message.type!=='joined'||message.protocol!==PROTOCOL||message.build!==BUILD||typeof message.resume!=='string'||!/^[A-Za-z0-9_-]{32}$/.test(message.resume)||(this.epoch&&(recoveryAttempted?message.epoch!==recoveryEpoch:message.epoch!==this.epoch))||!this.lan.configure(message.vip,message.epoch))throw networkError('LAN session changed; the running game address cannot be changed. Retry the same host or use Rejoin with saved character.','identity-changed');
            clearTimeout(this.deadline);this.deadline=null;this.rejectJoin=null;this.resume=message.resume;this.epoch=message.epoch;admitted=true;lastPing=lastInbound=clock();this.lan.connection(true);this.notify("connected","LAN connected");resolve({vip:message.vip,epoch:message.epoch});
            this.timer=setInterval(()=>{if(!current()||socket.readyState!==1)return;try{
              const now=clock();
              if(now-lastInbound>=30000){fail('LAN relay stopped responding. Reconnect to the same session.');return;}
              if(socket.bufferedAmount>262144){blocked ??= now;if(now-blocked>2000)fail('LAN backpressure');return;}blocked=null;
              for(let i=0;i<64&&socket.bufferedAmount<262144;i++){const frame=this.lan.takeOutgoing();if(!frame)break;socket.send(frame);}
              if(now-lastPing>10000){lastPing=now;socket.send('{"type":"ping"}');}
            }catch{fail('LAN send failed');}},10);
          }else{if(!admitted)throw Error('Datagram before admission');const frame=new Uint8Array(event.data);decode(frame);this.lan.deliver(frame);lastInbound=clock();}
        }catch(error){fail(error);}};
        socket.onerror=()=>fail(connectionFailure('connection interrupted'));
        socket.onclose=()=>{if(current()){const reason=admitted?undefined:this.resume?'LAN resume failed. Check the host and retry Reconnect; your running game is kept.':'Local engine-LAN admission failed';this.disconnect(reason);}};
      });
    }
    notify(state,message){try{if(this.status)this.status(state,message);}catch{}}
    disconnect(reason="LAN disconnected. Reconnect within 20 seconds to keep this session.",code='transport'){
      const socket=this.socket,rejectJoin=this.rejectJoin;this.socket=null;this.rejectJoin=null;++this.generation;
      if(this.timer)clearInterval(this.timer);if(this.deadline)clearTimeout(this.deadline);this.timer=this.deadline=null;
      this.lan.connection(false);if(socket)socket.close();if(rejectJoin)rejectJoin(networkError(reason,code));this.notify("disconnected",reason);
    }
  }
  function instance(module,imports,context,metadata=root.ZemaEngineLanModule) {
    if(!metadata||metadata.format!=='zema-browser-engine-lan-v1'||!context||context.version!==PROTOCOL)throw Error('Engine-LAN module/context missing');
    const lan=new SharedLan(context.buffer);if(!lan.connected)throw Error('Engine-LAN admission required before engine instantiation');
    const result=new WebAssembly.Instance(module,imports), table=result.exports.__indirect_function_table;
    const memory=imports.env && imports.env.memory;
    if(!(memory instanceof WebAssembly.Memory)||!(table instanceof WebAssembly.Table))throw Error('Engine-LAN memory/table boundary mismatch');
    if(metadata.features){if(!root.ZemaBrowserFeatures||!context.features)throw Error('Analog features bridge absent');root.ZemaBrowserFeatures.install(result,memory,context.features,metadata.features);}
    const originals={};for(const h of metadata.hooks){const f=result.exports[h.original_export];if(typeof f!=='function'||f.length!==h.params.length)throw Error('Engine-LAN original ABI mismatch');originals[h.field]=f;}
    const hooks=engineHooks(memory,lan,originals), callbacks={};
    let profile;
    if(metadata.social){
      if(!root.ZemaOnline||!root.ZemaProfileRPC||!context.profile)throw Error('Shared durable profile host absent');
      profile=new root.ZemaProfileRPC.Proxy(context.profile);
      const allocate=result.exports['zema:lan:allocate'],release=result.exports['zema:lan:release'];
      if(typeof allocate!=='function'||typeof release!=='function')throw Error('Engine allocator ABI absent');
      const host={allocate,release,inlineMemberSave:metadata.features?.inline_member_save===true,note:message=>{try{const channel=new BroadcastChannel('game-log');channel.postMessage('[online] '+message);channel.close();}catch(_){}},commit:()=>profile.commit(),transportReady:()=>lan.connected,networkUp:hooks.networkUp,
        interfacesReady:()=>Atomics.load(lan.words,12)===2,
        prepareInterfaces(){
          const state=Atomics.compareExchange(lan.words,12,0,1);
          if(state!==0){const until=Date.now()+5000;while(Atomics.load(lan.words,12)===1&&Date.now()<until)Atomics.wait(lan.words,12,1,100);return Atomics.load(lan.words,12)===2;}
          try{const m=new Memory(memory),base=allocate(1040n);if(base===0n)throw Error('Interface allocation');m.offset(base,1040);
            const profileObject=base,other=base+8n,pt=base+16n,ot=base+528n,roles=BigInt(metadata.social.base);
            m.set64(profileObject,pt);m.set64(other,ot);
            for(let i=0;i<64;i++){m.set64(pt+BigInt(i*8),roles+BigInt(i===0?0:i===1?2:i===3?3:1));m.set64(ot+BigInt(i*8),roles+BigInt(i===0?0:1));}
            for(let offset=88;offset<216;offset+=8)m.set64(15211472n+BigInt(offset),offset===96?profileObject:other);
            Atomics.store(lan.words,12,2);Atomics.notify(lan.words,12);return true;
          }catch{Atomics.store(lan.words,12,3);Atomics.notify(lan.words,12);return false;}
        }};
      Object.assign(hooks,root.ZemaOnline.hooks(memory,originals,profile,host,Memory));
      const m=new Memory(memory);
      metadata.social.entries.forEach((entry,i)=>{if(entry.role!==0&&entry.role!==3)return;
        callbacks['social_'+i]=(...args)=>{let value;
          if(entry.role===0){if(args[2]!==0n)m.set64(args[2],0);value=0x80004002;}
          else{const p=args[1];m.offset(p,33);m.set64(p+8n,profile.id);const text=new TextEncoder().encode(profile.name);m.bytes(p+16n,17).fill(0);m.bytes(p+16n,text.length).set(text);value=0;}
          return entry.results[0]==='i64'?BigInt(value):value;};
      });
    }
    const seenHooks=new Set();
    for(const h of metadata.hooks){if(typeof hooks[h.field]!=='function')throw Error('Socket callback absent');callbacks[h.field]=(...args)=>{if(!seenHooks.has(h.field)){seenHooks.add(h.field);try{const channel=new BroadcastChannel('game-log');channel.postMessage('[online] first callback '+h.field);channel.close();}catch(_){}}try{return hooks[h.field](...args);}catch(error){try{const channel=new BroadcastChannel('game-log');channel.postMessage('[online] '+h.field+' failed: '+String(error.message).slice(0,200));channel.close();}catch(_){}throw error;}};}
    const helper=new WebAssembly.Instance(new WebAssembly.Module(Uint8Array.from(metadata.auxiliary_wasm)),{zema:callbacks});
    for(const h of metadata.hooks)table.set(metadata.table64?BigInt(h.slot):h.slot,helper.exports[h.field]);
    if(metadata.social)metadata.social.entries.forEach((entry,i)=>table.set(metadata.table64?BigInt(metadata.social.base+4+i):metadata.social.base+4+i,helper.exports['social_'+i]));
    if(metadata.deferred_start){const start=result.exports['zema:lan:start'];if(typeof start!=='function')throw Error('Deferred engine start absent');start();}
    return result;
  }
  async function instantiate(bytes,imports,context,metadata=root.ZemaEngineLanModule) {
    const input=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes);
    const digest=Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',input)),b=>b.toString(16).padStart(2,'0')).join('');
    if(!metadata||digest!==metadata.patched_sha256)throw Error('Patched browser engine hash mismatch');
    const module=await WebAssembly.compile(input);return {module,instance:instance(module,imports,context,metadata)};
  }
  async function instantiateStreaming(response,imports,context,metadata=root.ZemaEngineLanModule){const res=await response;if(!res.ok)throw Error('Browser engine unavailable');return instantiate(await res.arrayBuffer(),imports,context,metadata);}
  function requireGameReady(metadata=root.ZemaEngineLanModule){if(!metadata||metadata.online_startup_ready!==true)throw Error('Engine-LAN transport is prepared; online startup/character integration is not ready for game launch');}
  const api={NET,MAX,PROTOCOL,BUILD,decode,encode,SharedLan,Memory,engineHooks,Client,localURL,instance,instantiate,instantiateStreaming,requireGameReady};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ZemaEngineLan=api;
})(globalThis);
