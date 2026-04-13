# MODULE: TypeRig / Core / Algo / Stroke Separator — Link Generation
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Link generation, validation, and filtering (§5).

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import math

from typerig.core.algo.stroke_sep_common import _EPS, _seg_intersects_seg
from typerig.core.algo.stroke_sep_mat import (
	ligature_node_set, protruding_direction, branch_salience, _TAU_SIGMA,
)
from typerig.core.algo.stroke_sep_csf import SectorAssignment


# - Link Class ----------

class Link(object):
	"""A candidate stroke-crossing line segment between two concave CSFs.

	Attributes:
		csf1, csf2:        the two concave CSFs whose extrema are the endpoints
		p1, p2:            (x, y) endpoint positions (= csf1.extremum, csf2.extremum)
		flow:              (fx, fy) unit flow vector = -(n1 + n2) / |...|
		link_type:         'normal' | 'compound' | None (unvalidated)
		fork:              MATNode — the fork that owns this link (normal links only)
		protruding_branch: MATNode — fork neighbor that is the protruding branch
		salience:          float — S(ℓ) = exp(...) + Φ
		good_continuation: float — Φ(ε1, ε2) alone
		valid:             bool — passed flow-vs-protruding-direction test
	"""

	__slots__ = (
		'csf1', 'csf2', 'p1', 'p2', 'flow',
		'link_type', 'fork', 'protruding_branch',
		'salience', 'good_continuation', 'valid',
	)

	def __init__(self, csf1, csf2):
		self.csf1 = csf1
		self.csf2 = csf2
		self.p1   = csf1.extremum
		self.p2   = csf2.extremum

		n1 = csf1.inward_normal or (0.0, 0.0)
		n2 = csf2.inward_normal or (0.0, 0.0)
		fx = -(n1[0] + n2[0])
		fy = -(n1[1] + n2[1])
		mag = math.hypot(fx, fy)
		self.flow = (fx / mag, fy / mag) if mag > _EPS else (1.0, 0.0)

		self.link_type         = None
		self.fork              = None
		self.protruding_branch = None
		self.salience          = 0.0
		self.good_continuation = 0.0
		self.valid             = False

	@property
	def length(self):
		return math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])

	def __repr__(self):
		return '<Link: {} {} {} ({:.0f},{:.0f})<->({:.0f},{:.0f}) S={:.3f}>'.format(
			'VALID' if self.valid else 'invalid',
			self.link_type or '?',
			'n/a' if self.fork is None else 'f({:.0f},{:.0f})'.format(
				self.fork.x, self.fork.y),
			self.p1[0], self.p1[1], self.p2[0], self.p2[1],
			self.salience)


# ── A: inside-glyph segment test ──────────────────────────────────────────────

def _precompute_glyph_edges(contours, sample_step=20.0):
	"""Precompute polyline edges and spatial grid for fast link-inside-glyph tests."""
	from typerig.core.algo.mat import _SpatialGrid, sample_contour as _sc

	polylines = []
	all_edges = []
	for contour in contours:
		pts = _sc(contour, step=sample_step)
		if not pts:
			continue
		polylines.append(pts)
		n = len(pts)
		for i in range(n):
			all_edges.append((pts[i][0], pts[i][1],
							  pts[(i + 1) % n][0], pts[(i + 1) % n][1]))

	if not polylines:
		return all_edges, None

	cell = max(sample_step * 5.0, 30.0)
	grid = _SpatialGrid(polylines, cell_size=cell)
	return all_edges, grid


def _link_inside_glyph(p1, p2, contours, n_interior_checks=4,
					   _cached_edges=None, _cached_grid=None):
	"""Return True if segment p1→p2 lies entirely inside the glyph outline."""
	x1, y1 = p1
	x2, y2 = p2

	if _cached_edges is not None:
		for ax, ay, bx, by in _cached_edges:
			if _seg_intersects_seg(x1, y1, x2, y2, ax, ay, bx, by):
				return False
	else:
		from typerig.core.algo.mat import sample_contour as _sc
		for contour in contours:
			pts = _sc(contour, step=20.0)
			n = len(pts)
			for i in range(n):
				ax, ay = pts[i]
				bx, by = pts[(i + 1) % n]
				if _seg_intersects_seg(x1, y1, x2, y2, ax, ay, bx, by):
					return False

	grid = _cached_grid
	if grid is None:
		from typerig.core.algo.mat import _SpatialGrid, sample_contour as _sc
		polylines = []
		for contour in contours:
			pts = _sc(contour, step=20.0)
			if pts:
				polylines.append(pts)
		if not polylines:
			return True
		cell = max(30.0, math.hypot(x2 - x1, y2 - y1) / 5.0)
		grid = _SpatialGrid(polylines, cell_size=cell)

	dx = x2 - x1
	dy = y2 - y1
	link_len = math.hypot(dx, dy)
	_PERP_EPS = 4.0
	if link_len > _EPS:
		px = -dy / link_len * _PERP_EPS
		py =  dx / link_len * _PERP_EPS
	else:
		px, py = _PERP_EPS, 0.0

	for k in range(1, n_interior_checks + 1):
		t = k / float(n_interior_checks + 1)
		mx = x1 + t * dx
		my = y1 + t * dy
		if grid.is_inside(mx, my):
			continue
		if grid.is_inside(mx + px, my + py):
			continue
		if grid.is_inside(mx - px, my - py):
			continue
		return False

	return True


# ── B: good-continuation / association fields (§5.3, Appendix B) ──────────────

_KAPPA1 = 0.27
_KAPPA2 = 0.47
_GC_A = 4.0 * _KAPPA1 * _KAPPA2
_GC_B = _KAPPA1 * _KAPPA2
_GC_COSH_MAX = math.cosh(_GC_A + _GC_B)


def good_continuation(csf1, csf2, sigma):
	"""Compute association-field good-continuation Φ(ε₁, ε₂) (§5.3 / App B)."""
	x1, y1 = csf1.extremum
	x2, y2 = csf2.extremum
	d = math.hypot(x2 - x1, y2 - y1)

	if d < _EPS or sigma < _EPS:
		return 0.0

	phi_r = math.exp(-(d * d) / (2.0 * sigma * sigma))

	lx = (x2 - x1) / d
	ly = (y2 - y1) / d

	def _best_tangent(csf):
		if csf.tangent_pair is None:
			n = csf.inward_normal or (0.0, 1.0)
			return (-n[1], n[0])
		t0, t1 = csf.tangent_pair
		d0 = abs(t0[0] * lx + t0[1] * ly)
		d1 = abs(t1[0] * lx + t1[1] * ly)
		return t0 if d0 <= d1 else t1

	tx1, ty1 = _best_tangent(csf1)
	tx2, ty2 = _best_tangent(csf2)

	beta  = math.atan2(lx * ty1 - ly * tx1, lx * tx1 + ly * ty1)
	alpha = math.atan2(tx1 * ty2 - ty1 * tx2, tx1 * tx2 + ty1 * ty2)

	arg   = _GC_A * math.cos(beta / 2.0) + _GC_B * math.cos(alpha - beta / 2.0)
	phi_a = math.cosh(arg) / _GC_COSH_MAX

	return phi_a * phi_r


# ── D: link generation and validation ─────────────────────────────────────────

def _flow_projection(link, fork, branch_nb, all_lig_ids):
	"""Compute F(ℓ) · P(b, f, C) — used for normal-link validation (Eq. 2)."""
	p = protruding_direction(fork, branch_nb, all_lig_ids)
	return link.flow[0] * p[0] + link.flow[1] * p[1]


def _sector_idx_for_csf(sa, csf):
	"""Return the sector index that csf is assigned to (or a candidate for), or None."""
	for i, c in enumerate(sa.assignments):
		if c is csf:
			return i
	for i in range(len(sa.sectors)):
		for cand in sa.candidates(i):
			if cand is csf:
				return i
	return None


def _protruding_branch_for_normal_link(link, fork, sa, all_lig_ids):
	"""For a normal link at fork, find the branch delimiting BOTH sectors.

	Returns (branch_neighbor, flow_projection) or (None, -inf).
	"""
	si1 = _sector_idx_for_csf(sa, link.csf1)
	si2 = _sector_idx_for_csf(sa, link.csf2)
	if si1 is None or si2 is None:
		return None, float('-inf')

	n_sectors = len(sa.sectors)

	shared = []
	for bi in range(n_sectors):
		left_sector  = (bi - 1) % n_sectors
		right_sector = bi
		if {left_sector, right_sector} == {si1, si2}:
			shared.append(bi)

	best_nb   = None
	best_proj = float('-inf')

	for bi in shared:
		_, nb = sa.branches[bi % len(sa.branches)]
		proj = _flow_projection(link, fork, nb, all_lig_ids)
		if proj > best_proj:
			best_proj = proj
			best_nb   = nb

	return best_nb, best_proj


def generate_links(sector_assignments, contours, graph, ligatures,
				   min_length=5.0, sample_step=20.0):
	"""Generate, validate, and score all candidate links (§5.1–5.3).

	Returns:
		list of Link objects with valid=True, sorted by descending salience
	"""
	# Collect concavities: primary winners + multi-contour runners-up
	csf_by_id = {}
	for sa in sector_assignments.values():
		for csf in sa.assignments:
			if csf is not None:
				csf_by_id[id(csf)] = csf

	fork_csf_ids = {}
	for fork_id, sa in sector_assignments.items():
		ids = set()
		for csf in sa.assignments:
			if csf is not None:
				ids.add(id(csf))

		winner_contours = {c.contour_idx for c in sa.assignments if c is not None}
		if len(winner_contours) > 1:
			for csf in sa.all_csfs:
				ids.add(id(csf))
				csf_by_id[id(csf)] = csf

		if ids:
			fork_csf_ids[fork_id] = frozenset(ids)

	unique_csfs = list(csf_by_id.values())

	if len(unique_csfs) < 2:
		return []

	all_lig_ids = ligature_node_set(ligatures)

	lig_fork_ids = {id(n) for lig in ligatures for n in lig.forks}
	non_lig_radii = [f.radius for f in graph.forks() if id(f) not in lig_fork_ids]
	sigma_phi = 2.0 * max(non_lig_radii) if non_lig_radii else 50.0

	all_radii = [csf.disk_radius for csf in unique_csfs]
	r_max = max(all_radii) if all_radii else 1.0

	_cached_edges, _cached_grid = _precompute_glyph_edges(contours, sample_step=sample_step)

	valid_links = []
	n = len(unique_csfs)

	for i in range(n):
		for j in range(i + 1, n):
			c1 = unique_csfs[i]
			c2 = unique_csfs[j]

			if (c1.contour_idx == c2.contour_idx and
					math.hypot(c1.extremum[0] - c2.extremum[0],
							   c1.extremum[1] - c2.extremum[1]) < min_length):
				continue

			if not _link_inside_glyph(c1.extremum, c2.extremum, contours,
									  _cached_edges=_cached_edges,
									  _cached_grid=_cached_grid):
				continue

			link = Link(c1, c2)
			if link.length < min_length:
				continue

			validated = False
			for fork_id, csf_ids in fork_csf_ids.items():
				if id(c1) in csf_ids and id(c2) in csf_ids:
					sa   = sector_assignments[fork_id]
					fork = sa.fork
					nb, proj = _protruding_branch_for_normal_link(
						link, fork, sa, all_lig_ids)
					if nb is not None and proj > -0.5:
						link.link_type         = 'normal'
						link.fork              = fork
						link.protruding_branch = nb
						link.valid             = True
						validated              = True
						break

			if not validated:
				validated = _try_compound_link(link, graph, sector_assignments,
											   all_lig_ids)

			if not link.valid:
				continue

			phi = good_continuation(c1, c2, sigma_phi)
			link.good_continuation = phi

			r1, r2 = c1.disk_radius, c2.disk_radius
			link.salience = math.exp(-(r1 + r2) / (2.0 * r_max)) + phi

			valid_links.append(link)

	valid_links.sort(key=lambda l: l.salience, reverse=True)
	return valid_links


def _try_compound_link(link, graph, sector_assignments, all_lig_ids):
	"""Test compound-link condition (§5.1.2).

	Marks link.link_type='compound' and link.valid=True if condition met.
	Returns True on success.
	"""
	p1x, p1y = link.p1
	p2x, p2y = link.p2

	crossed_forks = {}

	for fork in graph.forks():
		for nb in fork.neighbors:
			prev, cur = fork, nb
			branch_pts = [(fork.x, fork.y)]
			for _ in range(8):
				branch_pts.append((cur.x, cur.y))
				if cur.is_terminal or cur.is_fork:
					break
				nxt = [n for n in cur.neighbors if n is not prev]
				if not nxt:
					break
				prev, cur = cur, nxt[0]

			crossed = False
			for k in range(len(branch_pts) - 1):
				ax, ay = branch_pts[k]
				bx, by = branch_pts[k + 1]
				if _seg_intersects_seg(p1x, p1y, p2x, p2y, ax, ay, bx, by):
					crossed = True
					break

			if not crossed:
				continue

			sal = branch_salience(fork, nb)
			if sal >= _TAU_SIGMA:
				return False

			fid = id(fork)
			if fid not in crossed_forks:
				crossed_forks[fid] = (fork, nb, sal)

	if len(crossed_forks) < 2:
		return False

	fork_list = [v[0] for v in crossed_forks.values()]
	overlapping = False
	for a in range(len(fork_list)):
		for b in range(a + 1, len(fork_list)):
			fa, fb = fork_list[a], fork_list[b]
			d = math.hypot(fa.x - fb.x, fa.y - fb.y)
			if d < fa.radius + fb.radius:
				overlapping = True
				break
		if overlapping:
			break

	if not overlapping:
		return False

	link.link_type = 'compound'
	link.valid     = True
	return True


# ── E: incompatibility filtering ──────────────────────────────────────────────

def filter_incompatible_links(links):
	"""Remove geometrically incompatible links, keeping the highest-salience set.

	Two links are incompatible if their segments strictly cross.
	Greedy: keep highest-salience first, discard intersecting ones.

	Returns:
		list of Link — mutually compatible subset
	"""
	kept = []
	for link in links:
		x1, y1 = link.p1
		x2, y2 = link.p2
		conflict = False
		for existing in kept:
			ex1, ey1 = existing.p1
			ex2, ey2 = existing.p2
			if _seg_intersects_seg(x1, y1, x2, y2, ex1, ey1, ex2, ey2):
				conflict = True
				break
		if not conflict:
			kept.append(link)
	return kept
