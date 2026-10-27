# MODULE: Typerig / Proxy / GS3 / Path operations (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# --- Boolean operations on GSPaths: the ONE place that uses GSPathOperator ---
#
# Glyphs-native engine, GlyphsCore GSPathOperator class methods. The same
# three selectors exist on GS3 and GS4 (probe Dev/test_pathops_glyphs.py,
# GS 3.5 + 4.1, results in Handouts/boolean_handout.md §3a):
#   removeOverlapPaths:error:   union, result in the array passed
#   subtractPaths:from:error:   result in the from: array
#   intersectPaths:with:error:  result in the with: array
# Each returns (ok, error) through pyobjc. Input GSPaths are not changed:
# the array content is replaced by new paths.
#
# Engine quirks handled here:
#   - Direction counts (nonzero fill): a reversed operand cancels in union.
#     fold() sets every incoming operand to outer direction (CCW) first, so
#     each contour fills on its own (FL parity: one fgShape per contour).
#     The accumulator is engine output and keeps its holes as they are.
#   - Intersect of operands that do not overlap leaves the with: array
#     untouched instead of emptying it. intersect() drops each untouched
#     path that is not inside the other operand (path - a not empty).
#   - Exclude has no native call: (A - B) + (B - A).
#
# Callers write results through trLayer.path_boolean (layer.py), never here.
# ---------------------------------------------------------------------------

# - Dependencies -------------------------
from __future__ import print_function

import objc
from Foundation import NSClassFromString, NSMutableArray

# - Init ---------------------------------
__version__ = '0.1.0'

# Operation names follow FL contour_bool.
OP_ADD       = 'add'
OP_SUBTRACT  = 'subtract'
OP_INTERSECT = 'intersect'
OP_EXCLUDE   = 'exclude'

# trLayer.path_boolean status codes
STATUS_OK           = 'OK'
STATUS_TOO_FEW      = 'TOO_FEW'			# fewer than 2 closed operands
STATUS_EMPTY        = 'EMPTY'			# operation left nothing
STATUS_BAD_INDEX    = 'BAD_INDEX'
STATUS_ENGINE_ERROR = 'ENGINE_ERROR'

AREA_TOLERANCE = 1.		# units^2: below this a remainder counts as empty

# - Errors -------------------------------
class PathOpError(Exception):
	'''GSPathOperator missing or reported failure.'''
	pass

# - Helpers ------------------------------
_operator_class = None

def _operator():
	global _operator_class
	if _operator_class is None:
		_operator_class = NSClassFromString('GSPathOperator')
		if _operator_class is None:
			raise PathOpError('GSPathOperator not found in GlyphsCore')
	return _operator_class

def _array(paths):
	out = NSMutableArray.alloc().init()
	for path in paths:
		out.addObject_(path)
	return out

def _check(result, selector):
	'''Unpack pyobjc BOOL or (BOOL, NSError); raise on failure.'''
	if isinstance(result, tuple):
		ok = bool(result[0])
		error = result[1] if len(result) > 1 else None
	else:
		ok, error = bool(result), None

	if not ok:
		raise PathOpError('%s failed: %s' % (selector, error))

def signed_area(path):
	'''Shoelace area over all nodes of a GSPath. CCW (outer in Glyphs) > 0.
	Off-curves are included: the control polygon has the same orientation
	as the outline for any sane contour.
	'''
	points = [(node.position.x, node.position.y) for node in path.nodes]
	area = 0.
	for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
		area += x0 * y1 - x1 * y0
	return area / 2.

def as_outer(paths):
	'''Copies of paths, each set to outer direction (CCW).'''
	result = []
	for path in paths:
		path = path.copy()
		if signed_area(path) < 0:
			path.reverse()
		result.append(path)
	return result

# - Binary operations --------------------
# a, b: lists of GSPath with final directions (holes CW). Return new lists;
# inputs are not changed.
def union(a, b):
	paths = _array(list(a) + list(b))
	if not len(paths):
		return []
	_check(_operator().removeOverlapPaths_error_(paths, None), 'removeOverlapPaths:error:')
	return list(paths)

def subtract(a, b):
	if not a:
		return []
	if not b:
		return [path.copy() for path in a]
	minuend = _array(a)
	_check(_operator().subtractPaths_from_error_(_array(b), minuend, None), 'subtractPaths:from:error:')
	return list(minuend)

def intersect(a, b):
	if not a or not b:
		return []
	inputs = set(objc.pyobjc_id(path) for path in b)
	second = _array(b)
	_check(_operator().intersectPaths_with_error_(_array(a), second, None), 'intersectPaths:with:error:')

	# The engine leaves a with: path as it was when it does not cross a:
	# right when the path is inside a, wrong when it is apart. A changed
	# path is always a new object. Compare ObjC pointers, not Python
	# wrappers (Glyphs may hand out a new wrapper per access). Keep an
	# untouched path only when path - a is empty (inside a). Subtract is
	# correct for nested and disjoint operands (probe §3a); A - (A - B)
	# is avoided, it subtracts coincident outlines.
	result = []
	for path in second:
		if objc.pyobjc_id(path) in inputs and abs(sum(signed_area(p) for p in subtract([path], a))) > AREA_TOLERANCE:
			continue
		result.append(path)
	return result

def exclude(a, b):
	return subtract(a, b) + subtract(b, a)

OPERATIONS = {
	OP_ADD:       union,
	OP_SUBTRACT:  subtract,
	OP_INTERSECT: intersect,
	OP_EXCLUDE:   exclude,
}

# - Fold ---------------------------------
def fold(operands, operation, reverse=False):
	'''FL contour_bool: left fold of one operation over operand paths.

	Args:
		operands (list of GSPath): closed paths, one operand each, in order.
		operation (str): OP_ADD / OP_SUBTRACT / OP_INTERSECT / OP_EXCLUDE.
		reverse (bool): fold from the last operand (FL Alt).

	Returns:
		list of GSPath: new paths (may be empty). Operands are not changed.

	Raises:
		PathOpError, KeyError (unknown operation).
	'''
	op = OPERATIONS[operation]
	operands = list(reversed(operands)) if reverse else list(operands)
	if not operands:
		return []

	result = as_outer(operands[:1])
	for path in operands[1:]:
		result = op(result, as_outer([path]))
	return result
