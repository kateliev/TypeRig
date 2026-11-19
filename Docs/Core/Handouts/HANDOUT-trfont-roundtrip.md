# HANDOUT — trFont round trip: VFC → .trfont → VFC

**Status:** Stage 0, **A, B, C DONE; D DONE (2026-11-19)**. Full BasilMM round trip after save + reopen: 4 diffs (null contours in the source) on every stage incl. element links, rebuilt in Python (no FontLab Clean Up). C.4 (FL components) and Stage Z (Glyphs, Mac) remain. See §7.
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

**`refCnt` is not a sharing signal** (see §3.12: the documented counter is
`flShapeData.referenceCount`). An unshared, unnamed shape (`Q`) has
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

### 3.12 What the FontLab "Adam" packages tell us (read 2026-11-19)

Sources: fontlab-fontport guides (NATIVE-FEATURES, NATIVE-BOUNDARIES),
code.fontlab.com/fontlab-python-docs (generated by echopy), fontlab-remopy,
fontlab-python-instamix. Installed here: FontLab **9.0.9809**; the 9.1 beta is
build 9813. fontport's notes cite 9.0.9783 behaviour.

- **Persistence is not proven by reading a value back.** fontport found that on
  9.0.9783 Panose, weight, width and name-record writes through the
  `fg::Style` setters (`fg.info.*`) were lost after Undo or a VFJ reopen. Its
  native routes for Panose/weight/width are `flPackage.panose`,
  `weight_value`, `width_value` (key master). → **The Stage A gate must dump
  the new font after save + reopen**, not only in memory (§5 A gate).
- **Features read:** fontport does NOT use `fgOTLayout.get_prefix()` (it
  synthesizes panel classes) or `keys()/get_feature()` (can fall back to
  binary decompilation) — exactly what `_fl_features` uses today. It reads
  `fontpr.get_font_info(font_id=...)['openTypeFeatures']`: optional first
  entry `{feature: prefix}`, then ordered `{name, feature}` entries.
  `get_font_info` cannot be interrupted, so keep it out of 5-second
  `run_python` calls.
- **Features write:** `fg.features.clear()`, `set_prefix(prefix)`, then
  `set_feature(tag, code)` per block in order, then
  `notifyChangesApplied(name, [package, package.featuresContainer()])` and
  `notifyFeaturesChanged(font_id, False)`. `aalt` is forced first by native
  storage. fontport refuses: a changed prefix containing `languagesystem`,
  an initial `include` line, empty records, and **a tagless trailing
  `feature` — FontLab's loader reads past a heap buffer on it**.
  `_features_into_fl` now refuses that case too.
- **Crash lead:** `create_font` mounts features last, through the API above.
  Rank the features mount first among suspects; run the step-log probe once
  with `include_features=False` and once with it on.
- **Kerning:** the documented setter is `fgKerning.set(fgKerningObjectPair |
  (name1, name2), value)` (`__setitem__` is undocumented) — now used.
  Kerning is integer-only. fontport keeps the lib key
  `com.fontlab.kerningClassesInMainMaster` (whether kerning classes live in
  the main master only) — carry it in Stage B. fontport refuses divergent
  both-sided classes and a glyph in two classes on the same side.
- **Elements:** `flShapeData.referenceCount` is the documented "how many
  flShape objects point to this shape data". That is the sharing signal;
  the `flShape.refCnt` used in §3.6 is a different (internal) counter.
  Multiple `flShape`s, also across glyphs, may share one `flShapeData`.
  Stage C tools: `flPackage.replaceShapeWithReference(shape, process[,
  layer_name])`, `flPackage.findShapeRoot(shape_data)`.
- **UPM:** `flPackage.setUpm(upm, scale)` exists (documented, `scale` not
  explained); `fg.info.unitsPerEm` is what was verified.
- **Long runs:** remopy is subject to the same FontLab-side 5 s `run_python`
  deadline (and 32 KB code / 64 KB output). Its advice: split into short
  calls. A full-font round trip should run as a `.vfpy` script opened in
  FontLab (how every `install.vfpy` runs), writing its results to a JSON file.
- **fontTools in FontLab:** instamix can install it
  (`fontlab_instamix.install_packages("fonttools>=4")`). TypeRig keeps its
  local filename function so it does not depend on that.
- **Independent oracle (optional, owner's call):** fontport writes FL → UFO
  with exact feature source and per-master kerning; core `fileio/ufo.py` reads
  UFO. FL → fontport UFO → core dump vs our eject would cross-check Stage B
  with code we did not write. Needs fontport installed in FontLab.
- **Glyphs (Stage D/Z):** glyport runs Glyphs *scripts* inside FontLab (API
  emulation). It does not read or write `.glyphs` files, so it is not a
  Stage Z route; its `GSFont`/`GSLayer` mapping is still useful reading for D.

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

- [x] A.0 **Carry `Shape.transform`** (§3.5) — the most urgent item. In
      `trShape.eject()`, read `host.transform` (QTransform `m11 m12 m21 m22 dx dy`)
      into the core `Transform`. In `_build_fl_shape()` / `trShape.mount()`, set it
      back. Check the core `Transform` element order against QTransform before you
      write any code. Gate: `Aacute`'s acute node ejects at element space
      `(107, 550)` with transform `(308, 190)`, and it mounts back to the same
      place.
- [x] A.1 `Axis`: add `short_name`, `design_min`, `design_default`, `design_max`,
      optional `<map>` of (user, design) pairs. Serialize; core round trip test.
- [x] A.2 Per-master metrics: `Master.metrics` (a `FontMetrics`). `Font.metrics`
      becomes the default master's metrics; `upm` stays font-level. XML:
      `<master name="Bold"><location .../><metrics .../></master>`. Bump
      `TRFONT_FORMAT_VERSION_MINOR`; keep reading old packages.
- [x] A.3 Rewrite `_fl_axes`: master names are strings; locations via
      `f.location(name)[axis.shortName]`; default from `f.defaultMaster`;
      instances from `flInstance` (`name`, `location`, `weight`, `width`).
      Keep locations keyed by **axis name**: that is the existing format
      contract (`trfont.md`) and the designspace convention. An earlier draft
      of this plan said "tag", which would have been a silent format change.
      Map name ↔ shortName only at the FL boundary.
- [x] A.4 Rewrite `_fl_info` onto `fg.info` (mapping: `audit.INFO_MAP`, already
      verified against FL9). Unmapped UFO keys → `FontInfo.lib`. `FontInfo.lib`
      stores values as `str()` today, so list fields (Panose, unicode ranges)
      need typed lib values first. Version is composed from
      `versionMajor`/`versionMinor` (`1.002`). BasilMM has both `None`, so the
      eject must not invent the core default `'1.0'`.
- [x] A.5 Rewrite `_fl_metrics`: per master via `setMaster` + `*_value`; restore
      the original current master in a `finally`.
- [x] A.6 `trFontProxy.create_font(core_font)` → a **new** flPackage: axes,
      `addMaster` + `setLocation` + per-master metrics, `addInstance`, glyph
      order, then `mount`. Needed because `mount()` only updates a live font and
      a round trip must produce a fresh VFC.
- [x] A.7 Stage A does **not** decompose. Each shape is written as its own outline
      (element space) plus its transform (A.0), and the element name goes in
      `Shape.name`. The outlines are duplicated per use and the link between
      uses is lost until Stage C. Placement is correct. Stamp
      `elements="unlinked"` into `metainfo.xml` so a Stage-C reader can tell an
      A-era package apart.
- [x] A.9 Glyph mark: FL `mark 0` means "no mark", but `trGlyph.mark` returns
      `hue_to_hex(0)` = `#ff0000`, so every unmarked glyph ejects red (37 of 40
      in the baseline). Map 0 ↔ `None` both ways.
- [x] A.10 Guides: `flGuideLine.vector` is an **flNode** (the position), not a
      QLineF, so `_fl_to_guideline` takes its fallback path. FL `angle` is in
      radians. Fix the extraction and the UFO mapping (x / y / angle, None for
      axis-aligned); mount must invert it. BasilMM layer guides come in
      duplicate pairs: check whether that is the font or the API.
- [x] A.8 Mount-side parity check for layer identity: FL master name == layer
      name is the format's contract (`Master.layer_name`). Verify it holds for
      service/mask layers too, or exclude them explicitly.
- **Implementation notes (2026-11-19)**
  - A.0/A.7: `proxy/tr/objects/shape.py` reads/writes `flShape.transform` and the
    element name on `shapeData.name`. QTransform `(m11, m12, m21, m22, dx, dy)` has
    the same slot order as core `Transform`.
  - A.1/A.2: `FontMetrics` moved to `core/objects/metrics.py` (re-exported from
    `font.py`) so `Master.metrics` can use it. Metrics keep fractions
    (`_intish`). `Axis` gained `short_name`, `design_minimum/default/maximum`,
    `map`; numbers are written without a trailing `.0` so write/read/write is
    byte-stable (the idempotence check caught `0` vs `0.0`).
  - A.3–A.5: `_fl_axes`, `_fl_info`, `_fl_metrics` rewritten from the verified API.
    Every non-mapped `fg.info` field goes to `FontInfo.lib` (typed: lists and
    numbers are stored as JSON with `type="json"`). Skipped on purpose:
    `versionMajor/Minor` (→ `version`), `unitsPerEm` (→ upm), `ascender`,
    `descender`, `xHeight`, `capHeight` (per master), `openTypeHeadModified`
    (FontLab rewrites it on save). A file without a version now reads as `''`,
    not an invented `'1.0'`.
  - A.9: FL `mark 0` ↔ `None` both ways; mount always writes the mark.
  - A.10: guides are read from `flGuideLine.extLinef` (font space) and built
    with `flGuideLine(QLineF)`. snapFlags are ints: `0x4080` vertical,
    `0x2080` horizontal, `0x1080` angled (the old code assigned strings). Both
    audit dumps use `canonical_guide`, so FL and core compare without
    convention noise. Some FL guides are offset from a metric
    (`center y=654`, `extPosition 20`, line at 674); only the line is carried,
    the metric binding is deferred (§6).
  - A.6 write path, verified piece by piece on a scratch font: new font =
    `fl6.flPackage()` + `flWorkspace.instance().addPackage(pkg)`; UPM through
    `fg.info.unitsPerEm` (`flPackage.upm` is read-only); `flAxis()` +
    `addAxis` (**`designDef` defaults to the midpoint, always write it**);
    `renameMaster`, `addMaster(name, False, pkg, src, False, False, flLocation)`,
    `setLocation(flLocation, name)`, `defaultMaster = name`; per-master
    metrics through `setMaster` + `*_value`; `flInstance()` + `addInstance`;
    `fg.info` list fields (Panose) are writable.
  - **The first `create_font` run on 40 BasilMM glyphs crashed FontLab 9.**
    Not yet localized. Suspects: the bulk `fg.info` lib writes, or the
    per-glyph mount into the new package. `create_font(step_log=path)` now
    writes and fsyncs one line per step (per info field, per glyph) before
    running it; the last line names the culprit. Minidumps were left in
    `%LOCALAPPDATA%\FontLab\fontlab9\crash-reports\`.
  - Live reload in FontLab: use `audit.reload_typerig()`. Reloading `xmlio`
    alone empties its class registry and reads come back with no layers.
- **Gate result (2026-11-19): MET.** Full BasilMM font after save + close +
  reopen: `compare.json` = 754 glyphs, **4 diff lines**, all
  `shapes[i].contours: length 1 != 0` in `eogonek`, `Uogonek`,
  `ogoneksmall`, `uogonek.sc` (Light). The source font holds a **null
  contour** there (FontLab returns `None` in `flShape.contours`); it cannot be
  rebuilt and is reported by the eject (`eject <glyph>: null contour
  skipped`). Timings: eject + write 8 s, read 2 s, `create_font` 25 s.
- **How to run it** (no 5-second limit; nothing opened through MCP):
  1. FontLab open on the source. `"FontLab 9.exe" build.vfpy` where
     `build.vfpy` = `from typerig.proxy.tr import roundtrip;
     roundtrip.build(work_dir, source_path=...)` → `build.json`.
  2. Save the new font as `<work_dir>/rt.vfc` (MCP `save_font`), close it.
  3. `"FontLab 9.exe" <work_dir>/rt.vfc` and answer *Duplicate Element
     Names* with **Keep As Is** (expected until Stage C: element links are
     not restored yet). A helper that answers FontLab dialogs by UI
     Automation (crash report → Later, duplicates → Keep As Is) was used;
     it lives outside the repo.
  4. `"FontLab 9.exe" compare.vfpy` (`roundtrip.compare(work_dir,
     source_path=...)`) → `compare.json`.
- **Bugs found by the full-font run (all fixed):**
  - `create_font` crash: new glyphs are built like FontLab's tutorial
    (layers first, `addGlyph`, `findName`), Python handles kept alive.
  - FontLab-side persistence: node smooth flags and node names must be set
    on **live** nodes (after `addShape`); setting smooth there re-aligns
    handles (`uni044B.sc` moved 66 → 67), so coordinates are written back
    afterwards. Naming / OS2 / hhea values need the package fields
    (`tfn tsn psn sgn ffn`, `weight_value`, `width_value`,
    `underline*_value`), the `fg.info.dict` items written one by one, and
    `fg.info` through both `flPackage.info` and `fg.info`, all after the
    design space is set up.
  - Glyph order: the new font's starter `.notdef` was updated in place and
    stayed first; starters are now removed before mounting.
  - **Core:** `xmlio` type-guessed every attribute, so the glyph
    `infinity` read back as `float('inf')` (and `nan`, `1`, `no` would
    break too). Name-like attributes are now string-only and non-finite
    floats are never produced. Node names are now part of the format.
  - The eject no longer drops a failing glyph silently; failures are in
    `trFontProxy.problems`.
- **Known, not carried (Stage A):** element links (Stage C); FontLab-generated
  `#` layers; guide-to-metric bindings; the `fg.info.dict` flags read back
  False after reopen even though the values they govern persist (assigning a
  whole dict group back crashes FontLab; item writes are used).
- **Gate:** BasilMM → `.trfont` → new VFC → **save, close, reopen** → `diff`
  empty on the **stage a** field set. An in-memory dump is not enough: fontport
  found `fg.info` writes that read back fine and are lost on reopen (§3.12). Record the VFC file size delta and the glyph/master counts in the ledger.

### Stage B — kerning and features

- **Status 2026-11-19:** B.1, B.2 written, not yet run in FontLab (it was down).
  - Name mapping is pure and unit-tested: `proxy/tr/kern_map.py` +
    `proxy/tr/test_kern_map.py` (14 checks, runs without FontLab). FL class
    `X` KernLeft ↔ `public.kern1.X`, KernRight ↔ `public.kern2.X`,
    KernBothSide ↔ both; pair side `('X', groupMode)` ↔ kern1/kern2 key. A UFO
    font whose kern1.X and kern2.X differ gets the right one renamed `X.R`
    in FontLab (one class namespace there), pairs follow, a problem is logged.
  - **Kerning classes live on `flPackage.kerning(master).groups`, per master**
    (the FL-tested pFont/pKerning API) — not on `fg.groups`. The old
    `_fl_groups` guessed kerning sides from `fg.groups` attribute names that
    "vary across builds"; kerning classes now come from the kerning object,
    and `_groups_into_fl(..., skip_kerning_classes=True)` leaves them alone.
    What `fg.groups` (32 groups in BasilMM) actually holds is unverified.
  - Pairs are written with an explicit `fgKerningObjectPair(l, r, lmode,
    rmode)` key (a glyph and a class may share a name), falling back to the
    pKerning form `kern[l, r] = v`. The explicit form is unverified.
  - FL audit dump (stage b) records kerning and classes per master in FL-native
    form (`@class`). `groups` (fg.groups) and `features` records are still
    `None` until `fg.features` / `fg.groups` are probed in FontLab.
- [x] B.3a Features read: switch `_fl_features` to
      `fontpr.get_font_info(...)['openTypeFeatures']` (§3.12), and add the
      write-side notify calls. Probe the record shape in FontLab first.
- [ ] B.6 Carry `com.fontlab.kerningClassesInMainMaster`.
- [ ] B.7 (optional, owner) fontport as an independent oracle for Stage B.
- [x] B.1 FL → core kerning, per master: `pFont.kerning(master)` →
      `Font.kerning_for(master, create=True)`. Pick **one** canonical class
      naming in trFont — recommend UFO `public.kern1.` / `public.kern2.`, since
      `_fl_groups` already uses `KERN1_PREFIX` / `KERN2_PREFIX` — and map FL's
      `@`-prefixed names at the boundary only.
- [x] B.2 core → FL kerning, per master, including class pairs; clear before set
      so removals propagate.
- [x] B.3 Features: assert FEA text survives newline-normalized byte-equal
      through `features.fea`, and that FL **recompiles** it after mount. Watch
      the prefix / `languagesystem` / class-definition block ordering in
      `_split_fea_blocks`.
- [x] B.4 Groups: add to the audit field set; verify mode and per-side flags.
- **Gate result (2026-11-19): MET.** Full BasilMM, stage b, after save +
  reopen: 4 diff lines (the same null contours as Stage A). Kerning: 2085
  pairs per master and 105 classes per master with their sides; 32 OpenType
  classes; all 13 feature records. `compile_features` (dry run) on source and
  rebuilt font: **GDEF, GPOS, GSUB SHA-256 identical**; feature text identical
  except CRLF (source) vs LF (rebuilt).
- **FontLab calls that work (FL 9.0.9809)** — most taken from fontport's source:
  - Kerning classes: read `flPackage.kerning(master).groups.asDict()`; write
    `kerning(master).addGroup(name, members, kernMode='KernLeft'|'KernRight'|
    'KernBothSide')`. `groups[name] = ...` raises; `addGroup` without
    `kernMode` always makes KernBothSide.
  - Pairs: `kerning(master).set(((name, mode), (name, mode)), value)`, mode
    `'glyphMode'|'groupMode'`; zero-valued pairs are seeded as 1, then
    `scale(0.0)`, then the others, then `scale(1.0)` (fontport's sequence).
  - OpenType classes: read `fg.groups.getAsClassRecords()` →
    `'name: g1 g2'` (fgGroup exposes no members); write
    `fg.groups.fromDict({name: fgt.fgGroup(name, members,
    'FeaClassGroupMode', members[0])})`. `fromClassRecords` was a silent no-op.
  - Features: read `fontpr.get_font_info(font_id=fg.id)['openTypeFeatures']`
    (`fgFont.id` is the fontpr font id); write `fg.features.clear()`,
    `set_prefix`, `set_feature(tag, block)` per block, then
    `notifyChangesApplied`. FontLab's feature records keep the comments that
    FOLLOW a block inside that block, so the .fea is split at
    `feature TAG {` headers, not at `} TAG;`. Every block must close with
    `} TAG;` (fontport: unterminated blocks crash the native loader).
  - GDEF: per-glyph `flGlyph.otGlyphClass` / `otMarkClass`, carried in
    `Glyph.lib` as `com.fontlab.otGlyphClass` / `com.fontlab.otMarkClass`.
    Without them the rebuilt font compiled no GDEF.
- **Gate:** `diff` empty on the **stage b** field set on BasilMM. It has real
  per-master kerning (2085 entries on Bold, §3.7), 32 groups and a feature set.

### Stage C — components / element references

- **Stage C result (2026-11-19).** The C.1 proposal (no format change: the
  element name on every use is the link) is what was tested. Audit stage c =
  per master layer, element name → groups of glyphs sharing one
  `flShapeData` (`shapeData.id`).
  - **Gate on BasilMM: met** when the rebuilt `.vfc` is reopened and FontLab's
    *Duplicate Element Names* dialog is answered **Clean Up** ("merge them if
    they are identical or rename them if they are not"): stage-c diff = the 4
    source null contours only; 119 linked elements per master, e.g. `A`
    shared by 11 glyphs, identical to the source.
  - **Not possible from Python on FL 9.0.9809 (found so far):**
    `fl6.flShape(<flShapeData>)` and the `flShape` copy constructor fail
    ("Error creating object of type flShapeBuilder"); `flShape.shapeData` is
    read-only; `clone()` / `cloneTopLevel()` copy the data;
    `flPackage.replaceShapeWithReference(shape, process[, layer])` returns a
    shape (or None) without linking. **The same constructor is what
    TypeRig's Element panel *Link* uses** (`proxy/fl/actions/element.py`
    `element_link`), so that tool very likely fails on this build too —
    check it; re-test both on FL 9.1 (build 9813).
  - **UPDATE, same day: Python route found and in use.** `flLayer.addShape(
    <existing flShape>)` shares the element (same `shapeData.id`) — the route
    TypeRig's ElementComposer *Insert* has always used, with its "add twice,
    remove the first" trick. `create_font` now links same-named,
    same-outline shapes per master layer (registry in `trFontProxy.mount`,
    `trLayer.mount(elements=...)`, `_add_element_reference`). **Gate met
    without Clean Up:** full font, save + reopen, no *Duplicate Element
    Names* dialog, stage-c diff = the 4 source null contours.
  - `referenceCount` quirk: in a freshly built font the count is right (3 uses
    → 3) and deleting one use keeps the shared outline in the others. Adding
    into a font loaded from disk showed counts that lag by one (first add +0);
    after save + reopen the counts are recomputed.
  - Element panel **Link** (`proxy/fl/actions/element.py`) now inserts the
    reference with the same trick via `insertShape` (`_insert_reference`);
    helper verified in FL 9.0.9809 (shared data, right stack index); the
    panel button itself not clicked yet. `contour.py:258` still uses
    `fl6.flShape(<fgShape>)` — check it on FL9.
  - Old route kept for reference: rebuild → save → reopen with **Clean Up**. Caveat of Clean Up: it renames same-named elements
    whose outlines differ, which would change element names; BasilMM has
    none (every same-named use is one shared element in the source).
  - C.4 (FontLab's real components, `flLayer.components`) is still open: it
    needs a test font that has them.
- **C.1 proposal (2026-11-19, needs the owner's decision):**
  **Link by element name per master layer; no format change.**
  - What Stage A already writes is enough: every use of an element carries
    its name (`Shape.name`), its outline (element space) and its
    transform. Two shapes in the same master layer with the same element
    name are the same FontLab element.
  - Mount: per master layer, the first shape with a given name creates the
    `flShape`; every later shape with that name in the same master is built
    on the same `shapeData` with its own transform. Before linking, compare
    the outlines; if they differ, the shapes are NOT linked and a problem is
    logged (FontLab lets two different elements share a name).
  - Why not an element pool (`elements.xml` + contour-less references): it
    breaks the core `.trfont` rule that a `.trglyph` is a self-contained asset
    that belongs to no font (shared glyph pools, §Shared Glyph Pools in
    `trfont.md`). A glyph that points into a font-level pool is no longer
    portable. Duplicated outlines cost disk, not correctness.
  - Audit (stage c): per master, element name → set of glyphs using it, and
    "all uses have equal outlines". The gate compares that FL vs FL.
  - Glyphs (Stage D/Z): Glyphs has components (glyph references), not shared
    elements. An element whose outline equals a whole glyph layer (e.g. `A` in
    `Aacute`) can become a `GSComponent`; others stay outlines. This is the
    only place `Shape.component` (UFO base-glyph name) is needed.
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

- [x] D.1 Write `Typerig-Glyphs/Handouts/trfont_glyphs_roundtrip_handout.md`
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
- [x] D.2 List what cannot cross, with a reason per item (handout §4, to be filled during Z.3).

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
| Mask and service layers | `flGlyph.layers` | A.8 decided: layers whose name starts with `#` (FontLab-generated, e.g. `#instance`) are not carried; FontLab rebuilds them and adds its own guides on reopen. Other service/mask layers are carried. |
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
- `2026-11-19 | same | Stage A: eject side done (A.0-A.5, A.7, A.9, A.10). eject_report on 40 BasilMM glyphs: 829 -> 0 diff lines. create_font written (A.6); its first run crashed FontLab 9 and FL came back up only as a "FontLab Crash Report" window, left for the user to answer. | 1) Answer the FontLab crash dialog, reopen D:\Playground\Basil-Rev-2Wt.vfc. 2) In FL: audit.reload_typerig(); run create_font on ~5 glyphs with step_log=<file>; the last line of the log names the crashing step. 3) Fix, then the 40-glyph gate, then the full font.`
- `2026-11-19 | same | Stage B glue written (kern_map.py + tests 14/14, _fl_kerning/_kerning_into_fl, audit stage-b kerning in FL-native form); NOT run in FontLab. Stage C.1 proposal written: link elements by name per master layer, no format change. FontLab still on its crash-report window. | Same as previous line (crash dialog, step_log run), then Stage B probe of fg.groups / fg.features, then owner decision on C.1.`
- `2026-11-19 | same | Read the FontLab Adam suite (fontport guides, python-docs, remopy, instamix): §3.12. Code: kerning now via documented fgKerning.set(); features write refuses a tagless trailing `feature` (documented native heap over-read). Plan: Stage A gate now requires save + reopen; features mount is the top crash suspect. Installed FL 9.0.9809, beta is 9813. | Crash dialog still open. Then: step-log run of create_font with include_features=False, then True.`
- `2026-11-19 | same | STAGE A DONE. Full-font gate after save+reopen: 754 glyphs, 4 diffs = null contours in the source. Driver proxy/tr/roundtrip.py (build/compare as FontLab scripts, no MCP time limit). Fixed: create_font crash (glyph handles), live-node smooth/names + coordinate restore, package naming fields + info.dict + double info write after design space, starter glyph order, xmlio type-guessing of names (infinity -> inf), silent glyph drops in eject. | Stage B: run kerning/groups in FontLab; probe fg.features via fontpr.get_font_info; add groups/features to the FL dump; then the stage-b gate.`
- `2026-11-19 | same | STAGE B DONE. Full-font stage-b gate after save+reopen: 4 diffs (null contours). compile_features dry run: GDEF/GPOS/GSUB SHA-256 identical to source. Kerning classes via addGroup(kernMode=), pairs via set((name,mode),(name,mode)), OT classes via fg.groups.fromDict(fgGroup), features via fontpr openTypeFeatures + header-based split, GDEF via otGlyphClass/otMarkClass in Glyph.lib. | Stage C: element links (C.1 proposal; FontLab's own "Clean Up" on open does the same merge).`
- `2026-11-19 | same | STAGE C met on BasilMM via FontLab's on-open Clean Up: stage-c gate (element links per master) = 4 diffs (null contours), 119 linked elements per master identical to source. No Python linking route on FL 9.0.9809 (flShape(flShapeData) fails - TypeRig Element Link likely broken on this build). | Owner: confirm C.1 (no format change). Then Stage D handout; C.4 needs a font with FL components; re-test linking on FL 9.1 beta 9813.`
- `2026-11-19 | same | STAGE D DONE: Typerig-Glyphs/Handouts/trfont_glyphs_roundtrip_handout.md (+ Memory/project_trfont_glyphs.md there). Code read of proxy/gs3 found: outline-shape transforms ignored on mount (same bug as A.0), node names dropped, no guides/note/lib on eject, no font bridge. | Mac: Stage Z.0 (gs3 gaps), Z.1 font bridge, Z.2 Glyphs dumper. Windows/FL: C.4 needs a font with FL components; re-test element linking on FL 9.1 (9813); check TypeRig Element Link on 9.0.9809.`
- `2026-11-19 | same | STAGE C DONE in Python: create_font links same-named/same-outline elements per master via layer.addShape(existing shape) (ElementComposer's route); full-font gate after save+reopen = 4 diffs, no Duplicate Element Names dialog. Element panel Link fixed for FL9 (_insert_reference). | Click-test Element Link in the panel; check contour.py flShape(fgShape) on FL9; C.4 needs a font with FL components; Stage Z on the Mac.`
- `2026-11-19 | same | Part one closed. Part two (true UFO-level components incl. C.4, warnings for unmodelled FontLab features, spec + schema + validator -> format v1.0) planned in HANDOUT-trfont-v1.md. | Continue there.`
