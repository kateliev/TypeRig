# MODULE: TypeRig / Core / Algo / Planar Face Slicer
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
# ------------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

"""General N-contour planar slicer for StrokeSepV3.

Given a scene of contours and a list of cross-contour cuts, this module
constructs the planar graph formed by contour arcs (the on-curve segments
between cut endpoints) and cut edges (the connectors themselves), walks
the graph's faces using a standard half-edge / next-CW-at-vertex rule,
and returns each interior face as an output Contour piece.

This replaces the pair-by-pair `_slice_frame` dispatch that fails when
three or more contours share cross-cuts (B: outer + 2 bowl counters;
uni5C4A: outer + many inner counters). The pair-by-pair approach
operated on stale copies of a shared contour across iterations, producing
overlapping/spurious geometry. The planar-face approach treats every
involved contour exactly once.

Algorithm (summary)
-------------------
1. Snap each cut endpoint to the nearest on-curve node across all contours.
2. For each involved contour, sort its cut endpoints by on-curve index and
   build one forward+one reverse half-edge (arc) per consecutive pair.
   Arcs preserve the off-curve handles between their on-curve endpoints.
3. For each cut, build a forward+reverse half-edge (cut).
4. At every vertex, sort outgoing half-edges by direction angle (CCW).
5. Set `he.next` = the half-edge at `he.dest` that is *immediately CW*
   before `he.twin` in the sorted list (standard planar face-walking
   rule — walks each face on its left side).
6. Walk faces; skip faces bounded entirely by arcs from a single contour
   (those are the plane's outer face and inner-counter "hole" interiors).
7. Return the remaining faces as closed Contour objects.
"""

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.objects.contour import Contour
from typerig.core.algo.stroke_sep_common import _fast_clone_node


__version__ = '0.1.0'


# ============================================================
# Data classes
# ============================================================

class _Vertex(object):
	"""One cut endpoint at a specific on-curve node of a contour."""
	__slots__ = ('ci', 'on_idx', 'data_idx', 'node', 'outgoing')

	def __init__(self, ci, on_idx, data_idx, node):
		self.ci = ci				 # contour index
		self.on_idx = on_idx		 # index within on-curve-only view
		self.data_idx = data_idx	 # index within full contour.data
		self.node = node			 # the actual Node object
		self.outgoing = []			 # list of _HalfEdge originating here

	def __repr__(self):
		return "V(c{}.on{} @ ({:.0f},{:.0f}))".format(
			self.ci, self.on_idx, self.node.x, self.node.y)


class _HalfEdge(object):
	"""Directed half of an edge — either an arc along a contour or a cut.

	path_nodes: full list of Node objects traversed from origin to dest,
	including off-curve handles. For arcs, copied (with fast clone) from
	the contour's data array in the walking direction; for cuts, just
	[origin.node, dest.node].
	"""
	__slots__ = ('origin', 'dest', 'kind', 'ci',
				 'path_nodes', 'twin', 'next', 'angle')

	def __init__(self, origin, dest, kind, ci=None, path_nodes=None):
		self.origin = origin
		self.dest = dest
		self.kind = kind			 # 'arc' or 'cut'
		self.ci = ci				 # contour index (None for cuts)
		self.path_nodes = path_nodes if path_nodes is not None else []
		self.twin = None
		self.next = None
		self.angle = 0.0

	def __repr__(self):
		return "HE({}, {} -> {})".format(self.kind, self.origin, self.dest)


# ============================================================
# Snap helpers
# ============================================================

def _nearest_on_global(contours, pt, snap):
	"""Return (ci, on_idx, data_idx, node) of the on-curve node closest to
	pt across all contours, within `snap` units. None if nothing close."""
	best = None
	best_d = snap
	for ci, c in enumerate(contours):
		on_idx = 0
		for data_idx, n in enumerate(c.data):
			if not n.is_on:
				continue
			d = math.hypot(n.x - pt[0], n.y - pt[1])
			if d < best_d:
				best_d = d
				best = (ci, on_idx, data_idx, n)
			on_idx += 1
	return best


# ============================================================
# Arc extraction (handle-preserving)
# ============================================================

def _arc_between(contour, start_on_idx, end_on_idx):
	"""Return the list of Node objects (including off-curve handles) from
	on-curve node #start_on_idx to on-curve node #end_on_idx, walking the
	contour forward (index-increasing) with wrap-around.

	Includes both endpoints. If start == end, returns the entire contour
	loop (single-cut-endpoint degenerate case).
	"""
	data = list(contour.data)
	n_all = len(data)
	on_to_data = [i for i, nd in enumerate(data) if nd.is_on]
	i_start = on_to_data[start_on_idx]
	i_end = on_to_data[end_on_idx]

	out = [data[i_start]]
	idx = i_start
	# Walk at most n_all steps. If start==end we walk the full loop.
	first_step = True
	for _ in range(n_all):
		if idx == i_end and not first_step:
			break
		idx = (idx + 1) % n_all
		out.append(data[idx])
		first_step = False
	return out


# ============================================================
# Main entry point
# ============================================================

def slice_contours(contours, cross_cuts, snap=15.0, debug=False):
	"""Planar-face slice a set of contours along the given cross-contour cuts.

	Args:
		contours: list of Contour objects (the whole scene).
		cross_cuts: list of ((ax, ay), (bx, by)) tuples. Each endpoint must
			be snappable to an on-curve node of some contour within `snap`.
		snap: max snap distance (font units).
		debug: print diagnostic info.

	Returns:
		(pieces, involved_indices):
			pieces: list of new Contour objects — one per interior face.
			involved_indices: set of original contour indices that
				participated in cutting. The caller should remove these
				from the scene and replace them with `pieces`. Contours
				not in this set pass through unchanged.

		Returns (None, set()) on preconditions failure; caller should fall
		back to the older bridge-then-split path for that cut set.
	"""
	if not cross_cuts:
		return [], set()

	# --- Step 1: snap every cut endpoint to an on-curve node ---
	snapped_cuts = []
	involved = set()
	for cut in cross_cuts:
		a = _nearest_on_global(contours, cut[0], snap)
		b = _nearest_on_global(contours, cut[1], snap)
		if debug:
			print("  slicer: cut {} -> a={} b={}".format(cut, a, b))
		if a is None or b is None:
			if debug:
				print("  slicer: unsnappable cut endpoint, abort")
			return None, set()
		if a[0] == b[0]:
			if debug:
				print("  slicer: cut endpoints on same contour, abort")
			return None, set()
		snapped_cuts.append((a, b))
		involved.add(a[0])
		involved.add(b[0])

	# --- Step 2: build vertex set. A node that receives multiple cuts
	#     yields a single vertex with multiple cut half-edges. ---
	vertex_map = {}

	def _get_vertex(info):
		ci, on_idx, data_idx, node = info
		key = (ci, on_idx)
		v = vertex_map.get(key)
		if v is None:
			v = _Vertex(ci, on_idx, data_idx, node)
			vertex_map[key] = v
		return v

	for a, b in snapped_cuts:
		_get_vertex(a)
		_get_vertex(b)

	# Abort if any involved contour has fewer than 2 cut endpoints — the
	# self-loop single-arc case confuses face walking (arc origin == dest).
	# The single-bridge merge/split path handles those better.
	per_contour = {}
	for v in vertex_map.values():
		per_contour.setdefault(v.ci, []).append(v)
	for ci, vs in per_contour.items():
		if len(vs) < 2:
			if debug:
				print("  slicer: contour {} has only 1 cut endpoint, abort".format(ci))
			return None, set()

	# --- Step 3: build arc half-edges ---
	all_half_edges = []
	for ci in involved:
		contour = contours[ci]
		verts_on = sorted(per_contour[ci], key=lambda v: v.on_idx)
		N = len(verts_on)
		for i in range(N):
			v_start = verts_on[i]
			v_end = verts_on[(i + 1) % N]
			path = _arc_between(contour, v_start.on_idx, v_end.on_idx)
			# Clone nodes so output contours don't share references
			fwd_nodes = [_fast_clone_node(n) for n in path]
			rev_nodes = [_fast_clone_node(n) for n in reversed(path)]
			fwd = _HalfEdge(v_start, v_end, 'arc', ci=ci, path_nodes=fwd_nodes)
			rev = _HalfEdge(v_end, v_start, 'arc', ci=ci, path_nodes=rev_nodes)
			fwd.twin = rev
			rev.twin = fwd
			v_start.outgoing.append(fwd)
			v_end.outgoing.append(rev)
			all_half_edges.append(fwd)
			all_half_edges.append(rev)

	# --- Step 4: build cut half-edges ---
	for a, b in snapped_cuts:
		va = _get_vertex(a)
		vb = _get_vertex(b)
		fwd = _HalfEdge(va, vb, 'cut', path_nodes=[
			_fast_clone_node(va.node), _fast_clone_node(vb.node)])
		rev = _HalfEdge(vb, va, 'cut', path_nodes=[
			_fast_clone_node(vb.node), _fast_clone_node(va.node)])
		fwd.twin = rev
		rev.twin = fwd
		va.outgoing.append(fwd)
		vb.outgoing.append(rev)
		all_half_edges.append(fwd)
		all_half_edges.append(rev)

	# --- Step 5: angle for each half-edge (direction from origin) ---
	# Sort each vertex's outgoing list by ascending angle (CCW from +x).
	for he in all_half_edges:
		pn = he.path_nodes
		if len(pn) < 2:
			he.angle = 0.0
		else:
			dx = pn[1].x - pn[0].x
			dy = pn[1].y - pn[0].y
			he.angle = math.atan2(dy, dx)

	for v in vertex_map.values():
		v.outgoing.sort(key=lambda he: he.angle)

	# --- Step 6: wire he.next using the "immediately CW from twin" rule.
	# This walks every face on its left side (interior faces CCW, outer
	# face CW). Rule (standard half-edge / DCEL face walk):
	#   he.next = v_dest.outgoing[ (index_of(he.twin) - 1) mod deg ]
	for he in all_half_edges:
		v = he.dest
		try:
			idx = v.outgoing.index(he.twin)
		except ValueError:
			if debug:
				print("  slicer: twin not in dest.outgoing, abort")
			return None, set()
		he.next = v.outgoing[(idx - 1) % len(v.outgoing)]

	# --- Step 7: walk faces ---
	faces = []
	visited = set()
	guard_max = 10 * len(all_half_edges) + 10
	for he in all_half_edges:
		if id(he) in visited:
			continue
		face = []
		cur = he
		guard = 0
		while id(cur) not in visited:
			visited.add(id(cur))
			face.append(cur)
			cur = cur.next
			guard += 1
			if guard > guard_max:
				if debug:
					print("  slicer: face walk runaway, abort")
				return None, set()
		faces.append(face)

	if debug:
		print("  slicer: {} half-edges, {} faces found".format(
			len(all_half_edges), len(faces)))

	# --- Step 8: build output contours, skipping self-loop faces ---
	# A self-loop face (every half-edge is an arc from the same contour)
	# represents either the outer face of the plane (bounded by outer-
	# contour arcs only) or the interior of an inner counter hole
	# (bounded by that counter's arcs only). Neither is a stroke piece.
	new_contours = []
	for face in faces:
		is_self_loop = (
			all(he.kind == 'arc' for he in face)
			and len(set(he.ci for he in face)) == 1
		)
		if is_self_loop:
			if debug:
				ci = face[0].ci
				print("  slicer: skip self-loop face (contour {}, {} arcs)".format(
					ci, len(face)))
			continue

		# Concatenate path nodes; drop the last node of each segment so
		# we don't double-count shared endpoints (next segment starts
		# where the current one ends).
		piece_nodes = []
		for he in face:
			piece_nodes.extend(he.path_nodes[:-1])

		# Filter: a piece must have at least 3 on-curve nodes
		on_count = sum(1 for n in piece_nodes if n.is_on)
		if on_count < 3:
			if debug:
				print("  slicer: skip degenerate face ({} on-curve)".format(on_count))
			continue

		piece = Contour(piece_nodes, closed=True)
		# Normalize to CCW for output uniformity
		if not piece.is_ccw:
			piece.reverse()
		new_contours.append(piece)

	if debug:
		print("  slicer: {} pieces from {} involved contours".format(
			len(new_contours), len(involved)))

	return new_contours, involved
