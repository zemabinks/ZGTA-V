#![allow(dead_code)]
// muguet - proto.rs
// Constantin Clerc (c22dev) - 0.1

pub const DEFAULT_PORT: u16 = 47520;
pub const MAGIC: u8 = 0x47;
pub const TIMEOUT_SECS: u64 = 5;
pub const MAX_ROOM_PLAYERS: usize = 64;

// A replica's collision/streaming physics is not damage authority. Only a
// confirmed local attack may produce a delta for the owning player's vehicle.
pub fn vehicle_hit_delta(previous: [i16; 3], observed: [i16; 3], local_attack: bool) -> [i16; 3] {
    if !local_attack { return [0; 3]; }
    std::array::from_fn(|k| (previous[k] as i32 - observed[k] as i32).clamp(0, 5000) as i16)
}

pub fn vehicle_hit_targets_current_car(reported: Option<(u32, u32)>, model: u32, entity: u32) -> bool {
    reported == Some((model, entity))
}

#[cfg(test)]
mod vehicle_tests {
    use super::*;
    #[test]
    fn replicas_cannot_destroy_the_owner_by_simulating_a_collision() {
        let mut owner = [1000i16; 3];
        for _ in 0..64 {
            let delta = vehicle_hit_delta([1000; 3], [-4000, 0, -1000], false);
            for k in 0..3 { owner[k] -= delta[k]; }
        }
        assert_eq!(owner, [1000; 3]);
        assert_eq!(vehicle_hit_delta([1000; 3], [950, 900, 1000], true), [50, 100, 0]);
        assert_eq!(vehicle_hit_delta([500; 3], [1000; 3], true), [0; 3]);
        assert_eq!(vehicle_hit_delta([i16::MAX; 3], [i16::MIN; 3], true), [5000; 3]);
    }
    #[test]
    fn old_vehicle_hits_do_not_transfer_to_a_new_vehicle_of_the_same_model() {
        assert!(vehicle_hit_targets_current_car(Some((123, 77)), 123, 77));
        assert!(!vehicle_hit_targets_current_car(Some((123, 77)), 123, 78));
        assert!(!vehicle_hit_targets_current_car(Some((123, 77)), 124, 77));
        assert!(!vehicle_hit_targets_current_car(None, 123, 77));
        let mut wire=Vec::new();State::default().encode(&mut wire);
        assert_eq!(wire.len(), STATE_SIZE);
        assert_eq!(State::decode(&wire).unwrap().veh_key,0);
        wire.extend(1234u32.to_le_bytes()); // existing send timestamp
        wire.extend(77u32.to_le_bytes());   // optional owner-side vehicle handle
        assert_eq!(State::decode(&wire).unwrap().veh_key,77);
    }
    #[test]
    fn voice_chunk_codec_roundtrips() {
        let chunk = VoiceChunk {
            seq: 42,
            pos: [150, -220, 35],
            data: vec![0, 128, 255, 64, 32],
        };
        let mut wire = Vec::new();
        chunk.encode(&mut wire);
        assert_eq!(wire.len(), VOICE_HEADER_SIZE + 5);
        let decoded = VoiceChunk::decode(&wire).expect("decode voice");
        assert_eq!(decoded, chunk);
        assert!(VoiceChunk::decode(&wire[..VOICE_HEADER_SIZE - 1]).is_none());
        assert!(relayed(VOICE));
    }
}

pub const HELLO: u8 = 1;
pub const WELCOME: u8 = 2;
pub const STATE: u8 = 3;
pub const NAME: u8 = 4;
pub const LEAVE: u8 = 5;
pub const BYE: u8 = 6;
pub const FULL: u8 = 7;

pub const LOOK: u8 = 8;

pub const SHOT: u8 = 9;

pub const POP: u8 = 10;

pub const KILL: u8 = 11;

pub const VLOOK: u8 = 12;

pub const TAKEN: u8 = 13;

pub const EXPLODE: u8 = 14;

pub const HIT: u8 = 15;

pub const VHIT: u8 = 16;

pub const TIME: u8 = 17;

pub const POPX: u8 = 18;

pub const REL: u8 = 19;

pub const ACK: u8 = 20;

pub const KILLFEED: u8 = 21;

pub const VCTL: u8 = 22;

pub const VOICE: u8 = 23;

/// Roleplay status, about once a second: [wanted stars 0-5, flags (1 jailed, 2 cuffed)].
pub const ROLE: u8 = 24;
/// Reliable: a police officer arrests [target id, stars].
pub const ARREST: u8 = 25;
/// Reliable: a medic treats [target id].
pub const HEAL: u8 = 26;
/// Reliable, to everyone: a civilian calls the police from [x, y, z] (f32 each).
pub const CALL911: u8 = 27;
/// Reliable: a gang member robs [target id, amount u16].
pub const ROB: u8 = 28;
/// Reliable: the robbed player hands over [robber id, amount u16] (what the wallet really held).
pub const PAID: u8 = 29;

pub const WEATHERS: [&str; 14] = [
    "EXTRASUNNY", "CLEAR", "CLOUDS", "SMOG", "FOGGY", "OVERCAST", "RAIN", "THUNDER",
    "CLEARING", "NEUTRAL", "SNOW", "BLIZZARD", "SNOWLIGHT", "XMAS",
];

pub fn relayed(kind: u8) -> bool {
    !matches!(kind, HELLO | WELCOME | NAME | LEAVE | BYE | FULL)
}

pub const FLAG_IN_VEHICLE: u8 = 1;
pub const FLAG_DEAD: u8 = 2;

pub const FLAG_AIMING: u8 = 4;

pub const FLAG_INSIDE: u8 = 8;

pub const FLAG_RAGDOLL: u8 = 16;

pub const FLAG_ENTERING: u8 = 32;

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct State {
    pub ped_model: u32,
    pub pos: [f32; 3],
    pub heading: f32,
    pub vel: [f32; 3],
    pub flags: u8,
    pub veh_model: u32,
    // Optional STATE trailer after its timestamp; base wire layout is unchanged.
    pub veh_key: u32,
    pub veh_pos: [f32; 3],
    pub veh_rot: [f32; 3],
    pub veh_vel: [f32; 3],

    pub weapon: u32,
    pub health: u16,
    pub armour: u8,

    pub veh_owner: u8,

    pub seat: i8,
    pub veh_colours: [u8; 2],

    pub veh_engine: i16,
    pub veh_body: i16,
    pub veh_tank: i16,

    pub veh_tyres: u8,
    pub veh_windows: u8,

    pub veh_dead: bool,

    pub aim: [f32; 3],
}

pub const STATE_SIZE: usize = 4 + 12 + 4 + 12 + 1 + 4 + 12 + 12 + 12 + 4 + 2 + 1 + 1 + 1 + 2 + 6 + 3 + 12;

impl State {
    pub fn in_vehicle(&self) -> bool {
        self.flags & FLAG_IN_VEHICLE != 0
    }

    pub fn encode(&self, out: &mut Vec<u8>) {
        out.extend(self.ped_model.to_le_bytes());
        for v in self.pos { out.extend(v.to_le_bytes()); }
        out.extend(self.heading.to_le_bytes());
        for v in self.vel { out.extend(v.to_le_bytes()); }
        out.push(self.flags);
        out.extend(self.veh_model.to_le_bytes());
        for v in self.veh_pos.iter().chain(&self.veh_rot).chain(&self.veh_vel) { out.extend(v.to_le_bytes()); }
        out.extend(self.weapon.to_le_bytes());
        out.extend(self.health.to_le_bytes());
        out.extend([self.armour, self.veh_owner, self.seat as u8, self.veh_colours[0], self.veh_colours[1]]);
        for v in [self.veh_engine, self.veh_body, self.veh_tank] { out.extend(v.to_le_bytes()); }
        out.extend([self.veh_tyres, self.veh_windows, self.veh_dead as u8]);
        for v in self.aim { out.extend(v.to_le_bytes()); }
    }

    pub fn aiming(&self) -> bool {
        self.flags & FLAG_AIMING != 0
    }

    pub fn ragdoll(&self) -> bool {
        self.flags & FLAG_RAGDOLL != 0
    }
    pub fn entering(&self) -> bool {
        self.flags & FLAG_ENTERING != 0 && !self.in_vehicle()
    }
    pub fn inside(&self) -> bool {
        self.flags & FLAG_INSIDE != 0
    }
    pub fn dead(&self) -> bool {
        self.flags & FLAG_DEAD != 0
    }

    pub fn decode(b: &[u8]) -> Option<State> {
        if b.len() < STATE_SIZE { return None; }
        let mut at = 0;
        let mut u32_ = || { let v = u32::from_le_bytes(b[at..at + 4].try_into().unwrap()); at += 4; v };
        let ped_model = u32_();
        let pos = [f32::from_bits(u32_()), f32::from_bits(u32_()), f32::from_bits(u32_())];
        let heading = f32::from_bits(u32_());
        let vel = [f32::from_bits(u32_()), f32::from_bits(u32_()), f32::from_bits(u32_())];
        let flags = b[at];
        at += 1;
        let mut u32_ = || { let v = u32::from_le_bytes(b[at..at + 4].try_into().unwrap()); at += 4; v };
        let veh_model = u32_();
        let mut v3 = || [f32::from_bits(u32_()), f32::from_bits(u32_()), f32::from_bits(u32_())];
        let (veh_pos, veh_rot, veh_vel) = (v3(), v3(), v3());
        let weapon = u32_();
        let health = u16::from_le_bytes([b[at], b[at + 1]]);
        let t = &b[at + 2..at + 16];
        let h = |k: usize| i16::from_le_bytes([t[k], t[k + 1]]);
        let a = |k: usize| f32::from_le_bytes(b[at + 16 + k * 4..at + 20 + k * 4].try_into().unwrap());
        let aim = [a(0), a(1), a(2)];
        let s = State {
            ped_model, pos, heading, vel, flags, veh_model, veh_pos, veh_rot, veh_vel,
            veh_key: b.get(STATE_SIZE+4..STATE_SIZE+8).map(|v| u32::from_le_bytes(v.try_into().unwrap())).unwrap_or(0),
            weapon, health, armour: t[0], veh_owner: t[1], seat: t[2] as i8, veh_colours: [t[3], t[4]],
            veh_engine: h(5), veh_body: h(7), veh_tank: h(9), veh_tyres: t[11], veh_windows: t[12], veh_dead: t[13] != 0, aim,
        };
        let finite = s.pos.iter().chain(&s.vel).chain(&s.veh_pos).chain(&s.veh_rot).chain(&s.veh_vel).chain(&s.aim).all(|v| v.is_finite());
        (finite && s.heading.is_finite()).then_some(s)
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Look {
    pub comps: [(u16, u8, u8); 12],
    pub props: [(i16, u8); 5],
}

pub const PROP_SLOTS: [i32; 5] = [0, 1, 2, 6, 7];

impl Look {
    pub fn encode(&self, out: &mut Vec<u8>) {
        for (d, t, p) in self.comps {
            out.extend(d.to_le_bytes());
            out.extend([t, p]);
        }
        for (i, t) in self.props {
            out.extend(i.to_le_bytes());
            out.push(t);
        }
    }
    pub fn decode(b: &[u8]) -> Option<Look> {
        if b.len() < 12 * 4 + 5 * 3 { return None; }
        let mut l = Look::default();
        for (k, c) in l.comps.iter_mut().enumerate() {
            let o = k * 4;
            *c = (u16::from_le_bytes([b[o], b[o + 1]]), b[o + 2], b[o + 3]);
        }
        for (k, p) in l.props.iter_mut().enumerate() {
            let o = 48 + k * 3;
            *p = (i16::from_le_bytes([b[o], b[o + 1]]), b[o + 2]);
        }
        Some(l)
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct VehLook {
    pub model: u32,

    pub extra_colours: [u8; 2],
    pub livery: i8,
    pub window_tint: i8,
    pub wheel_type: i8,

    pub mods: [i8; 50],

    pub toggles: u8,
    pub plate: [u8; 8],

    pub radio: u8,
}

impl Default for VehLook {
    fn default() -> Self {
        VehLook { model: 0, extra_colours: [0; 2], livery: -1, window_tint: -1, wheel_type: -1, mods: [-1; 50], toggles: 0, plate: [0; 8], radio: 255 }
    }
}

pub const VLOOK_SIZE: usize = 4 + 2 + 3 + 50 + 1 + 8 + 1;

impl VehLook {
    pub fn encode(&self, out: &mut Vec<u8>) {
        out.extend(self.model.to_le_bytes());
        out.extend(self.extra_colours);
        out.extend([self.livery as u8, self.window_tint as u8, self.wheel_type as u8]);
        out.extend(self.mods.iter().map(|m| *m as u8));
        out.push(self.toggles);
        out.extend(self.plate);
        out.push(self.radio);
    }
    pub fn decode(b: &[u8]) -> Option<VehLook> {
        if b.len() < VLOOK_SIZE { return None; }
        let mut l = VehLook {
            model: u32::from_le_bytes(b[0..4].try_into().unwrap()),
            extra_colours: [b[4], b[5]],
            livery: b[6] as i8,
            window_tint: b[7] as i8,
            wheel_type: b[8] as i8,
            ..Default::default()
        };
        for (k, m) in l.mods.iter_mut().enumerate() { *m = b[9 + k] as i8; }
        l.toggles = b[59];
        l.plate.copy_from_slice(&b[60..68]);
        l.radio = b[68];
        Some(l)
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Shot {
    pub weapon: u32,
    pub from: [f32; 3],
    pub to: [f32; 3],
}

impl Shot {
    pub fn encode(&self, out: &mut Vec<u8>) {
        out.extend(self.weapon.to_le_bytes());
        for v in self.from.iter().chain(&self.to) { out.extend(v.to_le_bytes()); }
    }
    pub fn decode(b: &[u8]) -> Option<Shot> {
        if b.len() < 28 { return None; }
        let f = |o: usize| f32::from_le_bytes(b[o..o + 4].try_into().unwrap());
        let s = Shot { weapon: u32::from_le_bytes(b[0..4].try_into().unwrap()), from: [f(4), f(8), f(12)], to: [f(16), f(20), f(24)] };
        s.from.iter().chain(&s.to).all(|v| v.is_finite()).then_some(s)
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct PopEntry {
    pub key: u32,
    pub is_vehicle: bool,
    pub model: u32,
    pub driver_model: u32,
    pub pos: [f32; 3],

    pub rot: [f32; 3],
    pub vel: [f32; 3],

    pub dead: bool,

    pub engine: i16,
    pub body: i16,
}

pub const POP_ENTRY_SIZE: usize = 4 + 1 + 4 + 4 + 36 + 5;

pub const POP_MAX: usize = 26;

pub fn encode_pop(entries: &[PopEntry], out: &mut Vec<u8>) {
    let n = entries.len().min(POP_MAX);
    out.push(n as u8);
    for e in &entries[..n] {
        out.extend(e.key.to_le_bytes());
        out.push(e.is_vehicle as u8);
        out.extend(e.model.to_le_bytes());
        out.extend(e.driver_model.to_le_bytes());
        for v in e.pos.iter().chain(&e.rot).chain(&e.vel) { out.extend(v.to_le_bytes()); }
        out.push(e.dead as u8);
        out.extend(e.engine.to_le_bytes());
        out.extend(e.body.to_le_bytes());
    }
}

pub fn decode_pop(b: &[u8]) -> Vec<PopEntry> {
    let Some(&n) = b.first() else { return Vec::new() };
    let mut out = Vec::new();
    for k in 0..n as usize {
        let o = 1 + k * POP_ENTRY_SIZE;
        let Some(e) = b.get(o..o + POP_ENTRY_SIZE) else { break };
        let u = |i: usize| u32::from_le_bytes(e[i..i + 4].try_into().unwrap());
        let f = |i: usize| f32::from_bits(u(i));
        let v3 = |i: usize| [f(i), f(i + 4), f(i + 8)];
        let h = |i: usize| i16::from_le_bytes([e[i], e[i + 1]]);
        let p = PopEntry {
            key: u(0), is_vehicle: e[4] != 0, model: u(5), driver_model: u(9), pos: v3(13), rot: v3(25), vel: v3(37),
            dead: e[49] != 0, engine: h(50), body: h(52),
        };
        if p.pos.iter().chain(&p.rot).chain(&p.vel).all(|v| v.is_finite()) {
            out.push(p);
        }
    }
    out
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct VoiceChunk {
    pub seq: u16,
    pub pos: [i16; 3], // World position in decimeters (coord * 10)
    pub data: Vec<u8>, // Audio samples payload
}

pub const VOICE_HEADER_SIZE: usize = 2 + 6;

impl VoiceChunk {
    pub fn encode(&self, out: &mut Vec<u8>) {
        out.extend(self.seq.to_le_bytes());
        for k in 0..3 {
            out.extend(self.pos[k].to_le_bytes());
        }
        out.extend_from_slice(&self.data);
    }

    pub fn decode(src: &[u8]) -> Option<Self> {
        if src.len() < VOICE_HEADER_SIZE { return None; }
        let seq = u16::from_le_bytes(src[0..2].try_into().ok()?);
        let pos = [
            i16::from_le_bytes(src[2..4].try_into().ok()?),
            i16::from_le_bytes(src[4..6].try_into().ok()?),
            i16::from_le_bytes(src[6..8].try_into().ok()?),
        ];
        let data = src[VOICE_HEADER_SIZE..].to_vec();
        Some(Self { seq, pos, data })
    }
}

pub fn joaat(name: &str) -> u32 {
    let mut h: u32 = 0;
    for c in name.bytes() {
        h = h.wrapping_add(c.to_ascii_lowercase() as u32);
        h = h.wrapping_add(h << 10);
        h ^= h >> 6;
    }
    h = h.wrapping_add(h << 3);
    h ^= h >> 11;
    h.wrapping_add(h << 15)
}

pub fn packet(kind: u8, payload: &[u8]) -> Vec<u8> {
    let mut p = Vec::with_capacity(2 + payload.len());
    p.push(MAGIC);
    p.push(kind);
    p.extend_from_slice(payload);
    p
}

pub fn parse(b: &[u8]) -> Option<(u8, &[u8])> {
    (b.len() >= 2 && b[0] == MAGIC).then(|| (b[1], &b[2..]))
}

pub fn clean_name(raw: &[u8]) -> String {
    let s: String = String::from_utf8_lossy(raw).chars().filter(|c| !c.is_control()).take(24).collect();
    let s = s.trim().to_string();
    if s.is_empty() { "Player".into() } else { s }
}
