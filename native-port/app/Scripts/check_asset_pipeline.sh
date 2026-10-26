#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p Build/Probe
xcrun clang -std=c11 -O2 -fobjc-arc -fblocks -I Source -I Generated -I Tools/wabt-1.0.42/include \
  -I Tools/wabt-1.0.42/share/wabt/wasm2c -framework Foundation Tests/asset_pipeline.m -o Build/Probe/asset-pipeline
Build/Probe/asset-pipeline
