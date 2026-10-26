# Native iOS source

Native iOS app: version 2.0 / Build 91, minimum iOS / iPadOS 15.0. See [installation](../docs/START-HERE.md) and [sideloading options](../docs/IOS-SIDELOADING.md).

The App/Source trees and EngineLAN adapters are staged by engine-lan/prepare_experimental.py and compiled by build_experimental.py. Build tools require pinned external/generated engine, shader and toolchain inputs; a fresh-machine native build is not yet validated. Do not treat Scripts/build_native.sh alone as a command that reproduces the EngineLAN release. Existing inputs/source are preserved privately, with their build hashes in the release receipts. No commercial game files are included.

Keep the app installed when updating and preserve game archives, saves and exported backups. Upstream source credits remain in LICENSE, app/Resources/Licenses and engine-lan/THIRD_PARTY_NOTICES.md.
