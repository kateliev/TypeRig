# MODULE: TypeRig / Core / Algo / Width Audit (shared)
# -----------------------------------------------------------
# Common allowlist + violation vocabulary for stem_snap and
# stroke_snap. Capture semantics: a measurement inside any
# target's band is captured and snapped to that target's
# canonical value; measurements outside every band are
# silently ignored ("not in this allowlist's jurisdiction").
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function, division

__version__ = '0.2.0'


# - Allowlist primitives ----------------
class WidthTarget(object):
	'''A canonical width value plus an asymmetric capture window.

	value     -- the snap-to value. A captured measurement is rewritten
	             to this exact number, never to a band edge.
	tol_minus -- captures measurements down to value - tol_minus.
	tol_plus  -- captures measurements up to value + tol_plus.

	A symmetric `29 +/- 5` is WidthTarget(29, 5, 5).
	An asymmetric capture (e.g. preferring slightly heavier) might be
	WidthTarget(29, 3, 7).
	'''
	__slots__ = ('value', 'tol_minus', 'tol_plus')

	def __init__(self, value, tol_minus=0.0, tol_plus=0.0):
		self.value = float(value)
		self.tol_minus = float(tol_minus)
		self.tol_plus = float(tol_plus)

	def captures(self, w):
		'''True iff `w` falls within this target's capture band.'''
		return self.value - self.tol_minus <= w <= self.value + self.tol_plus

	def correction(self, w):
		'''Signed delta to bring `w` to self.value. Positive => measurement
		is too thin and must be increased.'''
		return self.value - w

	def __repr__(self):
		return 'WidthTarget({}, -{}, +{})'.format(
			self.value, self.tol_minus, self.tol_plus)


class WidthAllowlist(object):
	'''Keyed collection of WidthTarget lists.

	Key semantics are caller-defined: stem_snap uses 'V' / 'H';
	stroke_snap uses CJK stroke types ('horizontal', 'vertical', ...).
	'''
	__slots__ = ('targets_by_key',)

	def __init__(self, targets_by_key=None):
		self.targets_by_key = {}
		if targets_by_key:
			for k, lst in targets_by_key.items():
				self.targets_by_key[k] = list(lst)

	def add(self, key, target):
		self.targets_by_key.setdefault(key, []).append(target)

	def capture(self, key, measured):
		'''Capture lookup for a given measurement.

		If `measured` falls inside ANY target's band under `key`, returns
		(target, signed_correction) where signed_correction = target.value
		- measured. If multiple bands overlap and capture the same value,
		the target whose .value is closest wins; ties go to the earlier
		declaration.

		Out-of-band measurements (in no target's capture window) return
		None — the allowlist makes no claim on them.

		Empty / missing key returns None.
		'''
		targets = self.targets_by_key.get(key, ())
		if not targets:
			return None
		captors = [t for t in targets if t.captures(measured)]
		if not captors:
			return None
		# Nearer-by-value wins; min() is stable so the earlier-declared
		# target wins on a tie.
		nearest = min(captors, key=lambda t: abs(t.value - measured))
		return nearest, nearest.correction(measured)


# - Violation vocabulary ----------------
class Violation(object):
	'''Common shape for stem_snap / stroke_snap outputs.

	key       -- allowlist key that captured the measurement.
	measured  -- the input width.
	target    -- the WidthTarget whose band captured it.
	delta     -- signed correction (target.value - measured). May be 0
	             if the measurement was already exactly on target;
	             callers can choose to filter zero-delta entries for
	             reporting if desired.
	source    -- module-specific payload (StemCandidate, StrokeMeasurement).
	'''
	__slots__ = ('key', 'measured', 'target', 'delta', 'source')

	def __init__(self, key, measured, target, delta, source):
		self.key = key
		self.measured = float(measured)
		self.target = target
		self.delta = float(delta)
		self.source = source

	def __repr__(self):
		return 'Violation(key={!r}, measured={:.3f}, target={}, delta={:+.3f})'.format(
			self.key, self.measured, self.target, self.delta)
