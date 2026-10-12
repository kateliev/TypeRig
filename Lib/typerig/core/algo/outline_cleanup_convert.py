# MODULE: TypeRig / Core / Algo / Outline Cleanup — Conversion
# -----------------------------------------------------------
# TypeRig Contour (node list) <-> MContour (segments per master,
# shared knot metadata). Quadratic runs are expanded at implied
# on-curves and elevated exactly to cubics on the way in.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

from dataclasses import dataclass, replace

from typerig.core.objects.node import Node, node_types
from typerig.core.objects.contour import Contour

from typerig.core.algo.outline_cleanup_geom import Seg, elevate_quad
from typerig.core.algo.outline_cleanup_masters import IncompatibleMasters

__version__ = '1.0.0'


# - Data ---------------------------------
@dataclass(slots=True)
class Knot:
	'''On-curve that starts segment i; shared by all masters.'''
	src: int = -1				# input node index, -1 for implied on-curves
	implied: bool = False		# implied in the input or created by cu2qu
	locked: bool = False		# caller lock (node.lib['locked'] in any master)
	fixed: bool = False			# Stage B lock
	smooth: bool = False
	omit: bool = False			# written as an implied on-curve on output


@dataclass(slots=True)
class MContour:
	segs: list[list[Seg]]		# segs[m][i]; segment i starts at knots[i]
	knots: list[Knot]
	index: int | None = None	# contour index in the input

	@property
	def n_masters(self) -> int:
		return len(self.segs)

	def __len__(self) -> int:
		return len(self.knots)

	def copy(self) -> 'MContour':
		return MContour([list(segs) for segs in self.segs], [replace(k) for k in self.knots], self.index)


def is_cleanable(contour) -> bool:
	return bool(contour.closed) and contour.is_bezier and len(contour.nodes) > 1


def _caller_lock(node) -> bool:
	lib = getattr(node, 'lib', None)
	return bool(lib.get('locked', False)) if lib else False


# - In -----------------------------------
def _contour_segments(contour) -> tuple[list[Seg], list[Knot]]:
	nodes = contour.nodes
	n = len(nodes)
	pts = [(float(node.x), float(node.y)) for node in nodes]
	on_idx = [i for i, node in enumerate(nodes) if node.type == node_types['on']]

	if not on_idx:
		# All off-curve TrueType contour: implied on-curve between last and first
		if any(node.type != node_types['off'] for node in nodes):
			raise ValueError('Contour without on-curve nodes must be all-quadratic')
		start = None
	else:
		start = on_idx[0]

	segs, knots = [], []

	def add(p, knot):
		segs.append(Seg(tuple(p), (len(segs), len(segs) + 1)))
		knots.append(knot)

	if start is None:
		offs = list(range(n))
		first = ((pts[-1][0] + pts[0][0]) * .5, (pts[-1][1] + pts[0][1]) * .5)
		_quad_run(first, [pts[i] for i in offs], first, Knot(implied=True, smooth=True), add)
		return segs, knots

	order = [(start + k) % n for k in range(n)] + [start]
	i = 0
	while i < n:
		k = order[i]
		node = nodes[k]
		knot = Knot(src=k, locked=_caller_lock(node), smooth=bool(node.smooth))

		j = i + 1
		while nodes[order[j]].type != node_types['on']:
			j += 1

		offs = order[i + 1:j]
		kinds = {nodes[o].type for o in offs}
		p0, p1 = pts[k], pts[order[j]]

		if not offs:
			add((p0, p1), knot)
		elif kinds == {node_types['curve']} and len(offs) == 2:
			add((p0, pts[offs[0]], pts[offs[1]], p1), knot)
		elif kinds == {node_types['off']}:
			_quad_run(p0, [pts[o] for o in offs], p1, knot, add)
		else:
			raise ValueError('Unsupported off-curve run {} at node {}'.format(sorted(kinds), k))

		i = j

	return segs, knots


def _quad_run(p0, offs, p1, knot, add):
	start = p0
	for i, q in enumerate(offs):
		if i < len(offs) - 1:
			nq = offs[i + 1]
			end = ((q[0] + nq[0]) * .5, (q[1] + nq[1]) * .5)
		else:
			end = p1

		add(elevate_quad(start, q, end), knot if i == 0 else Knot(implied=True, smooth=True))
		start = end


def to_mcontour(contours, index: int | None = None) -> MContour:
	'''contours: the same contour from every master.'''
	per_master = [_contour_segments(c) for c in contours]
	knots = per_master[0][1]

	for segs, ks in per_master[1:]:
		if len(segs) != len(per_master[0][0]) or any(len(a.p) != len(b.p) for a, b in zip(segs, per_master[0][0])):
			raise IncompatibleMasters('contour {} does not match across masters'.format(index))

		for a, b in zip(knots, ks):
			a.locked = a.locked or b.locked

	return MContour([segs for segs, _ in per_master], knots, index)


# - Out ----------------------------------
def from_mcontour(mc: MContour, sources) -> list[Contour]:
	'''One TypeRig Contour per master. sources: input contour per master,
	used for node names and lib.'''
	result = []

	for m, segs in enumerate(mc.segs):
		src_nodes = sources[m].nodes
		nodes = []

		for knot, seg in zip(mc.knots, segs):
			p = seg.p

			if not knot.omit:
				x, y = p[0]
				kwargs = {'type': node_types['on'], 'smooth': knot.smooth}

				if knot.src >= 0:
					src = src_nodes[knot.src]
					kwargs['name'] = getattr(src, 'name', '') or ''
					lib = getattr(src, 'lib', None)
					if lib:
						kwargs['lib'] = dict(lib)

				nodes.append(Node(x, y, **kwargs))

			if len(p) == 4:
				nodes.append(Node(p[1][0], p[1][1], type=node_types['curve']))
				nodes.append(Node(p[2][0], p[2][1], type=node_types['curve']))
			elif len(p) == 3:
				nodes.append(Node(p[1][0], p[1][1], type=node_types['off']))

		result.append(Contour(nodes, closed=True, name=getattr(sources[m], 'name', '') or ''))

	return result


def clone_contour(contour) -> Contour:
	'''Plain copy for contours that bypass the pipeline (open, hobby).'''
	if not contour.is_bezier:
		return contour.clone()

	nodes = []
	for node in contour.nodes:
		kwargs = {'type': node.type, 'smooth': node.smooth, 'name': getattr(node, 'name', '') or ''}
		lib = getattr(node, 'lib', None)
		if lib:
			kwargs['lib'] = dict(lib)
		nodes.append(Node(node.x, node.y, **kwargs))

	return Contour(nodes, closed=contour.closed, name=getattr(contour, 'name', '') or '')
