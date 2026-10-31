# Browser character save worker investigation

The real v21 browser trial still created no character file after entering the
world. This supersedes any inference from the synthetic local-gamer fixture:
that fixture proves its scoped fallback behavior, not a successful game save.

The bounded real trace reported queued-operation states 1, 2 and 3, with no
state 4, local-gamer fallback, or member-file write. The error value 404 was
already present after the initial missing-file read; it does not establish a
new save failure. The revised trace names it `last-cloud-error` accordingly.
Private full traces remain in the ignored local evidence folder.

In the pinned engine, state 2 starts `SaveBlockDataThreadFunc` through table
entry 41759; state 3 waits for its block state to become 2 (failed) or 3
(complete). The worker calls `rage::psoBuilder::SaveToBuffer`, optionally
compresses/encrypts the resulting data, then marks completion. The external
active-gamer check investigated previously occurs later, in state 4. It cannot
explain this observed state-3 stall by itself.

The v22 browser stage adds forwarding-only, deduplicated diagnostics at thread
creation, worker entry/return, and builder entry/return. The operation trace
also reports the selected block's state. No filename, pointer, credentials,
stat value or save contents are logged. No engine state is advanced by the
diagnostics. Every original function retains its index and exact original
body as an appended export; only three selected bodies receive typed table
trampolines. All data sections and the offline engine remain unchanged.

These probes are browser LAN only. They do not modify the current IPA, stored
profile format, browser profile, game mirror, or original Intel build inputs.
Runtime character persistence and restoration remain pending. A fresh browser
launch is required to observe which worker boundary is actually reached.

The fresh v22 trial on 18 October reached worker creation and reported a
started thread, then remained at operation state 3 / block state 1. Neither
worker entry nor builder entry was observed. The screenshot confirms the game
is in the world while the badge still reports no character file. The remaining
boundary is thread dispatch/bootstrap before `SaveBlockDataThreadFunc`, not
the durable writer or active-gamer check. This is a narrowed observation, not
a confirmed root cause or a save fix. The private trace is preserved locally.

## v23 inline serialization candidate

An explicit LAN-only metadata flag permits the existing prepared member-save
block to use its original serializer inline, avoiding the unentered thread.
It applies only inside the queued member-save update, for local gamer zero,
prepared interfaces, one of the three pinned block addresses, pending/requested
block state and a non-null, in-bounds buffer of at most 1 MiB. Reentry, ordinary
thread calls, other gamers and other blocks retain their asynchronous path.

It calls the original `SaveBlockDataThreadFunc` and preserves the block state
that function actually produces. It does not fabricate a successful result or
write character bytes itself. The existing queued operation subsequently checks
the serializer result and uses the ordinary durable local file writer. Handle
1 is the engine's existing completed/no-thread sentinel: pinned function 131,
`sysIpcWaitThreadExit`, immediately returns true for that handle. The complete
join body SHA-256 is validated before staging this candidate.

The old stage fails the new dispatch/save fixture; the candidate commits the
original fixture serializer's bytes and profile stats together, preserves
serializer failure/exception behavior, and refuses ineligible contexts. The
pinned engine checks pass; both LAN and offline WASM remain byte-identical to
v22. Only the browser host, callback source and explicit LAN metadata flag
change. The actual game serializer's synchronous frame cost and real character
exit/rejoin remain unverified. No IPA or current save snapshot is replaced.

### Real game result — 18 October 2026

The user reported “Character saved and restored after rejoining.” The bounded
runtime trace now shows the inline serializer entering the worker and builder,
returning success, advancing through operation state 7 with cloud error 0, and
committing real member files (21,664 bytes and a later 51,735 bytes). This closes
the observed browser character-save/rejoin failure for that trial. Private save
contents were not exported or uploaded. Inline serializer frame cost and extended
session stability remain open; this does not establish that every game bug is fixed.
