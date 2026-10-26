# Build information

The public source contains the native iOS app, browser host, multiplayer and bridge code, plus local build/test tools. [SOURCE-AUDIT.json](SOURCE-AUDIT.json) records the source snapshot checks. Tests use `ZGTA_GAME_MIRROR` for an external prepared game folder.

The published native app is version **2.0 / Build 91**; browser packages use revision **93**. The original release tag and source archive record the release-time snapshot. Current installation and usage documentation lives on `main`.

A fresh native build needs the pinned matching engine, generated wasm2c inputs, Intel shader cache and toolchain used by the native build scripts. Those generated inputs are not bundled in this source snapshot. The existing native build reused checked inputs; a complete fresh-source native build has not been validated. See [native source](../native-port/README.md) and [release workflow](../RELEASE_WORKFLOW.md).

Browser downloads include their checked Runtime directory and run with matching prepared game files without rebuilding native iOS. Package checksums, source revisions and test results are provided with the [release](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.2). See [verification](VERIFICATION.md) for tested behavior and outstanding tests.

Upstream credits and licenses remain in [LICENSE](../LICENSE), [native-port/LICENSE](../native-port/LICENSE), the bundled Licenses resources and [third-party notices](../native-port/engine-lan/THIRD_PARTY_NOTICES.md).

## Desktop entrypoints

`desktop_launcher.py` copies only verified package-manifest members into an owned per-user folder and creates the Mac `.app` or Windows `.lnk`. It does not copy game files. macOS uses a locally generated app bundle that opens the checked command in Terminal. Windows uses the known Desktop folder and WScript.Shell, with paths passed as environment values. No login item or background service is installed. `--no-desktop` skips desktop setup; `--check` never installs it.

Desktop ICNS/ICO assets come from the existing iOS 1024px AppIcon. Their provenance is recorded in `native-port/engine-lan/desktop-assets/provenance.json`; the ICNS 1024px member retains the exact original PNG bytes. Grand V's launcher and packaging were reviewed at `831c9aefba58aefe5b284106f06bfbf414da7b4a` as a reference. No Grand V code or assets were copied.
