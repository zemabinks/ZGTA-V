//! Muguet's multiplayer protocol and replica logic on Port's native engine.
//! Rust here is only a static networking library: no Wasmtime/wgpu runtime.
#![allow(dead_code)]
pub mod engine_bridge;
#[path = "../upstream/mp.rs"] mod mp;
#[path = "../upstream/proto.rs"] pub mod proto;
#[path = "../upstream/server.rs"] pub mod server;
pub use engine_bridge::{coerce_args, default_val};
use std::{ffi::{c_char, c_void, CStr}, sync::{atomic::{AtomicBool, Ordering}, OnceLock}, cell::Cell};

pub struct HostState;
pub struct SharedMemory { instance: usize }
pub struct Runtime { pub mem: SharedMemory }
pub static RT: OnceLock<Runtime> = OnceLock::new();
static CONFIGURED: AtomicBool = AtomicBool::new(false);
static ENABLED: AtomicBool = AtomicBool::new(false);
thread_local! { static IN_TICK: Cell<bool> = const { Cell::new(false) }; }
extern "C" { fn mugoat_memory_data(instance: *mut c_void, size: *mut u64) -> *mut u8; }

impl SharedMemory {
    fn region(&self, at: u64, count: usize) -> Option<*mut u8> {
        let mut size = 0;
        let base = unsafe { mugoat_memory_data(self.instance as *mut c_void, &mut size) };
        if base.is_null() || at.checked_add(count as u64)? > size { return None; }
        Some(unsafe { base.add(usize::try_from(at).ok()?) })
    }
}
pub fn read_u32(m: &SharedMemory, a: u64) -> Option<u32> { m.region(a,4).map(|p| unsafe { std::ptr::read_unaligned(p.cast()) }) }
pub fn read_u64(m: &SharedMemory, a: u64) -> Option<u64> { m.region(a,8).map(|p| unsafe { std::ptr::read_unaligned(p.cast()) }) }
pub fn write_u32(m: &SharedMemory, a: u64, v: u32) { if let Some(p) = m.region(a,4) { unsafe { std::ptr::write_unaligned(p.cast(), v) } } }
pub fn write_u64(m: &SharedMemory, a: u64, v: u64) { if let Some(p) = m.region(a,8) { unsafe { std::ptr::write_unaligned(p.cast(), v) } } }
pub fn write_bytes(m: &SharedMemory, a: u64, v: &[u8]) { if let Some(p) = m.region(a,v.len()) { unsafe { std::ptr::copy_nonoverlapping(v.as_ptr(),p,v.len()) } } }
pub fn read_cstr(m: &SharedMemory, a: u64) -> String {
    // Runs for every script thread every frame: look the memory up once, not once per byte.
    let mut size = 0;
    let base = unsafe { mugoat_memory_data(m.instance as *mut c_void, &mut size) };
    if base.is_null() || a >= size { return String::new(); }
    let (Ok(start), Ok(available)) = (usize::try_from(a), usize::try_from(size - a)) else { return String::new(); };
    let bytes = unsafe { std::slice::from_raw_parts(base.add(start), available.min(65536)) };
    let end = bytes.iter().position(|b| *b == 0).unwrap_or(bytes.len());
    String::from_utf8_lossy(&bytes[..end]).into_owned()
}
mod config { pub fn bundled_resources() -> Option<std::path::PathBuf> { None } }
mod input { pub fn muguet_is_multiplayer() -> bool { super::ENABLED.load(super::Ordering::Relaxed) } }
mod pad {
    pub static ACTIVE: super::AtomicBool = super::AtomicBool::new(false);
    pub static IN_VEHICLE: super::AtomicBool = super::AtomicBool::new(false);
    pub fn horn_held() -> bool { false } // Native pad already provides the engine's horn input.
}
unsafe fn text(ptr: *const c_char) -> String { if ptr.is_null() { String::new() } else { CStr::from_ptr(ptr).to_string_lossy().trim().into() } }

#[no_mangle]
pub unsafe extern "C" fn MugoatOnlineConfigure(server: *const c_char, name: *const c_char, room: *const c_char, mode: i32) -> bool {
    // The engine starts once per app run: a second Play (after a failed boot) keeps the first settings
    // instead of being reported as an invalid server.
    if CONFIGURED.load(Ordering::Acquire) { return true; }
    let mut server = text(server);
    // Accept what players paste: "udp://1.2.3.4:47520/", "http://host", spaces inside.
    for scheme in ["udp://", "http://", "https://"] {
        if server.to_ascii_lowercase().starts_with(scheme) { server = server[scheme.len()..].to_string(); }
    }
    server = server.split('/').next().unwrap_or("").chars().filter(|c| !c.is_whitespace()).collect();
    if server.is_empty() { std::env::remove_var("MUGUET_SERVER"); }
    else {
        // IPv4/hostname[:port], the same format as the existing Muguet server.
        if server.len()>253 || server.chars().any(|c| c.is_control()) { return false; }
        let mut name: String = text(name).chars().filter(|c| !c.is_control()).collect();
        let mut room: String = text(room).chars().filter(|c| !c.is_control()).collect();
        if name.is_empty() { name = "Player".into(); }
        if room.is_empty() { room = "default".into(); }
        // Byte limits counted whole characters: Vietnamese names with a role prefix
        // ("[Băng đảng] ...") went over 48 bytes and the game refused to start.
        let clip = |s: String, max: usize| { let mut end = s.len().min(max); while !s.is_char_boundary(end) { end -= 1; } s[..end].trim_end().to_string() };
        name = clip(name, 48); room = clip(room, 64);
        std::env::set_var("MUGUET_SERVER",server);
        std::env::set_var("MUGUET_NAME",name);
        std::env::set_var("MUGUET_ROOM",room);
        std::env::set_var("MUGUET_MODE",if mode == 1 { "story" } else { "sandbox" });
        if std::env::var("MUGUET_PVP").is_err() { std::env::set_var("MUGUET_PVP","0"); }
        ENABLED.store(true,Ordering::Release);
    }
    CONFIGURED.store(true,Ordering::Release); true
}
#[no_mangle]
pub extern "C" fn MugoatOnlineEnabled() -> bool { ENABLED.load(Ordering::Acquire) }
#[no_mangle]
pub unsafe extern "C" fn MugoatOnlineStatus(output: *mut c_char, capacity: usize) -> usize {
    let status = if ENABLED.load(Ordering::Acquire) { mp::network_status().unwrap_or_else(|| "Online: waiting for game startup".into()) } else { "Offline".into() };
    if !output.is_null() && capacity > 0 {
        let mut count = status.len().min(capacity-1);
        while !status.is_char_boundary(count) { count -= 1; }
        std::ptr::copy_nonoverlapping(status.as_ptr(),output.cast(),count); *output.add(count) = 0;
    }
    status.len()
}
#[no_mangle]
pub extern "C" fn MugoatOnlineShutdown() { if ENABLED.load(Ordering::Acquire) { mp::shutdown(); } }
#[no_mangle]
pub unsafe extern "C" fn mugoat_script_tick(instance: *mut c_void, thread: u64, tls: u64) {
    if !ENABLED.load(Ordering::Acquire) || instance.is_null() || tls==0 { return; }
    IN_TICK.with(|active| {
        if active.replace(true) { return; }
        RT.get_or_init(|| Runtime { mem: SharedMemory { instance: instance as usize } });
        let mut caller = engine_bridge::Caller::<HostState>::new(instance);
        let memory = &RT.get().unwrap().mem;
        let Some(active_thread) = tls.checked_add(3088) else { active.set(false); return; };
        let saved = read_u64(memory, active_thread);
        if saved.is_none() { active.set(false); return; }
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| mp::script_tick(&mut caller,thread,tls)));
        // The original script hook also restores this on its normal path.
        // Preserve it if Rust rejects a sync update or catches a panic.
        write_u64(memory, active_thread, saved.unwrap());
        if !matches!(result, Ok(Ok(()))) { ENABLED.store(false,Ordering::Release); eprintln!("[online] native sync stopped after a bridge error"); }
        active.set(false);
    });
}
#[no_mangle]
pub extern "C" fn mugoat_explosion(args: u64) { if ENABLED.load(Ordering::Acquire) && RT.get().is_some() { mp::explosion(args); } }
#[no_mangle]
pub extern "C" fn mugoat_time_warp(direction: u32) -> u32 { if ENABLED.load(Ordering::Acquire) { mp::time_warp(direction as i64) as u32 } else { direction } }

#[no_mangle]
pub extern "C" fn MugoatVoiceIsMicEnabled() -> bool {
    mp::VOICE_MIC_ENABLED.load(Ordering::Acquire)
}

#[no_mangle]
pub extern "C" fn MugoatVoiceSetMicEnabled(enabled: bool) {
    mp::VOICE_MIC_ENABLED.store(enabled, Ordering::Release);
}

#[no_mangle]
pub extern "C" fn MugoatVoiceIsSpeakerEnabled() -> bool {
    mp::VOICE_SPEAKER_ENABLED.load(Ordering::Acquire)
}

#[no_mangle]
pub extern "C" fn MugoatVoiceSetSpeakerEnabled(enabled: bool) {
    mp::VOICE_SPEAKER_ENABLED.store(enabled, Ordering::Release);
}

#[no_mangle]
pub unsafe extern "C" fn MugoatVoiceSubmitMicAudio(samples: *const f32, count: u32) {
    if samples.is_null() || count == 0 { return; }
    let slice = std::slice::from_raw_parts(samples, count as usize);
    mp::submit_mic_audio(slice);
}

#[no_mangle]
pub unsafe extern "C" fn MugoatVoiceMixAudio(left: *mut f32, right: *mut f32, count: u32) {
    if left.is_null() || right.is_null() || count == 0 { return; }
    let l_slice = std::slice::from_raw_parts_mut(left, count as usize);
    let r_slice = std::slice::from_raw_parts_mut(right, count as usize);
    mp::voice_mix_audio(l_slice, r_slice);
}

#[no_mangle]
pub unsafe extern "C" fn MugoatVoiceActiveSpeakers(output: *mut c_char, capacity: usize) -> usize {
    let list = mp::voice_active_speakers().join(", ");
    if !output.is_null() && capacity > 0 {
        let mut count = list.len().min(capacity - 1);
        while !list.is_char_boundary(count) { count -= 1; }
        std::ptr::copy_nonoverlapping(list.as_ptr(), output.cast(), count);
        *output.add(count) = 0;
    }
    list.len()
}

#[no_mangle]
pub extern "C" fn MugoatGetWalletCash() -> i32 {
    mp::WALLET_CASH.load(Ordering::Relaxed)
}

#[no_mangle]
pub extern "C" fn MugoatAddWalletCash(amount: i32) {
    mp::WALLET_CASH.fetch_add(amount, Ordering::Relaxed);
}

#[no_mangle]
pub extern "C" fn MugoatTriggerAmmuBuy() {
    mp::AMMU_BUY_REQUESTED.store(true, Ordering::Relaxed);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[no_mangle]
    extern "C" fn mugoat_memory_data(instance: *mut c_void, size: *mut u64) -> *mut u8 { unsafe { *size=32; } instance.cast() }
    #[test]
    fn shared_memory_checks_end_and_integer_overflow() {
        let mut bytes = [0u8;32]; let m=SharedMemory { instance: bytes.as_mut_ptr() as usize };
        write_u64(&m,24,0x1234); assert_eq!(read_u64(&m,24),Some(0x1234));
        assert_eq!(read_u64(&m,25),None); assert_eq!(read_u64(&m,u64::MAX),None);
        write_u64(&m,25,u64::MAX); assert_eq!(read_u64(&m,24),Some(0x1234));
        write_bytes(&m,0,b"hello\0"); assert_eq!(read_cstr(&m,0),"hello");
    }
}
