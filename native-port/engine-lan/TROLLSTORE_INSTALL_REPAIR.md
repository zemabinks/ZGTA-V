# Build 29 TrollStore registration repair

The supplied 2026-10-17 18:04 device log reports successful ldid signing and
CoreTrust processing, followed by failed app registration and error 181.
It does not report a runtime crash or a failed memory-entitlement request.

Build 29's ZIP stores `Payload/PlayGTA5Native.app/` with mode 0700. The
previously installed Build 28 stores that root with mode 0755. Both packages'
Info.plists are equal except for the build number. The original Build 29
passed macOS signature verification, which does not establish that iOS can
traverse a root-owned app folder after installation.

[TrollStore's helper](https://github.com/opa334/TrollStore/blob/main/RootHelper/main.m)
uses `fixPermissionsOfAppBundle` to repair the children of the app directory;
its enumerator does not include the app root. Its
[registration implementation](https://github.com/opa334/TrollStore/blob/main/RootHelper/uicache.m)
reports the exact failure shown in the supplied log. The permission defect
is confirmed; its causal role in this device's refusal remains an inference
until the user retries installation.

The repair writes a new `Package-Build29-TrollStoreFix` output under the
isolated `EngineLAN-NativeRepair-20261017` build directory. It changes ZIP
permissions to 0755 for directories/executables and 0644 for resources,
preserving all 54 members' exact contents, bundle ID and Build 29 number.
The original executable, signature, two memory requests and Intel shaders
remain unchanged. The original IPA is preserved. Strict signature validation
on the re-extracted repaired IPA and archive CRC validation pass.

`ipa_permissions.py` now normalizes new package copies before and after
codesign, including the root and newly created signature directory. Both
TrollStore packaging routes call it. Their private output parents remain 0700.
Regression tests cover the root under a private parent, every archive member's
byte identity, executable/resource permissions, symlinks, traversal paths and
existing-output refusal. Four new tests and seven existing native packaging
boundary checks pass. All 46 historical preserved inputs still match their
recorded SHA-256 values.

The supplied log's hash, REA archive identity, exact package digests and
verification limits are recorded in `tests/trollstore_permissions_validation.json`.
The repaired IPA was not installed by the agent; phone registration and
post-spawn multiplayer remain unverified. Retry as an update in TrollStore;
do not delete the app or its game/save data to work around this error.
