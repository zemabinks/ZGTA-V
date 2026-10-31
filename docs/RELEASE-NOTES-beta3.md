# ZGTA V 2.0 beta 3

[Downloads](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.3) · [Installation](START-HERE.md)

**iOS 107 · Mac DMG 107.1 · Browser 107 · Mac relay controls 1.1**

## What changed

- **More reliable rendering:** fixed buildings flickering or disappearing at
  certain camera angles. The previously affected scene was retested on iPhone.
- **Memory controls for different devices:** Automatic, Standard and Reduced
  memory management are separate from graphics presets, resolution and FPS.
  Reduced mode uses fewer background prefetch jobs and releases completed idle
  graphics storage earlier. Higher-memory devices retain their Standard policy.
- **Heat protection and diagnostics:** frame-rate safeguards preserve saved
  settings, and reports distinguish active session settings from pending changes.
- **LAN server browsing:** discover nearby ZGTA hosts using their announced
  port. Updated managed Mac servers remain visible with zero players, so the
  first player can select the room without entering its address manually.
- **Cleaner settings:** browser Graphics, Controls, Mods, Saves and Support are
  integrated pages under one main navigation. iPhone preset descriptions and
  Find Lobby artwork are corrected.
- **Mac installation:** a new DMG lets you drag ZGTA V into Applications. The
  launcher includes its Python runtime; Chrome and your compatible game files
  are still required.

## Updating and current limits

- Keep your existing game files and saves. Install the app update over the
  existing app; do not remove its data to update.
- LAN discovery requires a compatible host announcement and local-network
  access. Existing managed Mac hosts need relay controls1.1 or a ZRemote bundle
  containing the updated helper. This is not a public worldwide server list;
  Tailscale remains a private invite/address connection.
- Reduced-memory improvements have not yet been benchmarked on a physical
  3 GB iPhone SE2020. There is no promise of stable 60 FPS on every device.
- Windows and Android receive the shared browser changes, but execution on
  those devices has not been tested. Android remains a Termux/browser package,
  not an APK.
- The Mac app is ad-hoc signed and is not Apple-notarized. Intel execution was
  checked; the bundled Apple Silicon runtime still needs execution testing.
- This remains a beta. Your own compatible game files are required; no
  commercial game content is included.
