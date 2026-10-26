//! Bounded engine datagrams, using glue5's virtual LAN and DATA wire layout.
//! No sockets, discovery, files, background threads or side effects on import.
//! The explicit WebSocket client owns transport and connection lifetime.
mod engine;
mod profile;
pub use engine::*;
use std::collections::{HashMap, VecDeque};
use std::sync::{Condvar, LazyLock, Mutex};
use std::time::Duration;
use std::sync::atomic::{AtomicBool,Ordering};
static GAME_PREPARED: AtomicBool = AtomicBool::new(false);

pub const NET: u32 = 0x0a4d0000;
pub const MAX_FRAME: usize = 2048;
pub const MAX_PAYLOAD: usize = MAX_FRAME - 16;
const MAX_QUEUED: usize = 256;
const MAX_HANDLES: usize = 128;
const MAX_PORTS: usize = 32;
pub(crate) static STATE: LazyLock<(Mutex<Lan>, Condvar)> = LazyLock::new(|| (Mutex::new(Lan::default()), Condvar::new()));

pub fn valid_ip(ip: u32) -> bool { ip & 0xffff0000 == NET && ip & 255 != 0 && ip & 255 != 255 }
pub fn broadcast(ip: u32) -> bool { ip == u32::MAX || (ip & 0xffff0000 == NET && ip & 255 == 255) }

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Datagram { pub from: u32, pub src_port: u16, pub to: u32, pub dst_port: u16, pub data: Vec<u8> }
impl Datagram {
    pub fn decode(frame: &[u8]) -> Option<Self> {
        if !(16..=MAX_FRAME).contains(&frame.len()) || frame[..4] != [b'G', b'5', 1, 3] { return None; }
        let d = Self { from: u32::from_be_bytes(frame[4..8].try_into().ok()?),
            src_port: u16::from_be_bytes(frame[8..10].try_into().ok()?),
            to: u32::from_be_bytes(frame[10..14].try_into().ok()?),
            dst_port: u16::from_be_bytes(frame[14..16].try_into().ok()?), data: frame[16..].to_vec() };
        (valid_ip(d.from) && (valid_ip(d.to) || broadcast(d.to)) && d.src_port != 0 && d.dst_port != 0).then_some(d)
    }
    pub fn encode(&self) -> Option<Vec<u8>> {
        if self.data.len() > MAX_PAYLOAD { return None; }
        let mut b = Vec::from([b'G', b'5', 1, 3]); b.extend(self.from.to_be_bytes()); b.extend(self.src_port.to_be_bytes());
        b.extend(self.to.to_be_bytes()); b.extend(self.dst_port.to_be_bytes()); b.extend(&self.data);
        Self::decode(&b).map(|_| b)
    }
}

#[derive(Default)]
pub(crate) struct Lan {
    pub vip: u32, epoch: u64, pub connected: bool, next: u32, ephemeral: u16,
    ports: HashMap<u32,u16>, queues: HashMap<u16, VecDeque<Datagram>>, outgoing: VecDeque<Vec<u8>>, queued: usize,
}
impl Lan {
    fn configure(&mut self, vip: u32, epoch: u64) -> bool {
        // The engine caches its virtual address and socket handles. A fresh
        // relay may admit that exact address while disconnected, never readdress
        // a running game or switch an active connection to a different epoch.
        if !valid_ip(vip) || epoch == 0 || (self.epoch != 0 &&
            (self.vip != vip || (self.connected && self.epoch != epoch))) { return false; }
        self.vip = vip; self.epoch = epoch; true
    }
    fn connection(&mut self, connected: bool) {
        self.connected = connected && self.epoch != 0;
        self.outgoing.clear(); self.queues.values_mut().for_each(VecDeque::clear); self.queued = 0;
    }
    pub fn bind(&mut self, mut port: u16) -> Option<(u32,u16)> {
        if !self.connected || self.ports.len() >= MAX_HANDLES { return None; }
        if port == 0 {
            for _ in 0..15536 {
                self.ephemeral = if self.ephemeral < 50000 || self.ephemeral == u16::MAX { 50000 } else { self.ephemeral + 1 };
                if !self.queues.contains_key(&self.ephemeral) { port = self.ephemeral; break; }
            }
            if port == 0 { return None; }
        }
        if !self.queues.contains_key(&port) && self.queues.len() >= MAX_PORTS { return None; }
        // Keep handles within the engine's 1024-bit fd_set while reclaiming
        // closed slots. The live-handle limit remains independent of churn.
        for _ in 0..1023 {
            self.next = self.next % 1023 + 1;
            if !self.ports.contains_key(&self.next) {
                self.ports.insert(self.next,port); self.queues.entry(port).or_default();
                return Some((self.next,port));
            }
        }
        None
    }
    pub fn port(&self,handle:u64)->Option<u16>{self.ports.get(&u32::try_from(handle).ok()?).copied()}
    pub fn close(&mut self,handle:u64)->bool {
        let Ok(handle)=u32::try_from(handle)else{return false};
        let Some(port)=self.ports.remove(&handle)else{return false};
        // Multiple engine sockets can share a port and its receive queue.
        if !self.ports.values().any(|p|*p==port) {
            if let Some(queue)=self.queues.remove(&port){self.queued-=queue.len();}
        }
        true
    }
    /// Select owns readiness: never confuse virtual handles with native file descriptors.
    pub fn selected(&self, readers:&[u32], writers:&[u32], except:&[u32])->Option<(Vec<u32>,Vec<u32>)> {
        if readers.iter().chain(writers).chain(except).any(|h|!self.ports.contains_key(h)){return None;}
        if !self.connected{return Some((vec![],vec![]));}
        Some((readers.iter().copied().filter(|h|self.has_data(*h)).collect(),if self.outgoing.len()<MAX_QUEUED{writers.to_vec()}else{vec![]}))
    }
    pub fn has_data(&self, handle: u32) -> bool { self.ports.get(&handle).and_then(|p|self.queues.get(p)).is_some_and(|q|!q.is_empty()) }
    fn send(&mut self, src_port: u16, to: u32, dst_port: u16, data: &[u8]) -> bool {
        if !self.connected || !self.queues.contains_key(&src_port) || self.outgoing.len() >= MAX_QUEUED { return false; }
        let d = Datagram {from:self.vip,src_port,to,dst_port,data:data.to_vec()};
        match d.encode() { Some(frame) => { self.outgoing.push_back(frame); true }, None => false }
    }
    fn deliver(&mut self, frame: &[u8]) -> bool {
        if !self.connected || self.queued >= MAX_QUEUED { return false; }
        let Some(d) = Datagram::decode(frame) else { return false };
        if d.from == self.vip || (d.to != self.vip && !broadcast(d.to)) { return false; }
        let Some(queue) = self.queues.get_mut(&d.dst_port) else { return false };
        queue.push_back(d); self.queued += 1; true
    }
    pub fn receive(&mut self, port: u16) -> Option<Datagram> {
        let d = self.queues.get_mut(&port)?.pop_front()?; self.queued -= 1; Some(d)
    }
}

#[no_mangle]
pub extern "C" fn ZemaLanConfigure(vip: u32, epoch: u64) -> i32 { STATE.0.lock().unwrap().configure(vip,epoch) as i32 }
#[no_mangle]
pub extern "C" fn ZemaLanConnected(value: i32) { STATE.0.lock().unwrap().connection(value != 0); STATE.1.notify_all(); }
#[no_mangle]
pub extern "C" fn ZemaLanTransportReady() -> i32 { STATE.0.lock().unwrap().connected as i32 }
/// Explicit experimental host preparation; never a gameplay verification claim.
#[no_mangle]
pub extern "C" fn ZemaLanGameReady() -> i32 { (GAME_PREPARED.load(Ordering::Acquire) && ZemaLanTransportReady()==1 && profile::ZemaProfileReady()==1) as i32 }
#[no_mangle]
pub extern "C" fn ZemaLanPrepared(value:i32) { GAME_PREPARED.store(value==1 && ZemaLanTransportReady()==1 && profile::ZemaProfileReady()==1,Ordering::Release); }
/// Caller supplies a readable buffer of len bytes. No frame is retained on rejection.
#[no_mangle]
pub unsafe extern "C" fn ZemaLanDeliver(frame: *const u8, len: usize) -> i32 {
    if frame.is_null() || !(16..=MAX_FRAME).contains(&len) { return 0; }
    let accepted = STATE.0.lock().unwrap().deliver(unsafe {std::slice::from_raw_parts(frame,len)});
    if accepted { STATE.1.notify_all(); } accepted as i32
}
/// A short buffer returns the negative required size without dropping the frame.
#[no_mangle]
pub unsafe extern "C" fn ZemaLanTakeOutgoing(out: *mut u8, capacity: usize) -> i32 {
    let mut state = STATE.0.lock().unwrap();
    let Some(frame) = state.outgoing.front() else { return 0; };
    if out.is_null() || capacity < frame.len() { return -(frame.len() as i32); }
    unsafe { std::ptr::copy_nonoverlapping(frame.as_ptr(),out,frame.len()); }
    let len = frame.len(); let was_full=state.outgoing.len()==MAX_QUEUED; state.outgoing.pop_front();
    drop(state);if was_full{STATE.1.notify_all();}len as i32
}

#[cfg(test)]
mod tests {
    use super::*;
    fn pair() -> (Lan,Lan) {
        let mut a = Lan::default(); let mut b = Lan::default();
        assert!(a.configure(NET|1,9)); assert!(b.configure(NET|2,9)); a.connection(true); b.connection(true);
        a.bind(6672).unwrap(); b.bind(6672).unwrap(); (a,b)
    }
    #[test] fn native_datagram_roundtrip_and_ports() {
        let (mut a,mut b)=pair(); assert!(a.send(6672,b.vip,6672,b"engine bytes"));
        assert!(b.deliver(&a.outgoing.pop_front().unwrap())); let d=b.receive(6672).unwrap();
        assert_eq!(d.data,b"engine bytes"); assert_eq!(d.from,a.vip); assert_eq!(d.src_port,6672); assert!(b.receive(1234).is_none());
    }
    #[test] fn codec_rejects_corruption_and_limits() {
        let (mut a,b)=pair(); assert!(a.send(6672,b.vip,6672,&vec![0;MAX_PAYLOAD])); let frame=a.outgoing.pop_front().unwrap();
        assert_eq!(frame.len(),MAX_FRAME); for n in 0..16 {assert!(Datagram::decode(&frame[..n]).is_none());}
        let mut wrong=frame.clone();wrong[2]=2;assert!(Datagram::decode(&wrong).is_none());
        assert!(!a.send(6672,b.vip,6672,&vec![0;MAX_PAYLOAD+1]));assert!(!a.send(0,b.vip,6672,b"x"));
    }
    #[test] fn disconnect_clears_queues_and_same_session_can_resume() {
        let (mut a,mut b)=pair(); a.send(6672,b.vip,6672,b"old");b.deliver(&a.outgoing[0]);
        b.connection(false);assert!(!b.has_data(1));assert!(!b.deliver(&a.outgoing[0]));
        assert!(b.configure(NET|2,9));assert!(!b.configure(NET|3,9));assert!(b.configure(NET|2,10));b.connection(true);
        assert!(!b.configure(NET|2,11));
        assert!(b.deliver(&a.outgoing[0]));assert!(b.has_data(1));
    }
    #[test] fn broadcast_and_wrong_destination() {
        let (mut a,mut b)=pair();a.send(6672,NET|3,6672,b"x");assert!(!b.deliver(&a.outgoing.pop_front().unwrap()));
        a.send(6672,u32::MAX,6672,b"broadcast");assert!(b.deliver(&a.outgoing.pop_front().unwrap()));
        let self_frame=Datagram {from:b.vip,src_port:6672,to:b.vip,dst_port:6672,data:vec![]}.encode().unwrap();assert!(!b.deliver(&self_frame));
    }
    #[test] fn restart_rejoin_retains_socket_address_handles_and_clears_stale_packets() {
        let (mut a,mut b)=pair();let handle=1;
        assert!(b.send(6672,a.vip,6672,b"stale outgoing"));
        assert!(a.send(6672,b.vip,6672,b"stale incoming"));assert!(b.deliver(&a.outgoing[0]));
        assert!(!b.configure(NET|2,10));b.connection(false);
        assert!(b.outgoing.is_empty());assert_eq!(b.queued,0);assert_eq!(b.port(handle),Some(6672));
        assert!(!b.configure(NET|3,10));assert!(b.configure(NET|2,10));b.connection(true);
        assert!(!b.has_data(handle as u32));assert!(b.send(6672,a.vip,6672,b"fresh"));
        assert_eq!(Datagram::decode(&b.outgoing[0]).unwrap().from,NET|2);
        assert_eq!(b.selected(&[],&[handle as u32],&[]),Some((vec![],vec![handle as u32])));
    }
    #[test] fn queue_and_handle_budgets() {
        let (mut a,mut b)=pair();for _ in 0..MAX_QUEUED {assert!(a.send(6672,b.vip,6672,b"x"));}
        assert!(!a.send(6672,b.vip,6672,b"overflow"));for f in &a.outgoing {assert!(b.deliver(f));}assert!(!b.deliver(&a.outgoing[0]));
        for _ in 1..MAX_HANDLES {a.bind(6672).unwrap();}assert!(a.bind(6672).is_none());
    }
    #[test] fn ephemeral_ports_and_invalid_configuration() {
        let mut a=Lan::default();assert!(a.bind(1).is_none());assert!(!a.configure(0,1));assert!(!a.configure(NET|1,0));
        a.configure(NET|1,1);a.connection(true);let x=a.bind(0).unwrap();let y=a.bind(0).unwrap();assert_ne!(x.1,y.1);assert!(x.1>=50000);
    }
    #[test] fn virtual_select_filters_queued_ports_and_connected_bound_writers() {
        let mut a=Lan::default();assert!(a.configure(NET|2,9));a.connection(true);
        let one=a.bind(6672).unwrap().0;let two=a.bind(7788).unwrap().0;let shared=a.bind(6672).unwrap().0;
        assert_eq!(a.selected(&[one,two],&[],&[]),Some((vec![],vec![])));
        let packet=Datagram{from:NET|1,src_port:6672,to:a.vip,dst_port:6672,data:vec![42]}.encode().unwrap();assert!(a.deliver(&packet));
        assert_eq!(a.selected(&[one,two,shared],&[two],&[one]),Some((vec![one,shared],vec![two])));
        for _ in 0..MAX_QUEUED{assert!(a.send(6672,NET|1,6672,b"full"));}
        assert_eq!(a.selected(&[],&[two],&[]),Some((vec![],vec![])));
        a.outgoing.pop_front();assert_eq!(a.selected(&[],&[two],&[]),Some((vec![],vec![two])));
        assert_eq!(a.selected(&[127],&[],&[]),None);
        assert_eq!(a.selected(&[],&[],&[127]),None);
        a.connection(false);assert_eq!(a.selected(&[one],&[two],&[shared]),Some((vec![],vec![])));
    }
    #[test] fn ffi_buffers_do_not_drop_frames_or_imply_game_readiness() {
        assert_eq!(ZemaLanConfigure(NET|1,1),1);ZemaLanConnected(1);
        assert_eq!(ZemaLanTransportReady(),1);assert_eq!(ZemaLanGameReady(),0);
        {let mut s=STATE.0.lock().unwrap();s.bind(6672).unwrap();assert!(s.send(6672,NET|2,6672,b"ffi"));}
        assert_eq!(unsafe{ZemaLanTakeOutgoing(std::ptr::null_mut(),0)},-19);
        let mut bytes=[0u8;2048];assert_eq!(unsafe{ZemaLanTakeOutgoing(bytes.as_mut_ptr(),2)},-19);
        assert_eq!(unsafe{ZemaLanTakeOutgoing(bytes.as_mut_ptr(),bytes.len())},19);
        assert_eq!(Datagram::decode(&bytes[..19]).unwrap().data,b"ffi");
        assert_eq!(unsafe{ZemaLanDeliver(std::ptr::null(),16)},0);
        ZemaLanConnected(0);assert_eq!(ZemaLanTransportReady(),0);assert_eq!(ZemaLanGameReady(),0);
    }
    #[test] fn close_reclaims_handle_and_port_budgets_after_many_cycles() {
        let mut s=Lan::default();assert!(s.configure(NET|1,9));s.connection(true);
        for _ in 0..4096 {let (h,_)=s.bind(0).unwrap();assert!(h>0&&h<1024);assert!(s.close(h.into()));assert!(!s.close(h.into()));}
        assert!(s.ports.is_empty()&&s.queues.is_empty());assert_eq!(s.queued,0);
        for port in 1..=MAX_PORTS as u16 {assert!(s.bind(port).is_some());}
        assert!(s.bind(1000).is_none());
    }
    #[test] fn shared_port_last_close_drops_only_its_receive_queue() {
        let (mut a,mut b)=pair();let first=1;let shared=b.bind(6672).unwrap().0;
        let other=b.bind(7788).unwrap().0;
        for port in [6672,7788] {a.send(6672,b.vip,port,b"pending");assert!(b.deliver(&a.outgoing.pop_front().unwrap()));}
        assert_eq!(b.queued,2);assert!(b.close(first));assert_eq!(b.queued,2);assert!(b.has_data(shared));
        assert!(b.close(shared.into()));assert_eq!(b.queued,1);assert!(!b.queues.contains_key(&6672));assert!(b.has_data(other));
        let fresh=b.bind(6672).unwrap().0;assert!(!b.has_data(fresh));assert_eq!(b.receive(7788).unwrap().data,b"pending");
    }
    #[test] fn transport_resume_preserves_handles_while_explicit_close_invalidates_select() {
        let (mut a,_)=pair();let h=1;a.connection(false);assert_eq!(a.port(h),Some(6672));
        a.connection(true);assert_eq!(a.selected(&[],&[h as u32],&[]),Some((vec![],vec![h as u32])));
        assert!(a.close(h));assert_eq!(a.selected(&[h as u32],&[],&[]),None);
        assert!(!a.close(u64::MAX));
    }
}
