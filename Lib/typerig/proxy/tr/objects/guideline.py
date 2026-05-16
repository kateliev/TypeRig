# MODULE: TypeRig / Proxy / Guideline (TR ↔ FL helpers)
# NOTE: Convert between core Guideline (UFO-spec) and FL flGuideLine.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

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

import fontlab as fl6
import PythonQt as pqt

from typerig.core.objects.guideline import Guideline

# - Init --------------------------------
__version__ = '0.1.0'

# FL snap-flag constants by kind. Names mirror what TypeRig's older code
# used in proxy/fl/objects/glyph.py _guide_types.
_SNAP_VERTICAL   = 'vertical'
_SNAP_HORIZONTAL = 'horizontal'
_SNAP_VECTOR     = 'vector'


def _snap_flags_for_angle(angle):
	'''Pick a FL snapFlags string based on the guideline angle.

	UFO angle conventions: 0 = vertical, 90 = horizontal, anything else = vector.
	'''
	if angle is None:
		return _SNAP_VECTOR
	a = angle % 180
	if abs(a) < 1e-6:
		return _SNAP_VERTICAL
	if abs(a - 90) < 1e-6:
		return _SNAP_HORIZONTAL
	return _SNAP_VECTOR


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


def _build_fl_guideline(guide):
	'''Build an flGuideLine from a core Guideline.

	UFO → FL vector trick: build a QLineF from (x, y) to the origin, then
	rotate the line so its angle matches the UFO convention. snapFlags is
	derived from the angle so the guide snaps correctly in FL's editor.
	'''
	x = guide.x if guide.x is not None else 0.0
	y = guide.y if guide.y is not None else 0.0
	angle = guide.angle if guide.angle is not None else 0.0

	# UFO: only x → vertical at x (line goes (x, 0) → (x, 1) effectively)
	# UFO: only y → horizontal at y
	# UFO: both → angled line through (x, y) at `angle` degrees
	if guide.x is not None and guide.y is None:
		# Vertical: implicit angle 90 in QLineF terms (since FL uses 90-angle)
		position = pqt.QtCore.QPointF(x, 0)
		vector = pqt.QtCore.QLineF(position, pqt.QtCore.QPointF(0, 0))
		vector.setAngle(90 - 0)        # vertical in UFO = angle 0
	elif guide.y is not None and guide.x is None:
		position = pqt.QtCore.QPointF(0, y)
		vector = pqt.QtCore.QLineF(position, pqt.QtCore.QPointF(0, 0))
		vector.setAngle(90 - 90)       # horizontal in UFO = angle 90
	else:
		position = pqt.QtCore.QPointF(x, y)
		vector = pqt.QtCore.QLineF(position, pqt.QtCore.QPointF(0, 0))
		vector.setAngle(90 - angle)

	fl_guide = fl6.flGuideLine(vector)
	fl_guide.snapFlags = _snap_flags_for_angle(
		0 if (guide.x is not None and guide.y is None)
		else (90 if (guide.y is not None and guide.x is None) else angle)
	)

	if guide.name:
		fl_guide.name = str(guide.name)

	qcolor = _color_to_qcolor(guide.color)
	if qcolor is not None:
		fl_guide.color = qcolor

	return fl_guide


def _fl_to_guideline(fl_guide):
	'''Read a core Guideline out of an flGuideLine.

	FL exposes guides as vector lines; we recover the UFO (x, y, angle) form
	from the QLineF position + angle, and use snapFlags as a hint for the
	axis-aligned cases.
	'''
	# Pull position and angle. flGuideLine exposes the underlying QLineF
	# either as .vector (recent FL) or via .position / .angle accessors.
	x = y = angle_deg = None

	try:
		line = fl_guide.vector
		p1 = line.p1()
		x_pos, y_pos = float(p1.x()), float(p1.y())
		# QLineF.angle() returns 0-360 with 0 = +x axis, ccw. FL's
		# guideline angle convention is (90 - QLineF.angle()) inverted.
		fl_angle = float(line.angle())
		angle_deg = (90.0 - fl_angle) % 360.0
		if angle_deg > 180:
			angle_deg -= 180
	except AttributeError:
		# Fallback: try direct attribute access
		try:
			pos = fl_guide.position
			x_pos = float(pos.x())
			y_pos = float(pos.y())
		except AttributeError:
			x_pos = y_pos = 0.0
		try:
			angle_deg = float(fl_guide.angle)
		except AttributeError:
			angle_deg = 0.0

	# Reduce to the UFO axis-aligned forms where possible
	snap = str(getattr(fl_guide, 'snapFlags', '') or '')

	if _SNAP_VERTICAL in snap or abs(angle_deg) < 1e-6 or abs(angle_deg - 180) < 1e-6:
		x = x_pos
		y = None
		angle = None
	elif _SNAP_HORIZONTAL in snap or abs(angle_deg - 90) < 1e-6:
		x = None
		y = y_pos
		angle = None
	else:
		x = x_pos
		y = y_pos
		angle = angle_deg

	name = getattr(fl_guide, 'name', '') or None

	color = None
	try:
		color = _qcolor_to_ufo(fl_guide.color)
	except (AttributeError, TypeError):
		pass

	return Guideline(x=x, y=y, angle=angle, name=name, color=color)
