# MODULE: TypeRig / Proxy / Guideline (TR ↔ FL helpers)
# NOTE: Convert between core Guideline (UFO-spec) and FL flGuideLine.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# FL stores guidelines as vector lines (QLineF) with snapFlags that tag the
# kind (vertical / horizontal / vector). UFO stores them as (x, y, angle)
# with optional name/color/identifier. This module converts between the two
# forms with no dependency on the old pGlyph/eGlyph wrappers.
#
# What's intentionally NOT round-tripped (FL-specific, no UFO counterpart):
#   - tag(...)        # FL-only string tag list
#   - expression       # FL-only metric expression
#   - style            # FL display style (gsGlyphGuideline, etc.)
#   - snapFlags        # derived on inject from angle; not preserved on eject

# - Dependencies ------------------------
from __future__ import print_function

import math

import fontlab as fl6
import PythonQt as pqt

from typerig.core.objects.guideline import Guideline

# - Init --------------------------------
__version__ = '0.1.0'

# FL snapFlags bit values, measured on FL9 (2026-11): a vertical guide in a
# real VFC carries 0x4080, a horizontal one 0x2080, a fresh flGuideLine
# 0x1080. 0x0080 is common to all; the high bit names the kind. (Older code
# assigned the strings 'vertical'/'horizontal'/'vector' to this int property.)
_SNAP_BASE       = 0x0080
_SNAP_VECTOR     = 0x1000
_SNAP_HORIZONTAL = 0x2000
_SNAP_VERTICAL   = 0x4000

# Below this (degrees) an angle counts as exactly horizontal / vertical.
_ANGLE_EPS = 1e-6


def _snap_flags_for(guide):
	'''FL snapFlags for a core Guideline (UFO semantics).'''
	if guide.x is not None and guide.y is None:
		return _SNAP_BASE | _SNAP_VERTICAL
	if guide.y is not None and guide.x is None:
		return _SNAP_BASE | _SNAP_HORIZONTAL
	return _SNAP_BASE | _SNAP_VECTOR


def _color_to_qcolor(color):
	'''Convert a UFO color string ("r,g,b,a" 0-1 floats) to QColor, or None.'''
	if not color:
		return None
	try:
		parts = [float(c.strip()) for c in color.split(',')]
		if len(parts) < 3:
			return None
		r, g, b = parts[0], parts[1], parts[2]
		a = parts[3] if len(parts) > 3 else 1.0
		# QColor expects 0-255 ints
		return pqt.QtGui.QColor(int(r * 255), int(g * 255), int(b * 255), int(a * 255))
	except (ValueError, AttributeError):
		return None


def _qcolor_to_ufo(qcolor):
	'''Convert QColor → UFO "r,g,b,a" string, or None if invalid.'''
	if qcolor is None or not qcolor.isValid():
		return None
	r = qcolor.red() / 255.0
	g = qcolor.green() / 255.0
	b = qcolor.blue() / 255.0
	a = qcolor.alpha() / 255.0
	return '{:.3f},{:.3f},{:.3f},{:.3f}'.format(r, g, b, a)


def _guide_line(guide):
	'''Two font-space points on the line of a core Guideline (UFO semantics):
	x only -> vertical through x; y only -> horizontal through y;
	x, y, angle -> through (x, y) at `angle` degrees counter-clockwise.'''
	if guide.x is not None and guide.y is None:
		x = float(guide.x)
		return (x, 0.0), (x, 100.0)
	if guide.y is not None and guide.x is None:
		y = float(guide.y)
		return (0.0, y), (100.0, y)
	x = float(guide.x or 0.0)
	y = float(guide.y or 0.0)
	a = math.radians(float(guide.angle or 0.0))
	return (x, y), (x + 100.0 * math.cos(a), y + 100.0 * math.sin(a))


def _build_fl_guideline(guide):
	'''Build an flGuideLine from a core Guideline.

	flGuideLine(QLineF) takes the line in font coordinates (verified FL9:
	extLinef reads back the same two points, angle in radians, CCW).
	'''
	(x1, y1), (x2, y2) = _guide_line(guide)
	line = pqt.QtCore.QLineF(pqt.QtCore.QPointF(x1, y1), pqt.QtCore.QPointF(x2, y2))
	fl_guide = fl6.flGuideLine(line)
	fl_guide.snapFlags = _snap_flags_for(guide)

	if guide.name:
		fl_guide.name = str(guide.name)

	qcolor = _color_to_qcolor(guide.color)
	if qcolor is not None:
		fl_guide.color = qcolor

	return fl_guide


def _fl_to_guideline(fl_guide):
	'''Read a core Guideline out of an flGuideLine.

	The line is flGuideLine.extLinef (a QLineF in font coordinates). Do not
	use .vector (a direction, as an flNode) or .center (a reference point
	that can be off the line for guides offset from a metric: center y=654,
	extPosition 20, line at y=674 in BasilMM).
	'''
	line = fl_guide.extLinef
	p1, p2 = line.p1(), line.p2()
	x1, y1 = float(p1.x()), float(p1.y())
	angle = math.degrees(math.atan2(float(p2.y()) - y1, float(p2.x()) - x1)) % 180.0

	if abs(angle - 90.0) < _ANGLE_EPS:
		x, y, angle = x1, None, None			# vertical
	elif angle < _ANGLE_EPS or abs(angle - 180.0) < _ANGLE_EPS:
		x, y, angle = None, y1, None			# horizontal
	else:
		x, y = x1, y1

	name = getattr(fl_guide, 'name', '') or None

	color = None
	try:
		if fl_guide.hasColor:
			color = _qcolor_to_ufo(fl_guide.color)
	except (AttributeError, TypeError):
		pass

	return Guideline(x=x, y=y, angle=angle, name=name, color=color)
