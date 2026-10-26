#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p Build/Probe
Tools/wabt-1.0.42/bin/wat2wasm --enable-threads Tests/threads64.wat -o Build/Probe/probe.wasm
Tools/wasm2c-native --enable-threads --module-name=probe Build/Probe/probe.wasm -o Build/Probe/probe.c
xcrun clang -std=c11 -O1 -DWASM_RT_USE_MMAP=0 -DWASM_RT_MEMCHECK_BOUNDS_CHECK=1 -DWASM_RT_SKIP_SIGNAL_RECOVERY=1 \
  -I Tools/wabt-1.0.42/include -I Tools/wabt-1.0.42/share/wabt/wasm2c -I Tools/simde -I Source -I Build/Probe \
  -include Source/NativeRuntime.h Tests/native_runtime.c Build/Probe/probe.c Source/WasmFutex.c \
  Tools/wabt-1.0.42/share/wabt/wasm2c/wasm-rt-impl.c \
  Tools/wabt-1.0.42/share/wabt/wasm2c/wasm-rt-mem-impl.c \
  Tools/wabt-1.0.42/share/wabt/wasm2c/wasm-rt-exceptions-impl.c -o Build/Probe/check
Build/Probe/check
