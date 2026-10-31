# Native stipple sources

This project-local tool translates the owner's pinned WGSL shader packs into
MSL for the full-body fallback fade. It does not replace the baseline metallib.
Naga is pinned to 30.0.1 and dependency versions/checksums are in Cargo.lock.

```sh
cargo build --locked --release
cargo test --locked --release
target/release/zgta-stipple-msl /path/to/shaders /path/to/shader-reflection.jsonl /tmp/stipple-sources.jsonl
python3 -B ../../Scripts/prepare_stipple_shaders.py \
  --sources /tmp/stipple-sources.jsonl \
  --reflection /path/to/shader-reflection.jsonl \
  --output /path/to/staged/GeneratedResources
```

Every fragment in the reflection must validate and translate; any failure exits
nonzero without producing a new output. The original group and Metal resource
indices, Tint-compatible `user(locnN)` stage attributes, and immediate-buffer
length offsets are retained. Legacy codes 1–15 preserve the upstream ordered 4-by-4 Bayer pattern.
Codes 16–31 carry bit 4 as an exact-mask flag and bits 0–3 as the owner's
original engine's 2-by-2 phase coverage. The phase is `(x & 1) + 2*(y & 1)`;
a zero phase bit discards. Code 16 is empty, 31 is full and GPU state 0 uses
the baseline shader. The producer derives phase bits from the original
`globalFade` mask and preserves its invert operation, so an existing fade
technique and a fallback technique use complementary pixels during LOD changes.
Function constant 0 specializes the requested code without storing a separate
source for every coverage mask.

The generated pair `shader-stipple-index.json` and
`shader-stipple-sources.bin` must be copied together into the staged native
app's GeneratedResources. Each program is compressed independently; the native
loader maps the blob, then decompresses and compiles only requested fragment
programs. Each resulting Metal library is cached once, and each requested code
is specialized and cached once. Source and compressed-blob hashes are included
for package verification. Baseline level 0 continues using the original
precompiled Metal library.

WGSL validation and MSL generation do **not** prove Metal compilation or visual
correctness. `check_metal.mm` uses the existing Mac Metal API to compile the
actual generated sources and specialize selected legacy and exact-mask codes. This is a Mac
compiler check, not an iPhone execution check:

```sh
xcrun clang++ -std=c++17 -fobjc-arc check_metal.mm -framework Foundation -framework Metal -o /tmp/check-metal
/tmp/check-metal /tmp/stipple-sources.jsonl
```

The native renderer logs and refuses invalid or incomplete sidecars. A failing
requested specialization returns no fragment function; it never silently draws
the fallback at full opacity. Test close/far full-body fading, first-use shader
compile latency and memory on the owner's iPhone before public promotion.

Primary implementation reference: [Glue5 stipple renderer commit
4423eee](https://github.com/mempage4k/glue5/commit/4423eeeac5e3a9086ee02db6d3d420832a85238d).
The platform adapter and shader translator here use the native port's original
reflection ABI instead of importing Glue5's complete GPU runtime.
