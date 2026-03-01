# TypeRig

A Python framework for font design and engineering, providing an extensive suite of tools for professional typeface development inside FontLab, alongside a standalone pure-Python geometry and interpolation core.

TypeRig offers geometric objects for manipulating font outlines — points, nodes, contours, shapes, layers and glyphs — together with advanced mathematical tools for interpolation, adaptive scaling and curve processing. A parallel proxy layer transparently wraps FontLab internals, so the same operations work both standalone and inside the host application. On top of this foundation sits a large collection of GUI panels, toolbars, and standalone dialog tools that provide professional font designers with a comprehensive production environment within FontLab.

## FontLab Scripts and Tools

The FontLab-facing part of TypeRig is its most extensive component — a rich set of GUI-driven tools that cover virtually every aspect of the font design and production workflow. All tools are built with PythonQt, integrate with FontLab's undo system, and support multi-master workflows out of the box.

### TypeRig Panel (`typerig-panel.py`)

The main interface is a dockable, always-on-top panel that dynamically loads sub-panels as tabbed modules. It features a masthead with layer-selection controls (active layer, master layers, selected layers) and glyph-scope selectors (active glyph, glyph window, font window selection). Panel visibility is user-configurable and persisted via JSON. The available sub-panels are:

**Node** — The most feature-dense panel. Node insertion (at arbitrary time, at extremes, at contour start), removal, conversion between on/off-curve types. Smart node movement with multiple methods: plain shift, proportional (LERP), italic-angle slant, slope-following, and a smart mode that preserves handle relationships. Node alignment to other nodes, to font metrics (ascender, caps height, x-height, baseline, descender, measurement line), and to user-defined targets with optional intercept and dimension-preserving modes. Slope copy/paste with flipping. Hobby spline tension copy/paste. Node coordinate banking for complex multi-step operations.  Primitive drawing tools: circle from 2 or 3 selected nodes, square from diagonal or midpoints.

**Contour** — Contour closing, opening, reversing, and boolean operations (union, subtract, intersect, exclude). Contour alignment to other contours, to font metrics, and bounding-box-relative positioning. Contour group alignment (A-to-B). Distribution (horizontal and vertical) of multiple contours. Contour reordering by position.

**Corner** — Smart corner filter management with multi-master presets. Apply, remove, and find-and-remove smart corners by preset value. Live slider control for captured smart angles. Mitre, round, loop, and ink-trap corner operations with dialog-based parameter entry. Corner rebuild for re-processing existing corners.

**Layer** — Full layer management: add, duplicate, delete, duplicate-as-mask. Copy and paste whole layer groups. Layer visibility toggle. Layer type assignment (mask, wireframe, service). Element-level operations across layers: swap, pull, push, clean. Element locking/unlocking. Contour-level cross-layer operations: pull/push nodes, copy/paste outlines between layers, paste by layer name. Side-by-side layer comparison view. Zero setup interpolation between selected layers.

**Delta** — The adaptive scaling (delta machine) panel. Virtual axis setup with stem values per master layer. Target layer generation with configurable horizontal/vertical stems, width, and height. Supports extrapolation, intensity control, italic-angle compensation, and multiple transform origins. Axis configurations can be saved/loaded from Font Lib or external JSON files. Integrates with the core delta-scaling engine based on Tim Ahrens' methodology.

**Element** — Shape (element) manipulation: naming, unlinking references, deletion, transform reset, transform rounding, auto-reorder by position, ungroup-all. Shape insertion and replacement from font-wide element library. Shape alignment to other shapes, to layer bounds, and to font metrics. A powerful expression-based element composition system with a full scripting syntax supporting coordinate placement by node tags, anchor names, bbox positions, per-layer overrides, and element swapping.

**Clipboard** — Multiple master aware contour clipboard with core-object storage for lossless copy/paste. Copy full contours or partial selections. Paste with configurable transform (translate, scale, rotate, skew), delta machine size fit and transform origin. Supports reversed and partial paste modes as well as drawing and connecting multiple (selected in UI) segments. Save/load clipboard contents to XML files for cross-session and cross-font workflows.

**Metrics** — Sidebearing and advance width tools. Copy metrics from other glyphs by name with percentage and unit adjustments. Metric expressions: get, set, auto-link from element references, and unlink. Copy bounding-box dimensions (width and height) between glyphs with proportional adjustments.

**Anchor** — Anchor management with tree-view display per layer. Add, move, and clear anchors with flexible coordinate input: absolute positions, font-metric-relative placement (ascender, caps, x-height, baseline, descender), bounding-box-relative positions, and expression-based coordinates. Per-layer coordinate lists for multi-master workflows. Italic-angle-aware positioning.

**Guide** — Guideline creation at percentage-based positions relative to advance width, bounding box, or font metrics (x-height, caps height, ascender, descender). Named and tagged guidelines with color assignment. Vertical and horizontal guide placement. Source glyph reference for cross-glyph guide alignment. Glyph tagging and node naming tools.

**Glyph** — Basic glyph operations: rename, copy/duplicate with configurable options (outlines, guidelines, anchors, tags, flags, references, LSB/RSB). Batch glyph duplication with auto-numbering and transform application.

**Outline** — Interactive node table with sortable columns showing node index, element index, contour index, coordinates, and node type per layer. Direct coordinate editing in the table with live viewport update. Synchronized selection between table and canvas.

**Pairs** — Kern string generation. Filler-based pair construction with customizable left/right fillers. Multiple pattern modes for systematic kerning string creation. Import kern data from DTL `.krn`, `.cla`, and `.afm` files.

**Stats** — Glyph statistics: bounding box dimensions, advance widths, sidebearings across layers. Comparative view with percentage and unit modes. Character-set-based batch queries.

**AutoMetrics** — Automated metric assignment tools.

**CopyKerning** — Kern pair copying between glyphs and layers with class-aware support. Source pair lookup with expression adjustment. Group kerning mode with automatic class resolution.

**CleanKerning** — Kerning table cleanup utilities.

### TypeRig Manager (`typerig-manager.py`)

A separate dialog for font-level operations, dynamically loading its own set of sub-panels:

**FontMetrics** — Multi-master font metrics editor with table-based interface for all vertical metrics across all master layers. Font zone management: add, remove, import/export zones as JSON. Zone creation from metric references.

### Toolbars

Dockable toolbars that provide quick access to common operations, complementing the panel system:

**Node Toolbar** — Node insertion, removal, extreme insertion, start-point management, and corner operations (mitre, round, loop, trap, rebuild) as toolbar buttons.

**Node Align Toolbar** — Node alignment to min/max coordinates, user-set targets, and font metrics (ascender, caps, x-height, baseline, descender, measurement line) with intercept, dimension-preserving, and smart-align options.

**Node Slope Toolbar** — Slope copy/paste with italic angle support. Paste to min/max pivot with optional horizontal flip.

**Contour Toolbar** — Contour boolean operations, closing, reversing, and winding correction as toolbar buttons.

**MacOS Panel** (`toolbar-mac.py`) — A unified panel-based interface that consolidates node, alignment, slope, corner, contour, and curve tools into a single flow layout. This exists because `QToolBar` widgets don't function properly in MacOS FontLab, so all toolbar functionality is reimplemented as a panel with `TRFlowLayout`.

### Standalone Tools

Self-contained dialog tools for specialized workflows:

**Delta Preview** (`TR-DeltaPreview.py`) — Visual preview of delta machine results without writing to the font. Dual-pane interface with source masters and computed target results rendered as `QPainterPath` objects built from core geometry. Live zoom and padding controls. Execute-to-font mode for committing approved results as real layers.

**Comparator** (`TR-Comparator.py`) — Cross-font and cross-layer glyph comparison. Detect outline differences, missing layers, shifted-but-identical layers, and anchor mismatches between two fonts or between layers within a single font. Visual overlay rendering with color-coded difference display. Time-stamp-aware comparison for change tracking. Batch processing with progress bar and font mark colorization.

**Match Contours** (`TR-MatchContours.py`) — Visual contour matching across masters. Contour order tab for drag-and-drop reordering with winding direction display (color-coded CW/CCW). Contour start-point tab for aligning start nodes across masters with corner-based (BL, TL, BR, TR) and sequential (next/prev) start-point adjustment. Visual icon rendering per contour per master.

**Encoder** (`TR-EncodeGlyphs.py`) — Unicode encoding management. Load encodings from JSON, FontLab `.nam` files, or Google protobuf `.textproto` files. Apply or clear unicode mappings for entire fonts or selected glyphs. Save/load encoding data to Font Lib.

**Sort Anchors** (`TR-SortAnchors.py`) — Sort anchor ordering across all masters for consistency. Reference-master mode preserves the anchor order from a chosen master. Alphabetical mode sorts all anchors uniformly. Verbose mode reports missing anchors across masters.

**Propagate Anchors** (`TR-PropagateAnchors.py`) — Table-driven batch anchor copying between glyphs. Per-action configuration for source glyph, anchor selection, destination glyphs, layer scope, and copy options (absolute/relative positioning with LSB/RSB/advance-relative modes, collision handling with overwrite or rename, suffix control). Save/load action tables as JSON for repeatable workflows.

**Export Glyph** (`TR-ExportGlyph.py`) — Export individual glyphs as `.trglyph` XML files via the core serialization system. Uses the proxy-to-core eject mechanism for lossless round-trip export.

## Architecture

The library is split into two complementary packages, bridged by a dual proxy layer.

### Core (`typerig.core`)

Zero external dependencies. Every object lives in pure Python and can run anywhere — CPython, Pyodide in a browser, or any other conforming runtime.

**`core.objects`** — geometric primitives and containers:

- `Point`, `Line`, `CubicBezier`, `QuadraticBezier` — foundational geometry with full operator overloading and complex-number math.
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

**`core.func`** — stateless math and geometry helpers:

- `math` — linear interpolation, rational fractions, randomisation, SLERP for angles, directional interpolation, Hobby velocity, matrix solvers.
- `transform` — delta machine, adaptive scaling (extending on Tim Ahrens), directional adaptive scaling, stem compensation, italic-angle correction, per-contour angle adjustment and utilities.
- `geometry` — CCW test, collinearity, intersection routines.
- `utils` — type-checking helpers.

**`core.fileio`** — serialisation:

- `xmlio` — XML round-trip engine with class registry, compact attribute encoding and lib-attribute support. Powers the `.trfont` experimental format.
- `svg` — SVG path filtering and pen-based import.
- `nam` — FontLab `.nam` encoding file parser.
- `textproto` — Google protobuf `.textproto` encoding file parser.

### Proxy — FontLab Layer (`typerig.proxy.fl`)

Depends on FontLab (`fontlab`, `fontgate`, `PythonQt`). Provides production-ready proxy objects, GUI components, and action collectors.

**`proxy.fl.objects`** — FontLab proxy objects:

- `pFont` / `pFontMetrics` — font access: glyph lookup, font metrics (all vertical metrics per master), kerning, classes, font lib, update/undo management.
- `pGlyph` / `eGlyph` — glyph proxy with full layer, shape, contour, node, anchor, guideline, component, and metric access. `eGlyph` extends with tool-preparation methods (`_prepareLayers`) and multi-master-aware operations.
- `pShape` / `eShape` — shape proxy with transform, bounds, naming, alignment, and reference management.
- `pContour` — contour proxy with alignment, bounds, and winding operations.
- `pNode` / `eNode` / `eNodesContainer` — node proxies with smart-angle access, coordinate manipulation, and batch container operations.
- `eCurveEx` — extended curve proxy with curvature analysis and Hobby tension control.

**`proxy.fl.actions`** — Action collector classes that encapsulate tool logic separately from GUI:

- `TRNodeActionCollector` — all node operations: insert, remove, move (smart/LERP/slope/slant), align, slope copy/paste, corner operations (mitre, round, loop, trap, rebuild), Hobby tension manipulation.
- `TRCurveActionCollector` — segment conversion, curve optimization, Hobby tension copy/paste.
- `TRContourActionCollector` — contour close/open, reverse, boolean operations, alignment, distribution, reordering.
- `TRDrawActionCollector` — primitive drawing (circles, squares from selected nodes).
- `TRLayerActionCollector` — layer add/delete/duplicate, visibility, type assignment, element operations, cross-layer contour transfer.

**`proxy.fl.gui`** — Reusable GUI components:

- `widgets` — `CustomPushButton` with icon-font support, `TRFlowLayout`, `TRVTabWidget`/`TRHTabWidget`, `TRCheckTableView`, `TRTableView`, `TRSliderCtrl`, `TRTransformCtrl`, `TRDeltaLayerTree`, `CustomSpinBox`/`CustomSpinLabel`/`CustomLineEdit`, `getProcessGlyphs` (glyph-scope resolver), `getTRIconFont`/`getTRIconFontPath` (custom icon font loader).
- `dialogs` — `TRLayerSelectDLG`/`TRLayerSelectNEW` (layer chooser with search/filter), `TR1FieldDLG`/`TR2FieldDLG` (quick input dialogs), `TRMsgSimple`.
- `styles` — `css_tr_button` and `css_tr_button_dark` stylesheets with automatic dark/light mode detection via `fl6.flPreferences().isDark`.
- `drawing` — Canvas drawing utilities: `TRDrawIcon`, `build_selection_contour`, `draw_contour_mode`, `draw_selection_mode`, `draw_node_markers`.

**`proxy.fl.application`** — FontLab application access:

- `pWorkspace` — workspace proxy for canvas access, text block/glyph queries, active kern pair retrieval, and frame creation.
- `pItems` — item notification helpers for undo.

### Proxy — Core Bridge (`typerig.proxy.tr`)

Each proxy class — `trNode`, `trContour`, `trShape`, `trLayer`, `trGlyph`, `trFont`, `trAnchor` — inherits from its core counterpart and holds a `.host` reference to the corresponding FL object.

Attribute access is rerouted through a `__meta__` mapping: reads and writes to mapped names (e.g. `x`, `y`, `name`, `closed`) go straight to the host, while everything else follows the normal core path. This means any core algorithm — interpolation, offset, delta scaling — runs identically on proxy objects with live FL data.

**Eject / Mount** — every proxy exposes `.eject()` to detach a pure core copy and `.mount(core_obj)` to write values back into the host. Eject for computation, mount to commit — keeps FL undo intact and avoids side-effects during multi-step operations.

**Host sync** — when structural changes occur (node count differs after a mount), the proxy rebuilds the FL contour and calls `_sync_host()` up the parent chain so the FL object tree stays consistent.

## Web

The core package runs in the browser via Pyodide. The **TR Glyph Viewer** (`Web/GlyphViewer`) loads TypeRig modules directly from GitHub at runtime, stubs the proxy and FL-dependent init files, and exposes the full core API to a live Python editor on an HTML canvas.

## License

No warranties. By using this you agree that you use it at your own risk.

© Vassil Kateliev — [kateliev.com](http://www.kateliev.com) | Karandash Type Foundry — [karandash.eu](http://www.karandash.eu)

[typerig.com](http://www.typerig.com)
