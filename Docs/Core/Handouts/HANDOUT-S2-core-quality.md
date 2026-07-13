# HANDOUT S2 — Core Quality Refactors (typerig.core)

**Audience:** implementation agent. Follow stages in order; each stage is self-contained,
landable on its own, and ends with a verification gate. Do not start a stage before the
previous stage's gate passes.

**Repo conventions (mandatory):**
- Indentation is **TABS**, not spaces, in all `Lib/typerig` code.
- Every module has a header banner and a `__version__` string — bump the minor version on any edit.
- Python 3 only. Py2 compatibility has been retired (2026-07) — do not add `from __future__`,
  `basestring`, `__cmp__`, `__getslice__`, or try/except import fallbacks.
- Public API signatures must not change unless the stage explicitly says so.
- Working tree: `D:\Remote\GitHub\TypeRig\Lib\typerig\core`.

**Global verification commands** (run after every stage):

```bash
cd D:/Remote/GitHub/TypeRig/Lib
python -m compileall -q typerig/core/objects typerig/core/func typerig/core/fileio
python typerig/core/objects/point.py       # smoke
python typerig/core/objects/contour.py     # smoke
python typerig/core/objects/layer.py       # smoke
python typerig/core/algo/test_cjk.py       # must end "0 failure(s)"
python typerig/core/algo/mat.py            # must end "Stage 6: all tests passed."
python typerig/core/algo/stem_snap.py      # must end "ALL STAGES PASSED"
python typerig/core/algo/stroke_snap.py    # must end "ALL STAGES PASSED"
python typerig/core/objects/test_objects.py  # from Stage 0 onward
```

---

## Stage 0 — Test suite scaffold (prerequisite for everything)

**Goal:** a flat, dependency-free regression suite for core objects and func, in the same
style as `core/algo/test_cjk.py` (plain `assert`-style checks, run with `python test_objects.py`,
prints `PASS`/`FAIL` per check, exits non-zero on failure). No pytest dependency — the suite
must run inside FontLab's bundled Python.

**Create:** `Lib/typerig/core/objects/test_objects.py`

**Steps:**
1. Copy the harness pattern from `core/algo/test_cjk.py` (a `check(name, cond)` helper,
   failure counter, exit code).
2. Port every check from the S1 verification script — `verify_s1_fixes.py`, in this
   directory (`Docs/Core/Handouts/`). Fix its hardcoded `sys.path` insert when porting.
   It covers: Point arithmetic (both `complex_math` modes), Point/Transform/bezier equality and
   hashing, `__truediv__` on Line/beziers, clone independence, 8-scalar and Point-list
   constructors, `scale()`, `asList()`, `find_roots` quadratic fallback, `intersect_line`,
   closed-form `get_inflection_points`, `solve_parallel` (parallel semantics, cubic/quad
   agreement on an elevated curve), `poly_area` translation invariance, `point_in_triangle`
   both windings, normalizer order preservation, `isclose` defaults, `is_hex` guards,
   `Glyph.unicode` setter, `Glyph.set_mark` with int/name/hex, `linAxis` with non-zero
   minimum position, `Node.randomize` / `Node.lerp_shift`, `Linker` tail removal,
   `Shape.lerp_function` incompatibility rejection.
3. Add structural round-trips not yet covered:
   - `Contour` → `to_XML()` → `from_XML()` → node count, types and coordinates equal.
   - `Contour.to_directional()` → `from_directional()` → on-curve coordinates within 1e-6.
   - `solve_slice(t)` at t=0.5 on a known cubic: both halves' shared point equals
     `solve_point(0.5)`.
   - `get_arc_length()` of a straight-line cubic `(0,0),(25,0),(75,0),(100,0)` equals 100 ± 1e-6.
4. Wire the same expected values as exact literals; do not compute expectations with the
   code under test.

**Gate:** `python typerig/core/objects/test_objects.py` prints ALL PASS; every command in the
global verification block passes.

---

## Stage 1 — Arithmetic mixin (deduplicate operator boilerplate)

**Problem:** `Point`, `Line`, `CubicBezier`, `QuadraticBezier` each hand-roll
`__add__ / __sub__ / __mul__ / __div__` with near-identical bodies. The historical bugs
(`other.x` for the y component, missing `__truediv__`) lived exactly in these duplicates.

**Files:** `objects/point.py`, `objects/line.py`, `objects/cubicbezier.py`,
`objects/quadraticbezier.py`. Put the mixin in `objects/atom.py`.

**Steps:**
1. In `atom.py` add:
   ```python
   class PointsArithmetic(object):
   	'''Mixin: element-wise operators for objects exposing .points (list of Point)
   	and a constructor accepting a list of Points.'''
   	__slots__ = ()

   	def __add__(self, other):
   		return self.__class__([p + other for p in self.points])

   	def __sub__(self, other):
   		return self.__class__([p - other for p in self.points])

   	def __mul__(self, other):
   		return self.__class__([p * other for p in self.points])

   	__rmul__ = __mul__

   	def __truediv__(self, other):
   		return self.__class__([p / other for p in self.points])
   ```
   Keep `__div__ = __truediv__` as a legacy alias on the mixin (external user scripts may
   call it directly).
2. `Line`, `CubicBezier`, `QuadraticBezier`: inherit the mixin, delete their local
   `__add__/__sub__/__mul__/__rmul__/__div__/__truediv__` definitions.
   **Precondition (already true):** each constructor accepts a single list of `Point`
   (the `isMultiInstance(argv[0], Point)` branch). Verify before deleting.
3. `Point` keeps its own operators (its semantics differ: complex product, scalar broadcast) —
   do NOT move Point onto the mixin.
4. Do not alter `Line.__and__`/bezier `__and__` (intersection operators).

**Gate:** global verification + these specific checks in `test_objects.py`:
`Line((0,0),(10,10)) * 2`, `2 * CubicBezier(...)`, `QuadraticBezier(...) / 2`,
`CubicBezier(...) + (5, 5)` all produce correct coordinates and correct types.

---

## Stage 2 — Make `__slots__` real (or remove it)

**Problem:** `XMLSerializable` (in `fileio/xmlio.py`) has no `__slots__`, so every Node,
Contour, Shape, Layer, Glyph instance carries a `__dict__` despite declaring slots. Nodes
number in the tens of thousands per font — the memory win is worth having. But
`Layer.scale_with_axis()` currently stashes ad-hoc attributes (`_scale_factors`,
`_scale_residual`, `_scale_converged`) on the returned Layer, which relies on `__dict__`.

**Decision made for you:** keep `__slots__` and make it effective.

**Steps:**
1. In `fileio/xmlio.py` add `__slots__ = ()` to `XMLSerializable`.
2. In `objects/layer.py` add the three diagnostic names to `Layer.__slots__`:
   `'_scale_factors', '_scale_residual', '_scale_converged'` and initialize them to
   `None` in `__init__` (host panels read them via `getattr(layer, '_scale_converged', None)` —
   check `proxy/` and `Scripts/` with grep and keep that contract working).
3. Remove duplicate slot names: `Member.__slots__` already declares
   `('uid', 'identifier', 'parent', 'lib')`. Delete re-declarations of `identifier`,
   `parent`, `lib` from the `__slots__` of `Node`, `Contour`, `Shape`, `Layer`, `Glyph`,
   `Anchor`, `Guideline`, `Axis`, `FontInfo`, `FontMetrics`, `Font` (keep the names that are
   NOT in a parent's slots).
4. `Member.__slots__` declares `lib` but `Member.__init__` never assigns it — initialize
   `self.lib = kwargs.pop('lib', {})` there and remove per-subclass `self.lib` inits that
   duplicate it.
5. **Trap:** after this stage `some_node.arbitrary_attr = 1` raises AttributeError. Grep
   `Lib/typerig` (core AND proxy) for assignments of undeclared attributes on these classes
   before landing: `grep -rn "\.\(_[a-z_]*\) = " proxy/ | grep -v self` is a start; also run
   every panel-facing smoke you can. If a needed dynamic attribute surfaces, add it to slots
   explicitly rather than reverting.

**Gate:** global verification; plus in `test_objects.py`:
`assert not hasattr(Node(0,0), '__dict__')` and a `Layer.scale_with_axis()` call whose
result still exposes `_scale_converged`.

---

## Stage 3 — One signed-area / winding implementation

**Problem:** three implementations disagree in method and sign convention:
- `Contour.get_on_area()` — iterates ALL nodes (off-curves add spurious edge terms),
  `(x2-x1)(y2+y1)` form, positive = clockwise (y-up).
- `Contour.signed_area` — sampled polyline, cross form, positive = CCW.
- `Contour._get_knot_area()` — knot positions, `(x2-x1)(y2+y1)` form.

**Steps:**
1. Add to `Contour`:
   ```python
   def get_signed_area(self, mode='on'):
   	'''Signed shoelace area. Positive = CCW (y-up). mode: 'on' (on-curve polygon),
   	'sampled' (curve-accurate, 100 steps/segment), 'knots' (hobby knot positions).'''
   ```
   Single shoelace core (`sum(x_i*y_j - x_j*y_i) / 2` over the chosen point list); the
   point list is the only thing that varies. For `'on'` collect **only** `node.is_on`
   coordinates in contour order.
2. Reimplement `signed_area` (property) as `self.get_signed_area('sampled')`;
   `get_on_area()` as `-self.get_signed_area('on')` **(keep its historical sign: positive =
   clockwise — `get_winding()` and `reverse()` depend on it)**; `_get_knot_area()` as
   `-self.get_signed_area('knots')`. Deprecation note in each docstring.
3. Fix the latent `get_on_area` off-curve bug by construction (step 1 uses on-curve only).
   Verify `get_winding()` still returns the same boolean for the three `__main__` test
   contours in `contour.py` (frame, square, circle) — square in that file is CW.
4. `func/geometry.py` `poly_area` stays (pure-tuple utility) but add
   `poly_area_signed(vertices)` beside it and make `poly_area` return `abs(poly_area_signed(...))`.

**Gate:** global verification; new checks: signed area of CCW unit square == +1.0, CW == -1.0
in all three modes on equivalent input; `get_winding()` unchanged for the three test contours;
a contour with curve segments: `'on'` mode ignores BCPs (add a BCP far outside, area unchanged).

---

## Stage 4 — Arc-length parameterization (kill the brute-force scans)

**Problem:** four linear scans exist per bezier class: `solve_distance_start`,
`solve_distance_end` (t-step probing of CHORD distance), `get_point_at_length`,
`divide_at_length` (1000-step polyline walks). Gauss–Legendre quadrature
(`get_arc_length`, 24-point tables) already exists in both classes.

**Steps (apply to `CubicBezier`, then identically to `QuadraticBezier`):**
1. Add:
   ```python
   def solve_t_at_length(self, length, tolerance=1e-6, max_iterations=32):
   	'''Find t such that arc length from p0 to B(t) equals `length`.
   	Newton on F(t) = arclen(0,t) - length; F'(t) = |B'(t)|.
   	Clamps to [0,1]; falls back to bisection when Newton steps outside
   	the bracket or |F'| < 1e-12.'''
   ```
   Arc length on a subinterval: reuse the Gauss–Legendre tables with remapped nodes
   (`t = c*x + m` for interval `[0, t_target]`) — factor the existing loop body of
   `get_arc_length` into `_arc_length_between(t0, t1)` and reuse it everywhere
   (including `get_arc_length()` itself → `_arc_length_between(0., 1.)`).
2. Rewrite `get_point_at_length(distance)` → `self.solve_point(self.solve_t_at_length(distance))`
   with the existing ≤0 / ≥total clamps preserved.
3. Rewrite `divide_at_length(distance)` → `self.solve_slice(self.solve_t_at_length(distance))`
   with the existing degenerate-end returns preserved.
4. **Do NOT change** `solve_distance_start/end` semantics — they measure CHORD distance
   (straight-line from endpoint), not arc length; several node operations
   (`insert_after_distance`, `corner` ops via `solve_distance_extended`) depend on chord
   semantics. Leave them as-is; only add a docstring line making the chord semantics explicit.

**Gate:** global verification; new checks:
- straight-line cubic `(0,0)..(100,0)`: `solve_t_at_length(50)` → point `(50, 0)` ± 1e-4.
- any curved cubic: `_arc_length_between(0, t) + _arc_length_between(t, 1) ==
  get_arc_length()` ± 1e-6 for t in {0.25, 0.5, 0.75}.
- `divide_at_length(L/2)`: both halves' `get_arc_length()` equal ± 0.01 units.
- timing sanity (informational, not gating): `solve_t_at_length` should do ≲ 40 quadrature
  evaluations vs 1000 polyline steps.

---

## Stage 5 — Remove eval/exec

**Files:** `objects/collection.py` (`ndList`), `objects/atom.py` (`Linker.where`),
`fileio/textproto.py` (line ~77).

**Steps:**
1. `ndList.__getitem__` / `__setitem__` with tuple index — replace string building + eval/exec:
   ```python
   from functools import reduce
   from operator import getitem

   def __getitem__(self, index):
   	if isinstance(index, tuple):
   		return reduce(getitem, index, self.data)
   	return self.data[index]

   def __setitem__(self, index, value):
   	if isinstance(index, tuple):
   		reduce(getitem, index[:-1], self.data)[index[-1]] = value
   	else:
   		self.data[index] = value
   ```
   (Preserve tab indentation; note current signature is `(*args)` — normalize to
   `(self, index)` / `(self, index, value)`, behavior identical.)
2. `Linker.where(search, value)` currently evals `'curr_link.{}{}'.format(search, value)`.
   Change the signature to `where(self, predicate)` taking a callable
   `predicate(link) -> bool`. Grep `Lib/` and `Scripts/` for `.where(` usages of Linker
   first — at the time of writing there are none in core; if proxy usages exist, add a
   shim that accepts the old two-arg string form and builds the predicate with
   `operator` functions (eq/lt/gt from a small lookup table), never eval.
3. `fileio/textproto.py`: replace `eval(extract_key), eval(extract_value)` with
   `ast.literal_eval` and a `try/except (ValueError, SyntaxError)` fallback to the raw
   string. `xmlio.py` already uses `ast.literal_eval` — mirror that pattern.

**Gate:** global verification; `grep -rn "eval(" Lib/typerig/core` shows only
`ast.literal_eval`; ndList `__main__` demo prints the same as before; new checks for tuple
get/set on a 2-level ndList.

---

## Stage 6 — `solve_equations` partial pivoting

**File:** `func/math.py`.

**Steps:**
1. Rewrite `solve_equations(AM, BM)` with partial pivoting; operate on **copies**
   (`[row[:] for row in AM]`) so inputs are no longer mutated. Same return shape (BM-style
   column matrix) so callers are untouched. Raise `ValueError('Singular matrix')` when the
   best pivot magnitude < 1e-12.
2. Grep callers (`grep -rn "solve_equations" Lib/`) — hobbyspline and arap are candidates;
   confirm their matrices are lists-of-lists and that they don't rely on the in-place
   mutation (if one does, keep mutating semantics OFF and fix the caller to use the return
   value).

**Gate:** global verification; new checks:
- system `[[0, 1], [1, 0]] x = [1, 2]` (zero pivot first) solves to `x = [2, 1]` instead of
  ZeroDivisionError;
- a 3×3 well-conditioned system matches hand-computed solution ± 1e-9;
- inputs are unchanged after the call (compare against a deep copy).
- `python typerig/core/objects/hobbyspline.py` still runs its `__main__` (if present) —
  hobby splines are the main consumer.

---

## Stage 7 — Bounds utilities

**File:** `objects/utils.py` (`Bounds`).

**Steps:**
1. Guard the empty case: `Bounds([])` currently dies inside `min()`. Raise
   `ValueError('Bounds requires at least one point')` with a clear message instead.
2. Add:
   ```python
   @classmethod
   def from_bounds(cls, bounds_list):
   	'''Union of Bounds objects.'''
   	# collect (x, y) and (xmax, ymax) corners of each and build once

   def union(self, other):        # returns NEW Bounds
   def contains(self, x, y):      # inclusive edges
   def inflate(self, dx, dy=None): # returns NEW Bounds, dy defaults to dx
   ```
3. Replace the repeated corner-flattening pattern in `Shape.bounds`, `Layer.bounds`
   (`sum([[(b.x, b.y), (b.xmax, b.ymax)] for b in ...], [])`) with
   `Bounds.from_bounds([...])`. Behavior must be identical.

**Gate:** global verification; new checks: union of two disjoint boxes, `contains` on
edges (inclusive), `inflate` negative shrink, `Shape.bounds`/`Layer.bounds` values unchanged
for the `__main__` test data in `shape.py` / `layer.py` (record the expected numbers first
by running current code).

---

## Final acceptance (whole handout)

1. Every command in the global verification block passes.
2. `test_objects.py` includes at least the checks named in each stage's gate.
3. `git diff --stat` touches only `Lib/typerig/core` (plus the new test file and this
   handout's checkbox updates, if tracked).
4. No public signature changed except: `Linker.where` (documented in Stage 5) and additions.
