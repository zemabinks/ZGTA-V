# ZGTA 5 versioning

The product is **ZGTA 5**. The current release is **1.1 beta 1**. Sileo uses
`1.1~beta1`, as explicitly chosen by the owner on 1 November 2026.

- Use 1.x for ongoing releases. Reserve 2.0 for a substantial major release.
- During a release's beta cycle, increment beta 1, beta 2 and so on. Once ready,
  release that version without the beta label. Select a new minor version when
  starting the next feature release; do not invent a new major version.
- Use Debian's `~betaN` ordering for Sileo. Do not append `-1`, `-2` or similar
  Debian revision suffixes. Keep internal build counters separate from the
  product version. Fixes require an increasing package version.
- Keep public and private product labels consistent; identify the private
  channel as Dev. A beta label never waives exact-candidate owner testing or
  the final Yes/No public-release choice.
- This naming transition relabels the already tested Build109 release. It does
  not change its IPA, Mac DMG or browser/Windows/Android payloads. Those legacy
  artifacts still carry their original internal filenames/build numbers and,
  where embedded, short version2.0. Do not rewrite signed/tested artifacts merely
  to change their labels. Apply1.1 to future app packaging metadata.
- Preserve previous URLs, tags, checksums, app/package identifiers and historical
  receipts for existing installs and recovery. Current pages use the new label;
  historical evidence retains what was actually built or observed.

Current public release: [ZGTA 5 — 1.1 beta 1](https://github.com/zemabinks/ZGTA-V/releases/tag/v1.1-beta.1).
