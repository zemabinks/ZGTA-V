//! glue5 vnet ABI, adapted to the existing bounded C memory provider.
//! See the pinned contract for field offsets and exact function signatures.
use super::*;
use std::ffi::c_void;
use std::sync::OnceLock;
use std::sync::atomic::{AtomicU32,Ordering};
use std::time::Instant;

type Instance = *mut c_void;
#[repr(C)]
#[derive(Clone,Copy)]
pub struct ZemaLanHost {
    pub version: u32,
    pub memory: Option<unsafe extern "C" fn(Instance,*mut u64)->*mut u8>,
    pub create: Option<unsafe extern "C" fn(Instance,u64,u32,u32,u32,u32)->u32>,
    pub profiler: Option<unsafe extern "C" fn(Instance,u64,u64,u32)->u32>,
    pub select: Option<unsafe extern "C" fn(Instance,u32,u64,u64,u64,u64)->u32>,
}
static HOST: OnceLock<ZemaLanHost> = OnceLock::new();
#[no_mangle]
pub unsafe extern "C" fn ZemaLanInstallHost(host: *const ZemaLanHost,size: usize)->i32 {
    if host.is_null() || size != std::mem::size_of::<ZemaLanHost>() {return 0;}
    let h=unsafe{*host};
    if h.version!=1 || h.memory.is_none() || h.create.is_none() || h.profiler.is_none() || h.select.is_none() {return 0;}
    HOST.set(h).is_ok() as i32
}

struct Mem { base:*mut u8, len:u64 }
impl Mem {
    unsafe fn of(instance:Instance)->Option<Self> {
        let mut len=0;let base=unsafe{HOST.get()?.memory?(instance,&mut len)};
        (!base.is_null()).then_some(Self{base,len})
    }
    fn ptr(&self,offset:u64,len:usize)->Option<*mut u8>{
        let end=offset.checked_add(len as u64)?;if end>self.len{return None;}
        Some(unsafe{self.base.add(usize::try_from(offset).ok()?)})
    }
    fn read<const N:usize>(&self,offset:u64)->Option<[u8;N]>{
        let p=self.ptr(offset,N)?;let mut bytes=[0;N];unsafe{std::ptr::copy_nonoverlapping(p,bytes.as_mut_ptr(),N);}Some(bytes)
    }
    fn u16(&self,offset:u64)->Option<u16>{Some(u16::from_le_bytes(self.read(offset)?))}
    fn u32(&self,offset:u64)->Option<u32>{Some(u32::from_le_bytes(self.read(offset)?))}
    fn u64(&self,offset:u64)->Option<u64>{Some(u64::from_le_bytes(self.read(offset)?))}
    fn write(&self,offset:u64,bytes:&[u8])->bool{
        let Some(p)=self.ptr(offset,bytes.len())else{return false};unsafe{std::ptr::copy_nonoverlapping(bytes.as_ptr(),p,bytes.len());}true
    }
}
const ADDRESS:u64=136;const ADDRESS_PORT:u64=20;const SOCKET_PORT:u64=188;
const NETWORK_UP:u64=13346512;const WINSOCK_STATE:u64=13347088;
#[no_mangle]
pub unsafe extern "C" fn ZemaLanNetworkUp(instance:Instance)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};
    let Some(p)=m.ptr(NETWORK_UP,4) else{return 0};
    if (p as usize)%std::mem::align_of::<AtomicU32>()!=0{return 0;}
    unsafe{&*p.cast::<AtomicU32>()}.store(1,Ordering::Release);
    m.write(WINSOCK_STATE,&2u32.to_le_bytes()) as u32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaLanCreateSocket(instance:Instance,socket:u64,port:u32,protocol:u32,blocking:u32,family:u32)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};
    let Some(state)=m.u32(WINSOCK_STATE)else{return 0};
    m.write(WINSOCK_STATE,&2u32.to_le_bytes());
    let result=unsafe{HOST.get().unwrap().create.unwrap()(instance,socket,port,protocol,blocking,family)};
    let Some(current)=(unsafe{Mem::of(instance)})else{return 0};
    if !current.write(WINSOCK_STATE,&state.to_le_bytes()){return 0;}result
}
#[no_mangle]
pub unsafe extern "C" fn ZemaLanBind(instance:Instance,socket:u64)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};
    let Some(port)=socket.checked_add(SOCKET_PORT).and_then(|at|m.u16(at))else{return 0};
    if socket.checked_add(357).is_none_or(|end|end>m.len){return 0;}
    let mut s=STATE.0.lock().unwrap();
    if let Some(bound)=m.u64(socket+8).and_then(|h|s.port(h)) {
        return (s.connected&&(port==0||port==bound))as u32;
    }
    let Some((handle,port))=s.bind(port)else{return 0};
    m.write(socket+8,&u64::from(handle).to_le_bytes());m.write(socket+ADDRESS,&s.vip.to_le_bytes());
    m.write(socket+ADDRESS+4,&[0]);m.write(socket+ADDRESS+ADDRESS_PORT,&port.to_le_bytes());m.write(socket+ADDRESS+22,&[0]);
    let flags=m.read::<1>(socket+356).unwrap()[0]|2;m.write(socket+356,&[flags]);1
}
/// Called under the engine socket lock by the pinned NativeClose adapter.
/// Transport disconnects deliberately do not invoke this lifecycle operation.
#[no_mangle]
pub unsafe extern "C" fn ZemaLanClose(instance:Instance,socket:u64)->u32 {
    let Some(m)=(unsafe{Mem::of(instance)})else{return 0};
    let Some(at)=socket.checked_add(8)else{return 0};
    let mut s=STATE.0.lock().unwrap();
    let Some(handle)=m.u64(at)else{return 0};
    // Invalidate memory before publishing a reusable slot to another socket.
    m.write(at,&u64::MAX.to_le_bytes());
    let closed=s.close(handle);drop(s);
    if closed{STATE.1.notify_all();}closed as u32
}
fn clear_error(m:&Mem,error:u64)->bool{error==0 || m.write(error,&0u32.to_le_bytes())}
#[no_mangle]
pub unsafe extern "C" fn ZemaLanSend(instance:Instance,socket:u64,to:u64,data:u64,len:u32,error:u64)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};if !clear_error(&m,error) || len as usize>MAX_PAYLOAD{return 0;}
    let Some(from)=socket.checked_add(ADDRESS+ADDRESS_PORT).and_then(|at|m.u16(at))else{return 0};
    let (Some(ip),Some(port),Some(p))=(m.u32(to),to.checked_add(ADDRESS_PORT).and_then(|at|m.u16(at)),m.ptr(data,len as usize))else{return 0};
    let bytes=unsafe{std::slice::from_raw_parts(p,len as usize)};let mut s=STATE.0.lock().unwrap();
    let Some(handle)=socket.checked_add(8).and_then(|at|m.u64(at))else{return 0};
    if s.port(handle)!=Some(from){return 0;}s.send(from,ip,port,bytes) as u32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaLanReceive(instance:Instance,socket:u64,from:u64,buffer:u64,max:u32,error:u64)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};if !clear_error(&m,error) || m.ptr(buffer,max as usize).is_none() || (from!=0 && m.ptr(from,23).is_none()){return 0;}
    let Some(port)=socket.checked_add(ADDRESS+ADDRESS_PORT).and_then(|at|m.u16(at))else{return 0};
    let mut s=STATE.0.lock().unwrap();let Some(handle)=socket.checked_add(8).and_then(|at|m.u64(at))else{return 0};
    if s.port(handle)!=Some(port){return 0;}
    let Some(d)=s.receive(port)else{return 0};drop(s);let len=d.data.len().min(max as usize);
    m.write(buffer,&d.data[..len]);if from!=0 {m.write(from,&d.from.to_le_bytes());m.write(from+4,&[0]);m.write(from+20,&d.src_port.to_le_bytes());m.write(from+22,&[0]);}len as u32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaLanLocalIp(instance:Instance,address:u64)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};if m.ptr(address,5).is_none(){return 0;}
    let s=STATE.0.lock().unwrap();if !s.connected{return 0;}m.write(address,&s.vip.to_le_bytes());m.write(address+4,&[0]);1
}
#[no_mangle]
pub unsafe extern "C" fn ZemaLanProfiler(instance:Instance,profiler:u64,name:u64,flag:u32)->u32{
    let Some(m)= (unsafe{Mem::of(instance)}) else{return 0};
    if name==3746537 && !m.write(WINSOCK_STATE,&0u32.to_le_bytes()){return 0;}
    unsafe{HOST.get().unwrap().profiler.unwrap()(instance,profiler,name,flag)}
}
/// rage::netSocket::Select returns a selected-bit count, 0 on timeout, or -1.
/// Its handles are process-local LAN handles, not NativeFiles/POSIX descriptors.
#[no_mangle]
pub unsafe extern "C" fn ZemaLanSelect(instance:Instance,count:u32,read:u64,write:u64,except:u64,timeout:u64)->u32{
    let invalid=u32::MAX;
    let Some(m)= (unsafe{Mem::of(instance)}) else{return invalid};if count>1024{return invalid;}
    let sets=[read,write,except];
    if sets.iter().any(|p|*p!=0&&m.ptr(*p,128).is_none()){return invalid;}
    let handles=|set:u64|->Option<Vec<u32>>{
        if set==0{return Some(vec![]);}
        let mut result=Vec::new();for fd in 0..count {let word=m.u64(set.checked_add(u64::from(fd/64)*8)?)?;
            if word>>(fd%64)&1!=0 {result.push(fd);}}Some(result)
    };
    let (Some(readers),Some(writers),Some(exceptions))=(handles(read),handles(write),handles(except))else{return invalid};
    let deadline=if timeout!=0{
        let (Some(seconds),Some(micros))=(m.u64(timeout),timeout.checked_add(8).and_then(|at|m.u32(at)))else{return invalid};
        if seconds>3600 || micros>=1_000_000{return invalid;}Some(Instant::now()+Duration::from_secs(seconds)+Duration::from_micros(micros.into()))
    }else{None};
    let mut s=STATE.0.lock().unwrap();
    let selected=loop{
        let Some(ready)=s.selected(&readers,&writers,&exceptions)else{return invalid;};
        if !ready.0.is_empty()||!ready.1.is_empty()||!s.connected{break ready;}
        if let Some(end)=deadline{
            let left=end.saturating_duration_since(Instant::now());if left.is_zero(){break ready;}
            s=STATE.1.wait_timeout(s,left).unwrap().0;
        }else{s=STATE.1.wait(s).unwrap();}
    };
    drop(s);
    // Reacquire the current memory view after waiting; providers may relocate it.
    let Some(current)=(unsafe{Mem::of(instance)})else{return invalid};
    if sets.iter().any(|p|*p!=0&&current.ptr(*p,128).is_none()){return invalid;}
    let mut output=[[0u8;128];3];
    for (row,ready) in [selected.0.as_slice(),selected.1.as_slice()].iter().enumerate(){
        for fd in *ready{output[row][(*fd/8)as usize]|=1u8<<(*fd%8);}
    }
    for (at,bytes) in sets.iter().zip(output.iter()){if *at!=0{current.write(*at,bytes);}}
    (selected.0.len()+selected.1.len())as u32
}

#[cfg(test)]
mod tests{
    use super::*;
    #[test]fn memory_ranges_overflow_and_unaligned_values(){
        let mut bytes=vec![0u8;256];let m=Mem{base:bytes.as_mut_ptr(),len:256};
        assert!(m.write(1,&0x11223344u32.to_le_bytes()));assert_eq!(m.u32(1),Some(0x11223344));
        assert!(m.u64(250).is_none());assert!(m.ptr(u64::MAX,10).is_none());assert!(!m.write(255,&[1,2]));
    }
}
