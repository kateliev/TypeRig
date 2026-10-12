# MODULE: TypeRig / Core / Algo / Outline Cleanup — Multi-master
# -----------------------------------------------------------
# Every structural decision is made once and applied to all
# masters: geometry is per master, topology is shared. Passes
# compute a per-master array, reduce it with one of the helpers
# below, then edit all masters with the same index operation.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import annotations

__version__ = '1.0.0'


class IncompatibleMasters(ValueError):
	pass


# - Reductions ---------------------------
def every(per_master) -> bool:
	'''Removal / line conversion: the test must pass in every master.'''
	return all(per_master)


def some(per_master) -> bool:
	'''Locking: the rule fires in any master.'''
	return any(per_master)


def worst(per_master) -> float:
	'''Simplifier cost: max of the per-master errors, +inf on any failure.'''
	result = 0.
	for value in per_master:
		if value is None:
			return float('inf')
		if value > result:
			result = value
	return result


# - Compatibility ------------------------
def signature(contour) -> tuple:
	return (bool(contour.closed), tuple(node.type for node in contour.nodes))


def assert_compatible(masters, stage: str = 'input') -> None:
	'''masters[m][c] are TypeRig Contours. Same contour count, node count
	and node kinds in the same order in every master.'''
	if not masters:
		return

	ref = masters[0]
	for m, contours in enumerate(masters[1:], 1):
		if len(contours) != len(ref):
			raise IncompatibleMasters('{}: master {} has {} contours, master 0 has {}'.format(stage, m, len(contours), len(ref)))

		for c, (a, b) in enumerate(zip(ref, contours)):
			if signature(a) != signature(b):
				raise IncompatibleMasters('{}: contour {} of master {} does not match master 0'.format(stage, c, m))


def assert_compatible_segments(mcs, stage: str) -> None:
	'''Internal check on MContours: same segment kinds in every master.'''
	for c, mc in enumerate(mcs):
		kinds = [tuple(len(s.p) for s in segs) for segs in mc.segs]
		if any(k != kinds[0] for k in kinds) or any(len(k) != len(mc.knots) for k in kinds):
			raise IncompatibleMasters('{}: contour {} lost compatibility'.format(stage, mc.index if mc.index is not None else c))

