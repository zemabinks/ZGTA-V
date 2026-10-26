"""Let the audio's signal processing compile like native code.

wasm2c turns every ordinary load and store on the engine's shared memory into a relaxed atomic
on a volatile pointer, plus an empty asm that forces the read. Correct for any code, but the
compiler can't vectorise, combine or reorder anything, and a profile of a benchmark on an
iPhone 13 Pro Max put the audio (Opus/Silk/CELT decoding, mixing, reverb, the synthesiser) at
about 37% of the game's CPU time; that heat throttles the phone within minutes.

These functions only transform buffers: they never wait on another thread through an ordinary
load (their synchronisation uses wasm atomics, which stay atomic). Their ordinary loads and
stores become plain memcpy accesses, as the browser's compiler treats them.
"""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[1]
# Function numbers (w2c_game_fN) in the pinned game.wasm, from its name section.
FUNCTIONS = [
    6462,  # rage::audBiquadFilterEffect::Process(rage::audDspEffectBuffer&)
    6463,  # rage::audBiquadFilterEffect::ProcessInterleaved_4Pole(float vector[4],
    6464,  # rage::audBiquadFilterEffect::ProcessInterleaved_2Pole(float vector[4],
    6466,  # rage::audDelayEffect::Process(rage::audDspEffectBuffer&)
    6474,  # rage::audDelayEffect4::Process(rage::audDspEffectBuffer&)
    6479,  # rage::audEarlyReflectionEffect::Process(rage::audDspEffectBuffer&)
    6480,  # rage::audEarlyReflectionEffect::ProcessInterleaved(float const*, float
    6487,  # rage::audReverbEffect4::Process(rage::audDspEffectBuffer&)
    6488,  # rage::audReverbEffect4::ProcessInterleaved(float const*, float*, unsig
    6493,  # rage::audUnderwaterEffect::Process(rage::audDspEffectBuffer&)
    6494,  # rage::audUnderwaterEffect::ProcessInterleaved(float const*, float*, un
    6498,  # rage::audVariableDelayEffect::Process(rage::audDspEffectBuffer&)
    7150,  # rage::synthCore::GenerateFrame(float const**, rage::atRangeArray<unsig
    7164,  # rage::synthCoreDspEffect::Process(rage::audDspEffectBuffer&)
    7266,  # rage::audMixerDevice::MixBuffers()
    7271,  # void rage::InterleaveAndMix_1to4<256u>(float vector[4], float vector[4
    7299,  # rage::audRateConvertorLinear::Process(float, float*, short const*, uns
    7341,  # rage::audMixerSubmix::ConvertBufferToFormat(rage::audDspEffectBuffer&,
    90152,  # silk_bwexpander_32
    90153,  # silk_LPC_inverse_pred_gain_c
    90154,  # silk_NLSF2A
    90155,  # silk_bwexpander
    90156,  # silk_LPC_analysis_filter
    90157,  # silk_sum_sqr_shift
    90158,  # silk_PLC
    90159,  # silk_reset_decoder
    90160,  # silk_resampler_private_up2_HQ
    90161,  # silk_resampler_private_IIR_FIR
    90162,  # silk_resampler_private_down_FIR
    90163,  # silk_resampler
    90164,  # ec_dec_init
    90165,  # ec_decode
    90166,  # ec_dec_update
    90167,  # ec_dec_bit_logp
    90168,  # ec_dec_icdf
    90169,  # ec_dec_uint
    90170,  # ec_dec_bits
    90171,  # silk_stereo_decode_pred
    90172,  # silk_stereo_decode_mid_only
    90173,  # silk_NLSF_unpack
    90174,  # silk_decode_indices
    90178,  # silk_decode_pulses
    90179,  # silk_decode_frame
    90180,  # silk_Get_Decoder_Size
    90181,  # silk_ResetDecoder
    90182,  # comb_filter
    90184,  # unquant_energy_finalise
    90185,  # exp_rotation
    90186,  # renormalise_vector
    90188,  # denormalise_bands
    90189,  # quant_band
    90191,  # quant_partition
    90193,  # _celt_lpc
    90194,  # _celt_autocorr
    90195,  # celt_pitch_xcorr_c
    90196,  # clt_mdct_backward_c
    90197,  # celt_decoder_get_size
    90199,  # celt_decode_with_ec_dred
    90200,  # deemphasis
    90202,  # celt_synthesis
    90203,  # celt_decode_with_ec
    90205,  # opus_decode_frame
    90808,  # lrint
    90809,  # lrintf
]
LOAD = re.compile(r'\b((?:i32|i64|f32|f64)_load(?:8_s|8_u|16_s|16_u|32_s|32_u)?|v128_load)_shared\(')
STORE = re.compile(r'\b((?:i32|i64|f32|f64)_store(?:8|16|32)?|v128_store)_shared\(')
HEADER = '''// Included right after the file's game-impl header (which has no include guard).
#include <string.h>
// Plain (non-atomic, non-volatile) ordinary accesses for the audio DSP (Scripts/prepare_plain_dsp.py).
// PG_ATOMIC_DSP=1 builds keep wasm2c's atomic accesses there, for comparisons.
#if PG_ATOMIC_DSP
#define PG_PLAIN_LOAD(name, t1, t2, t3) static inline t3 name##_plain(uint8_t* const base, uint64_t size, wasm_rt_shared_memory_t* mem, u64 addr) { return name##_shared(base, size, mem, addr); }
#define PG_PLAIN_STORE(name, t1, t2) static inline void name##_plain(uint8_t* const base, uint64_t size, wasm_rt_shared_memory_t* mem, u64 addr, t2 value) { name##_shared(base, size, mem, addr, value); }
#define v128_load_plain v128_load_shared
#define v128_store_plain v128_store_shared
#else
#define PG_PLAIN_LOAD(name, t1, t2, t3) static inline t3 name##_plain(uint8_t* const base, uint64_t size, wasm_rt_shared_memory_t* mem, u64 addr) { \\
  (void)base; (void)size; t1 value; memcpy(&value, (const void*)(uintptr_t)MEM_ADDR(mem, addr, sizeof(t1)), sizeof(t1)); return (t3)(t2)value; }
#define PG_PLAIN_STORE(name, t1, t2) static inline void name##_plain(uint8_t* const base, uint64_t size, wasm_rt_shared_memory_t* mem, u64 addr, t2 value) { \\
  (void)base; (void)size; t1 wrapped = (t1)value; memcpy((void*)(uintptr_t)MEM_ADDR(mem, addr, sizeof(t1)), &wrapped, sizeof(t1)); }
static inline v128 v128_load_plain(uint8_t* const base, uint64_t size, wasm_rt_shared_memory_t* mem, u64 addr) {
  (void)base; (void)size; return simde_wasm_v128_load((const void*)(uintptr_t)MEM_ADDR(mem, addr, 16)); }
static inline void v128_store_plain(uint8_t* const base, uint64_t size, wasm_rt_shared_memory_t* mem, u64 addr, v128 value) {
  (void)base; (void)size; simde_wasm_v128_store((void*)(uintptr_t)MEM_ADDR(mem, addr, 16), value); }
#endif
PG_PLAIN_LOAD(i32_load, u32, u32, u32) PG_PLAIN_LOAD(i64_load, u64, u64, u64) PG_PLAIN_LOAD(f32_load, f32, f32, f32) PG_PLAIN_LOAD(f64_load, f64, f64, f64)
PG_PLAIN_LOAD(i32_load8_s, s8, s32, u32) PG_PLAIN_LOAD(i64_load8_s, s8, s64, u64) PG_PLAIN_LOAD(i32_load8_u, u8, u32, u32) PG_PLAIN_LOAD(i64_load8_u, u8, u64, u64)
PG_PLAIN_LOAD(i32_load16_s, s16, s32, u32) PG_PLAIN_LOAD(i64_load16_s, s16, s64, u64) PG_PLAIN_LOAD(i32_load16_u, u16, u32, u32) PG_PLAIN_LOAD(i64_load16_u, u16, u64, u64)
PG_PLAIN_LOAD(i64_load32_s, s32, s64, u64) PG_PLAIN_LOAD(i64_load32_u, u32, u64, u64)
PG_PLAIN_STORE(i32_store, u32, u32) PG_PLAIN_STORE(i64_store, u64, u64) PG_PLAIN_STORE(f32_store, f32, f32) PG_PLAIN_STORE(f64_store, f64, f64)
PG_PLAIN_STORE(i32_store8, u8, u32) PG_PLAIN_STORE(i32_store16, u16, u32) PG_PLAIN_STORE(i64_store8, u8, u64) PG_PLAIN_STORE(i64_store16, u16, u64) PG_PLAIN_STORE(i64_store32, u32, u64)
'''
wanted = set(FUNCTIONS)
patched = 0
for path in sorted((root / 'Generated').glob('game_*.c')):
    s = path.read_text()
    changed = False
    for found in list(re.finditer(r'^[a-z0-9]+ w2c_game_f(\d+)\(w2c_game\* instance[^\n]*\{$', s, re.M)):
        if int(found.group(1)) not in wanted: continue
        start = s.index(found.group(0))
        end = s.index('\n}\n', start)
        body = s[start:end]
        new = STORE.sub(r'\1_plain(', LOAD.sub(r'\1_plain(', body))
        if new != body:
            s = s[:start] + new + s[end:]; changed = True; patched += 1
        wanted.discard(int(found.group(1)))
    if changed:
        include = '#include "game-plain-impl.h"'
        if include not in s:
            first = re.search(r'^#include "game-[a-z-]*impl\.h"$', s, re.M)
            s = s[:first.end()] + '\n' + include + s[first.end():]
        path.write_text(s)
(root / 'Generated/game-plain-impl.h').write_text(HEADER)
print(f'plain DSP: {patched} functions patched, {len(FUNCTIONS)} pinned')
