# HANDOUT T1 — One TypeRig Toolbar for FontLab (Windows + macOS)

**Audience:** implementation agent. Follow the stages in order; each ends with a verification
gate. Do not start a stage before the previous gate passes. Commit after every stage.

**Goal in one sentence:** replace the three existing FontLab toolbars with **one** native
FontLab panel, "TypeRig Toolbar", that works on Windows and macOS, FontLab 8 and 9, and contains
every button of the Glyphs sidebar palette in the same order, driven by the full TypeRig master
controller.

---

## 0. Read first (mandatory, ~30 min)

1. `Docs/Proxy/Documents/FL-native-panels.md` — **everything we learned about FontLab's panel
   system, the working recipe, the crashes, the PythonQt traps and the debugging toolbox.** This
   handout assumes you have read it. Do not re-derive it.
2. Reference implementation: `Scripts/TypeRig GUI/typerig-toolbar-dock.py` (git `1f82921`). It
   already does: native panel creation + registration, FL8/FL9 action lookup, per-button flow
   layout with scroll area, orientation by shape, debounce, hysteresis, dock-height fill, re-run
   safety. **Reuse its mechanisms, do not rewrite them blindly.**
3. The thing to port (read-only, do not modify):
   `/Users/kateliev/Remote/TypeRig-Glyphs/Plugins/TypeRig Toolbar.glyphsPalette/Contents/Resources/tr_toolbar.py`
   and the guide `/Users/kateliev/Remote/TypeRig-Glyphs/Lib/toolbar_guide.md`.
4. What is being retired (read to know what must not be lost):
   `Scripts/TypeRig GUI/typerig-toolbar.py` (Qt toolbars + controller),
   `Scripts/TypeRig GUI/toolbar-mac.py` (floating window), `Scripts/TypeRig GUI/typerig-toolbar-dock.py`
   (dock panel), `Scripts/TypeRig GUI/Toolbar/` (sub-toolbar package: `node.py`, `node_align.py`,
   `node_slope.py`, `curve.py`, `contour.py`).
5. FL actions to call: `Lib/typerig/proxy/fl/actions/` (`node.py` = `TRNodeActionCollector`,
   `curve.py`, `contour.py`, `cut.py`, `stem_center.py`, `layer.py`...), FL panel
   `Scripts/TypeRig GUI/Panel/Node.py`, and the platform-neutral dispatchers
   `Lib/typerig/core/actions/node_panel_actions.py` (`npa_*`, what the Glyphs buttons call; FL
   currently does **not** use them).

**Repo conventions (mandatory):**
- Indentation is **TABS** in all Python (scripts and `Lib/typerig`).
- New modules get the standard header banner + `__version__`; bump the minor version on every edit.
- Python 3 only (FontLab's bundled 3.11). No `from __future__`, no py2 fallbacks.
- Scripts stay **thin**; shared logic goes into `Lib/typerig/proxy/fl/gui/`.
- Commit style: `[FL][GUI] <imperative summary>`. One commit per stage. **Do not push.** Add the
  attribution trailer your environment tells you to add.
- Working tree: the repository root that contains `Lib/` and `Scripts/`
  (macOS: `/Users/kateliev/Remote/TypeRig`).

**Hard safety rules (these cost real crashes — see §10 of the knowledge doc):**
- Never call native C++ through `ctypes` with a guessed `this`. The only proven native call is
  `MainWindow::registerCustomPanel`.
- Never `deleteLater()` a PythonQt widget that owns a `QTimer` connected to its own bound method.
- Never grab the desktop for screenshots; use `widget.grab()`.
- A FontLab crash loses the user's unsaved work: prefer read-only probes and static analysis, say
  what you are about to run, and never leave experiment residue (distinct throw-away ids, ask the
  user to restart FontLab afterwards).
- Do not claim Windows works unless the user ran it. You cannot test Windows yourself.

---

## What "done" means (acceptance criteria)

1. Exactly **one** TypeRig toolbar script remains: `Scripts/TypeRig GUI/typerig-toolbar.py`
   (`#FLM: TypeRig: Toolbar`). `toolbar-mac.py`, `typerig-toolbar-dock.py` and the `Toolbar/`
   package are gone from the tree and from every doc / installer reference.
2. It is a **native FontLab panel** (appears under Window > Panels > Custom Panels, drags and docks on
   all four edges, tabs with other panels, right-click header menu works, **no crash** on drop,
   right-click, or Window menu) on **macOS FL8, macOS FL9** and **Windows** (user-verified).
3. Every button of the Glyphs palette exists in FL, **in the same order and groups**, with the same
   modifier behaviour (Alt/Shift/Ctrl) and tooltips (see Stage 2 matrix).
4. Full masthead: the complete TypeRig FL controller — layers **Active / Masters(All) / Selected**
   (with the layer-selection dialog) and everything else the old `TRToolbarController` offers
   (glyph scope: active glyph / glyph window / font selection) — not the reduced Active+All of Glyphs.
5. Layout follows the panel: horizontal rows when wide, vertical columns when docked left/right,
   no flicker while dragging/resizing (measured, see Stage 1 gate).
6. Foldable sections are **not** built; their keys and captions are kept as code comments so they
   can be added later.
7. A parity matrix document exists and every row is `OK`, or `FL-ONLY`, or `GLYPHS-ONLY (reason)`.

---

## Stage 0 — Inventory and parity matrix (no code yet)

**Create** `Docs/Proxy/Documents/FL-toolbar-parity.md`: one table, one row per Glyphs button
(and per field / option), columns:

`Section | Glyphs token | Tooltip (Glyphs) | Glyphs call (npa_*) | FL equivalent (module.function) | In old FL toolbar? | Status`

Source of truth = the Glyphs file. Its structure (sections in this order; within a section the
`flow()` calls are rows/groups, tuple order = button order). **Do not trust this summary over the
file, re-extract it:**

| Section (key) | Buttons / controls (token) |
|---|---|
| observers row (Glyphs-only helpers, under the masthead) | `visible` layer toast, `stem_vertical_alt` stem probe, `interpolate` node slide, `node_add` node ghost, `keyboard_arows` key nudge, + blank placeholder cells |
| `node` Nodes & Corners | `node_add_bgn` `node_add_mid` `node_add_end` `node_add_extreme_alt` `node_remove` `node_round` · `corner_mitre` `corner_round` `corner_loop` `corner_trap` `corner_rebuild` · field `fld_corner` (default 20) |
| `align` Align | options: `shift_dumb` `shift_smart` `shift_keep_dimension` `shift_interpolate` `shift_intercept` `extrapolate` · row: `node_align_left/right/top/bottom/selection_x/selection_y` · row: `node_align_outline_x/outline_y/neigh_x/neigh_y/min_max_Y/min_max_X` · metrics: `dimension_ascender/caps/xheight/baseline/descender` + toggle `node_target` · `node_target_collapse` |
| `curve` Curves | `node_smooth` `node_sharp` `line_to_curve` `curve_to_line` `curve_tunni` `curve_retract_alt` · `curve_hobby`(dialog) `curve_hobby_1` `_95` `_90` `curve_prop_alt`(dialog) `curve_prop_30` `_50` · `curve_hobby_copy` `curve_hobby_paste` + swapped paste |
| `contour` Contours | `contour_close` `contour_cw_alt` `contour_ccw_alt` `node_start` `node_previous` `node_next` · `node_bottom_left/bottom_right/top_left/top_right` · `contour_sort_y/x/y_rev/x_rev` |
| `bool` Booleans | `contour_union` `contour_subtract` `contour_intersect` `contour_difference` (Alt = reverse) |
| `cut` Cut | `contour_cut` `cut_stem_overlap` `auto_stem_overlap` `node_middle_top` (stem-center snap) `node_target` (loop target toggle) `corner_loop` · field `fld_loop_safe` (default 5) |
| `cap` End Caps | `cap_normal` `cap_round` `cap_restore` |
| `stroke` Collinear & Monoline | `curve_collinear` `channel_process` (monoline), with per-master snap targets (Ctrl = edit dialog, Shift = no snap) |
| `slope` Slope | `slope_copy` `slope_italic` `slope_paste_min/max/min_flip/max_flip` |

About 87 buttons + 2 fields + 5 observers. For each row find the FL function by reading the old FL
toolbars and `Lib/typerig/proxy/fl/actions/`. Typical locations (verify!):
`TRNodeActionCollector` (nodes, corners, align, slope, caps, collinear/monoline),
`TRCurveActionCollector` (segment convert, optimize, hobby), `TRContourActionCollector` (close,
winding, start, order, bool), `TRCutActionCollector` / `TRStemCenterActionCollector` (cut,
stem-center). If FL has **no** function for a Glyphs button, the core `npa_*` function may be
callable through a thin adapter; if neither works, the row is `GLYPHS-ONLY` with the reason.

**FL-only things that must be kept** (a superset, never a regression) — find them in the old FL
toolbars and add rows marked `FL-ONLY`, placed where they belong in the order. Known ones:
measurement-line metric align (`dimension_guide`), `curve_copy` (copy handle proportions to
masters, `hobby_tension_push`), FL dialog variants of insert-node / corner tools (keep them
reachable, e.g. Ctrl+click on the same button; document the choice). Drop only
`chk_ToggleTitle` (window-title toggle: meaningless in a panel).

**Observers** (layer toast, stem probe, node slide, node ghost, key nudge) are Glyphs sidebar
helpers built on Glyphs observers. Port a row only if FontLab has a workable equivalent
(`Lib/typerig/proxy/fl/gui/canvas_overlay.py`, `canvas_controls.py` are the FL canvas hooks); otherwise
build a **disabled placeholder cell** with a `# GLYPHS-ONLY` comment and list it in the final report
for the owner's decision. Do not silently drop and do not invent half-working versions.

**Icon tokens** are ligature names of the TypeRig icon font (`getTRIconFont()`): an unknown token
renders as literal text. Render each button (`widget.grab()`) and list every token that shows as
text; report them, do not invent icons.

**Gate 0:** matrix complete, every row has a status, reviewed by reading the Glyphs file one more
time for missing rows. Commit: `[FL][GUI] Add toolbar parity matrix`.

---

## Stage 1 — Cross-platform native panel module

**Create** `Lib/typerig/proxy/fl/gui/native_panel.py` (header + `__version__`). Move out of
`typerig-toolbar-dock.py` and generalise: pointer helper, registration, action lookup (`data()` key),
panel create/reuse/renew, `size_and_place`, `TRToolbarScroll` (flow, hysteresis, debounce,
dock-shape orientation, `fill_dock`), graveyard for retired widgets. Public API should be small, e.g.
`TRNativePanel(panel_id, title, content_builder)` with `.open()` / `.rebuild()`.

**Platform strategy** — registration is the only platform-specific part:
- macOS: as in the reference (`ctypes.CDLL(None)` + Itanium name). FL8 and FL9.
- **Windows: unknown.** On Windows FontLab's `app.main` is visible and Qt toolbars dock, but we want
  the same native panel. Investigate, in this order, and write down each result in
  `FL-native-panels.md` §11:
  1. Is the symbol exported? The name is MSVC-mangled, expected form
     `?registerCustomPanel@MainWindow@@QEAAXPEAVYPanelWidget@@@Z` (verify, it may differ). Write a
     **temporary probe script** that runs on Windows FontLab and logs (to an absolute path you can
     read, see knowledge doc §9) whether `kernel32.GetProcAddress(GetModuleHandleW(None), name)`
     resolves, and — if not — lists the export table of the main module by parsing the PE headers
     in-process and filtering for `registerCustomPanel` / `CustomPanel` / `YPanel`.
  2. If exported: same recipe as macOS with `ctypes.WinDLL`/`windll`; check calling convention
     (x64 = single ABI) and the pointer extraction from the PythonQt repr.
  3. If not exported: **stop and report.** Do not binary-patch, do not guess offsets. The fallback is
     a clearly separated strategy that docks the panel's widgets as a regular `QToolBar` in
     `app.main` (what the old script did on Windows), behind the same `TRNativePanel` API, so the
     toolbar content/button table is identical. The owner decides whether that is acceptable.
- Detect platform with `platform.system()`; everything FL8/FL9-specific stays in one place.
- Every unknown ⇒ one clear `print()` and a clean no-op (never crash, never half-register).

Keep from the reference, unchanged in behaviour: re-run safety (`Toolbar._dock_state` equivalent
on a long-lived module; renew the scroll area, **park** the old one), `setSizePolicy(Ignored)`,
`maximumViewportSize()` sizing with scrollbar room reserved, hysteresis 0.8/1.25, 2-tick debounce,
dock-shape orientation + fill for FL8.

**Gate 1 (FL9 live through the MCP, run it and show the numbers):**
- Open, resize wide→tall→wide through a 40-step sweep: viewport changes == number of resize steps,
  scrollbar toggles ≤ 4, no layout pass mid-sweep (debounce), no crash.
- 8 sizes (e.g. 70x900, 120x900, 300x500, 300x800, 325x1100, 400x420, 700x90, 1200x130): programmatic
  check that no buttons overlap and none lie outside the page.
- Simulate FL8 docking (tall dock, short panel): panel grows to the dock height, vertical layout.
- Re-run twice: same panel reused, no duplicate menu entry, no crash after the event loop runs.
- Right-click header menu and Window menu survive (programmatic recipes are in the knowledge doc).
- macOS FL8: ask the user for a **diagnostic-log round trip** (knowledge doc §9) docking left, right, top
  and bottom. Windows: same, after the probe. Commit: `[FL][GUI] Add native panel module`.

---

## Stage 2 — The toolbar itself

**Rewrite** `Scripts/TypeRig GUI/typerig-toolbar.py` (keep this path/name so installers and menus
keep working) as a thin script: build the button table, hand it to `TRNativePanel`.

- **One declarative table** (a tuple of sections like the Glyphs `SECTIONS` literal), in the Glyphs order,
  each button = (token, tooltip, callback, checkable, name). Put it in
  `Lib/typerig/proxy/fl/gui/toolbar_buttons.py` if it keeps the script thin.
- **Order and grouping exactly as in the Glyphs file**: the observers row first (see Stage 0 rule),
  then sections in `SECTIONS` order; each Glyphs `flow()` call is one group (use the existing
  `trGroupStart` gap; give a section start a slightly larger gap).
- **Foldable sections: do not implement folding.** Keep every section key + caption as a comment
  directly above its first group, e.g. `# SECTION 'node' - Nodes & Corners (fold target)`. Also keep
  a comment about the Glyphs `toolbar-sections.json` cut-down mechanism (not built).
- **Behaviour parity**: Alt/Shift/Ctrl semantics from the Glyphs tooltips (e.g. Alt = single selected node
  for insert/segment tools; Alt = reverse for booleans; Shift/Alt axis force for stem-center;
  Ctrl = edit per-master snap targets for collinear/monoline; Shift = no snap). Read modifiers
  **before** opening any dialog. Corner tools: Glyphs uses the one-cell corner field; FL previously used
  dialogs — implement the field as in Glyphs and keep the FL dialogs reachable (Stage 0 decision).
  Align options keep the FL defaults (`shift_dumb` on). Per-master snap targets use the same
  `lib_keys` (`NODE_COLLINEAR_LIB_KEY`, `NODE_MONOLINE_LIB_KEY`) as the Glyphs buttons so data
  is shared.
- **Full masthead** (Task 6): lift the old `TRToolbarController` (see `typerig-toolbar-dock.py` for the
  trimmed version and `typerig-toolbar.py`/`toolbar-mac.py` for the original) with **all** its
  layer scopes — Active, Masters (All), **Selected** with `TRLayerSelectNEW` — and the glyph scope
  (active glyph / glyph window / font-window selection). The scope state (`pMode`, `pLayers`) must be
  passed to **every** FL action call exactly as the old toolbars did. Replace the old
  `exec('Toolbar.x.pMode = ...')` module-global trick with one small shared state object read by
  the callbacks. Glyphs' reduced Active+All masthead is **not** the target.
- Every callback must be wrapped so an exception prints a traceback and does not break the panel.
- Update `Lib` tooltips only where FL behaviour genuinely differs from the Glyphs text.

**Gate 2:** the parity matrix is all green. Run the whole panel in FL9 (MCP): for a set of buttons per
section run the action on a prepared test glyph (use `mcp__fontlab__*` read tools to compare
before/after outline; undo afterwards — **never leave the user's font modified**) and show the
results in the report. Render the horizontal and the vertical layout with `widget.grab()` and attach
the images' paths. Commit: `[FL][GUI] Unified TypeRig toolbar`.

---

## Stage 3 — Retire the old toolbars

Only after Gate 2. Remove (`git rm`): `Scripts/TypeRig GUI/toolbar-mac.py`,
`Scripts/TypeRig GUI/typerig-toolbar-dock.py`, the `Scripts/TypeRig GUI/Toolbar/` package, and any
stale `*.pyc` next to them. Then:

- `grep -rnE "toolbar-mac|typerig-toolbar-dock|import Toolbar|Toolbar\.modules|TypeRig GUI/Toolbar"` over
  the whole repo and fix every hit. Known hits: `README.md` (~line 126, "MacOS Panel
  (toolbar-mac.py)"), `index.html` (~line 774), plus anything in `install*.py`, `pyproject.toml`,
  `Web/`, release scripts. Check the installers do not ship a file list that still names the removed files.
- README / site text: one TypeRig Toolbar, native panel on Windows and macOS, FL8 and FL9.
- Update `Docs/Proxy/Documents/FL-native-panels.md`: Windows findings, any new pitfall, and the final
  public API of `native_panel.py`.

**Gate 3:** `python -m compileall -q Lib/typerig/proxy/fl/gui "Scripts/TypeRig GUI"`; repo `pytest`
(`tests/`) still passes; grep shows zero stale references; FL9 starts, runs the script, panel opens.
Commit: `[FL][GUI] Retire old toolbars`.

---

## Stage 4 — Report

Reply with (no prose padding):

1. **Platform table**: macOS FL9 / macOS FL8 / Windows × {opens, docks top, left, right, bottom, tabs
   with other panels, right-click menu, Window menu, orientation switch, re-run} → `verified by me` /
   `verified by user` / `NOT tested`.
2. **Parity summary**: counts of `OK`, `FL-ONLY`, `GLYPHS-ONLY` and the list of every GLYPHS-ONLY row with
   its reason; list of icon tokens that render as text.
3. **Decisions needing the owner** (observers, FL dialogs vs corner field, Windows fallback if the
   symbol is not exported).
4. **Commits** (hash + title) and the files removed.
5. **Known risks / unverified** (persistence after restart, ResizePolicy, startup autorun).

## Do not

- Do not modify anything under `/Users/kateliev/Remote/TypeRig-Glyphs`.
- Do not add `QToolBar` docking tricks, hidden main-window tricks, or floating-window workarounds
  as the primary path (they are exactly what this replaces; only the explicit Windows fallback in
  Stage 1 may use a `QToolBar`).
- Do not add pages to FontLab's own `YTabWidget`s; do not call native FontLab functions other than
  `registerCustomPanel` (or a Windows equivalent proven by the probe).
- Do not change `pMode`/`pLayers` semantics or the FL action signatures.
- Do not push, do not rewrite history.
