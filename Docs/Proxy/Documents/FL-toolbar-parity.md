# TypeRig Toolbar — Glyphs ↔ FontLab parity matrix

Source of truth: `TypeRig-Glyphs/Plugins/TypeRig Toolbar.glyphsPalette/Contents/Resources/tr_toolbar.py`
(re-read in full for this matrix). Target: `Scripts/TypeRig GUI/typerig-toolbar.py` +
`Lib/typerig/proxy/fl/gui/toolbar_buttons.py`.

Legend — `OK` same function in FL; `FL-ONLY` exists in FL, not in Glyphs (kept: superset);
`GLYPHS-ONLY` not ported, reason given. **Old** = was in the old FL toolbars
(`T` toolbar package, `M` floating toolbar, `P` Panel/Node, `C` popup-contour-cut, `-` nowhere).
FL calls use `(pMode, pLayers)` unless noted; `eG` = `eGlyph()`.

Icon tokens: every token below was checked against the ligature table (GSUB) of
`typerig-icons.ttf`; **all** resolve to an icon, none renders as text.

## Masthead (FL controller, superset of Glyphs' Active+All)

| Section | Token | Tooltip | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| masthead | `layer_active` | Active layer | state.layers | `pLayers[0]` | T | OK |
| masthead | `layer_master` | Master layers | state.layers | `pLayers[1]` | T | OK |
| masthead | `select_option` | Select layers (dialog) | — | `TRLayerSelectNEW` → `pLayers` | T | FL-ONLY |
| masthead | `glyph_active` | Active glyph | — | `pMode = 0` | T | FL-ONLY |
| masthead | `select_window` | Glyph window | — | `pMode = 1` | T | FL-ONLY |
| masthead | `select_glyph` | Font window selection | — | `pMode = 2` | T | FL-ONLY |
| masthead | `window` | Toggle window title | — | dropped (meaningless in a panel) | T/M | dropped |

## Observers row (Glyphs-only sidebar helpers) - REMOVED

`visible` (layer toast), `stem_vertical_alt` (stem probe), `interpolate` (node slide), `node_add` (node ghost),
`keyboard_arows` (key nudge) and the blank cells are built on Glyphs observers and have no FontLab equivalent.
Owner decision: they are **not in the FL toolbar** (no placeholders). Status: GLYPHS-ONLY, dropped.

## `node` — Nodes & Corners

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| node | `node_add_bgn` | Insert node at beginning (Alt: one node) | `npa_insert(0.)` | `TRNodeActionCollector.node_insert(…, 0., alt)`; Ctrl = `node_insert_dlg` | T/M | OK |
| node | `node_add_mid` | … middle | `npa_insert(.5)` | `node_insert(…, .5, alt)`; Ctrl = `node_insert_dlg` | T/M | OK |
| node | `node_add_end` | … end | `npa_insert(1.)` | `node_insert(…, 1., alt)`; Ctrl = `node_insert_dlg` | T/M | OK |
| node | `node_add_extreme_alt` | Add nodes at extremes | `npa_insert_at_extremes` | `node_insert_extreme` (no Alt mode in FL: tooltip differs) | T/M | OK |
| node | `node_remove` | Remove selected nodes | `npa_remove` | `node_remove` | T/M | OK |
| node | `node_round` | Round to integer | `npa_round_coordinates` | `node_round(…, alt=floor, shift=all)` (FL semantics kept, tooltip differs) | T/M | OK |
| node | `corner_mitre` | Corner mitre | `npa_corner_mitre(size)` | `corner_mitre_dlg` (popup asks the size) | T/M | OK |
| node | `corner_round` | Corner round | `npa_corner_round(size)` | `corner_round_dlg` (popup) | T/M | OK |
| node | `corner_loop` | Corner loop | `npa_corner_loop(size)` | `corner_loop_dlg` (popup) | T/M | OK |
| node | `corner_trap` | Ink trap | `npa_corner_trap` | `corner_trap_dlg(…, smooth = not Alt)` (FL always asks incision/depth/trap) | T/M | OK |
| node | `corner_rebuild` | Rebuild corner | `npa_corner_rebuild` | `corner_rebuild` | T/M | OK |
| node | `fld_corner` | Corner size field | field | removed: the popup dialogs ask | - | GLYPHS-ONLY (dropped) |

## `align` — Align

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| align | `shift_dumb` | Simple shift (default on) | `align_smart=False` | `smart_shift=False` | T | OK |
| align | `shift_smart` | Smart shift | `align_smart=True` | `smart_shift=True` | T | OK |
| align | `shift_keep_dimension` | Keep relations | `keep_relations` | `keep_relations` | T | OK |
| align | `shift_interpolate` | Interpolated shift | `lerp_shift` | `lerp_shift` | P | OK |
| align | `shift_intercept` | Intercept vertical | `intercept` | `intercept` | T | OK |
| align | `extrapolate` | Extrapolate | `extrapolate` | `extrapolate` | P | OK |
| align | `node_align_left/right/top/bottom` | Align nodes L/R/T/B | `npa_align('L'…)` | `nodes_align(…, 'L'/'R'/'T'/'B', …)` | T | OK |
| align | `node_align_selection_x/y` | Center of selection | `'C'/'E'` | `nodes_align(…, 'C'/'E')` | T | OK |
| align | `node_align_outline_x/y` | Outline bbox middle | `'BBoxCenterX/Y'` | same modes | T | OK |
| align | `node_align_neigh_x/y` | Middle of neighbours | `'peerCenterX/Y'` | same modes | T | OK |
| align | `node_align_min_max_Y/X` | Line min–max | `'Y'/'X'` | same modes | T | OK |
| align | `dimension_ascender` | Metric: Ascender | `npa_align_to_y(ascender)` | `nodes_align(…, 'FontMetrics_0')` | T | OK |
| align | `dimension_caps` | Metric: Caps | capHeight | `'FontMetrics_1'` | T | OK |
| align | `dimension_xheight` | Metric: x-height | xHeight | `'FontMetrics_3'` | T | OK |
| align | `dimension_baseline` | Metric: Baseline | 0 | `'FontMetrics_4'` | T | OK |
| align | `dimension_descender` | Metric: Descender | descender | `'FontMetrics_2'` | T | OK |
| align | `dimension_guide` | Align to measurement line | — | `'FontMetrics_5'` | T | FL-ONLY |
| align | `node_target` | Pick align target per master (toggle) | `npa_target_set/clear` | `ext_target` dict, `eGlyph._prepareLayers` + `selectedNodes` (as old `target_set`) | T | OK |
| align | `node_target_collapse` | Collapse nodes to target | `npa_collapse_to_target` | old `target_collapse` logic | T | OK |

## `curve` — Curves

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| curve | `node_smooth` / `node_sharp` | Smooth / sharp | `npa_set_smooth` | `node_smooth(…, True/False)` | T | OK |
| curve | `line_to_curve` / `curve_to_line` | Convert segment (Alt: one node) | `npa_segment_convert` | `TRCurveActionCollector.segment_convert(…, True/False)` (no Alt mode in FL) | T | OK |
| curve | `curve_tunni` | Optimize: Tunni | `npa_curve_optimize('tunni')` | `curve_optimize_dlg(…, 'tunni')` | T | OK |
| curve | `curve_retract_alt` | Retract handles | proportion (0,0) | `curve_optimize(…, ('proportional',0.,0.))` | T | OK |
| curve | `curve_hobby` | Hobby dialog | `_hobby_dialog` | `curve_optimize_dlg(…, 'hobby')` | T | OK |
| curve | `curve_hobby_1/_95/_90` | Hobby 1 / .95 / .90 | `npa_curve_optimize('hobby')` | `curve_optimize(…, ('hobby', v, v))` | T | OK |
| curve | `curve_prop_alt` | Proportion dialog | `_prop_dialog` | `curve_optimize_dlg(…, 'proportional')` | T | OK |
| curve | `curve_prop_30/_50` | 30% / 50% | `npa_curve_optimize('proportional')` | `curve_optimize(…, ('proportional', p, p))` | T | OK |
| curve | `curve_copy` | Copy handle proportions to masters | — | `hobby_tension_push` | T | FL-ONLY |
| curve | `curve_hobby_copy` | Copy Hobby curvature | `npa_hobby_copy` | `hobby_tension_copy(eG, pLayers)` → bank | P | OK |
| curve | `curve_hobby_paste` | Paste Hobby curvature | `npa_hobby_paste(swap=False)` | `curve_optimize_by_dict(…, 'hobby', bank)` | P | OK |
| curve | `hobby_paste_swap` (token `curve_hobby_paste`) | Paste, α/β swapped | `swap=True` | `curve_optimize_by_dict(…, swap_values=True)` | P | OK |

## `contour` — Contours

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| contour | `contour_close` | Close contours | `npa_contour_close` | `TRContourActionCollector.contour_close` | T | OK |
| contour | `contour_cw_alt` / `contour_ccw_alt` | Winding CW / CCW | `npa_contour_winding` | `contour_set_winding(…, False/True)` | T | OK |
| contour | `node_start` | Set start node | `…start_at_selection` | `contour_set_start` | T | OK |
| contour | `node_previous` / `node_next` | Start to prev / next | `…start_next` | `contour_set_start_next(…, set_previous)` | - | OK |
| contour | `node_bottom_left/_bottom_right/_top_left/_top_right` | Smart start | `…smart_start` | `contour_smart_start(…, (0,0)/(1,0)/(0,1)/(1,1))` | T | OK |
| contour | `contour_sort_y/_x/_y_rev/_x_rev` | Reorder | `npa_contour_order` | `contour_set_order(…, (None,True),True / (True,None),False / (None,True),False / (True,None),True)` | T | OK |

## `bool` — Booleans

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| bool | `contour_union/_subtract/_intersect/_difference` | Boolean add/subtract/intersect/exclude (Alt: reverse) | `npa_contour_bool` | `contour_bool(…, 'add'/'subtract'/'intersect'/'exclude', alt)` | T | OK |

## `cut` — Cut - REMOVED

Owner decision: slice, cut + auto overlap align, auto overlap align, stem-center snap, loop target, corner loop
(with target), stroke separate and medial axis extract are **not in the FL toolbar**. Status: dropped
(`contour_cut`, `cut_stem_overlap`, `auto_stem_overlap`, `node_middle_top`, `node_target`/`loop_target`,
`corner_loop` (cut), `fld_loop_safe`, `cutter_auto`, `centerline`). They stay available in the Popup Contour Cut script.

## `cap` — End Caps

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| cap | `cap_normal` | Butt cap | `npa_cap_butt` | `TRNodeActionCollector.cap_normal(eG, pLayers)` | P | OK |
| cap | `cap_round` | Round cap (Alt: keep length) | `npa_cap_round(keep_length)` | `cap_round(eG, pLayers, alt)` | P | OK |
| cap | `cap_restore` | Rebuild cap | `npa_cap_rebuild` | `cap_rebuild(eG, pLayers)` | P | OK |

## `stroke` — Collinear & Monoline

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| stroke | `curve_collinear` | Collinear (Alt equalize, Ctrl edit targets, Shift no snap) | `npa_make_collinear` | `make_collinear(eG, pLayers, equalize, snap_lookup)`, lib key `NODE_COLLINEAR_LIB_KEY`, `TRMasterValuesDLG` | P | OK |
| stroke | `channel_process` | Monoline (Alt taper, Ctrl, Shift) | `npa_make_monoline` | `make_monoline(eG, pLayers, preserve_taper, snap_lookup)`, lib key `NODE_MONOLINE_LIB_KEY` | P | OK |

## `slope` — Slope

| Section | Token | Tooltip (Glyphs) | Glyphs call | FL equivalent | Old | Status |
|---|---|---|---|---|---|---|
| slope | `slope_copy` | Copy slope | `npa_slope_copy` | `slope_copy(eG, pLayers)` → bank (old toggle becomes a plain button) | T | OK |
| slope | `slope_italic` | Italic angle as slope | `npa_slope_from_angle` | `slope_italic(eG, pLayers)` → bank | T | OK |
| slope | `slope_paste_min/_max/_min_flip/_max_flip` | Paste slope | `npa_slope_paste` | `slope_paste(…, bank, (max, flip))` | T | OK |

## Decisions recorded
- No value entry fields: every value comes from the FL popup dialogs (corner size, loop overlap).
- No Cut section (slice ... medial axis extract).
- Insert buttons: Ctrl+click opens the FL `node_insert_dlg` (time slider).
- No observers row, no separators or gaps: the icons flow one after the other.
- FL `node_round` / `corner_trap` modifier semantics are kept; tooltips reflect FL, not Glyphs.
- Not built: foldable sections (keys/captions kept as comments), `toolbar-sections.json` cut-down.
