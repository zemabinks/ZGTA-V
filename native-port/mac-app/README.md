# Mac disk image candidate

`build_mac_dmg.py` wraps the frozen Build109 portable payload in a native universal
AppKit application. The DMG contains ZGTA V.app and an Applications shortcut.
The user drags the app to Applications and opens it there. No Python installer,
Terminal window, login item or new service is required. Chrome and the owner's
compatible game mirror remain separate requirements.

Both pinned Astral Python Build Standalone runtimes are bundled, with their
license texts. The Intel runtime is executed during local verification; Apple
Silicon execution needs that hardware. The native executable contains both CPU
architectures. macOS13 or newer is the packaging target, not a promise that every
Mac GPU supports the game's required WebGPU features.

The existing private `~/.local/share/ZGTA-V` data folder is reused. First launch
offers a native folder picker when no game folder is configured. The app serves
the same loopback origin, preserving browser storage. A matching running host
can be reused. A different or unidentified running version produces a visible
message; it is never silently replaced or presented as the new build. Quitting
the app interrupts only a helper it created, not an existing reused host.

The payload is verified before use and stays byte-identical to the published
Build109 package. Wrapper source and runtime pins have their own receipt; this
does not rebuild or modify the iOS candidate or the browser renderer.

This private candidate is ad-hoc signed, not Developer ID signed or Apple
notarized. Gatekeeper settings are never changed. Normal public distribution
needs the appropriate signing/notarization and owner testing; no new paid account
or credentials are configured by this builder.

Build from clean committed source, passing the checked portable payload folder,
a new output directory and a runtime download cache:

    python3 -B native-port/mac-app/build_mac_dmg.py --payload /path/to/ZGTA-V --output /path/to/new-output --cache /path/to/download-cache

The receipt records wrapper and payload source revisions separately. Check the
DMG by mounting read-only, verifying the copied app and bundled runtime, and
running the copied app's `--verify-payload` command. The normal UI and physical
gameplay still need owner checks. `--render-preview /path/to/image.png` captures
the production AppKit view for layout review without starting the host.
