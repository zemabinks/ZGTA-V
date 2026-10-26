# Sileo installer source

This is the exact0.91-1 source from Zema’s Repo. It renders the pinned Build91 download, size and SHA-256 into postinst. Templates and installer test interfaces are preserved. Render with `python3 -B tools/build_trollstore_package.py /new/staging/path`, then build the staging folder with Linux dpkg-deb. AppSync uses `--flavor appsync` and remains an untested rootful experimental route. No signing key is included; the signed live repository remains https://zemabinks.github.io/repo/. Tests use mocked helper/system calls, not a physical phone.
