# MODULE: TypeRig / Core / Algo / Medial Axis Extract
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

"""Source-node-driven medial-axis skeleton extraction.

Produces a clean cubic Bezier skeleton where each on-curve output node
corresponds 1:1 to an actual source on-curve node (projected onto the
medial axis). Spurious "corner legs" (MAT branches that dead-end at
sharp outline corners) are dropped by default, leaving only the
stroke spines.

Output contours carry ``node.lib['radius']`` = local inscribed-circle
radius = half the local stroke width, enabling variable-width pen
re-expansion.

Uses ``compute_mat`` as a black box for graph construction + radii.
All stroke-separation machinery (concavities, CutPair, slicer) is
bypassed.
"""

from __future__ import absolute_import, print_function, division
import math
from collections import defaultdict

from typerig.core.objects.point import Point
from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour

from typerig.core.algo.mat import (
	compute_mat,
	_catmull_rom_tangent,
)

__version__ = '0.2.0'

_EPS = 1e-9
_COLINEAR_EPS_RAD = 1e-4


# - Graph walking helpers --------------------------------------------

def _edge_key(a, b):
	return (min(id(a), id(b)), max(id(a), id(b)))


def _extract_branches_and_loops(graph):
	"""Walk the MAT graph, yielding fork/terminal-bounded branches
	and pure degree-2 cycles.

	Returns:
		branches: list[list[MATNode]] -- open polylines.
		loops:    list[list[MATNode]] -- closed polylines; first node
			repeated at end to signal closure.
	"""
	visited = set()
	branches = []
	loops = []

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

	for start in graph.nodes:
		if start.degree != 2:
			continue
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
				if n2 is not prev:
					nxt = n2
					break
			if nxt is None:
				break
			visited.add(_edge_key(curr, nxt))
			prev = curr
			curr = nxt
			guard -= 1
		loop.append(start)
		loops.append(loop)

	return branches, loops


# - Branch geometry helpers -----------------------------------------

def _branch_arc_length(branch):
	total = 0.0
	for i in range(len(branch) - 1):
		total += math.hypot(branch[i + 1].x - branch[i].x,
							branch[i + 1].y - branch[i].y)
	return total


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


# - Corner-leg filtering --------------------------------------------

def _filter_corner_legs(branches, loops, ratio):
	"""Drop terminal branches that are corner bisectors ("legs").

	At a convex outline corner (≤ 90°), the MAT emits a short branch
	that bisects the corner and runs out from the main spine to a
	degree-1 terminal with radius → 0. These appear as odd triangular
	stubs in the extracted skeleton.

	A terminal branch is classified as a corner leg and dropped when:
	  - one end is degree-1 (a terminal),
	  - the terminal radius divided by the branch's maximum radius is
	    below ``ratio``,
	  - the graph has other structure to fall back on (any fork-to-fork
	    branch, any closed loop, or any non-corner-leg terminal branch).

	The last condition protects simple shapes whose MAT is a single
	terminal-to-terminal segment (ellipse-like): those retain their
	branch even when the radius dips at the endpoints.
	"""
	if ratio <= 0:
		return list(branches)

	classified = []  # list of (branch, is_corner_leg)

	for b in branches:
		if len(b) < 2:
			classified.append((b, False))
			continue

		# Only single-terminal branches can be corner legs. A branch
		# with two terminals is a bilateral spine — never a leg.
		start_term = b[0].degree == 1
		end_term = b[-1].degree == 1

		if start_term and end_term:
			classified.append((b, False))
			continue
		if not (start_term or end_term):
			classified.append((b, False))
			continue

		terminal = b[0] if start_term else b[-1]
		max_r = max(n.radius for n in b)
		if max_r < _EPS:
			classified.append((b, False))
			continue

		is_leg = (terminal.radius / max_r) < ratio
		classified.append((b, is_leg))

	# Are there any non-leg structural branches / loops to fall back on?
	has_structure = bool(loops) or any(
		not is_leg for _b, is_leg in classified
	)

	if not has_structure:
		# Graph is entirely made of "legs" by the ratio test — rare; keep
		# everything so the user at least sees the skeleton.
		return [b for b, _ in classified]

	return [b for b, is_leg in classified if not is_leg]


# - Projection onto a polyline --------------------------------------

def _project_onto_polyline(px, py, polyline):
	"""Project (px, py) onto the polyline and return the closest foot.

	Returns (dist, arc_s, fx, fy, radius_at_foot) or None for empty
	polyline. The radius is linearly interpolated between the two
	endpoints of the nearest segment.
	"""
	if len(polyline) < 2:
		return None

	best = None
	cumulative = 0.0
	for i in range(len(polyline) - 1):
		a = polyline[i]
		b = polyline[i + 1]
		dx = b.x - a.x
		dy = b.y - a.y
		len_sq = dx * dx + dy * dy
		seg_len = math.sqrt(len_sq) if len_sq > _EPS else 0.0

		if len_sq < _EPS:
			# Degenerate segment — project onto the start point.
			d = math.hypot(px - a.x, py - a.y)
			if best is None or d < best[0]:
				best = (d, cumulative, a.x, a.y, a.radius)
		else:
			t = ((px - a.x) * dx + (py - a.y) * dy) / len_sq
			if t < 0.0:
				t = 0.0
			elif t > 1.0:
				t = 1.0
			fx = a.x + t * dx
			fy = a.y + t * dy
			d = math.hypot(px - fx, py - fy)
			r = a.radius + t * (b.radius - a.radius)
			s = cumulative + t * seg_len
			if best is None or d < best[0]:
				best = (d, s, fx, fy, r)

		cumulative += seg_len

	return best


# - Output contour builders -----------------------------------------

def _points_to_line_contour(points, closed):
	"""Build a straight-segment Contour from (x, y, r) triples."""
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
	"""Build a smooth cubic-Bezier Contour from (x, y, r) triples.

	Uses Catmull-Rom tangents to place handles. For closed contours
	the tangent at every knot wraps to its cyclic neighbours (smooth
	all the way around). For open contours the endpoint tangents fall
	back to chord direction.
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

	# Compute Catmull-Rom tangents at every knot.
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

	# Number of cubic segments: one per consecutive knot pair. For
	# closed loops, wrap from last back to first.
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

		# Last on-node: for closed contour, don't emit — the first is
		# the same point. For open, mark interior knots as smooth.
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


# - Public API -------------------------------------------------------

def extract_medial_axis(
		contours,
		sample_step=5.0,
		beta_min=1.5,
		quality='normal',
		smooth=True,
		drop_corner_legs=True,
		corner_leg_ratio=0.35,
		dedupe_eps=1.0,
		prune_short=None):
	"""Extract a clean medial-axis skeleton as cubic Bezier contours.

	Each output on-curve node corresponds 1:1 to a source on-curve node
	projected onto the (pruned) medial axis — so the skeleton's node
	positions track the outline's actual node positions, not sampling
	artifacts. Coincident projections (two source nodes that collapse
	to the same medial point, e.g. opposing sides of a stroke) are
	deduped within ``dedupe_eps``.

	"Corner legs" — the short MAT branches that bisect convex outline
	corners out to degree-1 terminals with radius → 0 — are dropped by
	default; source nodes at those corners re-project to the retained
	spine instead.

	Args:
		contours:           list[Contour] -- glyph outline.
		sample_step:        MAT boundary sampling step.
		beta_min:           MAT β-pruning threshold.
		quality:            'draft' | 'normal' | 'fine'.
		smooth:             True → cubic Beziers; False → polylines.
		drop_corner_legs:   True → drop corner-bisector stubs.
		corner_leg_ratio:   terminal-radius / branch-max-radius cutoff.
		dedupe_eps:         projections closer than this collapse to one.
		prune_short:        optional arc-length cut for terminal branches.

	Returns:
		list[Contour] -- skeleton contours (one per topological segment).
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

	branches, loops = _extract_branches_and_loops(graph)

	if drop_corner_legs:
		branches = _filter_corner_legs(branches, loops, corner_leg_ratio)

	if prune_short is not None and prune_short > 0:
		kept = []
		for b in branches:
			is_terminal = (b[0].degree == 1 or b[-1].degree == 1)
			if is_terminal and _branch_arc_length(b) < prune_short:
				continue
			kept.append(b)
		branches = kept

	# Colinear-collapse the retained polylines once so projection and
	# arc-length are computed on the cleaned geometry.
	polylines = []
	for i, b in enumerate(branches):
		if len(b) < 2:
			continue
		polylines.append(('b%d' % i, False, _collapse_colinear(b)))
	for i, l in enumerate(loops):
		if len(l) < 3:
			continue
		polylines.append(('l%d' % i, True, _collapse_colinear(l)))

	if not polylines:
		return []

	# Project each source on-curve node to the nearest polyline.
	projs_by_id = defaultdict(list)
	for contour in contours:
		for node in contour.nodes:
			if getattr(node, 'type', 'on') != 'on':
				continue
			best = None  # (dist, pid, s, fx, fy, r)
			for pid, _is_loop, poly in polylines:
				res = _project_onto_polyline(node.x, node.y, poly)
				if res is None:
					continue
				d, s, fx, fy, r = res
				if best is None or d < best[0]:
					best = (d, pid, s, fx, fy, r)
			if best is not None:
				_d, pid, s, fx, fy, r = best
				projs_by_id[pid].append((s, fx, fy, r))

	# Build output contours.
	out = []
	for pid, is_loop, _poly in polylines:
		projs = projs_by_id.get(pid, [])
		if not projs:
			continue

		projs.sort(key=lambda p: p[0])

		# Dedupe sequential coincident projections.
		deduped = []
		for p in projs:
			if deduped:
				dx = p[1] - deduped[-1][1]
				dy = p[2] - deduped[-1][2]
				if math.hypot(dx, dy) < dedupe_eps:
					continue
			deduped.append(p)

		# Closed loops: check wrap-around coincidence.
		if is_loop and len(deduped) >= 2:
			dx = deduped[0][1] - deduped[-1][1]
			dy = deduped[0][2] - deduped[-1][2]
			if math.hypot(dx, dy) < dedupe_eps:
				deduped.pop()

		points = [(x, y, r) for _s, x, y, r in deduped]

		if smooth:
			contour = _points_to_cubic_contour(points, closed=is_loop)
		else:
			contour = _points_to_line_contour(points, closed=is_loop)

		if contour is not None:
			out.append(contour)

	return out
