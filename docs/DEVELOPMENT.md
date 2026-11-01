# Current beta4 source and package identity

The owner approved public publication on 1 November 2026 after exact Build 109 iPhone/Mac voice tests. iOS/browser source is `3648065f50928fb8cd147d04bb17363f4b1e4b05`; Mac 109.1 wrapper source is `4bbf3dfb9dbbb51b1a42b68111fd2e9664054cf2`. [SOURCE-AUDIT.json](SOURCE-AUDIT.json) maps the curated public snapshot to those frozen inputs.

The five application downloads preserve their approved bytes. Their internal build manifests and START HERE files can identify the original private development provenance; public updates and current instructions are the links in this public repository. No private login is required to use the published packages. Installer1.1~beta1 changes the public download metadata while pinning that same IPA.

No private Git history, raw phone logs, recorded voice, active-controller captures, signing keys or game data are exported. Production source units and packaged helpers are byte-preserved; limited test/provenance examples use neutral addresses. The original SOURCE_VERSION record remains historical.

## Historical source notes

# Build information

The public source contains the native iOS app, browser host, multiplayer and bridge code, plus local build/test tools. [SOURCE-AUDIT.json](SOURCE-AUDIT.json) records the source snapshot checks. Tests use `ZGTA_GAME_MIRROR` for an external prepared game folder.

The product release is **ZGTA 5 — 1.1 beta 1**. The unchanged tested native/browser payload is internal Build109 and the Mac wrapper109.1; managed relay controls remain1.1. Older embedded app short version2.0 is historical artifact metadata, not the current product version. The original release tag and source archive record the release-time snapshot. Current installation and usage documentation lives on `main`.

A fresh native build needs the pinned matching engine, generated wasm2c inputs, Intel shader cache and toolchain used by the native build scripts. Those generated inputs are not bundled in this source snapshot. The existing native build reused checked inputs; a complete fresh-source native build has not been validated. See [native source](../native-port/README.md) and [release workflow](../RELEASE_WORKFLOW.md).

Browser downloads include their checked Runtime directory and run with matching prepared game files without rebuilding native iOS. Package checksums, source revisions and test results are provided with the [release](https://github.com/zemabinks/ZGTA-V/releases/tag/v2.0.0-beta.3). See [verification](VERIFICATION.md) for tested behavior and outstanding tests.

Upstream credits and licenses remain in [LICENSE](../LICENSE), [native-port/LICENSE](../native-port/LICENSE), the bundled Licenses resources and [third-party notices](../native-port/engine-lan/THIRD_PARTY_NOTICES.md).

## Desktop entrypoints

`desktop_launcher.py` copies only verified package-manifest members into an owned per-user folder and creates the Mac `.app` or Windows `.lnk`. It does not copy game files. macOS uses a locally generated app bundle that opens the checked command in Terminal. Windows uses the known Desktop folder and WScript.Shell, with paths passed as environment values. No login item or background service is installed. `--no-desktop` skips desktop setup; `--check` never installs it.

Desktop ICNS/ICO assets come from the existing iOS 1024px AppIcon. Their provenance is recorded in `native-port/engine-lan/desktop-assets/provenance.json`; the ICNS 1024px member retains the exact original PNG bytes. Grand V's launcher and packaging were reviewed at `831c9aefba58aefe5b284106f06bfbf414da7b4a` as a reference. No Grand V code or assets were copied.

## Beta 3 source identity

The tested iOS/browser payload derives from `ad973f1beb1584c2cc9ea952c53bd979d8fee60a`; the Mac wrapper from `37c5050a75ff45ccb59da3cea9e0dbe4079ddee9`; the relay-only update from `246aece16d0df4b77563c395fe9fbfb0628f6864`. The public snapshot preserves production source bytes while replacing private addresses in test fixtures and the local tool provenance path. Raw phone logs and earlier private audit history are omitted.

The downloadable IPA, DMG and three portable ZIPs retain their owner-tested bytes. Their original build manifests and START HERE files may identify the private development build origin. Public update downloads and current installation instructions are the links in this repository. The relay controls ZIP is the separately checked 1.1 update.
