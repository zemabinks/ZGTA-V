#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# Fail before generated-source/build writes if the selected Intel cache is bad.
python3 -B Scripts/prepare_shaders.py --check-only --sdk iphoneos
python3 Scripts/generate_imports.py
python3 Scripts/prepare_heap_diagnostics.py
python3 Scripts/prepare_memory_pressure.py
python3 Scripts/prepare_virtual_pad.py
python3 Scripts/prepare_movie_wait.py
python3 Scripts/prepare_missing_txd.py
python3 Scripts/generate_text_labels.py --native-only --check
python3 Scripts/prepare_text_fallback.py
python3 Scripts/prepare_blip_sprites.py
python3 Scripts/prepare_unchecked_memory.py
python3 Scripts/prepare_trap_context.py
python3 Scripts/prepare_scenario_blockers.py
python3 Scripts/prepare_level_index.py
python3 Scripts/prepare_fixup_guard.py
python3 Scripts/prepare_format_strings.py
python3 Scripts/prepare_video_memory.py
python3 Scripts/prepare_plain_dsp.py
python3 Scripts/prepare_plain_shared.py
python3 -B Scripts/prepare_shaders.py --shaders "${PG_SHADER_DIR:-Build/Inputs/shaders}" --sdk iphoneos
xcodegen generate --spec project.yml
xcodebuild -project PlayGTA5Native.xcodeproj -scheme PlayGTA5Native \
  -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' \
  -derivedDataPath Build/Release -jobs 2 \
  CODE_SIGNING_ALLOWED=NO CODE_SIGN_ENTITLEMENTS=App/Free.entitlements \
  PRODUCT_BUNDLE_IDENTIFIER="${BUNDLE_ID:-com.zemabinks.gtamp.englishlab}" \
  GCC_OPTIMIZATION_LEVEL=2 SWIFT_OPTIMIZATION_LEVEL=-O build
