# TypeRig

A Python framework for font design and engineering. Started as a personal toolkit for working inside FontLab, grew over the years into a standalone geometry and interpolation core with a bunch of GUI tools on top.

TypeRig has objects for manipulating font outlines — points, nodes, contours, shapes, layers and glyphs — plus math helpers for interpolation, adaptive scaling and curve processing. A proxy layer wraps FontLab internals so the same code works both standalone and inside the host app. On top of that sits a collection of GUI panels, toolbars, and dialog tools that cover most of what I need in a daily font production workflow. Experimental, evolving, and perpetually work-in-progress.

## Install the Python library

From a local checkout (Python 3.10 or newer):

```sh
python -m pip install .
```

For development, use `python -m pip install -e .` instead. Release versions come
from Git tags via `hatch-vcs`; see [releases](https://github.com/kateliev/TypeRig/blob/master/RELEASING.md) and [PyPI setup](https://github.com/kateliev/TypeRig/blob/master/PYPI.md).

This installs the `typerig` package from `Lib/`, including its bundled resources,
and the `fonttools` dependency used by font file I/O. For example:

```python
from typerig.core.objects.point import Point
```

The geometry core runs outside a font editor. Host proxies require their
respective FontLab or Glyphs APIs. This installation does not install the GUI
scripts from `Scripts/`; use the host installers for those: `install.vfpy`
(run from FontLab's scripting window) or `install.py` for FontLab, and
`install.glyphs.py` for Glyphs 3 and 4.

## FontLab Scripts and Tools

The FontLab-facing part of TypeRig is the biggest chunk in practice — a collection of GUI tools that cover most of the font design and production workflow. Built with PythonQt, hooked into FontLab's undo, multi-master aware.

### TypeRig Panel (`typerig-panel.py`)

The main interface is a dockable panel that loads sub-panels as tabs. Layer selectors and glyph-scope controls in the masthead. Panel visibility persisted via JSON. The available sub-panels are:

**Node** — The panel I use most. Node insertion (at arbitrary time, at extremes, at contour start), removal, conversion between on/off-curve types. Smart node movement with multiple methods: plain shift, proportional (LERP), italic-angle slant, slope-following, and a smart mode that preserves handle relationships. Node alignment to other nodes, to font metrics (ascender, caps height, x-height, baseline, descender, measurement line), and to user-defined targets with optional intercept and dimension-preserving modes. Slope copy/paste with flipping. Hobby spline tension copy/paste. Node coordinate banking for complex multi-step operations.  Primitive drawing tools: circle from 2 or 3 selected nodes, square from diagonal or midpoints.

**Contour** — Contour closing, opening, reversing, and boolean operations (union, subtract, intersect, exclude). Contour alignment to other contours, to font metrics, and bounding-box-relative positioning. Contour group alignment (A-to-B). Distribution (horizontal and vertical) of multiple contours. Contour reordering by position.

**Corner** — Smart corner filter management with multi-master presets. Apply, remove, and find-and-remove smart corners by preset value. Live slider control for captured smart angles. Mitre, round, loop, and ink-trap corner operations with dialog-based parameter entry. Corner rebuild for re-processing existing corners.

**Layer** — Full layer management: add, duplicate, delete, duplicate-as-mask. Copy and paste whole layer groups. Layer visibility toggle. Layer type assignment (mask, wireframe, service). Element-level operations across layers: swap, pull, push, clean. Element locking/unlocking. Contour-level cross-layer operations: pull/push nodes, copy/paste outlines between layers, paste by layer name. Side-by-side layer comparison view. Zero setup interpolation between selected layers.

**Delta** — The adaptive scaling (delta machine) panel. Virtual axis setup with stem values per master layer. Target layer generation with configurable horizontal/vertical stems, width, and height. Supports extrapolation, intensity control, italic-angle compensation, and multiple transform origins. Axis configurations can be saved/loaded from Font Lib or external JSON files. Integrates with the core delta-scaling engine based on Tim Ahrens' methodology.

**Element** — Shape (element) manipulation: naming, unlinking references, deletion, transform reset, transform rounding, auto-reorder by position, ungroup-all. Shape insertion and replacement from font-wide element library. Shape alignment to other shapes, to layer bounds, and to font metrics. An expression-based element composition system with a scripting syntax supporting coordinate placement by node tags, anchor names, bbox positions, per-layer overrides, and element swapping.

**Clipboard** — Multi-master aware contour clipboard using core-object storage. Copy full contours or partial selections. Paste with configurable transform (translate, scale, rotate, skew), delta machine size fit and transform origin. Supports reversed and partial paste modes as well as drawing and connecting multiple (selected in UI) segments. Save/load clipboard contents to XML files for cross-session and cross-font workflows.

**Metrics** — Sidebearing and advance width tools. Copy metrics from other glyphs by name with percentage and unit adjustments. Metric expressions: get, set, auto-link from element references, and unlink. Copy bounding-box dimensions (width and height) between glyphs with proportional adjustments.

**Anchor** — Anchor management with tree-view display per layer. Add, move, and clear anchors with various coordinate input modes: absolute positions, font-metric-relative placement (ascender, caps, x-height, baseline, descender), bounding-box-relative positions, and expression-based coordinates. Per-layer coordinate lists for multi-master workflows. Italic-angle-aware positioning.

**Guide** — Guideline creation at percentage-based positions relative to advance width, bounding box, or font metrics (x-height, caps height, ascender, descender). Named and tagged guidelines with color assignment. Vertical and horizontal guide placement. Source glyph reference for cross-glyph guide alignment. Glyph tagging and node naming tools.

**Glyph** — Basic glyph operations: rename, copy/duplicate with configurable options (outlines, guidelines, anchors, tags, flags, references, LSB/RSB). Batch glyph duplication with auto-numbering and transform application.

**Outline** — Interactive node table with sortable columns showing node index, element index, contour index, coordinates, and node type per layer. Direct coordinate editing in the table with live viewport update. Synchronized selection between table and canvas.

**Pairs** — Kern string generation. Filler-based pair construction with customizable left/right fillers. Multiple pattern modes for systematic kerning string creation. Import kern data from DTL `.krn`, `.cla`, and `.afm` files.

**Stats** — Glyph statistics: bounding box dimensions, advance widths, sidebearings across layers. Comparative view with percentage and unit modes. Character-set-based batch queries.

**AutoMetrics** — Automated metric assignment tools.

**CopyKerning** — Kern pair copying between glyphs and layers with class-aware support. Source pair lookup with expression adjustment. Group kerning mode with automatic class resolution.

**CleanKerning** — Kerning table cleanup utilities.

**Cleanup** — Outline cleanup: remove redundant nodes and debris. Analyze reports node counts and deviation without touching the outlines, Fix Degeneracies drops the debris, Clean & Simplify also refits curves within a tolerance, and Show Locks selects the nodes that would be kept. Layers follow the masthead and can be cleaned in sync or one by one; output curves stay cubic, convert to quadratic, or keep whatever kind they had. Groups, components and shared elements are skipped. Geometry in `core.algo.outline_cleanup`.

**StemSnap** — Find stems or strokes whose width is close to one of the master's standard stems and snap them onto it; anything outside the capture band is left alone. Two methods: node-level H/V stems, where corrections cascade IUP-style over the stem's contour family so nothing tears, and whole-contour strokes measured on the medial axis at any angle, with optional MAT stroke separation first. Targets come from each master's PostScript stems or a typed list, tolerance in units or percent. Geometry in `core.algo.stem_snap` and `stroke_snap`.

**MagicScale** — Stem-preserving 1D warp, per axis: the stems keep their thickness and the whitespace absorbs the change, redistributed by counter (中宫) and gravity (重心). Live editing writes into the glyph's own nodes like the Delta panel, with Reset and Apply. Geometry in `core.algo.magic_scale`.

**ElementComposer** — The naming half of element work: insert, replace and swap named elements across glyphs. Element management itself (merge, split, group, arrange, align, transform, round, style, link) lives in the Element panel.

Which tabs load is set in `Panel/typerig-panel-config.json` — the shipped default enables Node, Contour, Clipboard, Layer, Element, Delta, Cleanup, StemSnap and MagicScale and leaves the rest off. Two more panels sit in the folder unlisted and experimental: **Symbol Explorer** (`Explorer.py`), which searches a symbol set by tag and category with glyph and contour-part previews, and **Delta New** (`DeltaNew.py`), the canvas-driven rewrite of the Delta panel.

### TypeRig Manager (`typerig-manager.py`)

A separate dialog for font-level operations:

**FontMetrics** — Multi-master font metrics editor with table-based interface for all vertical metrics across all master layers. Font zone management: add, remove, import/export zones as JSON. Zone creation from metric references.

**Kerning** — Kerning overview for the whole font: browse, filter and edit pairs across masters in a table.

**KernGroups** — Kern class editor. Build, rename and merge classes, set the first/second key glyph, and import or export class sets as JSON.

**Impex** — A table of import/export actions (type, action, options) run in batch over the font. Currently ships the AFM kerning action (`ImpexActions/afm.py`).

### Toolbars

Dockable toolbars for quick access to common operations:

**Node Toolbar** — Node insertion, removal, extreme insertion, start-point management, and corner operations (mitre, round, loop, trap, rebuild) as toolbar buttons.

**Node Align Toolbar** — Node alignment to min/max coordinates, user-set targets, and font metrics (ascender, caps, x-height, baseline, descender, measurement line) with intercept, dimension-preserving, and smart-align options.

**Node Slope Toolbar** — Slope copy/paste with italic angle support. Paste to min/max pivot with optional horizontal flip.

**Contour Toolbar** — Contour boolean operations, closing, reversing, and winding correction as toolbar buttons.

**Curve Toolbar** — Line-to-curve and curve-to-line conversion, Tunni and Hobby optimization (dialog, or fixed 1.0 / 0.95 / 0.90 presets), proportional handles (dialog, or 0.5 / 0.3 / 0) and Hobby tension push.

**MacOS Panel** (`toolbar-mac.py`) — A unified panel-based interface that consolidates node, alignment, slope, corner, contour, and curve tools into a single flow layout. This exists because `QToolBar` widgets don't function properly in MacOS FontLab, so all toolbar functionality is reimplemented as a panel with `TRFlowLayout`.

### Standalone Tools

Separate dialog tools for specific tasks:

**Delta Preview** (`TR-DeltaPreview.py`) — Visual preview of delta machine results without writing to the font. Dual-pane interface with source masters and computed target results rendered as `QPainterPath` objects built from core geometry. Live zoom and padding controls. Execute-to-font mode for committing approved results as real layers.

**Comparator** (`TR-Comparator.py`) — Cross-font and cross-layer glyph comparison. Detect outline differences, missing layers, shifted-but-identical layers, and anchor mismatches between two fonts or between layers within a single font. Visual overlay rendering with color-coded difference display. Time-stamp-aware comparison for change tracking. Batch processing with progress bar and font mark colorization.

**Match Contours** (`TR-MatchContours.py`) — Visual contour matching across masters. Contour order tab for drag-and-drop reordering with winding direction display (color-coded CW/CCW). Contour start-point tab for aligning start nodes across masters with corner-based (BL, TL, BR, TR) and sequential (next/prev) start-point adjustment. Visual icon rendering per contour per master.

**Encoder** (`TR-EncodeGlyphs.py`) — Unicode encoding management. Load encodings from JSON, FontLab `.nam` files, or Google protobuf `.textproto` files. Apply or clear unicode mappings for entire fonts or selected glyphs. Save/load encoding data to Font Lib.

**Sort Anchors** (`TR-SortAnchors.py`) — Sort anchor ordering across all masters for consistency. Reference-master mode preserves the anchor order from a chosen master. Alphabetical mode sorts all anchors uniformly. Verbose mode reports missing anchors across masters.

**Propagate Anchors** (`TR-PropagateAnchors.py`) — Table-driven batch anchor copying between glyphs. Per-action configuration for source glyph, anchor selection, destination glyphs, layer scope, and copy options (absolute/relative positioning with LSB/RSB/advance-relative modes, collision handling with overwrite or rename, suffix control). Save/load action tables as JSON for repeatable workflows.

**Export Glyph** (`TR-ExportGlyph.py`) — Export individual glyphs as `.trglyph` XML files via the core serialization system. Uses the proxy-to-core eject mechanism for round-trip export.

**Import Glyph** (`TR-ImportGlyph.py`) — The other direction: read a `.trglyph` file back into a glyph, layer by layer.

**Font IO** (`TR-ExportFont.py`) — Whole-font `.trfont` write/read round-trip from FontLab, over the folder-level serialization in `core.fileio.trfont`.

**Copy Layers** (`TR-CopyLayers.py`) — Copy selected layers between two open fonts.

**Copy Anchors** (`TR-CopyAnchors.py`) — Copy selected anchors between two open fonts.

**Rename Anchors** (`TR-RenameAnchors.py`) — Batch anchor renaming across masters.

**trconvert** (`trconvert.py`) — Not a FontLab tool: a pure-Python CLI converting between `.trfont` and UFO 3 (`ufo2tr`, `tr2ufo`, `roundtrip`). Needs `fontTools`. `roundtrip` runs both directions on a temporary copy and reports PASS/FAIL with a structural diff.

### Popups and Utilities

`Scripts/TypeRig Popups/` holds two keyboard-friendly popups — node align (`popup-node-align.py`) and contour cut (`popup-contour-cut.py`). `Scripts/Delta Machine/DeltaMachine.py` is the original standalone Delta Machine dialog, kept alongside the Delta panel. `Scripts/TypeRig GUI/Utils/` holds small single-purpose scripts: select by anchor, copy metrics, copy metric bindings.

## Architecture

Two packages, connected by a proxy layer.

### Core (`typerig.core`)

Pure Python, runs anywhere — CPython, Pyodide in a browser, whatever. The geometry, interpolation and algorithm modules carry no external dependencies; `fontTools` is imported lazily and only where a format or a table demands it (quadratic output in Outline Cleanup, the full Unicode script table in TR Kern, compiled-font kerning). Two file-format modules do need it outright: `fileio.ufo` and `fileio.designspace`.

**`core.objects`** — geometric primitives and containers:

- `Point`, `Line`, `CubicBezier`, `QuadraticBezier` — basic geometry with operator overloading and complex-number math.
- `Node` — on/off-curve point with navigation (`next`, `prev`, `next_on`, `prev_on`), corner operations (mitre, round, trap), Hobby spline insertion and per-node stem weights for adaptive scaling.
- `Contour` — ordered node sequence supporting winding detection, segment iteration (line / cubic / quadratic with implicit on-curve expansion), Hobby spline solving, analytical outline offset with miter joins, SDF-clamped offset and compensated scaling.
- `Shape` — contour container with bounds, sorting, SDF computation, outline offset and per-contour angle-compensated scaling.
- `Layer` — shape container carrying advance widths, anchors, stem values and transformation origins. Offers linear, directional (polar-domain) and adaptive-scaling interpolation functions, plus brute-force dimension targeting via virtual axes.
- `Glyph` — layer container with unicode mapping and virtual-axis construction across masters.
- `Anchor` — named position marker for mark attachment and cursive connection.
- `Atom`, `Member`, `Container` — base classes providing UID tracking, parent-child navigation and typed-list semantics with coercion and locking.
- `PointArray`, `DeltaArray`, `DeltaScale` — array types for batch point math, multi-master interpolation and stem-preserving scaling.
- `Transform`, `TransformOrigin` — affine matrix and alignment-origin enums.
- `SignedDistanceField` — grid-based SDF for topology-aware offset clamping and gradient queries.
- `HobbySpline` — MetaPost-derived Hobby spline solver with configurable tension, curl and explicit tangent constraints.
- `Font`, `Master`, `Instance`, `Axis` — the font level above `Glyph`: masters, instances and a design space, so a whole font lives in core and not only a glyph. `FontFile` is the older compatibility wrapper over `Font` plus `.trfont` I/O.
- `Kerning`, `KernPair`, `Groups` — UFO-aligned kerning model: pairs on one side, flat group name → glyph list on the other.
- `Guideline`, `Encoding` — UFO-spec per-glyph and per-layer guidelines, and unicode/name mapping.
- `MetaPen` — pen stroke envelopes, after `plain_ex.mp` from MetaType1 (Jackowski and Nowacki).
- `ARAP` — as-rigid-as-possible contour deformation.
- `Matrix`, `Collection` — small matrix helper and typed collection used by the above.

**`core.func`** — stateless math and geometry helpers:

- `math` — linear interpolation, rational fractions, randomisation, SLERP for angles, directional interpolation, Hobby velocity, matrix solvers.
- `transform` — delta machine, adaptive scaling (extending on Tim Ahrens), directional adaptive scaling, stem compensation, italic-angle correction, per-contour angle adjustment and utilities.
- `geometry` — CCW test, collinearity, intersection routines.
- `utils` — type-checking helpers.

**`core.fileio`** — serialisation:

- `xmlio` — XML round-trip engine with class registry, compact attribute encoding and lib-attribute support. Powers the `.trfont` experimental format.
- `trfont` — the folder level of `.trfont` that `xmlio` does not cover: font, masters, glyph files on disk.
- `ufo` — pure-Python `.trfont` ↔ UFO 3 converter (`fontTools.ufoLib` for plists and `.glif`).
- `designspace` — axes, masters and instances ↔ `.designspace`.
- `svgio` — SVG path filtering and pen-based import (was `svg`).
- `nam` — FontLab `.nam` encoding file parser.
- `textproto` — Google protobuf `.textproto` encoding file parser.
- `afm`, `krn`, `cla`, `flc` — kerning and class interchange: AFM pairs as autokerners and DTL KernMaster hand them back, DTL `.krn` and `.cla`, legacy FontLab `.flc`.
- `otkern` — flat glyph-to-glyph kerning read out of a compiled `.otf`/`.ttf`, GPOS PairPos flattened the way a shaper applies it.
- `kerndoc` — a font for kerning work outside an editor: a `.trfont`, UFO or designspace read into core with what kerning needs, and written back without touching anything else.

**`core.algo`** — the algorithm layer added since this list was first written. Pure math on core objects, no host, unit-testable outside any editor:

- `outline_cleanup` (+ a dozen `outline_cleanup_*` modules) — staged outline cleanup: degeneracy removal, lock detection, Levien and Schneider curve fitting, simplification, integer rounding, quadratic output, multi-master synchronised cleaning, and a trace front end.
- `stem_snap`, `stroke_snap`, `stem_center`, `chord_probe` — stem detection and snapping. Stem width at a point comes from the outline chord along the normal of the nearest outline point, so diagonals and curves measure like uprights.
- `mat`, `mat_extract`, `csf`, `stroke_sep` (+ `stroke_sep_*`) — medial axis transform, curvilinear shape features after Berio, Leymarie, Asente and Echevarria (*StrokeStyles*, TOG 2022), and the stroke separator built on them: junctions, links, graph, planar face slicer, solver.
- `magic_scale` — stem-preserving 1D warp with counter and gravity distribution.
- `matchmaker` — physics-based polygon matching for point-compatible interpolation, after Sederberg and Greenwood (SIGGRAPH '92).
- `design_transfer` — reproduce a design change made in one master on another, as best-fit affine plus bbox-normalised per-point residual.
- `kern_analyze`, `kern_rules`, `kern_model`, `kern_groups`, `kern_query`, `kern_reclass`, `kern_cleanup`, `kern_strings`, `kern_script` — TR Kern: read-only analysis that reports findings as a tree, rule linting, class reclassification, cleanup and kern-string generation.
- `cjk` — CJK design analysis and per-glyph measurement, no host and no numpy.
- `element_ops`, `placement`, `node_slide`, `intersect` — the hostless half of element management, fit-into-bounds transforms, sliding an on-curve node along its segment by de Casteljau, and curve-curve intersection by bezier clipping.

**`core.actions`** — host-independent tool logic, so a panel, a CLI and a test can share one implementation. Node, contour, curve, draw, layer, cut, clipboard and delta actions, the glyph-group and designspace actions, and the TR Kern trio: `kern_engine` (the window's state and steps), `kern_font` (a core `Font` as a kerning host) and `kern_cli` — `tr-kern` on the command line for UFO, designspace and `.trfont` files, which snapshots every write next to the font.

**`core.base`** — `message` (the `output()` reporting and warning classes used throughout) and `lib_keys` (the font-lib key names TypeRig writes under).

### Proxy — FontLab Layer (`typerig.proxy.fl`)

Depends on FontLab (`fontlab`, `fontgate`, `PythonQt`). Proxy objects, GUI bits, and action collectors.

**`proxy.fl.objects`** — FontLab proxy objects:

- `pFont` / `pFontMetrics` — font access: glyph lookup, font metrics (all vertical metrics per master), kerning, classes, font lib, update/undo management.
- `pGlyph` / `eGlyph` — glyph proxy with full layer, shape, contour, node, anchor, guideline, component, and metric access. `eGlyph` extends with tool-preparation methods (`_prepareLayers`) and multi-master-aware operations.
- `pShape` / `eShape` — shape proxy with transform, bounds, naming, alignment, and reference management.
- `pContour` — contour proxy with alignment, bounds, and winding operations.
- `pNode` / `eNode` / `eNodesContainer` — node proxies with smart-angle access, coordinate manipulation, and batch container operations.
- `eCurveEx` — extended curve proxy with curvature analysis and Hobby tension control.
- `pKerning` — kerning proxy: pairs, classes and the key-glyph lookup behind the kerning tools.
- `dictComposer` — the element composition engine behind the Element and Element Composer panels.
- `GlyphSampler` / `MetricSampler` — outline sampling for measurement and probing.
- `cjk.Geometry` — CJK-specific glyph geometry feeding `core.algo.cjk`.
- `base`, `string` — shared base classes (`Coord` and friends) and glyph-name/string helpers.

**`proxy.fl.actions`** — Action collectors that separate tool logic from GUI:

- `TRNodeActionCollector` — all node operations: insert, remove, move (smart/LERP/slope/slant), align, slope copy/paste, corner operations (mitre, round, loop, trap, rebuild), Hobby tension manipulation.
- `TRCurveActionCollector` — segment conversion, curve optimization, Hobby tension copy/paste.
- `TRContourActionCollector` — contour close/open, reverse, boolean operations, alignment, distribution, reordering.
- `TRDrawActionCollector` — primitive drawing (circles, squares from selected nodes).
- `TRLayerActionCollector` — layer add/delete/duplicate, visibility, type assignment, element operations, cross-layer contour transfer.
- `TRElementActionCollector` — element merge, split, group, ungroup, arrange, align, transform, round and style.
- `TRCutActionCollector` — node-exact contour cutting and stroke separation across masters.
- `mat_extract`, `stem_center` — the FontLab side of medial-axis extraction and snapping nodes to a stem centreline.

**`proxy.fl.gui`** — GUI components:

- `widgets` — `CustomPushButton` with icon-font support, `TRFlowLayout`, `TRVTabWidget`/`TRHTabWidget`, `TRCheckTableView`, `TRTableView`, `TRSliderCtrl`, `TRTransformCtrl`, `TRDeltaLayerTree`, `CustomSpinBox`/`CustomSpinLabel`/`CustomLineEdit`, `getProcessGlyphs` (glyph-scope resolver), `getTRIconFont`/`getTRIconFontPath` (custom icon font loader).
- `dialogs` — `TRLayerSelectDLG`/`TRLayerSelectNEW` (layer chooser with search/filter), `TR1FieldDLG`/`TR2FieldDLG` (quick input dialogs), `TRMsgSimple`.
- `styles` — `css_tr_button` and `css_tr_button_dark` stylesheets with automatic dark/light mode detection via `fl6.flPreferences().isDark`.
- `drawing` — Canvas drawing utilities: `TRDrawIcon`, `build_selection_contour`, `draw_contour_mode`, `draw_selection_mode`, `draw_node_markers`.
- `canvas_overlay`, `canvas_controls`, `overlay_math` — reusable base for tools that draw on, and take mouse input from, the FontLab 8 glyph canvas: attachment to the active canvas, font ↔ viewport mapping, change detection, and on-canvas icon strips. Used by Delta New and Stem Snap.
- `QtGui` — the binding shim every module imports instead of PythonQt's `QtGui` directly, so widget differences stay in one place.

**`proxy.fl.application`** — FontLab application access:

- `pWorkspace` — workspace proxy for canvas access, text block/glyph queries, active kern pair retrieval, and frame creation.
- `pItems` — item notification helpers for undo.
- `automat` — runs FontLab's own UI actions from script.

**`proxy.fl.pens`** — pen protocol adapters (`abstractPen`, `outlinePen`) for feeding FL outlines through pen-based code.

### Proxy — Core Bridge (`typerig.proxy.tr`)

Each proxy class — `trNode`, `trContour`, `trShape`, `trLayer`, `trGlyph`, `trFont`, `trAnchor` — inherits from its core counterpart and holds a `.host` reference to the corresponding FL object.

Attribute access is rerouted through a `__meta__` mapping: reads and writes to mapped names (e.g. `x`, `y`, `name`, `closed`) go straight to the host, everything else follows the normal core path. So the same core algorithms work on proxy objects with live FL data without extra glue.

**Eject / Mount** — every proxy exposes `.eject()` to detach a pure core copy and `.mount(core_obj)` to write values back into the host. Eject for computation, mount to commit — keeps FL undo intact and avoids side-effects during multi-step operations.

**Host sync** — when structural changes occur (node count differs after a mount), the proxy rebuilds the FL contour and calls `_sync_host()` up the parent chain so the FL object tree stays consistent.

### Proxy — Glyphs 3 (`typerig.proxy.gs3`)

A second host proxy, for Glyphs 3 — added after the FontLab one and not a port of it. Same idea: `objects` wrap Glyphs' own classes (`glyph`, `layer`, `shape`, `contour`, `node`, `anchor`, `kern`, `pathops`) so the core algorithms run unchanged, and `gui` is a small panel toolkit over `vanilla`: `panel_base` and `toolbar_base` for tabs and toolbars, a `masthead` with the same glyph/layer scope controls as the FontLab panel, `entry`/`widgets`/`list_cells`/`tree_view` for controls, `icon_font`, `thumbnail`, `label_color`, `tint_list`, plus canvas pieces (`node_ghost`, `node_slider`, `stem_probe`, `layer_toast`, `key_nudge`) and the config modules each tool stores its state in.

The panels that exist on both hosts share everything below the GUI: Cleanup, Stem Snap and TR Kern were written once in `core.algo`/`core.actions` and shelled twice. Install with `install.glyphs.py`.

## Web

The core package also runs in the browser via Pyodide: it loads TypeRig modules from GitHub at runtime, stubs the host-dependent parts, and gives you a Python editor on an HTML canvas.

The viewer itself no longer lives here. `Web/GlyphViewer` moved out to [FontRig](https://github.com/kateliev/FontRig) in March 2026, which is where the browser work continues; this repository keeps only the core it imports.

## Docs and tests

`Docs/` holds reference material generated from and about the two proxy layers — `Docs/Core` and `Docs/Proxy`, each with an API reference in JSON plus handouts and documents. `tests/` covers the release and packaging machinery, not the geometry; the core's own tests sit next to the code they test (`core/objects/test_objects.py`, `core/actions/test_actions.py`, `core/algo/test_outline_cleanup.py`, `test_cjk.py`, `test_element_ops.py`). CI runs them on Python 3.11 across Linux, macOS and Windows; the exact recipe is in `.github/workflows/check.yml`.

## License

TypeRig is licensed under the **GNU Affero General Public License, version 3** (`AGPL-3.0-only`), with an additional permission for running it inside FontLab and Glyphs. See [LICENSE](https://github.com/kateliev/TypeRig/blob/master/LICENSE) and [NOTICE](https://github.com/kateliev/TypeRig/blob/master/NOTICE).

In short: you may use TypeRig freely, including for commercial font work. Fonts and other files you make with it are yours and are not covered by this license. If you distribute software that includes TypeRig, that software must be released under the AGPL with its full source code; if you modify TypeRig and let others use it over a network, you must offer them its source code.

Releases up to and including 3.0.0 were published under the Mozilla Public License 2.0; copies received under that license remain under it.

**Text and data mining.** The rightholders expressly reserve the use of this repository for text and data mining, including training AI models, under Article 4(3) of Directive (EU) 2019/790. See section 5 of [NOTICE](https://github.com/kateliev/TypeRig/blob/master/NOTICE).

No warranties. By using this you agree that you use it at your own risk.

© Vassil Kateliev — [kateliev.com](http://www.kateliev.com) | Karandash Type Foundry — [karandash.eu](http://www.karandash.eu)

[typerig.com](http://www.typerig.com)
