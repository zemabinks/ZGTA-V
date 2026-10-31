# Three touch-button appearances

Settings → Controls layout → Buttons offers **Original icons**, **Xbox-style
buttons** and **PlayStation-style buttons**. Existing icon/Xbox preferences keep
working and icons remain the default. Selection previews in the layout editor
and applies to the game through the existing Done callback. The same saved
positions, sizes, hidden controls, touch handling and emitted gamepad inputs
are used for every style.

PlayStation labels represent equivalent pad actions: A/B/X/Y become
Cross/Circle/Square/Triangle; LT/RT become L2/R2; LB/RB become L1/R1. Stick clicks
and D-pad directions stay the same. The camera-cycle button uses Touch and the
pause button uses Options. Bicycle, aircraft and phone variants retain their
existing action-specific mapping. Controls without an equivalent pad action
keep their utility icons. Spoken accessibility hints name the shapes rather
than reading mathematical glyphs.

The selector previously combined UIButton's tinted configuration background
with a separate UIView background. It now has a single configuration-owned dark
background, white text and a disclosure chevron. It no longer adds a second view
background or a separate corner-radius layer. The menu shows all three choices
and the selected state, with the full current choice in its accessibility value.

The existing 85-test offline app suite and expanded Foundation appearance
harness run without writing user preferences. Tests cover all three preference
round trips, old raw values/defaults, unknown values, unchanged stored layout,
physical-button equivalents, context variants, utility fallbacks and spoken
shape names. The existing touch-input byte-comparison regression also passes.
The compact result and exact source/log hashes are in
`tests/playstation_validation.json`; earlier audit receipts retain their original
scope and hashes. A local Xcode build checks the real UIKit source; appearance
and touch use on an actual iPhone still need visual confirmation.

This change targets a new **build 23** package under
`Package-PlayStation-20261016`. It preserves the earlier Package and
Package-Audit-20261016 outputs and the original English IPA/Intel build folder.
The isolated local build reuses the same verified Intel Metal/reflection pair
and device UI catalog. No new installation, shader compilation, hosted workflow,
paid service or device access is part of preparation. Exact-source build/package
receipts live next to the ignored artifact. Multiplayer behavior is unchanged;
actual paired gameplay remains unverified as recorded in AUDIT_20261016.md.
