# MODULE: TypeRig / Core / Algo / Medial Axis Extract
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

"""MAT-graph-based skeleton extraction.

Traces each topological stroke of a glyph as a single Bezier contour
running along the medial axis.  Strokes that meet at L-corners
(e.g. the frame of 'E') are walked as one continuous path; strokes
that meet at T-junctions (e.g. the middle arm of 'E', the stem-into-
bar of 'T') are split into separate contours.  Pure closed loops
(O, D, rounded frames) emit one closed contour.

Node positions are MAT-graph positions (fork/terminal nodes + DP-
retained knots at curvature bends), **not** source-node projections.
Short corner-bisector "leg" branches at convex outline corners are
dropped at the graph level so L-corners collapse into pass-throughs.

Reuses:
  - ``compute_mat``           — graph + radii
  - ``extract_stroke_paths``  — tangent-continuing path walker
    (from ``stroke_sep_mat``)
  - ``_simplify_branch``      — Douglas-Peucker

Each output on-curve node carries ``node.lib['radius']`` = half the
local stroke width at that point.
"""

from __future__ import absolute_import, print_function, division
import math

from typerig.core.objects.point import Point
from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour

from typerig.core.algo.mat import (
	compute_mat,
	_simplify_branch,
	_catmull_rom_tangent,
)
from typerig.core.algo.stroke_sep_mat import extract_stroke_paths

__version__ = '0.3.0'

_EPS = 1e-9
_COLINEAR_EPS_RAD = 1e-4


# - Graph walking helpers --------------------------------------------

def _edge_key(a, b):
	return (min(id(a), id(b)), max(id(a), id(b)))


def _walk_raw_branches(graph):
	"""Enumerate terminal/fork-bounded branches of the raw graph.

	Used ONLY for leg identification. Post-leg-drop traversal is done
	by ``extract_stroke_paths`` and the closed-loop post-pass below.
	"""
	visited = set()
	branches = []

	start_nodes = [n for n in graph.nodes if n.degree != 2]
	for start in start_nodes:
		for nb in start.neighbors:
			ek = _edge_key(start, nb)
			if ek in visited:
				continue
			branch = graph.walk_branch(start, nb)
			for i in range(len(branch) - 1):
				visited.add(_edge_key(branch[i], branch[i + 1]))
			branches.append(branch)

	return branches


def _identify_leg_branches(branches, ratio):
	"""Return the subset of ``branches`` classified as corner legs.

	A branch is a corner leg when:
	  - exactly one endpoint is degree-1 (a terminal),
	  - the terminal radius divided by the branch's maximum radius is
	    below ``ratio``.

	Bilateral-terminal branches (both endpoints degree-1, e.g. ellipse
	MAT) and fork-to-fork branches are never legs. Safety: if *every*
	classifiable branch would be a leg, nothing is dropped — so simple
	shapes with no structural fallback are preserved.
	"""
	if ratio <= 0:
		return []

	candidates = []  # (branch, is_leg)

	for b in branches:
		if len(b) < 2:
			candidates.append((b, False))
			continue

		start_term = b[0].degree == 1
		end_term = b[-1].degree == 1

		if start_term and end_term:
			candidates.append((b, False))
			continue
		if not (start_term or end_term):
			candidates.append((b, False))
			continue

		terminal = b[0] if start_term else b[-1]
		max_r = max(n.radius for n in b)
		if max_r < _EPS:
			candidates.append((b, False))
			continue

		candidates.append((b, (terminal.radius / max_r) < ratio))

	has_structure = any(not is_leg for _b, is_leg in candidates)
	if not has_structure:
		return []

	return [b for b, is_leg in candidates if is_leg]


def _disconnect_branch_edges(branch):
	"""Disconnect every consecutive-node edge in ``branch``.

	After disconnection, degree-1 terminals along the leg become
	orphans (degree 0) and the fork at the join drops in degree.
	A former 3-way fork whose only non-leg edges are two collinear
	continuations becomes a degree-2 pass-through, which
	``extract_stroke_paths`` then traces through transparently.
	"""
	for i in range(len(branch) - 1):
		a, b = branch[i], branch[i + 1]
		if b in a.neighbors:
			a.disconnect(b)


# - Closed-loop post-pass --------------------------------------------

def _walk_remaining_loops(graph, visited):
	"""Walk closed loops from edges left unvisited by stroke-path tracing.

	``visited`` is an undirected edge-key set populated from the stroke
	paths. Any remaining edge must be part of a closed cycle with no
	terminals (e.g. the MAT ring of 'O', 'frame', 'maps'), or a
	degenerate fragment. Only genuine cycles (endpoint revisits start)
	are emitted as closed loops.
	"""
	loops = []

	for start in graph.nodes:
		# Find an unvisited incident edge on this node.
		seed = None
		for nb in start.neighbors:
			if _edge_key(start, nb) not in visited:
				seed = nb
				break
		if seed is None:
			continue

		loop = [start]
		prev = start
		curr = seed
		visited.add(_edge_key(start, seed))
		guard = len(graph.nodes) + 4

		while curr is not start and guard > 0:
			loop.append(curr)
			nxt = None
			for n2 in curr.neighbors:
				if n2 is prev:
					continue
				if _edge_key(curr, n2) in visited:
					continue
				nxt = n2
				break
			# Fallback: accept any non-prev neighbor, even if we'd revisit
			# an edge. This closes the loop when degree-2 cycles share an
			# edge-key pattern with already-visited paths at a junction.
			if nxt is None:
				for n2 in curr.neighbors:
					if n2 is not prev:
						nxt = n2
						break
			if nxt is None:
				break
			visited.add(_edge_key(curr, nxt))
			prev = curr
			curr = nxt
			guard -= 1

		if curr is start and len(loop) >= 3:
			loop.append(start)  # close marker
			loops.append(loop)

	return loops


# - Polyline geometry helpers ---------------------------------------

def _collapse_colinear(branch, eps_rad=_COLINEAR_EPS_RAD):
	"""Drop interior nodes whose incoming/outgoing chords are colinear."""
	if len(branch) <= 2:
		return list(branch)

	out = [branch[0]]
	for i in range(1, len(branch) - 1):
		p_prev = out[-1]
		p_curr = branch[i]
		p_next = branch[i + 1]

		ax = p_curr.x - p_prev.x
		ay = p_curr.y - p_prev.y
		bx = p_next.x - p_curr.x
		by = p_next.y - p_curr.y

		la = math.hypot(ax, ay)
		lb = math.hypot(bx, by)
		if la < _EPS or lb < _EPS:
			continue

		cross = (ax * by - ay * bx) / (la * lb)
		if abs(cross) < eps_rad:
			dot = (ax * bx + ay * by) / (la * lb)
			if dot > 0.0:
				continue

		out.append(p_curr)

	out.append(branch[-1])
	return out


def _branch_arc_length(branch):
	total = 0.0
	for i in range(len(branch) - 1):
		total += math.hypot(branch[i + 1].x - branch[i].x,
							branch[i + 1].y - branch[i].y)
	return total


# - Output contour builders -----------------------------------------

def _points_to_line_contour(points, closed):
	"""Straight-segment Contour from (x, y, r) triples."""
	min_n = 3 if closed else 2
	if len(points) < min_n:
		return None

	nodes = []
	for x, y, r in points:
		n = Node((x, y), type='on')
		n.lib = {'radius': r}
		nodes.append(n)
	return Contour(nodes, closed=closed)


def _points_to_cubic_contour(points, closed):
	"""Cubic-Bezier Contour (Catmull-Rom tangents) from (x, y, r) triples.

	For closed contours tangents wrap cyclically; every knot is marked
	smooth. For open contours endpoint tangents fall back to chord
	direction and endpoint knots are left non-smooth.
	"""
	min_n = 3 if closed else 2
	if len(points) < min_n:
		return None

	n = len(points)

	if not closed and n == 2:
		(ax, ay, ra), (bx, by, rb) = points
		p0 = Point(ax, ay)
		p3 = Point(bx, by)
		p1 = p0 + (p3 - p0) * (1.0 / 3.0)
		p2 = p0 + (p3 - p0) * (2.0 / 3.0)

		on0 = Node((p0.x, p0.y), type='on'); on0.lib = {'radius': ra}
		bcp0 = Node((p1.x, p1.y), type='curve')
		bcp1 = Node((p2.x, p2.y), type='curve')
		on1 = Node((p3.x, p3.y), type='on'); on1.lib = {'radius': rb}
		return Contour([on0, bcp0, bcp1, on1], closed=False)

	tangents = []
	for i in range(n):
		if closed:
			prev_pt = (points[(i - 1) % n][0], points[(i - 1) % n][1])
			next_pt = (points[(i + 1) % n][0], points[(i + 1) % n][1])
		else:
			prev_pt = (points[i - 1][0], points[i - 1][1]) if i > 0 else None
			next_pt = (points[i + 1][0], points[i + 1][1]) if i < n - 1 else None
		tangents.append(_catmull_rom_tangent(
			prev_pt, (points[i][0], points[i][1]), next_pt))

	segments = n if closed else (n - 1)
	contour_nodes = []

	for seg_i in range(segments):
		a_i = seg_i
		b_i = (seg_i + 1) % n if closed else (seg_i + 1)
		ax, ay, ra = points[a_i]
		bx, by, rb = points[b_i]
		chord = math.hypot(bx - ax, by - ay)
		handle_len = chord / 3.0

		tx0, ty0 = tangents[a_i]
		p1x = ax + tx0 * handle_len
		p1y = ay + ty0 * handle_len

		tx1, ty1 = tangents[b_i]
		p2x = bx - tx1 * handle_len
		p2y = by - ty1 * handle_len

		if seg_i == 0:
			on_node = Node((ax, ay), type='on', smooth=closed)
			on_node.lib = {'radius': ra}
			contour_nodes.append(on_node)

		contour_nodes.append(Node((p1x, p1y), type='curve'))
		contour_nodes.append(Node((p2x, p2y), type='curve'))

		if closed and seg_i == segments - 1:
			pass  # starting knot already in list
		else:
			is_interior = (seg_i < segments - 1)
			on_end = Node((bx, by), type='on', smooth=is_interior or closed)
			on_end.lib = {'radius': rb}
			contour_nodes.append(on_end)

	if len(contour_nodes) < 2:
		return None
	return Contour(contour_nodes, closed=closed)


# - Simplification --------------------------------------------------

def _simplify_polyline(poly_nodes, tolerance, closed, min_count):
	"""Colinear-collapse + DP-simplify a polyline of MATNodes.

	For closed loops ``poly_nodes`` is expected in open form with the
	first node repeated at the end; the duplicate is stripped before
	returning.
	"""
	if closed and len(poly_nodes) >= 2 and poly_nodes[0] is poly_nodes[-1]:
		working = _collapse_colinear(poly_nodes[:-1] + [poly_nodes[0]])
		# Drop the trailing duplicate before DP so interior simplification
		# doesn't artificially pin it.
		if len(working) >= 2 and working[0] is working[-1]:
			working = working[:-1]
	else:
		working = _collapse_colinear(poly_nodes)

	if len(working) <= min_count:
		return list(working)

	if tolerance is None or tolerance <= 0:
		return list(working)

	# For closed loops, _simplify_branch's endpoint-pinning behavior is
	# not ideal (arbitrary start-point bias), but for typeface MATs the
	# effect is negligible — the simplified knots usually coincide with
	# curvature extrema regardless of where the cycle is unrolled.
	idx = _simplify_branch(working, tolerance)
	reduced = [working[i] for i in idx]

	if len(reduced) < min_count:
		return list(working)
	return reduced


# - Public API -------------------------------------------------------

def extract_medial_axis(
		contours,
		sample_step=5.0,
		beta_min=1.5,
		quality='normal',
		smooth=True,
		drop_corner_legs=True,
		corner_leg_ratio=0.35,
		simplify_tolerance=None,
		prune_short=None,
		lookback=8,
		curvature_bias=0.5,
		peek_steps=6):
	"""Extract a clean medial-axis skeleton as cubic Bezier contours.

	Each topological stroke becomes one open Bezier contour running
	from terminal to terminal through the medial axis; tangent-
	continuous forks are walked transparently (L-corners become a
	single contour passing through the bend). T-junctions split into
	separate contours. Pure closed loops emit one closed contour.

	Args:
		contours:           list[Contour] -- glyph outline.
		sample_step:        MAT boundary sampling step.
		beta_min:           MAT β-pruning threshold.
		quality:            'draft' | 'normal' | 'fine'.
		smooth:             True → cubic Beziers; False → polylines.
		drop_corner_legs:   True → disconnect short corner-bisector
			branches at convex outline corners so L-corners become
			pass-throughs in stroke-path tracing.
		corner_leg_ratio:   terminal-radius / branch-max-radius cutoff.
		simplify_tolerance: DP tolerance (font units). ``None`` defaults
			to ``sample_step`` — enough to collapse sampling noise on
			straight runs while preserving curvature knots.
		prune_short:        optional arc-length cut for terminal legs
			(applied *before* leg-ratio filtering).
		lookback,
		curvature_bias,
		peek_steps:         forwarded to ``extract_stroke_paths`` /
			``pick_best_branch`` for fork-disambiguation tuning.

	Returns:
		list[Contour] -- skeleton contours.
	"""
	if not contours:
		return []

	graph, _concavities = compute_mat(
		contours,
		sample_step=sample_step,
		beta_min=beta_min,
		quality=quality,
	)
	if not graph.nodes:
		return []

	# Optional arc-length pruning of very short terminal branches
	# before leg-ratio filtering.
	if prune_short is not None and prune_short > 0:
		for b in _walk_raw_branches(graph):
			if len(b) < 2:
				continue
			has_terminal = (b[0].degree == 1 or b[-1].degree == 1)
			if has_terminal and _branch_arc_length(b) < prune_short:
				_disconnect_branch_edges(b)

	# Corner-leg drop at graph level — mutates the graph so that
	# former 3-way forks with one leg become degree-2 pass-throughs.
	if drop_corner_legs and corner_leg_ratio > 0:
		raw_branches = _walk_raw_branches(graph)
		for leg in _identify_leg_branches(raw_branches, corner_leg_ratio):
			_disconnect_branch_edges(leg)

	# Stroke-path tracing with tangent-continuity at forks.
	stroke_paths = extract_stroke_paths(
		graph,
		lookback=lookback,
		curvature_bias=curvature_bias,
		peek_steps=peek_steps,
	)

	# Undirected visited-edge set from the stroke paths, for the
	# closed-loop post-pass.
	visited = set()
	for sp in stroke_paths:
		nodes = sp.nodes
		for i in range(len(nodes) - 1):
			visited.add(_edge_key(nodes[i], nodes[i + 1]))

	loops = _walk_remaining_loops(graph, visited)

	if simplify_tolerance is None:
		simplify_tolerance = sample_step

	out = []

	for sp in stroke_paths:
		nodes = sp.nodes
		if len(nodes) < 2:
			continue
		simplified = _simplify_polyline(
			nodes, simplify_tolerance, closed=False, min_count=2)
		if len(simplified) < 2:
			continue
		points = [(m.x, m.y, m.radius) for m in simplified]
		if smooth:
			contour = _points_to_cubic_contour(points, closed=False)
		else:
			contour = _points_to_line_contour(points, closed=False)
		if contour is not None:
			out.append(contour)

	for loop in loops:
		if len(loop) < 3:
			continue
		simplified = _simplify_polyline(
			loop, simplify_tolerance, closed=True, min_count=3)
		if len(simplified) < 3:
			continue
		points = [(m.x, m.y, m.radius) for m in simplified]
		if smooth:
			contour = _points_to_cubic_contour(points, closed=True)
		else:
			contour = _points_to_line_contour(points, closed=True)
		if contour is not None:
			out.append(contour)

	return out
