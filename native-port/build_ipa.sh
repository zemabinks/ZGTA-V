#!/bin/bash
# Local Intel/free profile, derived from the original Mugoat iOSVN build entry.
# Usage: ./build_ipa.sh --mirror /existing/game/folder [--check-only]
# Optional BUNDLE_ID/JOBS/PYTHON select existing local inputs; no installation.
set -euo pipefail
if [ "${1:-}" != "--mirror" ] || [ -z "${2:-}" ]; then
  echo 'Use --mirror /existing/game/folder [--check-only]; remote fetch and paid profiles are not supported.' >&2
  exit 2
fi
MIRROR="$(cd "$2" && pwd)"
shift 2
CHECK_ONLY=0
if [ "${1:-}" = "--check-only" ]; then CHECK_ONLY=1; shift; fi
if [ "$#" -ne 0 ]; then echo 'Unsupported option; only the local free profile is supported.' >&2; exit 2; fi
cd "$(dirname "$0")/app"
PY="${PYTHON:-/usr/bin/python3}"
JOBS="${JOBS:-2}"
case "$JOBS" in 1|2|3|4) ;; *) echo 'JOBS must be between 1 and 4.' >&2; exit 2 ;; esac
BUNDLE_ID="${BUNDLE_ID:-com.zemabinks.gtamp.englishlab}"
case "$BUNDLE_ID" in vn.iosvn.mugoat|*[^A-Za-z0-9.-]*|.*|*.|*..*|'') echo 'Use a separate valid app bundle identity.' >&2; exit 2 ;; esac
case "$BUNDLE_ID" in *.*.*) ;; *) echo 'Use a separate app bundle identity with at least three components.' >&2; exit 2 ;; esac
if [ "${PG_REUSE_PREPARED:-0}" != "0" ]; then
  echo 'Unchecked old generated engine reuse is not supported for the multiplayer source.' >&2
  exit 2
fi
export CARGO_NET_OFFLINE=true RUSTUP_AUTO_INSTALL=0
export GTA_RUST_TOOLCHAIN="${GTA_RUST_TOOLCHAIN:-$(cd ../../.. && pwd)/gta-intel-toolchain-20261016}"
export CARGO_HOME="$GTA_RUST_TOOLCHAIN/cargo" RUSTUP_HOME="$GTA_RUST_TOOLCHAIN/rustup"
export PATH="$CARGO_HOME/bin:$PATH"
"$PY" -B Scripts/check_intel_build.py --mirror "$MIRROR"
if [ "$CHECK_ONLY" = 1 ]; then exit 0; fi

# Following writes stay in this isolated native-port tree; no original workspace,
# reference app, paid entitlement or hosted runner is used.
mkdir -p Build/Online
IPHONEOS_DEPLOYMENT_TARGET=15.0 cargo build --offline --locked \
  --manifest-path ../online-bridge/Cargo.toml --target-dir "$PWD/Build/Online/RustTarget" \
  --release --lib --target aarch64-apple-ios
cp Build/Online/RustTarget/aarch64-apple-ios/release/libmugoat_online.a Build/Online/
test -s Build/Online/libmugoat_online.a
"$PY" -B Scripts/prepare.py --mirror "$MIRROR"
if [ -n "${GTA_UI_ASSETS_IPA:-}" ]; then
  "$PY" -B Scripts/prepare_ui_assets.py --reference-ipa "$GTA_UI_ASSETS_IPA" --generate-project
fi

RUN="$(mktemp -d "$PWD/Build/English-Intel-Free-XXXXXXXX")"
xcodebuild -project PlayGTA5Native.xcodeproj -scheme PlayGTA5Native \
  -configuration Release -sdk iphoneos -destination 'generic/platform=iOS' \
  -derivedDataPath "$RUN/DerivedData" -jobs "$JOBS" \
  GCC_OPTIMIZATION_LEVEL=2 SWIFT_OPTIMIZATION_LEVEL=-O DEBUG_INFORMATION_FORMAT=dwarf \
  CODE_SIGNING_ALLOWED=NO CODE_SIGN_ENTITLEMENTS=App/Free.entitlements \
  PRODUCT_BUNDLE_IDENTIFIER="$BUNDLE_ID" build > "$RUN/xcodebuild.log" 2>&1 || {
    echo "Build failed; retained log: $RUN/xcodebuild.log" >&2; exit 1;
  }
APP="$RUN/DerivedData/Build/Products/Release-iphoneos/PlayGTA5Native.app"
test -d "$APP"
mkdir -p "$RUN/Package/Payload"
ditto "$APP" "$RUN/Package/Payload/PlayGTA5Native.app"
PACKAGE="$RUN/Package/Payload/PlayGTA5Native.app"
git rev-parse HEAD > "$PACKAGE/zema-build-revision.txt"
cp Resources/manifest.json "$PACKAGE/manifest.json"
# Ad-hoc free metadata; an existing sideload workflow signs for the user later.
# No installation, paid developer profile or provisioning update occurs here.
codesign --force --sign - --entitlements App/Free.entitlements --generate-entitlement-der "$PACKAGE"
(cd "$RUN/Package" && zip -qry "$RUN/Mugoat-English-Intel-Free.ipa" Payload)
echo "Done: $RUN/Mugoat-English-Intel-Free.ipa (device/runtime verification still required)"
