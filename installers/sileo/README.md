# Sileo installer source

This is the matching0.107-2 source for the approved ZGTA V2.0 beta3 release. It renders the unchanged Build107 IPA URL, size and SHA-256 into the existing TrollStore/AppSync scripts. The0.107-2 change updates version and description only. Render with `python3 -B tools/build_trollstore_package.py /new/staging/path`, then build that folder with Linux dpkg-deb. AppSync uses `--flavor appsync` and remains an untested rootful experimental route.

No signing key is included. The signed live repository is https://zemabinks.github.io/repo/. Tests use mocked helper/system calls. The owner tested the Build107 app; the new metadata-only wrapper has not been separately installed on a physical phone. Older download confirmations retain their original scope.
