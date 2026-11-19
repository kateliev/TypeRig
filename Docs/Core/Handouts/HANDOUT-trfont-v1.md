# HANDOUT — trFont, part two: components, warnings, spec → format v1.0

**Status:** plan only. Written 2026-11-19, after part one closed (FontLab ↔ trFont
↔ FontLab round trip: Stages 0, A, B, C, D — `HANDOUT-trfont-roundtrip.md`).
**Owner decisions (2026-11-19):**
- **Keep it simple, interoperable with FontLab, close to UFO.** FontLab's shape
  objects (elements, groups, filters, live features) are not modelled.
- **References = UFO components; Glyphs components are the upper limit.**
- **No pens, no live / smart components, no smart corners** — detect and warn.
- **File layout stays as it is for now.** The "lean files" clean-up (dropping
  default-valued attributes, UFO point vocabulary, …) is deferred; do not
  change the on-disk shape of existing elements in this part.
- **Spec + schema + validator, then tag format v1.0** — so other agents and
  tools can adopt the format.

Progress ledger at the bottom; update it at every stop.

---

## 0. Where part one left things

| Topic | State after part one |
|---|---|
| FontLab round trip | Full BasilMM (754 glyphs, 2 masters) after save + reopen: only 4 diffs = null contours in the source. Kerning, classes, features, GDEF byte-identical when compiled. |
| References | Every use of a FontLab **element** is written as full outline + transform + element name; on import, same name + same outline is re-linked into one shared element (`trLayer.mount(elements=…)`). Contours are **duplicated** in the files. |
| `Shape.component` | Exists in core (`component` attribute on `<shape>`, UFO model: base glyph name + `transform`), **never written by the FontLab bridge**. The gs3 (Glyphs) proxy already maps it to `GSComponent`. |
| FontLab real components | `flLayer.components` (C.4) not handled. |
| Tools | `TR: Font IO` (`Scripts/TypeRig Tools/TR-ExportFont.py`) 1.0; driver `proxy/tr/roundtrip.py`; audit `core/fileio/trfont_audit.py` + `proxy/tr/audit.py`. |

---

## 1. True components (UFO level, Glyphs max)

### 1.1 Model

A layer holds **outline shapes** and **component shapes**:

```xml
<shape component="A" transform="…"/>      <!-- reference: no contours -->
<shape> <contour>…</contour> </shape>     <!-- outline -->
```

- A component is **base glyph name + affine transform**. Nothing else is
  normative. (Glyphs extras such as `alignment`, anchor attachment, `locked`,
  smart-component parameters are **not** part of the model; Glyphs import
  drops them with a warning or keeps them in shape `lib` if cheap.)
- The base glyph is resolved **by name in the same font** (through the
  manifest, so shared-pool glyphs work too). Per master: the component in
  layer *L* uses the base glyph's layer *L* (UFO / Glyphs semantics); a
  missing layer falls back to the default master (existing sparse-master rule).
- Nested components are allowed; **cycles are an error** (reported, the
  offending component is dropped on import).

### 1.2 Resolution rule for tools that open a single `.trglyph`

Self-contained glyphs are not a goal for component glyphs (owner, 2026-11-19:
glyphs rarely travel alone; a glyph shipped on its own would be decomposed).
A tool that opens one `.trglyph` containing components:

1. looks for the base glyphs next to it (same folder, then a `.trfont`
   manifest that lists it, then search paths);
2. **asks** for the missing files (or a `.trfont`) if it cannot find them;
3. warns, and shows the component as unresolved, only if they are not present
   or provided. It never fails silently and never invents geometry.

Put this rule in the spec (§3) so every reader behaves the same.

### 1.3 FontLab → trFont (eject)

Replace "outline + element name on every use" with:

- **Element whose outline equals the base glyph's whole layer** (in BasilMM:
  `A` inside `Aacute`, `acute`, `exclam` in `exclamdown`, …) → a component
  `base="<glyph>"` with the shape's transform. Decide the match on outline
  equality in element space, per master; the element name is a hint, not the
  proof.
- **FontLab real components** (`flLayer.components`, `shape.isComponent`) →
  components (this closes part one's C.4).
- **Anything else** (an element shared by several glyphs that is *not* a
  whole glyph, element groups, filters, brush/stroke elements) → plain
  outlines, transform baked, with a warning (§2). If cheap, keep a hint in
  shape `lib` (`com.fontlab.element`) so a FontLab → FontLab trip can re-link;
  otherwise accept the loss and list it.
- **Find a test font with FontLab real components** before writing code
  (BasilMM has none). Probe their API first (`flLayer.addComponent(name or
  (name, QTransform))`, `components`, `setGlyphComponents`) — FL 9.0.9809 has
  broken constructors elsewhere (`fl6.flShape(<flShapeData>)`).

### 1.4 trFont → FontLab (mount / create_font)

- Component → a FontLab **component** if the FL9 API builds one reliably;
  otherwise a **linked element** whose data is the base glyph's shape
  (`layer.addShape(<existing flShape>)`, the route that works on FL9 — see
  part one, Stage C). Pick one after a probe; the audit must show the result
  is stable after save + reopen.
- Glyph order of creation: bases before composites, or a second pass.

### 1.5 Other apps

- **Glyphs:** `GSComponent(componentName, transform)` — already in
  `proxy/gs3/objects/layer.py` mount; `Typerig-Glyphs/Handouts/
  trfont_glyphs_roundtrip_handout.md` §1.2 needs updating to this model (its
  "FL element" policy row becomes the default rule, not an option).
- **UFO:** `<component base transform>` 1:1 (`trconvert` tr2ufo / ufo2tr).

### 1.6 Audit and gates

- Audit stage c changes from "element links" to "components": per glyph and
  layer, `(base, transform)` list; plus the flattened (decomposed) outline so
  a component ↔ linked-element difference on the FontLab side is visible but
  geometry is still checked.
- **Gates:** (a) core round trip of a synthetic font with nested components and
  a cycle (pure Python); (b) BasilMM FontLab → trFont → FontLab after save +
  reopen: decomposed geometry identical, references come back as references;
  (c) the components test font, same.
- Measure: `.trfont` size before/after (the duplication goes away).

---

## 2. Warnings for what we do not model

Detect on eject, never carry, always list in `problems` (the TR: Font IO log
shows them):

| FontLab feature | Action |
|---|---|
| Smart corners / node extras (`g2`, smart angle, node `transform`) | warn; geometry exported as it is drawn |
| Live / auto components, auto layers | warn; export the current (expanded) outlines or components |
| Element groups, shape filters (`includesList`, containers) | warn; flatten to outlines (apply transforms) |
| Brush / pen / stroke elements | warn; export the outline FontLab shows, if available, else skip |
| Images, color layers, SVG / bitmap glyphs | warn; skip |
| Hinting (zones, stems, hints, links, TT programs) | warn once per font; skip (deferred) |
| Metric expressions | warn once per font; numbers are exported |
| Guides bound to metrics | export the line, warn that the binding is lost |

Same idea for Glyphs (smart components, corner/cap components, brace/bracket
layers) when Stage Z starts.

Implementation: a detector per feature in the eject path, one problem line per
glyph/layer, a summary count per kind at the end.

---

## 3. Spec, schema, validator → format v1.0

Goal: another agent or tool can read and write `.trfont` from the documents
alone, without reading TypeRig's code.

- [ ] **Spec** `Docs/Core/Documents/trfont-spec.md` (normative; `trfont.md`
      stays the overview). Folder layout; every file (`metainfo.xml`,
      `font.xml`, `glyphs.xml`, `groups.xml`, `features.fea`, `.trglyph`);
      every element and attribute with type, default and meaning; number
      formatting (integral values without `.0`); string-only attributes
      (names are never type-guessed — the `infinity` bug); coordinate
      spaces (contours in element space + shape transform); components and
      the resolution rule (§1.2); sparse masters; encoding priority;
      features (single source = `features.fea`, FontLab record boundaries);
      kerning per master and group naming (`public.kern1/2.`); versioning
      rules (major = breaking, minor = additive).
- [ ] **Lib-key register** in the spec: `public.*` (UFO meaning),
      `com.typerig.*`, `com.fontlab.*` (`package.*`, `info.*`,
      `otGlyphClass`, `otMarkClass`, …) — what each key means and who
      writes it. Unknown keys must be preserved by every reader.
- [ ] **Schema** for the XML files. RELAX NG (compact syntax readable by
      people, convertible to XSD) or XSD directly — pick one; keep it in
      `Docs/Core/Schema/`.
- [ ] **Validator** `core/fileio/trfont_validate.py`: schema check (when an
      XML schema library is available) **plus** semantic checks that a schema
      cannot express (manifest paths exist, component bases resolve, no
      cycles, layer names match masters, kerning groups exist). Pure Python,
      importable inside FontLab (no fontTools / lxml requirement for the
      semantic part). Wire it into `test_trfont.py`.
- [ ] **Conformance fixtures** `Docs/Core/Schema/fixtures/`: minimal valid
      packages and known-invalid ones, so third-party tools can test
      themselves.
- [ ] Set `TRFONT_FORMAT_VERSION_MAJOR = 1`, `MINOR = 0` deliberately (it
      already says 1.0 — confirm or bump if components change existing
      meaning), **tag** the repo when the spec, schema, validator and the
      component work are in.

---

## 4. Out of scope for part two

- "Lean files" clean-up (owner: keep the current file shape for a while).
- Hinting, metric expressions, color/bitmap glyphs.
- Glyphs implementation (Stage Z, on the Mac) — only its handout is updated.

---

## 5. Order of work

1. §1.3 probe: a font with FontLab real components; FL9 component API.
2. §1 core + FontLab eject/mount for components; audit + gates (§1.6).
3. §2 warnings.
4. §3 spec, lib-key register, schema, validator, fixtures.
5. Update the Glyphs handout (§1.5), README, `Docs/TODO.md`; tag v1.0.

---

## 6. Progress ledger — append at every stop

Format: `YYYY-MM-DD | machine | what changed | next action`

- `2026-11-19 | win/D:\Remote\GitHub\TypeRig | Handout written; owner decisions recorded (UFO-level components, warn on live features, keep file layout, spec + schema + validator before v1.0). No code. | §5 step 1: get a test font with FontLab components; probe the FL9 component API.`
