# Host broadcast capacity candidate 96

The host can exhaust the 7500- and 4000-unit broadcast pools as a second player joins or a small job starts. Apply Glue5's revised, bounded sizing: 7500-unit instances from 2 to 3 and 4000-unit instances from 4 to 6. Preserve the other host pools and existing player-pool adjustments.

Reference: https://github.com/mempage4k/glue5/commit/5d761642efbb5d73dbc056dc04ffa0748df89b61

The change adds 31,024 bytes of payload capacity using upstream's two-byte units and per-buffer header model. This is a sizing calculation, not measured heap consumption. It deliberately excludes the superseded broad pool increases.

Native and browser patch only in-memory configuration, retain exact byte length, preserve larger custom counts and reject incomplete or ambiguous input transactionally. Original game files and saves are not rewritten.

Verification: focused C/Python parity, actual local XML, HTTP range/batch overlay, larger custom counts, unrelated pool preservation, idempotence and malformed-input refusal pass. New-build paired gameplay and small-job crash reproduction remain separate runtime checks; this candidate does not claim those have passed.

Preserved baseline: iPhone Build91 archive access and current browser Build95.1 desktop launcher.
