# Browser trainer contract

This module uses the existing native host's source-defined controller cheat sequences and typed vehicle-spawn commands. It runs from the engine's post-controller-update callback, before UpdateDebug. It does not inject arbitrary console text, execute user JavaScript or write save/storage files.

`ZemaTrainer.createShared()` creates a separate 512-byte SharedArrayBuffer. The page publishes one validated command at a time with `request(buffer, {type: 'cheat', code})` or `request(buffer, {type: 'spawn', model})`. Each engine instance invokes `apply(memory, exports, buffer, mode, pad)`. The atomic acknowledgement grants each command to one engine-thread instance. `cancel(buffer)` cancels unclaimed commands immediately and requests release of running commands; call it when game input loses focus or the page closes. A running command's cancellation is consumed on the next engine callback; a stalled engine cannot release its pad immediately. Pad buttons, axes, triggers and the input-device selector use atomic shared-memory stores matching the native host.

Only `story`, `sandbox` and `freeroam` modes accept trainer commands. Engine LAN, multiplayer and unknown modes refuse them. No automatic trainer action occurs at launch. The browser overlay must label commands as experimental and warn that offline cheat effects can affect the current game session.

The first eight shared signed 32-bit words are sequence, command (1 cheat / 2 spawn), argument (catalog index / model hash), result, acknowledged sequence, detail, engine-hook-ready and cancellation counter. Results: 0 queued, 1 running, 2 delivered/created, -1 invalid request, -2 disabled online, -3 unavailable/native failure, -4 timed out, -5 cancelled. For cheats, result 2 means the complete button sequence was delivered, **not** that the game accepted its effect. For spawns, detail holds the returned vehicle handle. Hook-ready indicates only that the callback ran.

The 29 unique cheat sequences come from `native-port/app/Source/EngineHost.c`'s `pg_gamepad_cheats`. They keep its 100 ms initial release, 90 ms press and 60 ms release cadence, followed by a 400 ms final release. The native `SNOW` entry is the same sequence as weather cycling and is not exposed as a separate guaranteed snow feature. Native `VINEWOOD` declares ten entries but initializes nine; this implementation sends its nine actual nonzero entries. `UNFREEZE`, `DEATHCAR`, `BUBBLES` and `EXTINCT` have no source pad sequence and are not claimed as implemented cheats. A matching available vehicle can instead be requested by its model name.

Vehicle spawning follows `pg_process_vehicle_spawn`: borrow the `main` script's active-thread identity (or a named running script in Free Roam), request the model, wait across engine callbacks, obtain the player's coordinates and heading, create a vehicle ahead, retry once at a slightly higher position, leave the previous vehicle, seat the player and turn on its engine. The original active-script pointer is restored even when an export throws. The model wait expires after 30 seconds. One reusable 64-byte engine allocation stores the two native `scrVector` values. Model names do not install assets; absent DLC or mod vehicles may time out.

Required existing-engine export aliases use `zema:features:` plus:

| Alias | WASM signature |
| --- | --- |
| PlayerPedId | () → i32 |
| RequestModel | (i32) → void |
| HasModelLoaded | (i32) → i32 |
| GetEntityCoords | (i64, i32, i32) → void |
| GetEntityHeading | (i32) → f32 |
| CreateVehicle | (i32, i64, f32, i32, i32, i32) → i32 |
| IsPedInAnyVehicle | (i32, i32) → i32 |
| GetVehiclePedIsIn | (i32, i32) → i32 |
| TaskLeaveVehicle | (i32, i32, i32) → void |
| ClearPedTasksImmediately | (i32) → void |
| SetPedIntoVehicle | (i32, i32, i32) → void |
| SetVehicleEngineOn | (i32, i32, i32, i32) → void |
| malloc | (i64) → i64, existing operator new / f100 |
| tls-base | existing i64 `__tls_base` global |

The callback and pinned extension must preserve all original engine function indices. Shared offsets (pad 12840656, input-device 24627136, script list 15409704/count 15409712 and TLS active script +3088) are specific to the reviewed engine, not a portable version-independent API.

`tests/trainer_fixture.cjs` checks shared-memory sequencing, typed calls and safe failure paths. It does not establish physical controller, game-rendering, cheat-effect or phone-to-browser multiplayer success.
