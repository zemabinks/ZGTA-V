# Native profile startup correction — build 28

The first home test showed a pre-connection profile error. The human confirmed
an older lab build was installed; the screenshot's setup text also predates
build 26. This does not establish the exact phone-side filesystem failure.
The human later reported the same error with build 27; phone-side verification
therefore remains open and is not dismissed as an old-build-only problem.

Independent Mac reproduction found a defect still present in build 27:
`FileManager` supplies a Documents-style path through `/var`, and Foundation's
`resolvingSymlinksInPath()` can retain that system alias. The subsequent strict
profile constructor rejects `/var` as a symlink before any network connection.
The production class reproduced `Failure.symlink("var")` with disposable files.
Earlier tests supplied an already canonical `/private/var/...` fixture and did
not exercise this app-entry path.

Build 28 canonicalizes only the OS-supplied app Documents anchor with POSIX
`realpath`, then appends the same fixed `zema-engine-lan-profile-v1` child. It
does not resolve the profile directory or files, change ownership/permissions,
delete a profile, fall back to a backup, or create a different save store.
All existing no-symlink, ownership, mode, integrity, conflict and durability
checks remain in place. Missing/non-file Documents roots fail closed.

The native setup and error titles now show the actual bundle build number.
Profile failures distinguish unsafe paths, unsafe metadata, corruption, changed
files, storage access and disk-operation failures without exposing full paths.
If the phone still fails after updating, the build 28 error is the next evidence
to collect; no device success is claimed from a Mac fixture.

Validation covers five new app-Documents path tests, eight existing native save
and cross-runtime callback tests, five feature-retention tests, three launch-mode
tests and six save/reconnect safety tests: 27 targeted Python tests. These include
actual create/commit/new-process reopen through the system alias, a preserved
Story sentinel, linked-profile/file refusal, nonprivate-mode refusal and missing
or non-file root refusal. Build 27's historical broader test evidence remains
unchanged; the transport/browser implementation is unchanged in this correction.

The separate output is `Package-ProfileStartup-20261017`, build 28, using the
same lab bundle ID and staged Intel Metal/UI caches. Earlier packages and the
original Intel folder remain preserved. The browser stays on validated v5.
Update the existing lab app through TrollStore while retaining its data; do not
delete the old app or any saves to work around this error. Actual Wi-Fi play,
phone profile startup and Tailscale remain pending real device verification.
