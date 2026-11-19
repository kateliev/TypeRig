# HANDOUT — trFont round trip: VFC → .trfont → VFC

**Status:** Stage 0 DONE (2026-11-19). Stage A in progress. See §7 for the exact next action.
**Owner:** Vassil Kateliev. **Repo:** TypeRig (master).
**Goal:** a FontLab `.vfc` can be ejected to `.trfont` and mounted back into a new
FontLab font with no loss on a declared field set — then the same for Glyphs.

This file is the single source of truth for the project. It travels with the repo,
so work can stop on one machine and continue on another. **Update the Progress
ledger at the bottom at every stop.**

---

## 0. How to resume

1. Read §6 Progress ledger — it names the next action.
2. Run the machine-independent gate: `python Lib/typerig/core/fileio/test_trfont.py`
   and `python Lib/typerig/core/objects/test_objects.py`. Pure core, no FontLab.
3. If FontLab is available, run the FL side: §4B.
4. Do the next unchecked task, tick it, append a line to the ledger, commit.

Nothing in this plan requires the *same* machine twice. The only machine-specific
need is a FontLab 9 install plus a test VFC for the FL-side gates.

---

## 1. Scope and staging (as agreed)

| Stage | Content |
|-------|---------|
| **0** | Ground truth, dead-code retirement, audit harness. Prerequisite for everything. |
| **A** | Outlines + font/glyph metadata + axis/master/instance setup. Element references unlinked: each use is written as its own outline + transform. No kerning, no features. |
| **B** | A + kerning + features (+ groups verified). |
| **C** | B + components / FL element references (links restored). |
| **D** | Handout for the Glyphs round trip. |
| **Z** | FontLab → Glyphs → FontLab through `.trfont`. |

"Round trip" never means byte-equal VFC. It means: **the audit diff (§4) is empty
on the field set declared for that stage.** Each stage adds fields to the set and
never removes any.

---

## 2. Where the code lives

| Piece | Path | State |
|-------|------|-------|
| Core font object | `Lib/typerig/core/objects/font.py` | `Font(Container of Glyph)` + `FontInfo` + `FontMetrics`. Per-master kerning, groups, features all serialize. Good shape. |
| Axis / Master / Instance | `core/objects/{axis,master,instance}.py` | Thin; need fields (§3.2, §3.3). |
| Encoding / Kern / Groups | `core/objects/{encoding,kern,groups}.py` | Complete for our purposes. |
| Shape (component slot) | `core/objects/shape.py` | Has `component` (UFO base-glyph name) + `transform` + `is_component`. Not the FL model — see §3.6. The proxy drops `transform` today — see §3.5. |
| Folder IO | `core/fileio/trfont.py` | `TrFontIO.write/read/new`, `GlyphManifest`, `metainfo.xml`, `features.fea`, `groups.xml`. Works. |
| **The FL bridge** | `proxy/tr/objects/font.py` → `trFontProxy` | v0.3.0. The one to keep and fix. |
| Dead bridge | `proxy/tr/objects/trfontfile_proxy.py` | v0.1.0, imports `TrFontInfo/TrMetrics/TrAxes/TrEncoding` which no longer exist → `ImportError`. **Delete.** |
| Thin wrapper | `core/objects/fontfile.py` | dict-like wrapper over `Font` + `TrFontIO`. Decide: keep as sugar or delete. |
| eject/mount chain | `proxy/tr/objects/{glyph,layer,shape,contour,node}.py` | Works for geometry, anchors, per-layer guides, mark, note, unicodes. |
| Glyphs proxy | `proxy/gs3/` | Exists; the Stage D/Z target. |
| Format doc | `Docs/Core/Documents/trfont.md` | Describes the format. Keep in step with every format change. |

---

## 3. Ground truth — probed in FontLab 9 against a live 2-master VFC

Verified on **BasilMM** (`Basil-Rev-2Wt.xfo`, 754 glyphs, masters `Light` / `Bold`,
one `weight` axis). Everything below is measured, not assumed. These findings are
the reason Stage A is mostly *repair*, not new features.

### 3.1 `_fl_info` returns an entirely empty FontInfo

`fgFont` has **no** `familyName`, `styleName`, `designer`, `copyright`, … attributes.
All naming lives on `fg.info` (an `fgFontInfo` with UFO-spelled fields:
`familyName`, `openTypeNameDesigner`, `openTypeOS2Panose`, `openTypeHheaLineGap`, …).
`_fl_info` reads them off `fg_font` through `getattr(..., '')`, so **every field
comes back `''`**. Silent, because the fallbacks hide it.

→ Rewrite onto `fg.info`. `fg.info.dict` is an `fgFontInfoDict` (no `len()`;
iteration route needs a short spike). Curated fields go to `FontInfo._FIELDS`,
everything else into `FontInfo.lib` so nothing is dropped.

### 3.2 `_fl_metrics` returns the defaults, and metrics are per master

`fgFont` has no `ascender`/`descender`/`xHeight`/`capHeight`/`lineGap` either, so
`_fl_metrics` returns the hardcoded `800 / -200 / 500 / 700 / 0` for every font.

Real access is on the **flPackage, per master**:

```python
f.setMaster('Bold')
f.ascender_value, f.descender_value, f.xHeight_value, f.capsHeight_value, f.lineGap_value
```

Measured: Light → `674 / -174 / 450 / 674 / 200`, Bold → `674 / -184 / 477 / 674 / 200`.
Descender and x-height **differ per master**. `upm` is genuinely font-level
(`flPackage.upm` = 1000).

→ `FontMetrics` must hang off `Master`, not only off `Font` (§3.3). Always restore
the previously current master after walking them.

### 3.3 `flPackage.masters` is a list of strings — the master loop throws

```python
f.masters        # ['Light', 'Bold']   <-- plain str
f.defaultMaster  # 'Light'
f.master         # 'Light'  (current master, an attribute, not a method)
f.location('Bold')  # <flLocation wt=1000>
```

`_fl_axes` does `master.name` on those strings → `AttributeError` → caught by its
own `except (AttributeError, TypeError)` → **falls into the single-master
fallback**. So today every multi-master font ejects as one master. This is the #1
blocker for Goal A ("axis setup").

`flLocation` exposes nothing through `dir()` (PythonQt), but **subscript by the
axis `shortName` works**: `f.location('Bold')['wt'] → 1000.0`. Integer subscript
returns `None`.

→ Rewrite `_fl_axes`: iterate master *names*, read locations via
`f.location(name)[axis.shortName]`, take the default from `f.defaultMaster` (not
index 0).

### 3.4 `flAxis` has no `.minimum`

Real attributes: `name`, `tag`, `shortName`, `minimal`, `default`, `maximum`,
`designMin`, `designDef`, `designMax`, `map`, `styleName`, `isWeight`, `isWidth`.
Measured: `('weight', 'wght', 'wt', min 0.0, def 0.0, max 1000.0, design 0/0/1000, map None)`.

`_fl_axes` reads `ax.minimum` behind a `hasattr` guard → silently writes
`0 / 0 / 1000` for every axis.

→ Use `minimal`. Add `short_name` and the design-space triple to `Axis` — the
shortName is not cosmetic, it is the key `flLocation` is indexed by.

### 3.5 Shape transforms are dropped — 345 of 754 glyphs eject misplaced

`flShape.contours` returns nodes in **element space**. The placement is only in
`shape.transform`. Measured on `Aacute` / Bold: the acute shape's first node is
`(107, 550)` — identical to the `acute` glyph's own node — and the shape's
transform is `translate(308, 190)`.

`trShape.eject()` builds `Shape(core_contours, name=self.name)` and never reads
`self.host.transform`; `_build_fl_shape()` never sets one. So every transformed
shape comes back at the origin. In BasilMM that is **345 glyphs** (every accented
letter and more). Today's eject is geometrically wrong, not just lossy on identity.

The core format already has the slot: `Shape.transform` is in `XML_ATTRS`, and an
identity transform is skipped on write. Only the proxy needs to fill it in and
read it back. This is Stage A work (A.0), not Stage C.

### 3.6 FontLab composites are **element references**, not UFO components

For `Aacute` in a real VFC:

```
layer 'Bold': shapes 2, layer.components 0
  shape 0: shapeData.name 'A'      contours 2  isComponent False  transform identity
  shape 1: shapeData.name 'acute'  contours 1  isComponent False  transform translate(308,190)
```

So there is no `flLayer.components`, and `shape.isComponent` is `False`. The
outline data is on each shape because `shapeData` is **shared** with the element
named `A`. The identity is in `shapeData.name`. The placement is in
`shape.transform` (§3.5).

**`refCnt` is not a sharing signal.** An unshared, unnamed shape (`Q`) has
`refCnt 4`. Across the font the histogram is `3: 1038, 4: 1, 5: 1, 8: 2`. It is an
internal reference count. Use the **element name** instead. In BasilMM (first
layer): 120 named elements, and each one is used by more than one glyph (for
example `exclam` in `exclam` + `exclamdown`). There are 248 unnamed shapes, which
are plain local outlines. No shape has `includesList` entries, so nested
references are **unverified**.

Consequences:

- `Shape.component` (UFO: the name of a *base glyph*) is the **wrong model for
  FontLab**, which references an *element*. Keep `component` for the UFO/Glyphs
  path and add a separate element reference for the FL path (§5 C.1).
- Once A.0 carries the transform, Stage A and Stage B close **geometrically**: the
  outlines are duplicated per use, but the placement is correct. Only Stage C
  closes on identity.
- FL also has real components (`flLayer.addComponent`, `components`,
  `setGlyphComponents`, `shape.isComponent`). This font has none. Stage C needs a
  second test font that has them.

### 3.7 Kerning and features

- Kerning is per master: `flPackage.kerning(master_name)` → `fgKerning`
  (`asDict`, `getPlainPairs`, `getPlainPairsDict`, `groups`, `set`, `remove`).
  `pFont.kerning(layer)` in `proxy/fl/objects/font.py` already wraps this —
  reuse it rather than writing new access code.
- **BasilMM is kerned:** `f.kerning('Bold')` → 2085 entries. The `fg.kerning`
  attribute on `fgFont` is a different object and is empty (`len 0`). Do not read
  kerning from `fg.kerning`.
- `fg.groups` → 32 groups. `_fl_groups` / `_groups_into_fl` already handle mode and
  per-side flags.
- `fg.features` is an `fgOTLayout` (`len 12`). `_fl_features` /
  `_features_into_fl` already split and rejoin FEA blocks.
- The core side of kerning is **done**: `Font.kerning_for(master)`,
  `<kerning master="...">` serialization, and `core/actions/kern_font.py`
  (`kernset_from_font`, `apply_to_font`, `CoreFontKernHost`). Only the FL↔core
  bridge is missing.

### 3.8 Glyph layer order is not master order

`flPackage.masters` is `['Light', 'Bold']`, but `Aacute.layers` is
`['Bold', 'Light']`. The audit and every mount must match layers **by name**,
never by index.

### 3.10 `fg.info` enumeration (spike 0.4)

Idiom: iterate `dir(fg.info)`, skip `_*`, `dict` and callables. That gives 97
UFO-named fields (54 non-empty in BasilMM). Value types are only None, bool, int,
float, str and list, so everything serializes. `fg.info.dict` is an
`fgFontInfoDict` with FL-private groups `names`, `values`, `flags`
(`OS2UseTypoMetrics`, `hhea_use_custom`) and `metrics` (`MEASURE_*`).

**`fg.info` is not per master.** `ascender`, `descender` and `xHeight` stay at the
key master's values whatever `setMaster` says, and `styleName` (`Thin`) is
unrelated to the master names (`Light`, `Bold`). Per-master metrics come only
from `flPackage.*_value`.

### 3.11 Other findings from Stage 0

- `flShape.name` is `''`. The element name is `shape.shapeData.name` (A.7).
- FL glyphs have service layers such as `#instance` next to the masters (A.8).
- FL kerning keys are `fgKerningObject`s with `.id` and `.mode` (`glyphMode` /
  `groupMode`). The dump writes them as `F` and `@_lc_a`.

### 3.9 Features are written twice (fixed in 0.5)

`TrFontIO.write` writes `features.fea`, **and** `Font._to_xml_element` writes a
`<features>` text child into `font.xml`. On read, `font.xml` loads first and
`features.fea` overwrites it. Two sources of truth that can drift.

→ Decide one. Recommendation: `features.fea` is authoritative in a `.trfont`
folder; keep `<features>` in the element only for the single-file/in-memory case,
and have `TrFontIO.write` pass `exclude_attrs`-style suppression. Document it.

---

## 4. The audit harness (Stage 0 — build this first)

Without a verifier, "round trip" is an opinion. Two halves:

**A. Pure core, runs anywhere** — `Lib/typerig/core/fileio/test_trfont.py`
(schema, normalization, `dump_font`, `diff`, `summarize`, `xml_dir_diff` live in
`Lib/typerig/core/fileio/trfont_audit.py`). It has an `XFAIL` table: a known
failure tied to a task prints `XFAIL`, and an XFAIL that starts passing fails the
run as `XPASS` so the table gets pruned.
Builds a synthetic 2-master font in code (2 axes, 3 glyphs, anchors, guides,
kerning on both masters, groups, features), then asserts:
`Font → write → read → write` gives an **equal XML tree** (compare parsed trees,
not bytes — attribute order is not stable) and an equal object graph on the
Stage-set fields. No FontLab. This is the gate that must stay green on every
machine and in CI.

**B. FontLab side** — `Lib/typerig/proxy/tr/audit.py` (in the library, so FL and
the MCP can import it). It reads the **raw FL API**, never the trGlyph/trLayer
proxies, because the audit exists to catch what the proxies lose.

```python
from typerig.proxy.tr import audit
from typerig.core.fileio.trfont_audit import summarize
d = audit.dump_fl(stage='a', glyph_names=None)      # same schema as dump_font
audit.save_json(d, path); audit.load_json(path)
lines = audit.eject_report(work_dir, stage='a', glyph_names=[...])   # DIAGNOSTIC
summarize(lines)                                    # {field pattern: count}
```

- **GATE** = `dump_fl(source)` vs `dump_fl(round-tripped font)`. Convention-free.
- **DIAGNOSTIC** = `dump_fl(source)` vs `dump_font(.trfont read back)`. Localizes
  a loss to the eject side. On the FL side guides use FL's convention (position
  from `guide.vector`, angle in radians), so guides can differ here for
  convention alone until A.10 settles the mapping.
- The fontlab MCP `run_python` has a ~5 s limit: about 25 glyphs/s for an eject
  report, so use `glyph_names=` chunks there. The FL console has no limit.

**Field sets** (cumulative):

- **stage a** — upm; axes (name, tag, shortName, min/def/max, design triple, map);
  masters (name, location, default flag, per-master metrics); instances (name,
  location); glyph order; per-glyph unicodes, mark, note; per-layer name (matched
  by name, §3.8), advance width/height; per-shape transform (6 values); per-contour
  node count, node coordinates in **layer space**, i.e. after the shape transform
  (rounded to 1e-6), node types, smooth flags, closed flag; anchors (name, x, y);
  layer guides (x, y, angle, name); font info fields.
- **stage b** — + kerning pairs per master (incl. class pairs); groups (name,
  members, side/mode); FEA text (newline-normalized); the list of compiled
  features.
- **stage c** — + per-shape element name; for each element name, the set of glyphs
  that use it (the link); nested includes, if a test font has any.

Rounding and normalization rules live in the harness, in one place, commented.

---

## 5. Stages

### Stage 0 — ground truth and harness

- [x] 0.1 Deleted `proxy/tr/objects/trfontfile_proxy.py`. `core/objects/fontfile.py`
      **stays** as the thin compatibility wrapper (test_objects F7 and the README
      reference it); no new features go into it. `trfont.md` now documents
      `trFontProxy`.
- [x] 0.2 `core/fileio/test_trfont.py`: a synthetic 2-axis, 2-master font with
      curves, element-style transformed shapes, anchors, guides, per-master
      kerning, groups, CRLF features and a case clash (`A`/`a`). A negative
      control (moved node, changed location) was confirmed to fail.
- [x] 0.3 `proxy/tr/audit.py` (FL) + `core/fileio/trfont_audit.py` (core), §4.
- [x] 0.4 `fg.info` spike, §3.10.
- [x] 0.5 Features: **`features.fea` is the single source of truth** in a
      `.trfont` folder. `TrFontIO.write` strips `<features>` from `font.xml`.
      `Font.to_XML()` keeps it for the single-file case. Old packages with
      `<features>` in `font.xml` still read (`features.fea` wins).
- [x] 0.6 (found in Stage 0) **trfont.py could not import inside FontLab**:
      FL9's Python has no `fontTools`, and `userNameToFileName` came from it.
      Replaced with a local `user_name_to_file_name`, checked equal to fontTools
      on a corpus that includes clash counters.
- [x] 0.7 (found in Stage 0) Manifest paths were written with `os.path.join`, so
      a package made on Windows had backslash paths and would load as empty
      placeholder glyphs on macOS. Now always `/`; backslashes are normalized
      on read.
- **Gate:** MET 2026-11-19. `test_trfont.py` all pass, `test_objects.py` 185/185.
  `audit.dump_fl` dumps BasilMM in FL without exceptions.
- **Baseline** (`eject_report`, stage a, 40 glyphs of BasilMM): the Stage A
  to-do, measured. Field pattern, diff count, cause, task:

  | Field | Count | Cause | Task |
  |---|---|---|---|
  | `layers.*.guides[]` (x / y / angle) | 727 | guide extraction + UFO None convention | A.10 |
  | `glyphs.*.mark` | 37 | FL `mark 0` (no mark) ejects as `#ff0000` | A.9 |
  | `layers.*.shapes[].name` | 35 | element name is on `shapeData.name`; `flShape.name` is `''` | A.7 |
  | `shapes[].transform[4/5]` | 4 | transform dropped | A.0 |
  | `info.*` | 15 | every field empty or the constructor default | A.4 |
  | `metrics.*` | 5 | hardcoded defaults | A.5 |
  | `masters` | 1 | collapsed to one master | A.3 |
  | `instances[].location` | 5 | locations empty | A.3 |
  | `axes` | 0 | only because BasilMM's axis is 0/0/1000, the same as the fallback | A.1, A.3 |

  Glyph `A` also has a `#instance` service layer, which the eject carries (A.8).

### Stage A — outlines, metadata, axis setup

- [ ] A.0 **Carry `Shape.transform`** (§3.5) — the most urgent item. In
      `trShape.eject()`, read `host.transform` (QTransform `m11 m12 m21 m22 dx dy`)
      into the core `Transform`. In `_build_fl_shape()` / `trShape.mount()`, set it
      back. Check the core `Transform` element order against QTransform before you
      write any code. Gate: `Aacute`'s acute node ejects at element space
      `(107, 550)` with transform `(308, 190)`, and it mounts back to the same
      place.
- [ ] A.1 `Axis`: add `short_name`, `design_min`, `design_default`, `design_max`,
      optional `<map>` of (user, design) pairs. Serialize; core round trip test.
- [ ] A.2 Per-master metrics: `Master.metrics` (a `FontMetrics`). `Font.metrics`
      becomes the default master's metrics; `upm` stays font-level. XML:
      `<master name="Bold"><location .../><metrics .../></master>`. Bump
      `TRFONT_FORMAT_VERSION_MINOR`; keep reading old packages.
- [ ] A.3 Rewrite `_fl_axes`: master names are strings; locations via
      `f.location(name)[axis.shortName]`; default from `f.defaultMaster`;
      instances from `flInstance` (`name`, `location`, `weight`, `width`).
      Keep locations keyed by **axis name**: that is the existing format
      contract (`trfont.md`) and the designspace convention. An earlier draft
      of this plan said "tag", which would have been a silent format change.
      Map name ↔ shortName only at the FL boundary.
- [ ] A.4 Rewrite `_fl_info` onto `fg.info` (mapping: `audit.INFO_MAP`, already
      verified against FL9). Unmapped UFO keys → `FontInfo.lib`. `FontInfo.lib`
      stores values as `str()` today, so list fields (Panose, unicode ranges)
      need typed lib values first. Version is composed from
      `versionMajor`/`versionMinor` (`1.002`). BasilMM has both `None`, so the
      eject must not invent the core default `'1.0'`.
- [ ] A.5 Rewrite `_fl_metrics`: per master via `setMaster` + `*_value`; restore
      the original current master in a `finally`.
- [ ] A.6 `trFontProxy.create_font(core_font)` → a **new** flPackage: axes,
      `addMaster` + `setLocation` + per-master metrics, `addInstance`, glyph
      order, then `mount`. Needed because `mount()` only updates a live font and
      a round trip must produce a fresh VFC.
- [ ] A.7 Stage A does **not** decompose. Each shape is written as its own outline
      (element space) plus its transform (A.0), and the element name goes in
      `Shape.name`. The outlines are duplicated per use and the link between
      uses is lost until Stage C. Placement is correct. Stamp
      `elements="unlinked"` into `metainfo.xml` so a Stage-C reader can tell an
      A-era package apart.
- [ ] A.9 Glyph mark: FL `mark 0` means "no mark", but `trGlyph.mark` returns
      `hue_to_hex(0)` = `#ff0000`, so every unmarked glyph ejects red (37 of 40
      in the baseline). Map 0 ↔ `None` both ways.
- [ ] A.10 Guides: `flGuideLine.vector` is an **flNode** (the position), not a
      QLineF, so `_fl_to_guideline` takes its fallback path. FL `angle` is in
      radians. Fix the extraction and the UFO mapping (x / y / angle, None for
      axis-aligned); mount must invert it. BasilMM layer guides come in
      duplicate pairs: check whether that is the font or the API.
- [ ] A.8 Mount-side parity check for layer identity: FL master name == layer
      name is the format's contract (`Master.layer_name`). Verify it holds for
      service/mask layers too, or exclude them explicitly.
- **Gate:** BasilMM → `.trfont` → new VFC; `diff` empty on the **stage a** field
  set. Record the VFC file size delta and the glyph/master counts in the ledger.

### Stage B — kerning and features

- [ ] B.1 FL → core kerning, per master: `pFont.kerning(master)` →
      `Font.kerning_for(master, create=True)`. Pick **one** canonical class
      naming in trFont — recommend UFO `public.kern1.` / `public.kern2.`, since
      `_fl_groups` already uses `KERN1_PREFIX` / `KERN2_PREFIX` — and map FL's
      `@`-prefixed names at the boundary only.
- [ ] B.2 core → FL kerning, per master, including class pairs; clear before set
      so removals propagate.
- [ ] B.3 Features: assert FEA text survives newline-normalized byte-equal
      through `features.fea`, and that FL **recompiles** it after mount. Watch
      the prefix / `languagesystem` / class-definition block ordering in
      `_split_fea_blocks`.
- [ ] B.4 Groups: add to the audit field set; verify mode and per-side flags.
- **Gate:** `diff` empty on the **stage b** field set on BasilMM. It has real
  per-master kerning (2085 entries on Bold, §3.7), 32 groups and a feature set.

### Stage C — components / element references

- [ ] C.1 **Design decision, write it down first:** add an element reference to
      `Shape` — `Shape.ref` (element name) — distinct from `Shape.component`
      (UFO base-glyph name, kept for the Glyphs/UFO path). Element definitions go
      in a font-level pool (`elements.xml` + `elements/*.trelement`, reusing the
      `GlyphManifest` pattern), or, if the pool proves redundant, "first
      definition wins and later uses are references". Decide, document in
      `trfont.md`, bump the format minor version.
- [ ] C.2 Eject: detect shared elements by `shapeData.name` (the same name in
      more than one glyph). **Do not use `refCnt`** (§3.6). Emit one definition
      and references with transforms. Before you depend on nested composites via
      `shape.includesList`, find a font that has them. BasilMM has none.
- [ ] C.3 Mount: rebuild references with `flShape.include` / `setIncludes` /
      shared `shapeData`. Order so a referenced element exists before its users;
      detect and refuse cycles.
- [ ] C.4 Support FL's real components too (`flLayer.components`, `addComponent`,
      `setGlyphComponents`, `shape.isComponent`) — needs a test font that has
      them.
- [ ] C.5 Add an optional `eject(decompose=True)` for export pipelines: apply
      each transform to the nodes and drop the element link.
- **Gate:** `diff` empty on the **stage c** field set. Composite glyphs have the
  same layer-space geometry as in Stage A, and every element name links the same
  set of glyphs as in the source.

### Stage D — Glyphs round trip handout

- [ ] D.1 Write `Typerig-Glyphs/Handouts/trfont_glyphs_roundtrip_handout.md`
      (that is where Glyphs-port handouts live, shared with the Mac).
      Cover the mapping and every mismatch:
      - `GSFont` / `GSFontMaster` / `GSAxis` / `GSInstance` ↔ `Font` / `Master` /
        `Axis` / `Instance`.
      - **Master identity:** Glyphs keys layers by `GSFontMaster.id`, trFont by
        layer *name*. `Master.identifier` must carry the Glyphs id, and the
        `master.layer_name` contract has to survive a name change.
      - `GSComponent` is a true *glyph* component → this is where
        `Shape.component` earns its place; FL elements (§3.6) have no direct
        Glyphs equivalent and need a documented policy.
      - Kerning: per master, `@MMK_L_` / `@MMK_R_` ↔ `public.kern1/2.`.
      - Features: Glyphs splits classes / prefixes / features as objects, not one
        FEA blob — state the lossy direction.
      - Per-master metrics map cleanly (Glyphs has them per master already).
      - Anchors, guides, glyph colour/mark, `userData` ↔ `lib`.
- [ ] D.2 List what cannot cross, with a reason per item.

### Stage Z — FontLab → Glyphs → FontLab

- [ ] Z.1 Implement the Glyphs side against `proxy/gs3/`.
- [ ] Z.2 Three-way audit: FL dump vs Glyphs dump vs FL dump.
- [ ] Z.3 Record the lossy field list in this file.

---

## 6. Deferred ledger — known data that no stage above carries

Listed so nothing is dropped silently. None of it blocks A–C.

| Data | Where it lives in FL | Verdict |
|------|----------------------|---------|
| Hinting: zones, standard stems | `flPackage` hinting, per master | Stage E. `get_font_hinting` in the FL MCP shows the shape of it. |
| Glyph hints, links, TT programs | `flLayer` hints | Stage E. |
| Smart corners / node extras | `node.py` `XML_LIB_ATTRS` has `g2`, `transform` commented out | Stage E; re-enable deliberately, it affects every node. |
| Metric expressions (lsb/rsb/advance formulas) | `flLayer` / `flGlyph` | Stage E — real design data, currently flattened to numbers. |
| Mask and service layers | `flGlyph.layers` (the eject walks **all** layers) | Decide in A.8: carry or exclude explicitly. |
| Glyph tags, OpenType tags | `flGlyph` | Stage E. |
| Font-level guides | `fg.guides` | Stage E. |
| `fg.lib`, `fg.tables`, `fg.hinting` | fontgate | Pass through `Font.lib` when cheap. |
| Images / pictures, colour layers | `fg.hasPictures`, `hasColors` | Out of scope. |
| Compiled binary tables | — | Never. `.trfont` is a work format. |

---

## 7. Progress ledger — append at every stop

Format: `YYYY-MM-DD | machine | what changed | next action`

- `2026-11-19 | win/D:\Remote\GitHub\TypeRig | Plan written. FL9 probed against BasilMM: _fl_info, _fl_metrics and the master loop all confirmed broken (§3.1–3.4); FL composites confirmed to be element references, not components (§3.5). No code changed. | Start Stage 0.1 — delete trfontfile_proxy.py, then 0.2 test_trfont.py.`
- `2026-11-19 | same | Re-verification pass found and fixed three wrong claims: (1) shape transforms are dropped by trShape.eject/_build_fl_shape, so 345/754 glyphs eject misplaced (new §3.5, task A.0); (2) refCnt is not a sharing signal, use shapeData.name (§3.6, C.2); (3) BasilMM IS kerned via flPackage.kerning(master), so B.5 is gone. Added §3.8 (match layers by name). | Unchanged: Stage 0.1, then A.0 first in Stage A.`
- `2026-11-19 | same | Stage 0 DONE. trfontfile_proxy.py deleted; test_trfont.py + trfont_audit.py + proxy/tr/audit.py added; trfont.py: fontTools dependency removed (FL could not import it), portable "/" manifest paths, features.fea single source. Baseline eject_report recorded under the Stage 0 gate. | Stage A, starting with A.0 (transform), A.7 (element name), A.9 (mark).`
