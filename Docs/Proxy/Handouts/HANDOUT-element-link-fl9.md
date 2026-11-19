# HANDOUT — Element panel *Link* on FontLab 9

**Status:** fix committed (`7f8fade`), helper verified in FL 9.0.9809, **panel
button not click-tested**. Found 2026-11-19 while doing Stage C of the trFont
round trip (`Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md`).

## The bug

`TRElementActionCollector.element_link` (`Lib/typerig/proxy/fl/actions/element.py`)
built each reference with

```python
layer.insertShape(sid, fl6.flShape(key_shape.shapeData))
```

On FontLab **9.0.9809** `fl6.flShape(<flShapeData>)` raises
`TypeError: Error creating object of type flShapeBuilder` (PythonQt picks the
wrong overload). The copy constructor `fl6.flShape(<flShape>)` fails the same
way. Reproduced both through the fontlab MCP and as a plain `.vfpy` script. It
worked FL6 → FL8 (user). Result: **Element → Link does nothing / raises on FL9.**

## The fix

New helper `_insert_reference(layer, index, key_shape)` in `element.py`:

```python
temp = layer.insertShape(index, key_shape)     # existing flShape, not a new one
new_shape = layer.insertShape(index, key_shape)
layer.removeShape(temp)
```

Inserting the **existing** flShape shares its `flShapeData` (same
`shapeData.id`). Insert twice / remove the first is the trick ElementComposer
*Insert* has used since FL6 (`pGlyph.addShape` route) to get a properly
registered reference.

Verified in FL 9.0.9809: the new shape shares the key element's data and lands
at the requested stack index.

## Open

- [ ] **Click-test** Element → Link (and Alt = link to bottommost) in the panel
      on FL9: select nodes in two elements, press Link, check both share one
      element (`shapeData.id`), and that **Undo** restores the original.
      `typerig.proxy.fl.devtools` can drive it (`open_glyph`, `press('Element',
      'Link')`, `snapshot`/`diff`, `history`). Note: in the 2026-11-19 attempt
      `open_glyph(name)` did not switch an open glyph window away from
      `.notdef` — open the glyph by hand first.
- [ ] `referenceCount` caveat: with `insertShape` the twice/remove trick shared
      the data but did not raise `referenceCount` on a font loaded from disk
      (11 → 11), and removing the shape later lowered it (→ 10). Data stayed
      shared and correct; counts are recomputed on save + reopen. Check whether
      Unlink / deleting a linked element right after Link misbehaves.
- [ ] Same constructor family elsewhere: `proxy/fl/actions/contour.py:258`
      uses `fl6.flShape(<fgShape>)` — check on FL9.
- [ ] Re-test on FL 9.1 beta (build 9813); report the `flShape(<flShapeData>)`
      regression to FontLab if it is still there.
