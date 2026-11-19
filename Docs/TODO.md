# TypeRig — to do / to fix

One line per item; details live in the linked handout. Remove a line when done.

## To fix

- **Element panel → Link on FontLab 9** — `fl6.flShape(<flShapeData>)` fails on FL 9.0.9809; fixed via insert-existing-shape (`7f8fade`), **panel button not click-tested**. → `Docs/Proxy/Handouts/HANDOUT-element-link-fl9.md`
- **`proxy/fl/actions/contour.py:258`** uses `fl6.flShape(<fgShape>)` — same constructor family, check on FL9. → same handout

## To do

- **trFont round trip** — Stage C.4 (FontLab components, needs a test font) and Stage Z (Glyphs, on the Mac). → `Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md`
