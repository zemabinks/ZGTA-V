# Native startup failure presentation

The supplied iPhone screenshot reports `Native trap 5`. In the staged WABT
runtime, value 5 is `WASM_RT_TRAP_UNREACHABLE`; invalid indirect call is value 6.
A generic trap is recorded before the thread-local trap handler stops the
affected engine thread. Other workers can still render or report readiness.
Continuation after dismissing the alert is therefore not evidence of recovery.

The native launcher previously accepted `First frame` and `WORLD_READY` after
setting `engineFailed`. An animation completion could hide the launcher after a
fatal alert, and touch controls could remain visible over it. The source now
keeps failure terminal: late ready events cannot mark boot stable, restart the
health timer or re-enable controls; pending fade completions check failure;
failure cancels the fade and releases/hides inputs and the FPS display. Per-frame
input polling and pending debug input/capture callbacks also stop after failure.
The real trap remains visible and all subsequent diagnostic lines remain logged.

This corrects contradictory UI state. It does not repair the underlying native
trap or establish that the multiplayer spawn freeze is fixed. Diagnosis still
requires `native-port.log` from the failing run, including lines before the trap,
its native frame addresses and the subsequent thread/boot stop message. The image
base alone cannot identify the failing function. Settings → Share log exports
both the current and previous log; no reinstall or save deletion is needed.

Verification: `tests/test_native_boot_presentation.py` compiles and executes the
actual readiness/failure source block with lightweight UI doubles. It checks
healthy readiness, trap before readiness, trap during a queued animation,
late-ready events, timer invalidation, input visibility and duplicate failure
messages. This is a source-level UI-ordering regression, not an iPhone/Metal or
multiplayer gameplay test. The existing IPA is unchanged; the source correction
will only be present in a future separately packaged build.

## Supplied log identifies the stopped thread's host call

The subsequently supplied `native-port-previous.log` records
`Engine stopped at unported host function: env.__syscall_poll` at line 13881,
then trap 5 and `Native game thread stopped: Unreachable instruction executed`.
This proves that this launch reached a missing poll import; it is no longer just
a screenshot-based hypothesis. Other workers continued printing archive entries.

The LAN select adapters previously waited for any requested datagram and then
called the original engine select. That enters libc select, which constructs
8-byte guest pollfd rows and reaches the missing poll import on iOS. It could
also report unrelated virtual handles ready after the wait. Native and browser
LAN select now derive readiness directly from the bound virtual handle/port
queues. Read sets include only handles with data, write sets include only bound
handles while connected and the outgoing queue has capacity, and exception sets are empty. A handle selected in both
read and write contributes two selected bits, matching the engine's count ABI.
No original select callback is invoked for these virtual handles.

The adapters validate complete 128-byte fd sets, count <= 1024, known handles,
and the existing one-hour bounded timeval contract. Invalid arguments return
`0xffffffff` (-1) without modifying sets; no guessed guest errno is written.
Timeout returns zero with empty sets. Condition/atomic waits wake on actual
packet delivery, a successful drain from a full outgoing queue, or disconnect;
queues are not consumed by select. A fresh memory
view is obtained before output writes after a wait. This is separate from generic
native file-descriptor poll handling; virtual handles and file descriptor IDs
can overlap and must never be confused.

`tests/native_select.c` drives the production Rust C ABI with an original-select
callback that aborts if reached. `tests/browser_state.cjs` exercises the matching
browser behavior. These use synthetic memory and in-process datagrams only;
actual post-spawn iPhone/browser gameplay remains unverified.

## Entropy-device repair and separate Build 29

The same previous log contains 1,415 crypto `InitRng -199` failures. The exact
engine `_InitRng` opens `/dev/urandom`, falls back to `/dev/random`, and reads
52 seed bytes; the both-open-failed branch returns -199. NativeFiles previously
mapped both paths into the private app tree. Only those exact virtual aliases
now open the OS `/dev/urandom` read-only; create/write/truncate attempts fail,
private lookalike files are ignored, and real open/read errors are propagated.
No crypto success flag, key material or pseudo-random fallback is fabricated.

Generic native file `poll` is separate from virtual LAN select. It translates
Emscripten flags to Darwin flags, checks descriptors, duplicates a snapshot
before blocking and releases the descriptor lock during waits. Invalid/negative
entries and timeouts follow poll semantics. Regular files and the exact
nonblocking device aliases have synchronous readiness; pipes use OS readiness.
The isolated stage regenerates typed imports so the old fail-fast poll stub
cannot remain beside the implementation.

Source checks pass: 113 offline tests and 12 Rust unit tests, including actual
C host reads/polls, pipe wait/close/reuse, forbidden entropy writes, matching
browser/native virtual select, queue backpressure and import regeneration.
Build 29 is prepared in a new `EngineLAN-NativeRepair-20261017` output using the
same verified Intel shader/catalog inputs. Build, package and subsequent phone
runtime results are recorded separately; source tests do not prove gameplay.
The current Build 28 IPA and original Intel inputs remain preserved.
