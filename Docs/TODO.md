# TypeRig — to do / to fix

One line per item; details live in the linked handout. Remove a line when done.

## To fix

- **Element panel → Link on FontLab 9** — `fl6.flShape(<flShapeData>)` fails on FL 9.0.9809; fixed via insert-existing-shape (`7f8fade`), **panel button not click-tested**. → `Docs/Proxy/Handouts/HANDOUT-element-link-fl9.md`
- **`proxy/fl/actions/contour.py:258`** uses `fl6.flShape(<fgShape>)` — same constructor family, check on FL9. → same handout

## To do

- **trFont part two → format v1.0** — true components (UFO level; includes FontLab components, needs a test font), warnings for unmodelled FontLab features, spec + schema + validator, then tag v1.0. → `Docs/Core/Handouts/HANDOUT-trfont-v1.md`
- **trFont ↔ Glyphs** (Stage Z, on the Mac). → `Typerig-Glyphs/Handouts/trfont_glyphs_roundtrip_handout.md`
- **TR: Font IO** (`Scripts/TypeRig Tools/TR-ExportFont.py`) — rebuilt 1.0 on the round-trip bridge; Export / Inspect / Open as new font tested on BasilMM in FL 9.0.9809; *Update current* (mount into an existing font) not tested.
