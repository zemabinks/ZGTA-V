#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
simulator_id=${SIMULATOR_ID:?set SIMULATOR_ID to your simulator (xcrun simctl list devices)}
xcrun simctl boot "$simulator_id" 2>/dev/null || true
xcrun simctl bootstatus "$simulator_id" -b
xcrun simctl install "$simulator_id" Build/Simulator/Build/Products/Release-iphonesimulator/PlayGTA5Native.app
open -a Simulator --args -CurrentDeviceUDID "$simulator_id"
SIMCTL_CHILD_JSC_useJIT=false SIMCTL_CHILD_JSC_useRegExpJIT=false xcrun simctl launch --terminate-running-process "$simulator_id" io.github.playgta5ios.app --boot-engine --capture-world "$@"
