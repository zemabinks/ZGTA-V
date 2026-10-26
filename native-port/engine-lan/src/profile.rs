//! Isolated, bounded character files and supplemental stat bits. No disk I/O.
//! Snapshot import is transactional and only permitted before the first write.
use std::collections::BTreeMap;
use std::sync::Mutex;

const MAGIC: &[u8; 8] = b"ZEMAPF1\0";
pub const MAX_FILE: usize = 1024 * 1024;
pub const MAX_BYTES: usize = 8 * 1024 * 1024;
const MAX_RECORDS: usize = 32768;
static PROFILE: Mutex<Option<Profile>> = Mutex::new(None);

#[derive(Clone, Debug, PartialEq)]
pub struct Profile {
    pub id: u32,
    pub name: String,
    values: BTreeMap<String, Vec<u8>>,
    bytes: usize,
    pub revision: u64,
}
pub fn valid_key(key: &str) -> bool {
    if key.len() > 512 || !key.is_ascii() { return false; }
    if let Some(path) = key.strip_prefix("f:") {
        return !path.is_empty() && path.split('/').all(|s| !s.is_empty() && s != "." && s != ".."
            && s.bytes().all(|b| b.is_ascii_alphanumeric() || b"._- ".contains(&b)));
    }
    if let Some(hash) = key.strip_prefix('h') { return hash.len() == 8 && hash.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()); }
    if let Some(packed) = key.strip_prefix('p') {
        if let Some((slot, index)) = packed.split_once(':') {
            return slot.parse::<i32>().is_ok_and(|v| (-1..32).contains(&v))
                && index.parse::<u32>().is_ok_and(|v| v <= 1_000_000)
                && format!("{}:{}", slot.parse::<i32>().unwrap(), index.parse::<u32>().unwrap()) == packed;
        }
    }
    false
}
fn crc(data: &[u8]) -> u32 {
    let mut c = !0u32;
    for &byte in data { c ^= u32::from(byte); for _ in 0..8 { c = (c >> 1) ^ (0xedb88320u32 & 0u32.wrapping_sub(c & 1)); } }
    !c
}
impl Profile {
    fn valid_name(name: &str) -> bool {
        !name.is_empty() && name.len() <= 16 && name.bytes().all(|b| (32..127).contains(&b)) && !name.trim().is_empty()
    }
    pub fn new(id: u32, name: &str) -> Option<Self> {
        (id >= 65536 && id <= i32::MAX as u32 && Self::valid_name(name))
            .then(|| Self { id, name: name.to_owned(), values: BTreeMap::new(), bytes: 0, revision: 0 })
    }
    /// Display metadata only: numeric identity, character files and stats stay intact.
    pub fn rename(&mut self, name: &str) -> bool {
        if !Self::valid_name(name) { return false; }
        if self.name != name { self.name = name.to_owned(); self.revision += 1; }
        true
    }
    pub fn get(&self, key: &str) -> Option<&[u8]> { self.values.get(key).map(Vec::as_slice) }
    pub fn put(&mut self, key: &str, value: &[u8]) -> bool {
        if !valid_key(key) || value.len() > MAX_FILE || (!key.starts_with("f:") && value.len() != 8) { return false; }
        if self.get(key) == Some(value) { return true; }
        if !self.values.contains_key(key) && self.values.len() >= MAX_RECORDS { return false; }
        let before = self.values.get(key).map_or(0, Vec::len);
        let extra = if self.values.contains_key(key) { 0 } else { key.len() + 6 };
        let total = self.bytes - before + value.len() + extra;
        if total > MAX_BYTES { return false; }
        self.values.insert(key.to_owned(), value.to_vec()); self.bytes = total; self.revision += 1; true
    }
    pub fn stat(&self, key: &str) -> u64 { self.get(key).and_then(|v| v.try_into().ok()).map(u64::from_le_bytes).unwrap_or(0) }
    pub fn delete_slot(&mut self, slot: i32) {
        if !(-1..32).contains(&slot) { return; }
        let prefix = format!("p{slot}:"); let before = self.values.len();
        self.values.retain(|k,_| !k.starts_with(&prefix));
        if self.values.len() != before { self.bytes = self.values.iter().map(|(k,v)| k.len()+v.len()+6).sum(); self.revision += 1; }
    }
    pub fn encode(&self) -> Vec<u8> {
        let mut b = Vec::from(MAGIC.as_slice()); b.extend(self.id.to_le_bytes());
        b.extend((self.name.len() as u16).to_le_bytes()); b.extend((self.values.len() as u16).to_le_bytes()); b.extend(self.name.as_bytes());
        for (key, value) in &self.values { b.extend((key.len() as u16).to_le_bytes()); b.extend((value.len() as u32).to_le_bytes()); b.extend(key.as_bytes()); b.extend(value); }
        b.extend(crc(&b).to_le_bytes()); b
    }
    pub fn decode(b: &[u8]) -> Option<Self> {
        if b.len() < 21 || b.len() > MAX_BYTES + 36 || &b[..8] != MAGIC { return None; }
        let end = b.len() - 4; if crc(&b[..end]) != u32::from_le_bytes(b[end..].try_into().ok()?) { return None; }
        let id = u32::from_le_bytes(b[8..12].try_into().ok()?);
        let n = u16::from_le_bytes(b[12..14].try_into().ok()?) as usize;
        let count = u16::from_le_bytes(b[14..16].try_into().ok()?) as usize;
        let mut at = 16usize.checked_add(n)?; if at > end || count > MAX_RECORDS { return None; }
        let mut profile = Self::new(id, std::str::from_utf8(&b[16..at]).ok()?)?;
        let mut previous = String::new();
        for _ in 0..count {
            if at.checked_add(6)? > end { return None; }
            let kl = u16::from_le_bytes(b[at..at+2].try_into().ok()?) as usize;
            let vl = u32::from_le_bytes(b[at+2..at+6].try_into().ok()?) as usize; at += 6;
            let split = at.checked_add(kl)?; let next = split.checked_add(vl)?; if next > end { return None; }
            let key = std::str::from_utf8(&b[at..split]).ok()?;
            if key <= previous.as_str() || !profile.put(key, &b[split..next]) { return None; }
            previous = key.to_owned(); at = next;
        }
        if at != end { return None; } profile.revision = 0; Some(profile)
    }
}
unsafe fn text<'a>(p: *const u8, n: usize) -> Option<&'a str> {
    if p.is_null() || n == 0 || n > 512 { return None; }
    std::str::from_utf8(unsafe { std::slice::from_raw_parts(p,n) }).ok()
}
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileConfigure(id:u32,name:*const u8,n:usize)->i32 {
    let Some(name)=(unsafe{text(name,n)}) else{return 0}; let Some(new)=Profile::new(id,name) else{return 0};
    let mut s=PROFILE.lock().unwrap(); if let Some(old)=s.as_ref(){return (old.id==id && old.name==name) as i32;} *s=Some(new);1
}
/// A running native engine caches gamer identity. Admission is one lifetime per
/// app process; reconnect must retain its admitted name even while disconnected.
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileRename(name:*const u8,n:usize)->i32 {
    let Some(name)=(unsafe{text(name,n)}) else{return 0};
    let lan=crate::STATE.0.lock().unwrap();
    let mut state=PROFILE.lock().unwrap();let Some(profile)=state.as_mut()else{return 0};
    if profile.name==name { return 1; }
    if lan.epoch!=0 { return 0; }
    profile.rename(name) as i32
}
#[no_mangle]
pub extern "C" fn ZemaProfileReady()->i32 { PROFILE.lock().unwrap().is_some() as i32 }
#[no_mangle]
pub extern "C" fn ZemaProfileId()->u32 { PROFILE.lock().unwrap().as_ref().map_or(0,|s|s.id) }
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileName(out:*mut u8,capacity:usize)->i32 {
    let s=PROFILE.lock().unwrap();let Some(s)=s.as_ref()else{return -1};let n=s.name.len();
    if out.is_null()||capacity<n+1{return -((n+1)as i32);}
    unsafe{std::ptr::copy_nonoverlapping(s.name.as_ptr(),out,n);*out.add(n)=0;}n as i32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileRead(key:*const u8,n:usize,out:*mut u8,capacity:usize)->i32 {
    let Some(key)=(unsafe{text(key,n)}).filter(|k|valid_key(k))else{return -2};
    let s=PROFILE.lock().unwrap();let Some(s)=s.as_ref()else{return -2};let Some(v)=s.get(key)else{return -1};
    if capacity<v.len()||(!v.is_empty()&&out.is_null()){return -3;}
    if !v.is_empty(){unsafe{std::ptr::copy_nonoverlapping(v.as_ptr(),out,v.len());}}v.len() as i32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileWrite(key:*const u8,n:usize,value:*const u8,len:usize)->i32 {
    let Some(key)=(unsafe{text(key,n)})else{return 0};if len>MAX_FILE||(!value.is_null()&&len>isize::MAX as usize)||(value.is_null()&&len!=0){return 0;}
    let bytes=if len==0{&[]}else{unsafe{std::slice::from_raw_parts(value,len)}};
    PROFILE.lock().unwrap().as_mut().is_some_and(|s|s.put(key,bytes)) as i32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileStat(key:*const u8,n:usize)->u64 {
    let Some(key)=(unsafe{text(key,n)}).filter(|k|!k.starts_with("f:")&&valid_key(k))else{return 0};
    PROFILE.lock().unwrap().as_ref().map_or(0,|s|s.stat(key))
}
#[no_mangle]
pub extern "C" fn ZemaProfileDeleteSlot(slot:i32) {if let Some(s)=PROFILE.lock().unwrap().as_mut(){s.delete_slot(slot);}}
#[no_mangle]
pub extern "C" fn ZemaProfileRevision()->u64 {PROFILE.lock().unwrap().as_ref().map_or(0,|s|s.revision)}
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileExport(out:*mut u8,capacity:usize)->i32 {
    let s=PROFILE.lock().unwrap();let Some(s)=s.as_ref()else{return 0};let bytes=s.encode();
    if out.is_null()||capacity<bytes.len(){return -(bytes.len() as i32);}
    unsafe{std::ptr::copy_nonoverlapping(bytes.as_ptr(),out,bytes.len());}bytes.len() as i32
}
#[no_mangle]
pub unsafe extern "C" fn ZemaProfileImport(bytes:*const u8,len:usize)->i32 {
    if bytes.is_null()||len>MAX_BYTES+36{return 0;}
    let Some(profile)=Profile::decode(unsafe{std::slice::from_raw_parts(bytes,len)})else{return 0};
    let mut s=PROFILE.lock().unwrap();if let Some(old)=s.as_ref(){if old.revision!=0||!old.values.is_empty()||old.id!=profile.id||old.name!=profile.name{return 0;}}
    *s=Some(profile);1
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]fn binary_files_stats_identity_roundtrip(){let mut p=Profile::new(123456,"zema").unwrap();assert!(p.put("f:GTA5/char0001.save",&[0,255,128,0]));assert!(p.put("hdeadbeef",&0xff812345u64.to_le_bytes()));let b=p.encode();let r=Profile::decode(&b).unwrap();assert_eq!(r.get("f:GTA5/char0001.save"),Some([0,255,128,0].as_slice()));assert_eq!(r.stat("hdeadbeef"),0xff812345);assert_eq!(r.encode(),b);assert_eq!(r.revision,0);}
    #[test]fn rename_preserves_identity_files_stats_and_snapshot_format(){
        let mut p=Profile::new(123456,"OldName").unwrap();
        assert!(p.put("f:GTA5/char0001.save",&[0,255,128,0,42]));
        assert!(p.put("hdeadbeef",&0xff812345u64.to_le_bytes()));
        let before=p.clone();assert!(p.rename("New Name"));
        assert_eq!(p.id,before.id);assert_eq!(p.values,before.values);assert_eq!(p.bytes,before.bytes);
        assert_eq!(p.revision,before.revision+1);let renamed=p.clone();assert!(p.rename("New Name"));assert_eq!(p,renamed);
        let decoded=Profile::decode(&p.encode()).unwrap();assert_eq!(decoded.id,before.id);assert_eq!(decoded.name,"New Name");assert_eq!(decoded.values,before.values);
        for invalid in ["", "   ", "name\n", "12345678901234567", "é"] {assert!(!p.rename(invalid));assert_eq!(p,renamed);}
        assert!(p.rename("OldName"));assert_eq!(p.encode(),before.encode());
    }
    #[test]fn corruption_refused_without_mutation(){let mut p=Profile::new(123456,"zema").unwrap();p.put("hdeadbeef",&9u64.to_le_bytes());let original=p.clone();let b=p.encode();for n in 0..b.len(){let mut bad=b.clone();bad[n]^=1;assert!(Profile::decode(&bad).is_none());}assert_eq!(p,original);for n in 0..b.len(){assert!(Profile::decode(&b[..n]).is_none());}}
    #[test]fn names_limits_no_path_aliases_and_slot_isolation(){let mut p=Profile::new(123456,"zema").unwrap();for k in ["f:../Story.save","f:/tmp/x","f:a//b","f:.","f:a\\b","hZZZZZZZZ","p32:0","p1:01"]{assert!(!p.put(k,&[0;8]),"{k}");}assert!(!p.put("f:large",&vec![0;MAX_FILE+1]));p.put("p1:10",&7u64.to_le_bytes());p.put("p2:10",&8u64.to_le_bytes());p.delete_slot(1);assert_eq!(p.stat("p1:10"),0);assert_eq!(p.stat("p2:10"),8);assert!(Profile::new(1,"zema").is_none());assert!(Profile::new(123456,"\n").is_none());}
}
