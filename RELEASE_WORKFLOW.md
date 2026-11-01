# ZGTA 5 development and release workflow

## Development and public-release rule — owner instruction, 27 October 2026

This rule supersedes any earlier wording that automatically publishes every native build or treats keeping GitHub updated as permission to promote a development candidate.

- Continue authorized implementation, automated checks, builds, private candidate packages, private source pushes and progress records without routine approval questions. Use `zemabinks/ZGTA-V-Private-Development` for unfinished work.
- Keep untested application code and packages out of `zemabinks/ZGTA-V` and the public Sileo repository `zemabinks/repo`, including public branches, pull requests, draft releases and prereleases. A prerelease label is not a substitute for this rule.
- Identify when a candidate is almost ready and tell the owner what changed, which checks pass and what still needs their testing. Prepare the concrete candidate privately before requesting a test.
- Before offering public promotion, complete the applicable local checks and obtain the owner's test result for the exact candidate on every relevant platform/device they own: iPhone/iOS and Mac/browser. Verify affected startup, saves, mods and paired multiplayer behavior as appropriate to the change; do not equate packaging or mocked tests with physical gameplay. A materially changed binary/source invalidates affected prior test evidence.
- Windows and Android are explicit exceptions to owner hardware testing because the owner does not own those devices. Still perform available package/static/shared-code checks, disclose untested platform execution and do not claim universal compatibility. This exception does not waive iPhone or Mac testing.
- When the candidate is ready, present one yes/no choice identifying the exact build and test summary: **Publish this build to the public ZGTA 5 repo and matching Sileo source?** Offer **Yes — publish** and **No — keep in development**. Wait for an actual answer. Generic requests to continue, fix, build, update GitHub or keep repositories current do not authorize public promotion.
- A yes authorizes the complete matching release transaction: approved source/packages, public README/download guides and the Sileo packages/catalogs/depictions/signed indexes. Complete and read back that transaction without asking again for each routine step. A no keeps the candidate private while development continues. Material changes after a yes require renewed affected testing and a new publication choice.
- Public channels stay on the last explicitly approved build. Keep development indexes current privately; never advertise an unapproved candidate as the public current build. Record candidate identity, owner results, outstanding gaps and the publication answer in the private release receipt and UPM evidence.
- Correcting release policy text alone does not approve or promote application changes. This clarification does not retroactively approve already published Build96, authorize a rollback, or establish any missing device test result.

## Synchronize Sileo after an approved public iOS release

The public-release rule above is the prerequisite. Only after the owner's yes for a tested candidate should `zemabinks/repo` serve its matching IPA. A private development build does not trigger a public Sileo update.

1. Mirror the approved exact IPA and checksum in the owned Sileo repository release. Match the approved build, byte count, SHA-256 and source revisions.
2. Increment both installer versions and build the existing TrollStore and experimental AppSync templates with the approved IPA's URL, size and hash. Preserve installation methods, app data and previous package versions.
3. Update catalogs, depictions, README, landing page and installation guide together. Keep historical device confirmations labeled with their actual build.
4. Regenerate package indexes; sign Release and InRelease with the existing key. Verify signatures, index hashes, archive contents and preserved older stanzas.
5. Publish the approved source/assets, then read back the live catalogs, signed indexes, packages and IPA bytes. Report the advertised version and accurate verification limits.

Use existing keys and credentials. Never export private keys or infer physical installation/gameplay from fixtures. No paid hosted runner, billing change or new service is required.

## Product/version naming — owner instruction, 1 November 2026

Use **ZGTA 5 — 1.1 beta 1**, package `1.1~beta1`. Follow
`docs/VERSIONING.md` and `VERSION.json`; no Debian `-N` revision suffixes.
Future beta numbers increase within1.x;2.0 requires a real major release.
Preserve historical artifact URLs/receipts. Browser styling changes remain
private until applicable owner testing and the separate final public choice.
