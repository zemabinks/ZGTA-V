# Restore Story and Free Roam alongside Engine LAN

The build 21–23 experimental stage incorrectly replaced the two-mode HomeView
with a single Engine LAN card and required LAN readiness for every launch. The
original offline game paths were still in source, but this staged launcher made
them inaccessible. Build 24 restores the two cards and adds an optional third
**Engine LAN** card. Free Roam is the existing Sandbox engine start mode, not a
new game mode. The three touch appearances and selector styling fix are retained.

LAN selection is process-local and does not overwrite the saved Story/Free Roam
preference. The original start values remain Story=1 and Free Roam=2; Engine LAN
uses the required online-entry value 1 without persisting it as the offline
choice. Invalid card indices cannot index outside GameMode.allCases. The setup
button selects LAN explicitly; selecting an offline card disconnects prelaunch
LAN transport. Fresh launches honor the saved offline mode instead of reconnecting
automatically. Changing a running game's mode requires an app restart.

Offline starts keep `-nonetwork`, skip online host attachment and use the
generated callback adapter's existing original-function fallback. LAN command
arguments, shared-network threads, profile hooks and gameconfig overlay apply
only to an explicitly selected LAN boot. Connecting a relay alone cannot turn
an offline selection into LAN, and losing that connection cannot turn a running LAN game into
offline mode. The native launch-mode gate is immutable once committed immediately
before engine startup. It refuses LAN without validated readiness.

The lab disables the old snapshot multiplayer bridge for that launch through its
configuration API using an empty endpoint; it does not rewrite the saved bridge
settings or connect a second backend. Staged online UI/cheat checks include the
actual LAN mode and ignore stale legacy preferences. Standard application source,
legacy configuration defaults and all original game C files remain unchanged.

Three new offline tests exercise the actual native mode gate in fresh processes,
the production Swift launch-choice helper, and the reviewed staged controller
routes. They cover offline boot with zero relay-readiness calls, refusal of an
unready LAN boot, saved start values, invalid indices, explicit LAN selection,
restart defaults, legacy online detection and stable mode across disconnects.
The existing 85 Python app tests and 8 experimental integration tests also pass,
including adapter original fallback and checked dispatch. Exact source/log hashes
are in `tests/launch_modes_validation.json`. Actual on-phone loading/gameplay in
each mode remains unverified; this is not a claim that the underlying game's
Story progress or paired multiplayer has passed a device test.

Build 24 is packaged separately under `Package-Modes-20261016`, using the existing
isolated Intel setup and pinned shader/UI caches. Previous packages, the original
English IPA and original Intel folder are preserved. No installation, phone
access, public service, hosted workflow, paid tool or billing change is involved.
Build/package receipts next to the ignored IPA establish exact source and archive
integrity separately from fixture results. Rollback is to keep a preserved prior
IPA; do not delete saves or working apps to troubleshoot a lab launch.
