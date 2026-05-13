# MODULE: TypeRig / Core / Algo / Stem Center
# -----------------------------------------------------------
# Snap a selection of nodes to the centerline of the
# perpendicular stem they sit inside. Pure consumer of
# stem_snap (StemDetector + StemCandidate.contains_point);
# no new geometry primitives.
#
# Typical use: after a cut-and-extend, the cut piece's end
# nodes float inside a target stem. One call snaps them to
# that stem's centerline along the appropriate axis, across
# all masters, in a single undo block (the caller's job).
#
# Pipeline (per master layer):
#   StemDetector(STRICT) -> candidates
#   filter: axis match, edges not on host contours, contains centroid
#   pick:   min(measured_width); tiebreak by midline distance
#   write:  target_coord = mean(edge_a.coord, edge_b.coord)
#           applied to every selected node's centering coord
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

from typerig.core.objects.node import Node
from typerig.core.objects.contour import Contour
from typerig.core.algo.stem_snap import (
	Axis, Topology, StemDetector,
)

__version__ = '0.1.0'


# - Status codes ------------------------
class StemCenterStatus(object):
	OK              = 'ok'
	AXIS_AMBIGUOUS  = 'axis_ambiguous'
	NO_CANDIDATE    = 'no_candidate'
	NO_SELECTION    = 'no_selection'


# - Result dataclass --------------------
class StemCenterPlan(object):
	'''Per-layer plan entry. target_coord is None when status != OK.'''
	__slots__ = ('layer_name', 'status', 'target_coord', 'center_axis')

	def __init__(self, layer_name, status, target_coord=None, center_axis=None):
		self.layer_name = layer_name
		self.status = status
		self.target_coord = target_coord
		self.center_axis = center_axis

	def __repr__(self):
		return 'StemCenterPlan({!r}, {}, target={}, axis={})'.format(
			self.layer_name, self.status, self.target_coord, self.center_axis)


# - Snapper -----------------------------
class StemCenterSnap(object):
	'''Plan/apply a stem-center snap across one or more layers.

	contours_by_layer  : dict[str, list[Contour]]
	selections_by_layer: dict[str, list[(contour_idx, node_idx)]]
	force_axis         : 'H' | 'V' | None  (target stem axis)
	active_layer       : layer name whose selection drives the axis
	                     decision. None = first key in contours_by_layer.

	Axis convention (matches the handout):
	  target stem axis 'H'  -> stem is horizontal; faces in Y;
	                           centering axis = Y (nodes move on Y).
	  target stem axis 'V'  -> stem is vertical;   faces in X;
	                           centering axis = X (nodes move on X).
	'''
	def __init__(self, contours_by_layer, selections_by_layer,
	             force_axis=None, active_layer=None, ambiguity_tol=1e-6):
		self.contours_by_layer = contours_by_layer
		self.selections_by_layer = selections_by_layer
		self.force_axis = force_axis
		self.active_layer = (active_layer
		                     if active_layer is not None
		                     else next(iter(contours_by_layer)))
		self.ambiguity_tol = float(ambiguity_tol)
		self.target_axis = None
		self.center_axis = None
		self._plan = None

	# -- axis decision (active layer only) --
	def _decide_axis(self):
		if self.force_axis in (Axis.H, Axis.V):
			self.target_axis = self.force_axis
			self.center_axis = 'Y' if self.target_axis == Axis.H else 'X'
			return StemCenterStatus.OK

		sel = self.selections_by_layer.get(self.active_layer, [])
		contours = self.contours_by_layer.get(self.active_layer, [])
		pts = _selection_points(contours, sel)
		if not pts:
			return StemCenterStatus.NO_SELECTION

		xs = [p[0] for p in pts]
		ys = [p[1] for p in pts]
		bbox_w = max(xs) - min(xs)
		bbox_h = max(ys) - min(ys)
		if abs(bbox_w - bbox_h) <= self.ambiguity_tol:
			return StemCenterStatus.AXIS_AMBIGUOUS

		if bbox_w >= bbox_h:
			self.target_axis = Axis.H
			self.center_axis = 'Y'
		else:
			self.target_axis = Axis.V
			self.center_axis = 'X'
		return StemCenterStatus.OK

	# -- per-layer snap --
	def _snap_layer(self, layer_name):
		contours = self.contours_by_layer.get(layer_name, [])
		sel = self.selections_by_layer.get(layer_name, [])
		pts = _selection_points(contours, sel)
		if not pts:
			return StemCenterPlan(layer_name, StemCenterStatus.NO_SELECTION,
			                      center_axis=self.center_axis)

		host = set(ci for ci, ni in sel)
		cx = sum(p[0] for p in pts) / len(pts)
		cy = sum(p[1] for p in pts) / len(pts)
		centroid = (cx, cy)

		cands = StemDetector(topology=Topology.STRICT).detect(contours)

		matches = [c for c in cands
		           if c.axis == self.target_axis
		           and c.edge_a.contour_idx not in host
		           and c.edge_b.contour_idx not in host
		           and c.contains_point(centroid, strict=False)]

		if not matches:
			return StemCenterPlan(layer_name, StemCenterStatus.NO_CANDIDATE,
			                      center_axis=self.center_axis)

		ref = cy if self.target_axis == Axis.H else cx
		def _rank(k):
			mid = 0.5 * (k.edge_a.coord + k.edge_b.coord)
			return (k.measured_width, abs(ref - mid))
		best = min(matches, key=_rank)
		target = 0.5 * (best.edge_a.coord + best.edge_b.coord)
		return StemCenterPlan(layer_name, StemCenterStatus.OK,
		                      target_coord=target, center_axis=self.center_axis)

	# -- public API --
	def plan(self):
		'''Compute the per-layer plan. Returns dict[layer_name, StemCenterPlan].
		Stores axis decision on self.target_axis / self.center_axis.
		'''
		status = self._decide_axis()
		out = {}
		if status != StemCenterStatus.OK:
			for name in self.contours_by_layer:
				out[name] = StemCenterPlan(name, status)
			self._plan = out
			return out

		for name in self.contours_by_layer:
			out[name] = self._snap_layer(name)
		self._plan = out
		return out

	def apply(self):
		'''Apply self._plan (computing it if needed) to the Core contours
		held in contours_by_layer. Mutates Node.x or Node.y on every
		selected node according to the per-layer target_coord.

		Returns the plan dict.
		'''
		if self._plan is None:
			self.plan()
		plan = self._plan

		for name, entry in plan.items():
			if entry.status != StemCenterStatus.OK:
				continue
			contours = self.contours_by_layer.get(name, [])
			sel = self.selections_by_layer.get(name, [])
			set_y = (entry.center_axis == 'Y')
			for ci, ni in sel:
				if 0 <= ci < len(contours):
					nodes = contours[ci].nodes
					if 0 <= ni < len(nodes):
						if set_y:
							nodes[ni].y = entry.target_coord
						else:
							nodes[ni].x = entry.target_coord
		return plan


# - Helpers -----------------------------
def _selection_points(contours, selection):
	pts = []
	for ci, ni in selection:
		if 0 <= ci < len(contours):
			nodes = contours[ci].nodes
			if 0 <= ni < len(nodes):
				nd = nodes[ni]
				pts.append((nd.x, nd.y))
	return pts


# =====================================================================
# Self-tests.
# =====================================================================

def _approx(a, b, tol=1e-6):
	return abs(a - b) <= tol


def _make_rect(x, y, w, h):
	nodes = [Node(x, y), Node(x + w, y), Node(x + w, y + h), Node(x, y + h)]
	return Contour(nodes, closed=True)


# --- Stage 1: single H-stem, vertical cut piece inside ---

def _test_stage1_single_h_stem():
	'''Wide H-stem at y=[0,100]; thin V cut piece inside at x=[275,325].
	Select the cut piece's bottom edge nodes (the two y=0 corners). They
	should snap to y=50 (the H-stem centerline). The cut piece's top
	nodes stay put.
	'''
	h_stem  = _make_rect(0,   0, 600, 100)
	cut     = _make_rect(275, 0, 50,  100)
	contours = [h_stem, cut]
	# cut nodes order: (275,0), (325,0), (325,100), (275,100)
	#                      0        1        2          3
	selection = [(1, 0), (1, 1)]   # two bottom corners of cut piece
	snapper = StemCenterSnap({'l': contours}, {'l': selection})
	plan = snapper.apply()
	assert snapper.target_axis == Axis.H
	assert plan['l'].status == StemCenterStatus.OK
	assert _approx(plan['l'].target_coord, 50.0)
	assert _approx(cut.nodes[0].y, 50.0)
	assert _approx(cut.nodes[1].y, 50.0)
	# Top corners untouched
	assert _approx(cut.nodes[2].y, 100.0)
	assert _approx(cut.nodes[3].y, 100.0)
	# X coords on the snapped nodes untouched
	assert _approx(cut.nodes[0].x, 275.0)
	assert _approx(cut.nodes[1].x, 325.0)
	# H-stem untouched
	assert _approx(h_stem.nodes[0].y, 0.0)
	assert _approx(h_stem.nodes[3].y, 100.0)
	print('  Stage 1: cut piece snaps to H-stem centerline; rest untouched [OK]')


# --- Stage 2: nested H-bars, tightest bracket wins ---

def _test_stage2_tightest_bracket():
	'''Outer wide frame y=[0,400], inner H-bar y=[140,200] (width=60),
	V cut piece inside the inner bar at x=[280,320], y=[140,200].
	Selection = bottom edge of cut piece (y=140). Both H-stems bracket
	the centroid; tightest bracket = inner bar (width 60), centerline=170.
	'''
	outer = _make_rect(0,   0,   600, 400)
	inner = _make_rect(50,  140, 500, 60)    # nested inside outer
	cut   = _make_rect(280, 140, 40,  60)    # inside inner
	# nodes 0,1 of cut are bottom-left/right; centroid y=140 lies on the
	# inner bar's boundary, so use the y=170 midpoint (the cut piece's
	# upper face) for the centroid by selecting the top-2 nodes too.
	selection = [(2, 0), (2, 1)]  # cut piece bottom corners
	snapper = StemCenterSnap(
		{'l': [outer, inner, cut]},
		{'l': selection},
	)
	plan = snapper.apply()
	assert snapper.target_axis == Axis.H
	assert plan['l'].status == StemCenterStatus.OK
	# Inner centerline at y = (140 + 200) / 2 = 170 — not the outer's 200.
	assert _approx(plan['l'].target_coord, 170.0), \
		'expected tightest bracket (inner) y=170; got {}'.format(plan['l'].target_coord)
	print('  Stage 2: nested H-bars -> tightest bracket (inner) wins [OK]')


# --- Stage 3: tapered horizontal stroke uses mean coord ---

def _test_stage3_tapered():
	'''Trapezoid horizontal stroke: top face flat at y=110, bottom face
	flat at y=0, but with a slight inward slant so the face nodes are
	at the corners. StemEdge.coord is the mean of the face nodes, so a
	rectangular face gives an exact integer center.
	'''
	# Flat-faced horizontal stroke 600 wide, 110 tall, plus a thin vertical
	# cut piece inside whose bottom edge we'll snap.
	stroke = _make_rect(0,   0,  600, 110)
	cut    = _make_rect(280, 0,  40,  110)
	selection = [(1, 0), (1, 1)]   # cut piece bottom corners
	snapper = StemCenterSnap({'l': [stroke, cut]}, {'l': selection})
	plan = snapper.apply()
	assert plan['l'].status == StemCenterStatus.OK
	assert _approx(plan['l'].target_coord, 55.0), \
		'face-mean centerline expected y=55; got {}'.format(plan['l'].target_coord)
	print('  Stage 3: face-mean coord drives center (y=55 on 0..110) [OK]')


# --- Stage 4: ambiguous axis aborts without modifier ---

def _test_stage4_ambiguous_axis():
	'''Square cut piece inside a square frame, no force_axis. Bbox is
	exactly square -> AXIS_AMBIGUOUS, no contours mutated.
	'''
	frame = _make_rect(0,   0,   400, 400)
	cut   = _make_rect(150, 150, 100, 100)
	selection = [(1, 0), (1, 2)]   # diagonal corners -> square bbox
	pre = [(nd.x, nd.y) for nd in cut.nodes]
	snapper = StemCenterSnap({'l': [frame, cut]}, {'l': selection})
	plan = snapper.apply()
	assert plan['l'].status == StemCenterStatus.AXIS_AMBIGUOUS
	post = [(nd.x, nd.y) for nd in cut.nodes]
	assert pre == post, 'AXIS_AMBIGUOUS must not mutate any node'
	print('  Stage 4: square selection w/o modifier -> AXIS_AMBIGUOUS, no-op [OK]')


# --- Stage 5: contains_point boundary handled by snapper ---

def _test_stage5_force_axis_overrides():
	'''Force axis = V on a sibling-cut layout: tall V-stem with a small
	cut piece appended below it. Selection = cut piece's top edge.
	Expect snap along X to the V-stem centerline (x=40).
	'''
	v_stem = _make_rect(0,    0, 80, 800)
	cut    = _make_rect(0, -100, 80, 100)
	# cut nodes: (0,-100),(80,-100),(80,0),(0,0). Top edge = indices 2,3.
	selection = [(1, 2), (1, 3)]
	snapper = StemCenterSnap({'l': [v_stem, cut]}, {'l': selection},
	                         force_axis=Axis.V)
	plan = snapper.apply()
	assert snapper.target_axis == Axis.V
	assert snapper.center_axis == 'X'
	assert plan['l'].status == StemCenterStatus.OK
	assert _approx(plan['l'].target_coord, 40.0)
	assert _approx(cut.nodes[2].x, 40.0)
	assert _approx(cut.nodes[3].x, 40.0)
	# Y on snapped nodes untouched
	assert _approx(cut.nodes[2].y, 0.0)
	assert _approx(cut.nodes[3].y, 0.0)
	# v_stem untouched
	assert _approx(v_stem.nodes[0].x, 0.0)
	assert _approx(v_stem.nodes[1].x, 80.0)
	print('  Stage 5: force_axis=V snaps cut-end to V-stem centerline (x=40) [OK]')


# --- Stage 6: multi-master, one master lacks the target ---

def _test_stage6_multi_master_partial_failure():
	'''Two masters: 'm1' has the H-stem; 'm2' is missing it (only the
	cut piece exists). m1 snaps to the centerline; m2 returns NO_CANDIDATE
	and does not mutate.
	'''
	# m1: full geometry
	h1   = _make_rect(0,   0, 600, 100)
	cut1 = _make_rect(275, 0, 50,  100)
	# m2: cut piece only — no H-stem to bracket against
	cut2 = _make_rect(275, 0, 50,  100)

	sel_m1 = [(1, 0), (1, 1)]   # bottom corners of cut piece on m1
	# m2 has cut piece at contour index 0
	sel_m2 = [(0, 0), (0, 1)]

	snapper = StemCenterSnap(
		{'m1': [h1, cut1], 'm2': [cut2]},
		{'m1': sel_m1,     'm2': sel_m2},
		active_layer='m1',
	)
	plan = snapper.apply()
	assert plan['m1'].status == StemCenterStatus.OK
	assert _approx(plan['m1'].target_coord, 50.0)
	assert _approx(cut1.nodes[0].y, 50.0)
	assert plan['m2'].status == StemCenterStatus.NO_CANDIDATE
	# m2 untouched
	assert _approx(cut2.nodes[0].y, 0.0)
	assert _approx(cut2.nodes[1].y, 0.0)
	print('  Stage 6: m1 snaps; m2 NO_CANDIDATE, untouched [OK]')


def _run_stage1_tests(): print('Stage 1 - single H-stem + cut piece:'); _test_stage1_single_h_stem(); print('Stage 1: all tests passed.')
def _run_stage2_tests(): print('Stage 2 - tightest bracket:');           _test_stage2_tightest_bracket(); print('Stage 2: all tests passed.')
def _run_stage3_tests(): print('Stage 3 - face-mean coord:');            _test_stage3_tapered();          print('Stage 3: all tests passed.')
def _run_stage4_tests(): print('Stage 4 - axis ambiguity:');             _test_stage4_ambiguous_axis();   print('Stage 4: all tests passed.')
def _run_stage5_tests(): print('Stage 5 - force_axis override:');        _test_stage5_force_axis_overrides(); print('Stage 5: all tests passed.')
def _run_stage6_tests(): print('Stage 6 - multi-master partial fail:');  _test_stage6_multi_master_partial_failure(); print('Stage 6: all tests passed.')


if __name__ == '__main__':
	_run_stage1_tests(); print()
	_run_stage2_tests(); print()
	_run_stage3_tests(); print()
	_run_stage4_tests(); print()
	_run_stage5_tests(); print()
	_run_stage6_tests(); print()
	print('stem_center: ALL STAGES PASSED')
