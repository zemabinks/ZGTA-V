/* Local entry/character callbacks, adapted from the pinned glue5 interfaces.
 * No import-time activity. Host must provide durable storage and typed tables.
 * A shared profile proxy keeps production pthreads on one durable owner.
 */
(function(root){'use strict';
  const MAX=8*1024*1024,FILE=1048576,encoder=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true});
  const MAGIC=Uint8Array.from([90,69,77,65,80,70,49,0]);
  function crc(bytes){let c=0xffffffff;for(const byte of bytes){c^=byte;for(let i=0;i<8;i++)c=(c>>>1)^(0xedb88320&-(c&1));}return (~c)>>>0;}
  function validKey(k){
    if(typeof k!=='string'||k.length>512||!/^[\x00-\x7f]*$/.test(k))return false;
    if(k.startsWith('f:'))return k.length>2&&k.slice(2).split('/').every(s=>s&&s!=='.'&&s!=='..'&&/^[A-Za-z0-9._ -]+$/.test(s));
    if(/^h[0-9a-f]{8}$/.test(k))return true;
    const p=/^p(-1|0|[1-9]\d*):(0|[1-9]\d*)$/.exec(k);return !!p&&Number(p[1])<32&&Number(p[2])<=1000000;
  }
  class Profile {
    constructor(id,name){if(!Number.isInteger(id)||id<65536||id>2147483647||typeof name!=='string'||!name.trim()||name.length>16||!/^[\x20-\x7e]+$/.test(name))throw Error('Profile identity');
      this.id=id;this.name=name;this.values=new Map();this.size=0;this.revision=0;}
    rename(name){if(typeof name!=='string'||!name.trim()||name.length>16||!/^[\x20-\x7e]+$/.test(name))return false;
      if(this.name!==name){this.name=name;this.revision++;}return true;}
    get(key){const v=this.values.get(key);return v===undefined?null:v.slice();}
    put(key,value){if(!validKey(key)||!(value instanceof Uint8Array)||value.length>FILE||(!key.startsWith('f:')&&value.length!==8))return false;
      const old=this.values.get(key);if(old&&old.length===value.length&&old.every((b,i)=>b===value[i]))return true;
      if(!old&&this.values.size>=32768)return false;
      const size=this.size-(old?old.length:0)+value.length+(old?0:key.length+6);if(size>MAX)return false;
      this.values.set(key,value.slice());this.size=size;this.revision++;return true;}
    stat(key){const v=this.values.get(key);return v&&v.length===8?new DataView(v.buffer,v.byteOffset,8).getBigUint64(0,true):0n;}
    setStat(key,bits){const b=new Uint8Array(8);new DataView(b.buffer).setBigUint64(0,BigInt.asUintN(64,bits),true);return this.put(key,b);}
    deleteSlot(slot){if(!Number.isInteger(slot)||slot< -1||slot>=32)return;for(const [key,v] of this.values)if(key.startsWith('p'+slot+':')){this.values.delete(key);this.size-=key.length+v.length+6;this.revision++;}}
    encode(){const bytes=new Uint8Array(20+this.name.length+this.size),view=new DataView(bytes.buffer);bytes.set(MAGIC);view.setUint32(8,this.id,true);view.setUint16(12,this.name.length,true);view.setUint16(14,this.values.size,true);bytes.set(encoder.encode(this.name),16);let at=16+this.name.length;
      for(const [key,v] of [...this.values].sort((a,b)=>a[0]<b[0]?-1:a[0]>b[0]?1:0)){view.setUint16(at,key.length,true);view.setUint32(at+2,v.length,true);at+=6;bytes.set(encoder.encode(key),at);at+=key.length;bytes.set(v,at);at+=v.length;}
      view.setUint32(at,crc(bytes.subarray(0,at)),true);return bytes;}
    static decode(input){const b=new Uint8Array(input);if(b.length<21||b.length>MAX+36||!MAGIC.every((x,i)=>b[i]===x))throw Error('Profile header');const v=new DataView(b.buffer,b.byteOffset,b.byteLength),end=b.length-4;
      if(crc(b.subarray(0,end))!==v.getUint32(end,true))throw Error('Profile checksum');const n=v.getUint16(12,true),count=v.getUint16(14,true);let at=16+n;if(at>end||count>32768)throw Error('Profile bounds');const p=new Profile(v.getUint32(8,true),decoder.decode(b.subarray(16,at)));let previous='';
      for(let i=0;i<count;i++){if(at+6>end)throw Error('Profile record');const kl=v.getUint16(at,true),vl=v.getUint32(at+2,true);at+=6;if(at+kl+vl>end)throw Error('Profile bounds');const key=decoder.decode(b.subarray(at,at+kl));at+=kl;if(key<=previous||!p.put(key,b.subarray(at,at+vl)))throw Error('Profile key/value');previous=key;at+=vl;}
      if(at!==end)throw Error('Profile trailing bytes');p.revision=0;return p;}
  }
  function hooks(memory,originals,profile,host,Memory){
    if((!(profile instanceof Profile)&&profile?.protocol!=='zema-profile-rpc/1')||!host||['commit','prepareInterfaces','allocate','release','networkUp','transportReady'].some(k=>typeof host[k]!=='function'))throw Error('Explicit typed/persistent online host required');
    const m=new Memory(memory),at=(p,n)=>BigInt(p)+BigInt(n),call=(f,args)=>{if(typeof originals[f]!=='function')throw Error('Online original absent: '+f);return originals[f](...args);};
    const str=p=>{if(p===0n)throw Error('Null engine string');const bytes=[];for(let i=0;i<513;i++){const b=m.bytes(at(p,i),1)[0];if(!b)return decoder.decode(Uint8Array.from(bytes));bytes.push(b);}throw Error('Engine string too long');};
    const writeStr=(p,text,n)=>{n>>>=0;if(!n)return;const target=m.bytes(p,n),bytes=encoder.encode(text);const length=Math.min(bytes.length,n-1);target.set(bytes.subarray(0,length));target[length]=0;};
    const finish=(p,c,r=0)=>{if(p!==0n){m.offset(p,8);m.set32(at(p,4),r);m.set32(p,c);}};
    const slot=name=>{const hit=/(\d+)\.save$/.exec(name);return hit&&Number(hit[1])<32?Number(hit[1]):-1;};
    let interfaces=false,newSlots=0,inStats=0,inMemberSave=0,inSaveWorker=0,missing=false,missMap='';const misses=new Map();
    const interfacesReady=()=>interfaces||(typeof host.interfacesReady==='function'&&host.interfacesReady());
    const slotMask=()=>typeof profile.newSlotMask==='function'?profile.newSlotMask():newSlots;
    const markSlot=(s,value)=>{if(typeof profile.markNewSlot==='function')profile.markNewSlot(s,value);else if(value)newSlots|=1<<s;else newSlots&=~(1<<s);};
    const scope=(field,args)=>{const old=m.u64(13346752n);m.set64(13346752n,0);try{return call(field,args);}finally{m.set64(13346752n,old);}};
    const hash=h=>'h'+(h>>>0).toString(16).padStart(8,'0'),packed=(n,s)=>'p'+(s|0)+':'+(n>>>0),mask=b=>(b>>>0)>=64?0xffffffffffffffffn:(1n<<BigInt(b>>>0))-1n;
    const engineOr=(name,args,fallback)=>{missing=false;const r=call(name,args);return missing?fallback():r;};
    const result=(out,value)=>{m.set32(out,Number(BigInt.asUintN(32,value)));return 1;};
    // Bounded local diagnostics: never include stat values or save contents.
    const saveNotes=new Set();
    const saveNote=message=>{if(saveNotes.has(message)||saveNotes.size>=32)return;saveNotes.add(message);try{host.note?.('LAN save: '+message);}catch{}};
    const saveGuards=()=>{try{return [25461592n,25461332n,25461608n,25461220n,25461221n].map(p=>m.bytes(p,1)[0]).join(',');}catch{return 'unavailable';}};
    const out={
      rl_gamer_handle(p){m.offset(p,10);m.set64(p,profile.id);m.set8(at(p,8),3);m.set8(at(p,9),0);return 1;},
      rl_offline_name(p){writeStr(p,profile.name,17);return 1;},rl_pc_initialized(){return 0;},
      live_manager_init(mode){if(!interfaces){if(host.prepareInterfaces()!==true)throw Error('Checked Social Club interface tables are not prepared');interfaces=true;}call('live_manager_init',[mode]);out.populate_store_data();},
      live_manager_update(mode){if(!interfacesReady())throw Error('Online interfaces absent');host.networkUp();call('live_manager_update',[mode]);host.networkUp();},
      bail_on_multiplayer(reason,context){if((reason>>>0)!==2||(context>>>0)!==0x3001)call('bail_on_multiplayer',[reason,context]);},
      presence_online(index){return index===0?1:call('presence_online',[index]);},
      ros_privilege(_c,id){id>>>=0;return id<32?((0x6fef7f>>>id)&1):0;},ros_privilege_end_date(){return 0;},
      profile_setting_int(p,id){return (id>>>0)===903?1:call('profile_setting_int',[p,id]);},
      can_access_network_features(_a,p){if(p!==0n)m.set32(p,0);return 1;},
      can_enter_multiplayer(p){if(!interfacesReady()||!host.transportReady())return 0;return call('can_enter_multiplayer',[p])||((m.bytes(29309000n,1)[0]&1)&&!m.bytes(29309001n,1)[0]&&!m.u32(23275800n)&&!m.u32(at(p,99916)))?1:0;},
      populate_store_data(){m.offset(29308996n,7);m.set32(29308996n,2);m.set16(29309000n,1);m.set8(29309002n,0);},
      photo_to_jpeg(_out,size){m.set32(size,0);return 0;},
      script_program_loaded(p,rsc){const r=call('script_program_loaded',[p,rsc]);if(str(m.u64(at(p,96)))!=='MainTransition')return r;if(host.note)host.note('MainTransition loaded');const pages=m.u64(at(p,16)),size=m.u32(at(p,28));
        for(const [offset,old,next] of [[2510677,[44,1,3,171],[113,0,0,0]],[2504003,[115,100,124,222,18,102,44,8,3,121],[44,0,0,249,0,0,0,0,0,0]]]){
          if(offset+old.length>size||offset%16384+old.length>16384){if(host.note)host.note('MainTransition patch '+offset+' out of bounds');continue;}const base=m.u64(at(pages,Math.floor(offset/16384)*8));if(base===0n)continue;const code=m.bytes(at(base,offset%16384),old.length);if(old.every((b,i)=>code[i]===b)){code.set(next);if(host.note)host.note('MainTransition patch '+offset+' applied');}else if(host.note)host.note('MainTransition patch '+offset+' mismatch: '+Array.from(code).join(','));}
        return r;},
      xml_bool_attribute(e,n,d){return n===1596083n?0:call('xml_bool_attribute',[e,n,d]);},
      stats_init(mode){scope('stats_init',[mode]);},stats_queue_save(){saveNote('queue requested; guards='+saveGuards());scope('stats_queue_save',[]);},stats_queue_load(){return scope('stats_queue_load',[]);},stats_save(...args){const r=scope('stats_save',args);saveNote('save requested; result='+r+' guards='+saveGuards());return r;},stats_load(kind){return scope('stats_load',[kind]);},
      stats_update(){scope('stats_update',[]);m.set32(25461316n,m.u32(25461316n)&~slotMask());},
      stats_load_failed(s){const r=call('stats_load_failed',[s]);return (s>>>0)<32&&(slotMask()&(1<<s))?0:r;},
      cloud_available(){return 1;},profile_stats_failed(){return 0;},profile_stats_synced(){return 1;},
      ros_credentials_valid(c){return inStats?1:call('ros_credentials_valid',[c]);},
      active_gamer_info(){const original=call('active_gamer_info',[]);if(original!==0n)return original;
        // The pinned queued-save caller only tests this pointer for non-null.
        // Do not mark Social Club online, synthesize credentials, or affect its
        // ordinary callers. Serialized saves still go through our local writer.
        if(!inMemberSave||!interfacesReady()||m.u32(6713864n)!==0)return original;
        m.offset(15219624n,1);saveNote('using local gamer for queued save');return 15219624n;},
      save_thread_create(...args){const saving=args[0]===41759n;if(saving)saveNote('worker creation requested');
        // The real browser trial never entered the created save worker. For
        // this explicit candidate only, serialize the already prepared local
        // member-save block inline. Preserve the original worker's own result
        // and let the normal queued operation perform the durable file write.
        // Handle 1 is the pinned engine's completed/no-thread join sentinel.
        const block=args[1];
        if(saving&&host.inlineMemberSave===true&&inMemberSave&&!inSaveWorker&&interfacesReady()&&m.u32(6713864n)===0&&
          [23158104n,23158184n,23158264n].includes(block)&&m.u32(at(block,68))===1&&m.bytes(at(block,72),1)[0]===1){
          const size=m.u32(at(block,64)),data=m.u64(at(block,32));
          if(size>0&&size<=FILE&&data!==0n){m.offset(data,size);saveNote('using inline local save serializer');out.save_block_worker(block);return 1n;}
        }
        const r=call('save_thread_create',args);if(saving)saveNote('worker creation '+(r===1n?'skipped':r===-1n||r===0xffffffffffffffffn?'failed':'started'));return r;},
      save_block_worker(p){inSaveWorker++;saveNote('worker entered');
        try{const r=call('save_block_worker',[p]);saveNote('worker returned; state='+m.u32(at(p,68)));return r;}
        catch(error){saveNote('worker threw');throw error;}finally{inSaveWorker--;}},
      save_builder_buffer(...args){if(inSaveWorker)saveNote('builder entered');
        const r=call('save_builder_buffer',args);if(inSaveWorker)saveNote('builder returned; result='+r);return r;},
      post_member_file(_g,_s,path,data,size,_i,_a,status){if(status!==0n)m.offset(status,8);size>>>=0;let ok=false;try{const name=str(path);if(size<=FILE&&profile.put('f:'+name,m.bytes(data,size))){ok=host.commit()===true;if(ok&&slot(name)>=0)markSlot(slot(name),false);}}catch{}saveNote('file write '+(ok?'committed':'refused')+'; bytes='+size);finish(status,ok?3:2);return 1;},
      get_member_file(_g,_m,_s,path,_sec,_since,_options,device,handle,_i,_a,status){if(status!==0n)m.offset(status,8);let data,name;try{name=str(path);if(device!==8638336n||!validKey('f:'+name)){saveNote('file read refused: '+(device!==8638336n?'device':'path'));finish(status,2);return 1;}data=profile.get('f:'+name);}catch{saveNote('file read refused: profile or path unavailable');finish(status,2);return 1;}
        if(data===null){saveNote('file read missing; slot='+slot(name));const s=slot(name);if(s>=0)markSlot(s,true);finish(status,2,404);return 1;}let p=0n,ok=false;
        try{p=host.allocate(BigInt(data.length||1));if(p!==0n){m.bytes(p,data.length).set(data);ok=!!call('grow_buffer_append',[handle,p,data.length]);}}finally{if(p!==0n)host.release(p);}saveNote('file read '+(ok?'delivered':'refused')+'; bytes='+data.length);finish(status,ok?3:2);return 1;},
      ugc_query_content(){return 0;},grow_buffer_append(...args){return call('grow_buffer_append',args);},grow_buffer_file_name(p,n,b){writeStr(p,'growbuffer:'+b.toString(16),n);},
      stat_find(...args){const r=call('stat_find',args);missing=!r;return r;},
      packed_key(id,index,slot){m.offset(id,4);const map=m.u64(25461184n)+':'+m.u16(25461192n)+':'+m.bytes(25461176n,1)[0];if(map!==missMap){missMap=map;misses.clear();}
        const key=packed(index,slot);if(misses.has(key)){m.set32(id,misses.get(key));missing=true;return 0;}
        const r=call('packed_key',[id,index,slot]);missing=!r;if(!r&&misses.size<32768)misses.set(key,m.u32(id));return r;},
      packed_get(p,n,s){return engineOr('packed_get',[p,n,s],()=>result(p,profile.stat(packed(n,s))));},
      packed_set(v,n,s){engineOr('packed_set',[v,n,s],()=>profile.setStat(packed(n,s),BigInt(v|0)));},
      stat_get_int(h,p,player){return engineOr('stat_get_int',[h,p,player],()=>result(p,profile.stat(hash(h))));},
      stat_get_float(h,p,player){return engineOr('stat_get_float',[h,p,player],()=>result(p,profile.stat(hash(h))));},
      stat_get_bool(h,p,player){return engineOr('stat_get_bool',[h,p,player],()=>result(p,profile.stat(hash(h))!==0n?1n:0n));},
      stat_get_masked_int(h,p,start,bits,player){return engineOr('stat_get_masked_int',[h,p,start,bits,player],()=>result(p,(profile.stat(hash(h))>>BigInt(start&63))&mask(bits)));},
      stat_set_int(h,v,save){return engineOr('stat_set_int',[h,v,save],()=>profile.setStat(hash(h),BigInt(v|0))?1:0);},
      stat_set_float(h,v,save){return engineOr('stat_set_float',[h,v,save],()=>{const bits=new DataView(new ArrayBuffer(4));bits.setFloat32(0,v,true);return profile.setStat(hash(h),BigInt(bits.getUint32(0,true)))?1:0;});},
      stat_set_bool(h,v,save){return engineOr('stat_set_bool',[h,v,save],()=>profile.setStat(hash(h),v?1n:0n)?1:0);},
      stat_set_masked_int(h,v,start,bits,save){return engineOr('stat_set_masked_int',[h,v,start,bits,save],()=>{const field=BigInt.asUintN(64,mask(bits)<<BigInt(start&63));return profile.setStat(hash(h),(profile.stat(hash(h))&~field)|((BigInt(v>>>0)<<BigInt(start&63))&field))?1:0;});},
      stat_delete_slot(slot){call('stat_delete_slot',[slot]);profile.deleteSlot(slot|0);}
    };
    for(const field of ['mpstats_load_update','mpstats_save_update'])out[field]=(...args)=>{const saving=field==='mpstats_save_update';inStats++;if(saving)inMemberSave++;
      try{const r=call(field,args);if(saving){try{const state=m.u32(at(args[0],20)),kind=m.u32(at(args[0],24)),buffer=kind===1?23158184n:kind===2?23158264n:23158104n;
        saveNote('operation state='+state+' block-state='+m.u32(at(buffer,68))+' last-cloud-error='+m.u32(23159968n));}catch{}}return r;}finally{if(saving)inMemberSave--;inStats--;}};
    for(const [field,value] of [['profanity_valid',1],['profanity_pending',0],['profanity_status',0],['savemigration_mp_enabled',0],['bad_pack_order',0]])out[field]=info=>{call(field,[info]);m.set32(m.u64(info),value);};
    return out;
  }
  const api={Profile,hooks,validKey,crc};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.ZemaOnline=api;
})(globalThis);
