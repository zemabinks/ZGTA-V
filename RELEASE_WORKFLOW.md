# Release workflow

Build and test locally; no paid hosted runners. Freeze the source first. Every installer/package has a SHA-256 checksum and source/build manifest. Compare remote asset bytes and sizes after upload. Keep the README download link, guide, platform matrix and release notes consistent. Preserve game files, saves, original installers and previous private history. Mark untested device behavior as beta/alpha; never infer reboot persistence from an install or launcher check. The native release currently reuses validated generated inputs; fresh-machine native reproducibility remains unverified.

## Required Sileo publication for every native iOS release

A native release is incomplete until `zemabinks/repo` serves the same current IPA through Sileo. Do not report GitHub publication alone as a completed iOS release.

1. Mirror the exact verified IPA and checksum in the owned Sileo repository release. Keep its build, byte count, SHA-256 and source revisions equal to the application release.
2. Increment both installer package versions; stage and build the existing TrollStore and experimental AppSync templates with that IPA's exact URL, size and hash. Preserve installation methods, existing app data and previous package versions.
3. Update the download catalogs, depictions, README, landing page and installation guide together. Keep historical device confirmations labeled with their actual build.
4. Regenerate all package indexes; sign `Release` and `InRelease` with the existing repository key. Verify both signatures, index hashes, archive contents and preserved older package stanzas before publication.
5. Publish the source and release assets, then read back the live GitHub Pages catalogs, signed indexes, packages and IPA bytes. Report the advertised Sileo version and any physical-device checks still pending.

Use the existing key and credentials. Never generate a replacement key, export private keys, install dependencies on a phone, or claim physical installation/gameplay evidence from package fixtures.
