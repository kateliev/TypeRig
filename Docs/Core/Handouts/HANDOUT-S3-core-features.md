# HANDOUT S3 — Missing Core Features (typerig.core)

**Audience:** implementation agent. Features F1–F3 are independent — implement in any
order. F4 → F5 → F6 form a dependency chain and must be done in that order. F7 and F8 are
independent of everything else. Each feature ends with a verification gate.

**Read first:** `HANDOUT-S2-core-quality.md` — its "Repo conventions" and "Global
verification commands" blocks apply verbatim here. If S2 Stage 0 (test_objects.py) has
landed, add every gate check there; otherwise create the checks as a `__main__` block in
the touched module.

**Design ground rules:**
- Pure Python, no numpy, no Qt, no FontLab imports in `core/` (fontTools is allowed only
  behind a guarded import, as `to_quadratic_contour()` already does).
- Cubic-only where noted — follow the existing `Contour._assert_cubic_only()` pattern and
  tell the caller to run `to_cubic_contour()` first.
- New geometry math that is FL-independent and non-trivial goes in `core/algo/` (per repo
  convention); thin object-level wrappers go on the objects themselves.

---

## F1 — True (tight) curve bounds

**Problem:** `Contour.bounds` / `Shape.bounds` / `Layer.bounds` are built from node
coordinates INCLUDING off-curve BCPs, so every alignment origin computed from
`bounds.align_matrix` overshoots on round shapes. The per-segment solution already exists:
`CubicBezier.get_bbox()` uses `solve_extremes()`.

**Files:** `objects/contour.py`, `objects/shape.py`, `objects/layer.py`.

**Steps:**
1. `Contour.tight_bounds` (property) → `Bounds`:
   - iterate `self.segments`; for `Line` take endpoints; for `CubicBezier` /
     `QuadraticBezier` call `seg.get_bbox()` and take its corner pairs;
   - build one `Bounds` from all collected corners.
2. `Shape.tight_bounds`, `Layer.tight_bounds`: same shape as their existing `bounds`
   properties but delegating to contour `tight_bounds` (use `Bounds.from_bounds` if S2
   Stage 7 landed, else the corner-flatten pattern).
3. Do **not** change what `bounds` returns — panels and delta code depend on control-box
   semantics. Tight bounds is a new parallel property.
4. Add `tight=False` keyword to `Layer.align_matrix`? **No** — instead add
   `Layer.tight_align_matrix` property that builds the same dict from `tight_bounds`
   (metrics and outline tiers are identical; only Tier 1 differs). Smaller blast radius.

**Gate:**
- Circle contour from `contour.py.__main__` (`src_circle`): control box vs tight bounds —
  tight width/height must be smaller (BCPs of a circle stick out); expected tight bounds
  equal the on-curve extrema: x ∈ [161, 638], y ∈ [328, 805] for that dataset (verify by
  reading the node list: extremes are on-curve there, so tight == on-curve box, while
  `bounds` equals the same values too — so ALSO add a test with a quarter-arc whose BCPs
  overshoot: `CubicBezier((0,0),(0,55),(45,100),(100,100))` wrapped in a contour; control
  box x-min is 0/y-max is 100 in both, but a contour of `(0,0),(60,110),(40,-10),(100,100)`
  style with outside BCPs must differ).
- `bounds` values unchanged for all three `__main__` datasets.

---

## F2 — Point-in-contour / point-in-layer hit testing

**Problem:** no winding-aware containment query at object level; all ingredients exist
(`sample()`, `func.geometry.point_in_polygon`).

**Files:** `objects/contour.py`, `objects/layer.py`.

**Steps:**
1. `Contour.contains_point(point, steps_per_segment=32)` → bool:
   - accept `Point`, tuple, or Node (duck-type `.x`/`.y` first, fall back to indexing);
   - quick-reject with `tight_bounds` (F1) or `bounds` if F1 not landed;
   - polygonize with `self.sample(steps_per_segment)` and call `point_in_polygon`.
2. `Layer.contains_point(point, steps_per_segment=32)` → bool, even-odd across contours:
   `sum(c.contains_point(p) for c in self.contours) % 2 == 1`. Even-odd is deliberate —
   it needs no winding assumptions and matches filled-with-counters rendering for sane
   outlines. Document that nonzero-winding is NOT implemented.
3. Edge behavior: points exactly on the outline are undefined (document it) — the
   underlying ray-caster is half-open. Do not try to special-case.

**Gate:**
- Square contour (`src_square` in contour.py `__main__`): inside point True, outside False.
- Circle contour: center True, corner of its bbox False (curve pulls in).
- Layer with outer square + inner (counter) square: point in the counter → False;
  between outer and counter → True.

---

## F3 — Compatibility diagnosis

**Problem:** `is_compatible()` returns a bare bool from a hash of node types; MM workflows
need to know WHERE compatibility broke.

**Files:** `objects/layer.py` (primary), `objects/shape.py`, `objects/contour.py`.

**Steps:**
1. `Contour.diff_compatibility(other)` → list of dicts, empty when compatible:
   - node count mismatch → `[{'kind': 'node_count', 'self': n, 'other': m}]` and stop;
   - else per-index type mismatches →
     `{'kind': 'node_type', 'index': i, 'self': t1, 'other': t2}` (collect ALL, not first).
2. `Shape.diff_compatibility(other)`:
   - contour count mismatch → single `contour_count` record;
   - else per-contour: prefix each contour's records with `'contour': ci`.
3. `Layer.diff_compatibility(other)`: same one level up (`shape` index added). Also compare
   `len(self.anchors)` → `anchor_count` record (anchors interpolate too).
4. `is_compatible()` implementations stay hash-based (fast path) — do not reroute them
   through the differ.
5. Human-readable rendering: `Layer.report_compatibility(other)` → multi-line string, one
   finding per line, e.g. `shape[0] contour[2] node[14]: type 'curve' != 'on'`. This is
   what panels will show.

**Gate:**
- Two compatible layers → `[]` and `report_compatibility` == `''`.
- Break one node type at a known index → exactly one record with the right shape/contour/
  node indices; `is_compatible()` False.
- Different contour counts → single `contour_count` record, no crash.

---

## F4 — Curve–curve intersection (prerequisite for F5, F6)

**Problem:** only curve–line intersection exists. Boolean ops, overlap detection and
slanted-stem measurement all need curve–curve.

**Files:** new `core/algo/intersect.py` (pure math), thin wrappers on `CubicBezier` and
`Contour`.

**Algorithm — bezier clipping via recursive subdivision (simple, robust, adequate):**
1. `curve_curve_intersections(c1, c2, tolerance=0.1)` in `algo/intersect.py`:
   - operate on 4-point tuples, not objects, for speed
     (`((x0,y0),(x1,y1),(x2,y2),(x3,y3))`);
   - recursive control-polygon bbox test: if bboxes disjoint → no intersections; if both
     curves' bboxes are smaller than `tolerance` in both dimensions → report an
     intersection at the bbox-center midpoint with the accumulated (t1, t2) interval
     midpoints;
   - else split the larger curve (or both) at t=0.5 with de Casteljau and recurse,
     carrying each half's (t_lo, t_hi) interval;
   - depth cap 40; deduplicate results whose t1 differ by < 1e-4 (same pattern as
     `_nr_roots_unclamped` uses).
   - return list of `(t1, t2, (x, y))`.
2. Handle line segments by elevating to cubic (`p0, p0+⅓d, p0+⅔d, p1`) so one code path
   serves all segment pairs. Quadratics elevate via the existing `to_cubic()`.
3. `CubicBezier.intersect_curve(other, tolerance=0.1)` → wrapper returning
   `(t_pairs, points)` mirroring `intersect_line`'s shape.
4. `Contour.intersections(other_contour, tolerance=0.1)` → all segment-pair hits with
   segment indices: list of `(seg_i, seg_j, t_i, t_j, (x, y))`. Skip pairs whose segment
   bboxes are disjoint before recursing. `self_intersections()` variant: same but pairs
   within one contour, skipping adjacent segments' shared-endpoint hits (drop results with
   t within 1e-3 of the shared endpoint).

**Gate (exact cases):**
- Two straight-line "cubics" crossing at (50,50) → exactly 1 hit at (50,50) ± tolerance.
- `CubicBezier((0,0),(0,100),(100,100),(100,0))` (arch) vs its mirror
  `((0,75),(0,-25),(100,-25),(100,75))` — 2 hits, symmetric about x=50 (mirror-image x
  positions sum to 100 ± 0.5).
- Disjoint curves → `[]`.
- Identical curves → don't hang; depth cap kicks in; document that overlapping-coincident
  curves return an unspecified sample of hits.
- A figure-eight contour → `self_intersections()` returns exactly 1 crossing.

---

## F5 — Boolean operations (polygon fallback) — requires F4

**Problem:** no union/intersect/subtract in core; overlap removal is delegated to FontLab.
A curve-exact boolean is a big project — this feature ships a POLYGON-BASED fallback that
is explicitly approximate, good for previews, area math and headless trfont pipelines.

**Files:** new `core/algo/boolean.py`; wrappers on `Shape`.

**Algorithm — Greiner–Hormann on sampled polygons:**
1. `polygon_clip(subject, clip, operation)` in `algo/boolean.py`:
   - `subject`, `clip`: lists of (x, y), any winding; `operation` in
     `{'union', 'intersection', 'difference'}`;
   - classic Greiner–Hormann: insert pairwise edge intersections into both rings (reuse
     `func.geometry.intersect`-style segment tests, but compute the actual intersection
     point with the existing `line_intersect`), mark entry/exit by point-in-polygon
     midpoint tests, trace;
   - degenerate-vertex hygiene: perturb exact vertex-on-edge coincidences by 1e-9 before
     clipping (documented, standard G–H limitation);
   - non-crossing cases: return `[subject]`, `[subject, clip]`, `[]`, etc. by containment
     tests.
   - returns list of polygons (each a list of (x, y)).
2. `Shape.boolean(other, operation, steps_per_segment=32)` → NEW `Shape` of polygonized
   result contours (all-line contours, `closed=True`). Big docstring warning: output is a
   POLYLINE approximation; do not run on production outlines, intended for preview/measure.
3. `Shape.remove_overlap_preview(steps_per_segment=32)` → union of all contours of the
   shape with themselves (pairwise union fold).

**Gate:**
- Two overlapping axis-aligned squares (0..100 and 50..150):
  union area == 17500, intersection area == 2500, difference area == 7500 (use
  `poly_area`; tolerance 1 unit²).
- Disjoint squares: union → 2 polygons; intersection → `[]`.
- Contained square (10..20 inside 0..100): difference → 2 rings (outer + hole) OR outer
  with hole ring — assert total signed area == 9900 ± 1.
- Sampled circle vs square overlap: union area within 2% of analytic value.

---

## F6 — Offset loop cleanup — requires F4

**Problem:** `Contour.offset_outline()` self-intersects at concave joins for large
distances; nothing prunes the resulting loops.

**Files:** `objects/contour.py`.

**Steps:**
1. `Contour.offset_outline_clean(distance, curvature_correction=True, tolerance=0.5)`:
   - run existing `offset_outline`;
   - `self_intersections()` (F4) on the result; if none → return as-is;
   - for each crossing `(seg_i, seg_j, t_i, t_j, pt)`: split segment i at t_i and segment
     j at t_j (`solve_slice`), then drop the node run BETWEEN the two split points that
     forms the small loop — "small" = the candidate loop whose sampled `poly_area` is the
     lesser of the two possible removals;
   - rebuild the contour welding the two split points into one on-curve node at `pt`;
   - iterate until no self-intersections remain or 10 passes (return best effort with a
     `_offset_clean_converged = False` attribute, mirroring the `scale_with_axis`
     diagnostics pattern).
2. Keep `offset_outline` untouched — MM point compatibility depends on its fixed node
   structure. `offset_outline_clean` explicitly does NOT preserve node count; say so in
   the docstring in caps.

**Gate:**
- Convex contour (circle test data), offset -30: clean output identical node count to
  plain offset (no loops to remove).
- L-shaped / concave contour (build an L polygon of lines), offset inward past the concave
  corner radius: plain offset has ≥1 self-intersection, clean output has 0
  (`self_intersections() == []`) and its sampled area is smaller than the plain offset's.
- Idempotence: running clean on an already-clean result changes nothing.

---

## F7 — Serialization round-trip completeness

**Problem A:** `Font._to_xml_element()` / `Font.from_XML()` silently drop `groups` and
`features` (both are constructor kwargs but never serialized).
**Problem B (pre-existing breakage, found 2026-07):** `objects/fontfile.py` imports
`TrFont, TrFontInfo, TrMetrics, TrAxes, TrAxis, TrMaster, TrInstance, TrEncoding,
TrGlyphManifest` from `fileio/trfont.py`, but trfont.py now exports a different API
(`TrFontIO`, `GlyphManifest`, `GlyphEntry`, ...). `import typerig.core.objects.fontfile`
raises ImportError today.

**Steps:**
1. Font XML: serialize `groups` the same way `kerning`/`encoding` are handled (they are
   `Groups` Container/Member classes — check `objects/groups.py` for an existing
   `_to_xml_element`; if present, append when non-empty and parse in `from_XML`). Features:
   store as a text child element `<features>` with CDATA-safe text (it is raw .fea code);
   parse it back. Round-trip must preserve byte-equality of the features string.
2. fontfile.py: reconcile against the CURRENT trfont API. Read both files fully first.
   The likely resolution is that `fontfile.py` predates the trfont rewrite and should be
   either (a) rewritten as a thin wrapper over `TrFontIO`, or (b) deleted if `TrFontIO`
   covers everything (grep `Lib/` and `Scripts/` for `fontfile` imports — if nothing
   imports it, prefer deletion and note it in the commit message). Do not guess: whichever
   path, `import typerig.core.objects.fontfile` must either work or the module must be gone.
3. Add a full-font round-trip check: build a small Font (2 glyphs, 1 master, kerning pair,
   1 group, features string), `to_XML()` → `from_XML()` → compare info fields, metrics,
   axes count, group content, features string, kerning content.

**Gate:** the round-trip check passes; `python -c "import typerig.core.objects.fontfile"`
works or the module no longer exists; `python typerig/core/fileio/trfont.py` (if it has a
`__main__`) still passes.

---

## F8 — Multi-master piecewise evaluation (n > 2 masters)

**Problem:** `delta.py` handles two-master axes (DeltaScale + the new secant solver);
`Glyph.create_virtual_axis(['Light', 'Regular', 'Bold'])` builds ONE DeltaScale over the
list, but interpolation time is derived from a single stem pair — there is no piecewise
evaluator that picks the correct master SEGMENT for a target stem.

**Files:** new class in `objects/delta.py`; convenience method on `Glyph`.

**Steps (read `delta.py` fully first — do not duplicate what DeltaArray already does):**
1. `class PiecewiseAxis(object)` in delta.py:
   - `__init__(self, data_array, stem_array)`: same inputs as DeltaScale but with n ≥ 2
     ordered masters; store per-adjacent-pair DeltaScale objects
     (`self.segments = [DeltaScale(data[i:i+2], stems[i:i+2]) for i in range(n-1)]`);
   - `segment_for_stem(self, target_stem)` → (index, DeltaScale): pick the pair whose
     stem interval contains the target (x-stem drives selection; document this); clamp to
     first/last segment outside the range (extrapolation happens inside that segment,
     consistent with DeltaScale's `extrapolate` flag);
   - `scale_by_stem(...)`: same signature as `DeltaScale.scale_by_stem`, delegating to the
     selected segment;
   - `solve_scale_for_dimension(...)`: same delegation.
2. `Glyph.create_piecewise_axis(layer_names, attributes=None)` mirroring
   `create_virtual_axis` but returning PiecewiseAxis per attribute; leave
   `create_virtual_axis` untouched.
3. `Layer.scale_with_axis` must work unchanged when handed a dict of PiecewiseAxis
   (it only calls `solve_scale_for_dimension` and `scale_by_stem` — verify the duck-type
   holds and add a check).

**Gate:**
- 3 synthetic masters: squares of width 100/200/400 with stems 40/80/160. Target stem 60 →
  segment 0 selected, interpolated width 150 ± 0.5. Target stem 120 → segment 1, width
  300 ± 0.5. Target stem 200 (beyond) with extrapolate=True → width 500 ± 1.
- Continuity at the knot: stem 80 − ε and 80 + ε produce widths within 0.1 of each other.
- `Layer.scale_with_axis` with a piecewise axis reaches target_width within the default
  precision and sets `_scale_converged` True.
