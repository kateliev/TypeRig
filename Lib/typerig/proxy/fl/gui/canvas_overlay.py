# MODULE: TypeRig / Proxy / FontLab / GUI / Canvas Overlay
# -----------------------------------------------------------
# Reusable base for tools that draw on, and take mouse input
# from, FontLab 8's glyph canvas. Knows nothing about any
# particular tool: it provides attachment to the active canvas,
# the font <-> viewport mapping, change detection, drawing
# helpers, draggable handles and a drag/nudge protocol.
#
# Structure (two child widgets of the canvas viewport):
#   CanvasOverlay  - full-size paint layer; transparent for mouse
#   _InputLayer    - same size, masked to the handle hit regions;
#                    paints nothing, routes mouse to the overlay
# Two layers are needed because QWidget.setMask() clips painting
# as well as input: one masked widget could not both draw the
# full overlay and let clicks outside the handles reach FontLab.
#
# Mapping chain (see ViewMapping):
#   font --gi.transform--> canvas --canvas.mapToViewportF--> viewport px
#
# Usage:
#   class MyTool(CanvasOverlay):
#       NAME = 'my_tool'
#       def paint_overlay(self, p, mapping): ...
#   MyTool.toggle()
#
# Demo and checklist (Macro panel):
#   from typerig.proxy.fl.gui import canvas_overlay
#   canvas_overlay._demo()
#   canvas_overlay._manual_checklist()
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
#
# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import absolute_import, print_function, division

import sys
import time

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.gui import overlay_math as om

# - Init --------------------------------
__version__ = '0.1.0'

_log = om.LogOnce(interval=10.)

# Registry of running overlays {NAME: instance}. Kept on sys so that
# re-running or reloading this module from the Macro panel finds the
# instances started by a previous run and never stacks duplicates.
_REGISTRY = getattr(sys, '_typerig_canvas_overlays', None)
if _REGISTRY is None:
	_REGISTRY = {}
	sys._typerig_canvas_overlays = _REGISTRY

OBJECT_NAME_PREFIX = 'tr_overlay_'

# - Accent colors (fixed; theme-independent)
ACCENT_ACTIVE = QtGui.QColor(230, 30, 160)		# magenta
ACCENT_FRAME = QtGui.QColor(0, 180, 230)		# cyan
ACCENT_STEM = QtGui.QColor(255, 176, 0)			# amber
ACCENT_ERROR = QtGui.QColor(230, 40, 40)		# red

# - Utilities ---------------------------
def qv(obj, name):
	'''Property-or-method access. PythonQt exposes Qt properties as attributes
	(widget.rect is a QRect), while plain methods stay callable.'''
	value = getattr(obj, name)
	return value() if callable(value) else value

def cp(p):
	'''Copy a QPointF/QPoint into a new QPointF (event positions alias event memory).'''
	return QtCore.QPointF(float(p.x()), float(p.y()))

def cr(r):
	'''Copy a QRectF/QRect into a new QRectF.'''
	return QtCore.QRectF(float(r.x()), float(r.y()), float(r.width()), float(r.height()))

def ct(t):
	'''Copy a QTransform.'''
	return QtGui.QTransform(t.m11(), t.m12(), t.m13(), t.m21(), t.m22(), t.m23(), t.m31(), t.m32(), t.m33())

def transform_to_affine(t):
	'''QTransform -> overlay_math affine tuple (2D part only).'''
	return (float(t.m11()), float(t.m12()), float(t.m21()), float(t.m22()), float(t.dx()), float(t.dy()))

def affine_to_transform(a):
	'''overlay_math affine tuple -> new QTransform.'''
	return QtGui.QTransform(a[0], a[1], a[2], a[3], a[4], a[5])

def pt(p):
	'''QPointF/QPoint -> (x, y) floats.'''
	return (float(p.x()), float(p.y()))

_EV_POS_ATTR = []

def ev_pos(e):
	'''Copied local position of a mouse event as QPointF (Qt5 localPos/pos, Qt6 position).'''
	if _EV_POS_ATTR:
		return cp(getattr(e, _EV_POS_ATTR[0])())

	for name in ('localPos', 'position', 'pos'):
		try:
			p = cp(getattr(e, name)())
		except (AttributeError, TypeError):
			continue
		_EV_POS_ATTR.append(name)
		return p
	raise AttributeError('ev_pos: unsupported mouse event {}'.format(e))

def modifiers_set(mods):
	'''Qt.KeyboardModifiers -> frozenset of 'shift', 'ctrl', 'alt', 'meta'.'''
	out = []
	for name, flag in (('shift', QtCore.Qt.ShiftModifier), ('ctrl', QtCore.Qt.ControlModifier),
					   ('alt', QtCore.Qt.AltModifier), ('meta', QtCore.Qt.MetaModifier)):
		try:
			if int(mods) & int(flag): out.append(name)
		except TypeError:
			if mods & flag: out.append(name)
	return frozenset(out)

def _workspace(ws=None):
	return ws if ws is not None else fl6.flWorkspace.instance()

def find_active_viewport(ws=None):
	'''Find the viewport widget of the active glyph canvas.
	Returns:
		(viewport_widget, flCanvas) or (None, None)
	'''
	ws = _workspace(ws)

	for w in QtGui.QApplication.allWidgets():
		if isinstance(w, (CanvasOverlay, _InputLayer)):
			continue
		try:
			c = ws.getCanvasForViewport(w)
			if c is not None and ws.isActiveCanvas(c):
				return w, c
		except Exception:
			continue

	return None, None

def glyph_infos(canvas, max_lines=256):
	'''All flGlyphInfo on the canvas: every text block, every line.'''
	out = []
	for tb in canvas.textBlocks() or []:
		for li in range(max_lines):
			try:
				line = tb.getGlyphsInLine(li)
			except Exception:
				break
			if not line:
				break
			out.extend(line)
	return out

def active_glyph_info(canvas):
	'''The active flGlyphInfo on the canvas, or None.'''
	for gi in glyph_infos(canvas):
		try:
			if qv(gi, 'isActive'): return gi
		except Exception:
			continue
	return None

def fl_layer_signature(layer):
	'''Cheap change signature of an flLayer.
	Note: the plan called for node count + sum of on-curve coordinates; reading
	every flNode through PythonQt costs ~10 ms on a 2,000-node glyph, too slow
	for a 33 ms tick. Instead this uses a few native calls per contour (element
	count, arc length, bounds of FontLab's own QPainterPath) plus the layer's
	node count and bounding box. Any node move changes length or bounds.
	'''
	if layer is None: return None
	sig = [int(qv(layer, 'nodesCount'))]
	bb = qv(layer, 'boundingBox')
	sig.extend(om.round_sig((bb.x(), bb.y(), bb.width(), bb.height()), 2))

	for contour in layer.getContours() or []:
		path = contour.path()
		br = path.boundingRect()
		sig.append(path.elementCount())
		sig.extend(om.round_sig((path.length(), br.x(), br.y(), br.width(), br.height()), 2))

	return tuple(sig)

# - Path helpers ------------------------
def ops_to_path(ops, fill_rule=None):
	'''overlay_math path ops -> QPainterPath (same units as the ops).'''
	path = QtGui.QPainterPath()
	path.setFillRule(fill_rule if fill_rule is not None else QtCore.Qt.WindingFill)

	for op in ops:
		kind = op[0]
		if kind == 'move':
			path.moveTo(op[1][0], op[1][1])
		elif kind == 'line':
			path.lineTo(op[1][0], op[1][1])
		elif kind == 'cubic':
			path.cubicTo(op[1][0], op[1][1], op[2][0], op[2][1], op[3][0], op[3][1])
		elif kind == 'quad':
			path.quadTo(op[1][0], op[1][1], op[2][0], op[2][1])
		elif kind == 'close':
			path.closeSubpath()
	return path

def core_layer_to_path(core_layer, fill_rule=None):
	'''QPainterPath in font units from a core Layer/Shape/Contour (or list of them).
	Handles lines, cubics and TrueType quadratics; closes closed contours.'''
	return ops_to_path(om.layer_ops(core_layer), fill_rule)

def fl_layer_to_path(fl_layer):
	'''QPainterPath in font units from an flLayer's own contours (shape
	transforms applied; components are not expanded).'''
	path = QtGui.QPainterPath()
	path.setFillRule(QtCore.Qt.WindingFill)
	if fl_layer is None: return path

	for shape in fl_layer.shapes or []:
		try:
			t = qv(shape, 'transform')
		except Exception:
			t = None
		for contour in shape.contours or []:
			cpath = contour.path()
			path.addPath(t.map(cpath) if t is not None else cpath)
	return path

# - Theme ------------------------------
def theme_colors():
	'''Theme-aware colors from the application palette plus the fixed accents.'''
	pal = qv(QtGui.QApplication, 'palette')
	window = pal.color(QtGui.QPalette.Window)
	text = pal.color(QtGui.QPalette.WindowText)
	dark = window.lightness() < 128

	label_bg = QtGui.QColor(window)
	label_bg.setAlpha(215)
	muted = QtGui.QColor(160, 160, 160) if dark else QtGui.QColor(110, 110, 110)
	outline = QtGui.QColor(20, 20, 20) if dark else QtGui.QColor(255, 255, 255)

	return {
		'dark': dark,
		'text': QtGui.QColor(text),
		'label_bg': label_bg,
		'muted': muted,
		'outline': outline,
		'active': QtGui.QColor(ACCENT_ACTIVE),
		'frame': QtGui.QColor(ACCENT_FRAME),
		'stem': QtGui.QColor(ACCENT_STEM),
		'error': QtGui.QColor(ACCENT_ERROR),
	}

def cosmetic_pen(color, width=1., style=None, alpha=None):
	'''Pen whose width stays in screen pixels regardless of zoom.'''
	c = QtGui.QColor(color)
	if alpha is not None: c.setAlpha(alpha)
	pen = QtGui.QPen(c)
	pen.setWidthF(width)
	pen.setCosmetic(True)
	if style is not None: pen.setStyle(style)
	return pen

def solid_brush(color, alpha=None):
	c = QtGui.QColor(color)
	if alpha is not None: c.setAlpha(alpha)
	return QtGui.QBrush(c)

# - Mapping -----------------------------
class ViewMapping(object):
	'''Frozen snapshot of the font -> viewport transform chain for one glyph.
	Rebuild it every repaint/tick; it is cheap (five canvas calls).

	Attributes:
		font_to_canvas (QTransform): copy of flGlyphInfo.transform
		canvas_to_view (QTransform): affine solved from three mapToViewportF samples
		font_to_view (QTransform): font_to_canvas then canvas_to_view
		view_to_font (QTransform): inverse of font_to_view
		px_per_unit (float): screen px per font unit (keep handle sizes constant)
		ok (bool): the composed transform matched the explicit two-step mapping
			within 0.5 px; if False every mapping goes the slow two-step way.
	'''
	__slots__ = ('font_to_canvas', 'canvas_to_view', 'font_to_view', 'view_to_font', 'px_per_unit', 'ok',
				 'canvas', '_f2c', '_c2v', '_f2v', '_v2f', '_c2f')

	SELF_CHECK_TOL = 0.5
	_SAMPLES = ((0., 0.), (1000., 0.), (0., 1000.))

	@classmethod
	def build(cls, canvas, glyph_info, dpr_divisor=1.):
		'''Build a mapping, or return None if the glyph transform is degenerate.
		dpr_divisor: HiDPI hook. If mapToViewportF turns out to return physical
		pixels on a device-pixel-ratio != 1 screen (unverified; DPR was 1.0 on the
		test machine), pass the ratio here and canvas->view gets divided by it.
		'''
		self = cls.__new__(cls)
		self.canvas = canvas

		t = ct(qv(glyph_info, 'transform'))
		self._f2c = transform_to_affine(t)
		if not om.affine_is_invertible(self._f2c): return None

		dst = []
		for x, y in cls._SAMPLES:
			v = pt(canvas.mapToViewportF(QtCore.QPointF(x, y)))
			dst.append((v[0] / dpr_divisor, v[1] / dpr_divisor))

		self._c2v = om.affine_from_points(cls._SAMPLES, dst)
		self._f2v = om.affine_compose(self._f2c, self._c2v)
		if not om.affine_is_invertible(self._f2v): return None

		self._v2f = om.affine_invert(self._f2v)
		self._c2f = om.affine_invert(self._f2c)

		self.font_to_canvas = t
		self.canvas_to_view = affine_to_transform(self._c2v)
		self.font_to_view = affine_to_transform(self._f2v)
		self.view_to_font = affine_to_transform(self._v2f)
		self.px_per_unit = om.affine_scale(self._f2v)
		self.ok = True

		# - Self-check: composed QTransform vs explicit two-step path
		for x, y in ((0., 0.), (1000., 1000.)):
			composed = pt(self.font_to_view.map(QtCore.QPointF(x, y)))
			explicit = pt(canvas.mapToViewportF(t.map(QtCore.QPointF(x, y))))
			ex, ey = explicit[0] / dpr_divisor, explicit[1] / dpr_divisor
			if abs(composed[0] - ex) > cls.SELF_CHECK_TOL or abs(composed[1] - ey) > cls.SELF_CHECK_TOL:
				self.ok = False
				_log('ViewMapping.selfcheck', 'TypeRig Overlay: ViewMapping self-check failed ({} vs {}); using two-step mapping.'.format(composed, (ex, ey)))
				break

		return self

	@property
	def signature(self):
		'''Rounded (m11, m22, dx, dy) of font_to_view, for change detection.'''
		a = self._f2v
		return om.round_sig((a[0], a[3], a[4], a[5]), 3)

	# - Font <-> view
	def to_view_xy(self, x, y):
		'''Font units -> view (x, y) floats.'''
		if self.ok: return om.affine_apply(self._f2v, x, y)
		return pt(self.canvas.mapToViewportF(self.font_to_canvas.map(QtCore.QPointF(x, y))))

	def to_view(self, x, y):
		'''Font units -> viewport QPointF.'''
		vx, vy = self.to_view_xy(x, y)
		return QtCore.QPointF(vx, vy)

	def to_font(self, qpointf):
		'''Viewport QPointF (or (x, y)) -> (x, y) font units.'''
		vx, vy = (qpointf[0], qpointf[1]) if isinstance(qpointf, tuple) else pt(qpointf)
		if self.ok: return om.affine_apply(self._v2f, vx, vy)
		c = pt(self.canvas.mapFromViewport(QtCore.QPointF(vx, vy)))
		return om.affine_apply(self._c2f, c[0], c[1])

	def len_to_font(self, px):
		return px / self.px_per_unit

	def len_to_view(self, units):
		return units * self.px_per_unit

	def rect_to_view(self, xmin, ymin, xmax, ymax):
		'''Font-unit rect -> normalized viewport QRectF.'''
		pts = [self.to_view_xy(x, y) for x, y in ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax))]
		xs = [p[0] for p in pts]
		ys = [p[1] for p in pts]
		return QtCore.QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

	def path_to_view(self, path):
		'''QPainterPath in font units -> new QPainterPath in viewport px.'''
		if self.ok: return self.font_to_view.map(path)
		return self._path_two_step(path)

	# - Canvas helpers (flGlyphInfo rects are in canvas coordinates)
	def canvas_rect_to_view(self, r):
		x0, y0 = om.affine_apply(self._c2v, r.left(), r.top())
		x1, y1 = om.affine_apply(self._c2v, r.right(), r.bottom())
		return QtCore.QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))

	def canvas_rect_to_font(self, r):
		'''Canvas QRectF -> (xmin, ymin, xmax, ymax) in font units.'''
		x0, y0 = om.affine_apply(self._c2f, r.left(), r.top())
		x1, y1 = om.affine_apply(self._c2f, r.right(), r.bottom())
		return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

	def _path_two_step(self, path):
		out = QtGui.QPainterPath()
		out.setFillRule(path.fillRule())
		count = path.elementCount()
		i = 0
		while i < count:
			e = path.elementAt(i)
			x, y = self.to_view_xy(e.x, e.y)
			if e.isMoveTo():
				out.moveTo(x, y); i += 1
			elif e.isLineTo():
				out.lineTo(x, y); i += 1
			else:
				# CurveTo element followed by two CurveToData elements
				c1 = (x, y)
				e2 = path.elementAt(i + 1); e3 = path.elementAt(i + 2)
				c2 = self.to_view_xy(e2.x, e2.y)
				p3 = self.to_view_xy(e3.x, e3.y)
				out.cubicTo(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1])
				i += 3
		return out

# - Handles -----------------------------
_AXIS_CURSORS = {
	om.AXIS_X: QtCore.Qt.SizeHorCursor,
	om.AXIS_Y: QtCore.Qt.SizeVerCursor,
	om.AXIS_XY: QtCore.Qt.SizeAllCursor,
	om.AXIS_DOMINANT: QtCore.Qt.SizeAllCursor,
}

class Handle(object):
	'''A draggable on-canvas control.

	Attributes:
		key (str): id, e.g. 'scale_x'
		anchor (callable): anchor(mapping) -> QPointF in VIEW coordinates,
			evaluated on every paint/hit-test, e.g. lambda m: m.to_view(x, y)
		shape (str): 'circle' | 'square' | 'diamond' | 'bar_h' | 'bar_v'
		radius (float): size in screen px
		axis (str): drag constraint in font axes: 'x' | 'y' | 'xy' | 'dominant'
		cursor: Qt cursor shape; None = derived from axis
		role (str): paint style: 'primary' | 'secondary' | 'muted'
		enabled (bool): disabled handles are drawn muted and never hit
		tooltip (str): label shown while hovered
	'''
	__slots__ = ('key', 'anchor', 'shape', 'radius', 'axis', 'cursor', 'role', 'enabled', 'tooltip')

	def __init__(self, key, anchor, shape=om.SHAPE_CIRCLE, radius=6., axis=om.AXIS_XY, cursor=None, role='primary', enabled=True, tooltip=''):
		if shape not in om.HANDLE_SHAPES:
			raise ValueError('Handle: unknown shape {!r}'.format(shape))
		self.key = key
		self.anchor = anchor
		self.shape = shape
		self.radius = float(radius)
		self.axis = axis
		self.cursor = cursor
		self.role = role
		self.enabled = enabled
		self.tooltip = tooltip

	def __repr__(self):
		return '<Handle: {} {} axis={}>'.format(self.key, self.shape, self.axis)

	def cursor_shape(self):
		return self.cursor if self.cursor is not None else _AXIS_CURSORS.get(self.axis, QtCore.Qt.SizeAllCursor)

class Drag(object):
	'''State of one handle drag. Deltas are always computed from the press
	point (never accumulated), so there is no drift.

	Attributes:
		press_view, cur_view (QPointF): viewport px; cur_view is axis-constrained
		press_font, cur_font ((x, y)): font units; cur_font is axis-constrained
		modifiers (frozenset): 'shift', 'ctrl', 'alt', 'meta' at the last event
		moves (int): number of move events received
		axis (str): constraint used (the handle's axis)
		started (bool): moved past the drag threshold (otherwise it is a click)
	'''
	__slots__ = ('press_view', 'cur_view', 'press_font', 'cur_font', 'modifiers', 'moves', 'axis', 'started')

	def __init__(self, press_view, press_font, modifiers, axis):
		self.press_view = cp(press_view)
		self.cur_view = cp(press_view)
		self.press_font = (float(press_font[0]), float(press_font[1]))
		self.cur_font = self.press_font
		self.modifiers = modifiers
		self.moves = 0
		self.axis = axis
		self.started = False

	@property
	def delta_view(self):
		return (self.cur_view.x() - self.press_view.x(), self.cur_view.y() - self.press_view.y())

	@property
	def delta_font(self):
		return (self.cur_font[0] - self.press_font[0], self.cur_font[1] - self.press_font[1])

	@property
	def shift(self): return 'shift' in self.modifiers

	@property
	def ctrl(self): return 'ctrl' in self.modifiers

	@property
	def alt(self): return 'alt' in self.modifiers

	def fine_delta_font(self, factor=om.FINE_FACTOR):
		'''delta_font, scaled by factor while Shift is held (fine mode).'''
		return om.drag_delta(self.press_font, self.cur_font, om.AXIS_XY, self.shift, factor)

	def fine_font(self, factor=om.FINE_FACTOR):
		'''Effective dragged font point in fine mode: press + fine_delta_font.'''
		return om.drag_point(self.press_font, self.cur_font, om.AXIS_XY, self.shift, factor)

	def _update(self, view_point, mapping, modifiers):
		self.modifiers = modifiers
		self.moves += 1
		raw_font = mapping.to_font(view_point)
		self.cur_font = om.drag_point(self.press_font, raw_font, self.axis)
		self.cur_view = mapping.to_view(*self.cur_font)

# - Qt glue -----------------------------
class _InputLayer(QtGui.QWidget):
	'''Masked, unpainted widget above the overlay that receives handle input.'''
	def __init__(self, owner):
		QtGui.QWidget.__init__(self)
		self._owner = owner
		self.setObjectName(OBJECT_NAME_PREFIX + 'input')
		self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
		self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
		self.setAutoFillBackground(False)
		self.setFocusPolicy(QtCore.Qt.NoFocus)
		self.setMouseTracking(True)

	def mousePressEvent(self, e): self._owner._dispatch('press', e)
	def mouseMoveEvent(self, e): self._owner._dispatch('move', e)
	def mouseReleaseEvent(self, e): self._owner._dispatch('release', e)
	def mouseDoubleClickEvent(self, e): self._owner._dispatch('double', e)
	def leaveEvent(self, e): self._owner._dispatch('leave', e)

class _EventFilter(QtCore.QObject):
	'''Event filter for the viewport (and the focused widget while keys are captured).'''
	def __init__(self, owner):
		QtCore.QObject.__init__(self)
		self._owner = owner

	def eventFilter(self, obj, ev):
		try:
			return bool(self._owner._filter_event(obj, ev))
		except Exception:
			_log.exception('eventFilter')
			return False

# - Overlay base ------------------------
class CanvasOverlay(QtGui.QWidget):
	'''Base class for on-canvas tools. Subclass and override the hooks.

	Lifecycle (class methods): start(), stop(), toggle()
	Instance: attach(), detach(), kill()

	Hooks (all optional; exceptions are caught and logged):
		paint_overlay(p, mapping)        draw in view px; use the draw_* helpers
		on_attach() / on_kill()
		on_target_changed(mapping)       canvas, glyph or layer changed (mapping may be None)
		on_view_changed(mapping)         zoom, pan, resize or target changed
		on_geometry_changed()            outline of the same layer edited while open
		on_drag_start/move/end/cancel(handle, drag)
		on_handle_click(handle, drag)    released without passing the drag threshold
		on_handle_reset(handle)          double-click
		on_nudge(handle, dx, dy, big)    arrow keys (font units; big = Shift)
		on_key_press(key, modifiers)     other key presses on the canvas; return True to consume
		wants_key(key, modifiers)        return True to claim a key from FontLab shortcuts

	State for subclasses:
		self.handles (list[Handle]), self.canvas, self.viewport, self.glyph_info,
		self.fl_glyph, self.fl_layer, self.mapping, self.drag, self.colors
	'''
	NAME = 'overlay'
	TICK_MS = 33
	DRAG_THRESHOLD_PX = 2.
	HIT_TOLERANCE_PX = 3.
	MASK_PAD_PX = 4.
	NUDGE_STEP = 1.
	NUDGE_BIG = 10.
	REFIND_INTERVAL = 0.25		# seconds between viewport searches while none is active

	_ARROWS = {
		QtCore.Qt.Key_Left: (-1., 0.),
		QtCore.Qt.Key_Right: (1., 0.),
		QtCore.Qt.Key_Up: (0., 1.),			# font Y up
		QtCore.Qt.Key_Down: (0., -1.),
	}

	def __init__(self):
		QtGui.QWidget.__init__(self)
		self.setObjectName(OBJECT_NAME_PREFIX + self.NAME)
		self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
		self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
		self.setAutoFillBackground(False)
		self.setFocusPolicy(QtCore.Qt.NoFocus)

		self._input = _InputLayer(self)
		self._filter = _EventFilter(self)
		self._timer = QtCore.QTimer(self)
		self._timer.setInterval(self.TICK_MS)
		self._timer.timeout.connect(self._tick)

		self.ws = fl6.flWorkspace.instance()
		self.viewport = None
		self.canvas = None
		self.glyph_info = None
		self.fl_glyph = None
		self.fl_layer = None
		self.mapping = None
		self.colors = theme_colors()
		self.dpr_divisor = 1.

		self.handles = []
		self.drag = None
		self.drag_handle = None
		self.hover_handle = None
		self.last_handle = None

		self._filtered = []				# objects our filter is installed on
		self._key_capture = False
		self._mask_sig = None
		self._repaint_requested = False
		self._sig_target = None
		self._sig_view = None
		self._sig_geom = None
		self._refind = om.Throttle(self.REFIND_INTERVAL)
		self._lost_button_ticks = 0
		self._alive = True

	# - Class lifecycle -----------------
	@classmethod
	def instance(cls):
		'''Running instance registered under cls.NAME, or None.'''
		return _REGISTRY.get(cls.NAME)

	@classmethod
	def start(cls, *args, **kwargs):
		'''Kill any instance with the same NAME, then create, attach and return a new one.'''
		cls.stop()
		inst = cls(*args, **kwargs)
		_REGISTRY[cls.NAME] = inst
		if not inst.attach():
			print('TypeRig Overlay: {} waiting for an active glyph canvas.'.format(cls.NAME))
		return inst

	@classmethod
	def stop(cls):
		inst = _REGISTRY.pop(cls.NAME, None)
		if inst is not None:
			try:
				inst.kill()
			except Exception:
				_log.exception('{}.stop'.format(cls.NAME))

	@classmethod
	def toggle(cls, *args, **kwargs):
		'''Start if not running, otherwise stop. Returns the new instance or None.
		An instance whose Qt object was destroyed (its window closed while it
		was visible) counts as not running.'''
		inst = _REGISTRY.get(cls.NAME)
		if inst is not None and inst.alive and inst.qt_alive():
			cls.stop()
			return None
		return cls.start(*args, **kwargs)

	# - Instance lifecycle --------------
	def attach(self):
		'''Find the active viewport, reparent into it, sync geometry, install
		filters and start ticking. Returns True if a viewport was found.'''
		if not self._alive: return False
		self._timer.start()
		vp, cv = find_active_viewport(self.ws)
		if vp is None: return False
		self._bind(vp, cv)
		self._safe_hook('on_attach')
		return True

	def detach(self):
		'''Remove filters and hide; keep the object (attach() resumes).'''
		self._timer.stop()
		self._abort_drag()
		self._set_key_capture(False)
		self._remove_filters()
		self._input.hide()
		self.hide()

	def kill(self):
		'''Detach, stop the timer, schedule deletion and leave the registry.'''
		if not self._alive: return
		self._alive = False
		self._safe_hook('on_kill')
		try:
			self.detach()
		finally:
			self._timer.stop()
			try:
				self._timer.timeout.disconnect(self._tick)
			except Exception:
				pass
			self._input.deleteLater()
			self._filter.deleteLater()
			self.deleteLater()
			if _REGISTRY.get(self.NAME) is self:
				_REGISTRY.pop(self.NAME, None)

	@property
	def alive(self):
		return self._alive

	def qt_alive(self):
		'''False if the underlying C++ widget has been destroyed.'''
		try:
			qv(self, 'objectName')
			return True
		except Exception:
			return False

	def request_repaint(self):
		'''Ask for a repaint (and handle/mask relayout) on the next tick.'''
		self._repaint_requested = True

	# - Binding -------------------------
	def _bind(self, vp, cv):
		if vp is not self.viewport:
			self._abort_drag()
			self._set_key_capture(False)
			self._remove_filters()
			self.setParent(vp)
			self._input.setParent(vp)
			self.viewport = vp

			try:
				dpr = float(qv(vp, 'devicePixelRatioF'))
				if abs(dpr - 1.) > 1e-6:
					_log('dpr', 'TypeRig Overlay: device pixel ratio {} - verify with the demo\'s 500-unit cross; set overlay.dpr_divisor if off by exactly the ratio.'.format(dpr))
			except Exception:
				pass

			self._sig_target = self._sig_view = self._sig_geom = self._mask_sig = None

		self.canvas = cv
		self._install_filter(vp)		# no-op if present; needed after detach() on the same viewport
		self._sync_geometry()
		self.show()
		self._input.show()
		for w in (self, self._input):
			raise_fn = getattr(w, 'raise_', None) or getattr(w, 'raise', None)
			if raise_fn is not None: raise_fn()
		self._repaint_requested = True

	def _orphan(self):
		'''The viewport is going away (hidden/closed): leave it before it deletes us.'''
		self._abort_drag()
		self._set_key_capture(False)
		self._remove_filters()
		self.hide()
		self._input.hide()
		self.setParent(None)
		self._input.setParent(None)
		self.viewport = None
		self.canvas = None
		self.glyph_info = self.fl_glyph = self.fl_layer = self.mapping = None
		self._refind.reset()

	def _sync_geometry(self):
		r = qv(self.viewport, 'rect')
		if qv(self, 'geometry') != r:
			self.setGeometry(r)
		if qv(self._input, 'geometry') != r:
			self._input.setGeometry(r)

	def _install_filter(self, obj):
		if obj is None or any(o is obj for o in self._filtered): return
		obj.installEventFilter(self._filter)
		self._filtered.append(obj)

	def _remove_filter(self, obj):
		for i, o in enumerate(self._filtered):
			if o is obj:
				try:
					obj.removeEventFilter(self._filter)
				except Exception:
					pass
				self._filtered.pop(i)
				return

	def _remove_filters(self):
		for obj in list(self._filtered):
			self._remove_filter(obj)
		self._filtered = []

	# - Tick ----------------------------
	def _tick(self):
		try:
			self._tick_impl()
		except Exception:
			_log.exception('{}.tick'.format(self.NAME))

	def _tick_impl(self):
		if not self._alive: return

		# - Follow the active canvas
		# (searches are throttled: while no canvas is active, e.g. focus is in
		# the Font window, walking allWidgets every tick would be wasteful)
		if self.viewport is None or self.canvas is None or not self.ws.isActiveCanvas(self.canvas):
			if not self._refind.ready(): return
			vp, cv = find_active_viewport(self.ws)
			if vp is None: return
			self._bind(vp, cv)

		self._sync_geometry()
		self._check_lost_drag()

		# - Target and mapping
		gi = active_glyph_info(self.canvas)
		self.glyph_info = gi
		mapping = None
		layer = None
		glyph_name = layer_name = None

		if gi is not None:
			mapping = ViewMapping.build(self.canvas, gi, self.dpr_divisor)
			self.fl_glyph = qv(gi, 'glyph')
			layer = qv(self.fl_glyph, 'activeLayer') if self.fl_glyph is not None else None
			glyph_name = str(qv(gi, 'name'))
			layer_name = str(qv(layer, 'name')) if layer is not None else None
		else:
			self.fl_glyph = None

		self.fl_layer = layer
		self.mapping = mapping

		# - Signatures
		r = qv(self.viewport, 'rect')
		sig_target = (id(self.viewport), glyph_name, layer_name)
		sig_view = ((r.x(), r.y(), r.width(), r.height()), sig_target, mapping.signature if mapping is not None else None)
		sig_geom = fl_layer_signature(layer) if layer is not None else None

		changed = False

		if sig_target != self._sig_target:
			self._sig_target = sig_target
			self._sig_geom = sig_geom
			self._safe_hook('on_target_changed', mapping)
			changed = True

		elif sig_geom != self._sig_geom:
			self._sig_geom = sig_geom
			self._safe_hook('on_geometry_changed')
			changed = True

		if sig_view != self._sig_view:
			self._sig_view = sig_view
			self._safe_hook('on_view_changed', mapping)
			changed = True

		if changed or self._repaint_requested:
			self._repaint_requested = False
			self._update_mask(mapping)
			self.update()

	def _check_lost_drag(self):
		'''Cancel a drag whose button release never arrived.'''
		if self.drag is None:
			self._lost_button_ticks = 0
			return
		buttons = qv(QtGui.QApplication, 'mouseButtons')
		try:
			down = bool(int(buttons) & int(QtCore.Qt.LeftButton))
		except TypeError:
			down = bool(buttons & QtCore.Qt.LeftButton)
		self._lost_button_ticks = 0 if down else self._lost_button_ticks + 1
		if self._lost_button_ticks >= 3:
			_log('lost_release', 'TypeRig Overlay: mouse release lost; drag cancelled.')
			self._cancel_drag()

	# - Hooks (override) ----------------
	def paint_overlay(self, p, mapping): pass
	def on_attach(self): pass
	def on_kill(self): pass
	def on_target_changed(self, mapping): pass
	def on_view_changed(self, mapping): pass
	def on_geometry_changed(self): pass
	def on_drag_start(self, handle, drag): pass
	def on_drag_move(self, handle, drag): pass
	def on_drag_end(self, handle, drag): pass
	def on_drag_cancel(self, handle, drag): pass
	def on_handle_click(self, handle, drag): pass
	def on_handle_reset(self, handle): pass
	def on_nudge(self, handle, dx, dy, big): pass
	def on_key_press(self, key, modifiers): return False
	def wants_key(self, key, modifiers): return False

	def _safe_hook(self, name, *args):
		try:
			return getattr(self, name)(*args)
		except Exception:
			_log.exception('{}.{}'.format(self.NAME, name))
			return None

	# - Painting ------------------------
	def paintEvent(self, e):
		p = None
		try:
			if self.canvas is None or self.glyph_info is None: return
			mapping = ViewMapping.build(self.canvas, self.glyph_info, self.dpr_divisor)
			if mapping is None: return
			self.mapping = mapping

			p = QtGui.QPainter(self)
			p.setRenderHint(QtGui.QPainter.Antialiasing, True)
			p.save()
			try:
				self.paint_overlay(p, mapping)
			except Exception:
				_log.exception('{}.paint_overlay'.format(self.NAME))
			p.restore()
			self._paint_handles(p, mapping)

		except Exception:
			_log.exception('{}.paintEvent'.format(self.NAME))

		finally:
			if p is not None:
				try:
					p.end()
				except Exception:
					pass

	def draw_font_path(self, p, path_font, pen=None, brush=None):
		'''Draw a QPainterPath given in font units.'''
		p.setPen(pen if pen is not None else QtCore.Qt.NoPen)
		p.setBrush(brush if brush is not None else QtCore.Qt.NoBrush)
		p.drawPath(self.mapping.path_to_view(path_font))

	def draw_font_rect(self, p, xmin, ymin, xmax, ymax, pen=None, brush=None):
		p.setPen(pen if pen is not None else QtCore.Qt.NoPen)
		p.setBrush(brush if brush is not None else QtCore.Qt.NoBrush)
		p.drawRect(self.mapping.rect_to_view(xmin, ymin, xmax, ymax))

	def draw_font_line(self, p, x0, y0, x1, y1, pen=None):
		p.setPen(pen if pen is not None else cosmetic_pen(self.colors['frame']))
		p.drawLine(self.mapping.to_view(x0, y0), self.mapping.to_view(x1, y1))

	def draw_label(self, p, view_point, text, align='BL', color=None, background=None, offset=6., point_size=None):
		'''Small text label with a translucent, theme-aware background.
		Args:
			view_point (QPointF): anchor in view px
			align (str): which corner/edge of the label sits at the anchor:
				'TL' 'TM' 'TR' 'LM' 'C' 'RM' 'BL' 'BM' 'BR' (offset pushes it away)
		'''
		text = str(text)
		font = QtGui.QFont(qv(QtGui.QApplication, 'font'))
		size = point_size if point_size is not None else max(7., font.pointSizeF() - 1.)
		font.setPointSizeF(size)
		p.save()
		p.setFont(font)
		fm = QtGui.QFontMetricsF(font)
		lines = text.split('\n')
		w = max(fm.width(line) if hasattr(fm, 'width') else fm.horizontalAdvance(line) for line in lines) + 8.
		h = fm.height() * len(lines) + 4.

		x, y = view_point.x(), view_point.y()
		code = align.upper()
		if code in ('TL', 'LM', 'BL'): x += offset
		elif code in ('TR', 'RM', 'BR'): x -= w + offset
		else: x -= w * .5
		if code in ('TL', 'TM', 'TR'): y += offset
		elif code in ('BL', 'BM', 'BR'): y -= h + offset
		else: y -= h * .5

		rect = QtCore.QRectF(x, y, w, h)
		p.setPen(QtCore.Qt.NoPen)
		p.setBrush(QtGui.QBrush(background if background is not None else self.colors['label_bg']))
		p.drawRoundedRect(rect, 3., 3.)
		p.setPen(QtGui.QPen(color if color is not None else self.colors['text']))
		flags = QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter
		try:
			flags = int(flags)
		except TypeError:
			pass
		p.drawText(rect.adjusted(4., 2., -4., -2.), flags, text)
		p.restore()
		return rect

	def draw_view_marker(self, p, view_point, radius=5., pen=None, cross=True):
		'''Circle (with optional crosshair) at a view point; size in screen px.'''
		p.setPen(pen if pen is not None else cosmetic_pen(self.colors['active'], 1.5))
		p.setBrush(QtCore.Qt.NoBrush)
		p.drawEllipse(view_point, radius, radius)
		if cross:
			x, y = view_point.x(), view_point.y()
			r = radius * 1.8
			p.drawLine(QtCore.QPointF(x - r, y), QtCore.QPointF(x + r, y))
			p.drawLine(QtCore.QPointF(x, y - r), QtCore.QPointF(x, y + r))

	core_layer_to_path = staticmethod(core_layer_to_path)
	fl_layer_to_path = staticmethod(fl_layer_to_path)

	# - Handles: layout, paint, mask ----
	def _layout(self, mapping):
		'''[(handle, (vx, vy))] for every handle whose anchor resolves.'''
		out = []
		if mapping is None: return out
		for h in self.handles:
			try:
				a = h.anchor(mapping)
			except Exception:
				_log.exception('{}.handle[{}].anchor'.format(self.NAME, h.key))
				continue
			if a is None: continue
			out.append((h, pt(a) if not isinstance(a, tuple) else a))
		return out

	def _pick(self, view_point, mapping=None):
		mapping = mapping or self.mapping
		layout = [(h, a) for h, a in self._layout(mapping) if h.enabled]
		items = [(h.shape, a[0], a[1], h.radius) for h, a in layout]
		idx = om.pick_handle(items, view_point.x(), view_point.y(), self.HIT_TOLERANCE_PX)
		return layout[idx][0] if idx >= 0 else None

	def _handle_colors(self, h):
		if not h.enabled or h.role == 'muted':
			fill = self.colors['muted']
		elif h.role == 'secondary':
			fill = self.colors['frame']
		else:
			fill = self.colors['active']

		fill = QtGui.QColor(fill)
		if h is self.drag_handle or h is self.hover_handle:
			fill = fill.lighter(135)
		return fill

	def _paint_handles(self, p, mapping):
		for h, (x, y) in self._layout(mapping):
			hot = h is self.hover_handle or h is self.drag_handle
			r = h.radius + (1.5 if hot else 0.)
			p.setPen(cosmetic_pen(self.colors['outline'], 1.5 if hot else 1.))
			p.setBrush(QtGui.QBrush(self._handle_colors(h)))

			if h.shape == om.SHAPE_CIRCLE:
				p.drawEllipse(QtCore.QPointF(x, y), r, r)
			elif h.shape == om.SHAPE_DIAMOND:
				diamond = QtGui.QPainterPath()
				diamond.moveTo(x, y - r)
				diamond.lineTo(x + r, y)
				diamond.lineTo(x, y + r)
				diamond.lineTo(x - r, y)
				diamond.closeSubpath()
				p.drawPath(diamond)
			else:
				hw, hh = om.shape_half_extents(h.shape, r)
				rect = QtCore.QRectF(x - hw, y - hh, 2 * hw, 2 * hh)
				if h.shape == om.SHAPE_SQUARE: p.drawRect(rect)
				else: p.drawRoundedRect(rect, min(hw, hh), min(hw, hh))

		if self.hover_handle is not None and self.drag is None and self.hover_handle.tooltip:
			for h, (x, y) in self._layout(mapping):
				if h is self.hover_handle:
					self.draw_label(p, QtCore.QPointF(x + h.radius, y - h.radius), h.tooltip, 'BL', offset=4.)
					break

	def _mask_rects(self, mapping):
		rects = []
		for h, (x, y) in self._layout(mapping):
			if not h.enabled: continue
			x0, y0, x1, y1 = om.shape_hit_rect(h.shape, x, y, h.radius + 1.5, self.HIT_TOLERANCE_PX, self.MASK_PAD_PX)
			rects.append((int(x0) - 1, int(y0) - 1, int(x1 - x0) + 3, int(y1 - y0) + 3))
		return tuple(rects)

	def _update_mask(self, mapping, force=False):
		'''Mask the input layer to the enabled handles. No handles: transparent.
		During a drag the mask is cleared so the whole layer captures.'''
		if self.drag is not None:
			if self._mask_sig != 'drag':
				self._input.clearMask()
				self._input.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
				self._mask_sig = 'drag'
			return

		rects = self._mask_rects(mapping)
		if rects == self._mask_sig and not force: return
		self._mask_sig = rects

		if not rects:
			self._input.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
			self._input.clearMask()
			return

		region = QtGui.QRegion()
		for x, y, w, h in rects:
			region = region.united(QtGui.QRegion(x, y, w, h))
		self._input.setMask(region)
		self._input.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

	# - Mouse ---------------------------
	def _dispatch(self, kind, e):
		try:
			getattr(self, '_on_' + kind)(e)
		except Exception:
			_log.exception('{}.mouse.{}'.format(self.NAME, kind))
			if kind == 'press': self._abort_drag()

	def _set_hover(self, handle):
		if handle is self.hover_handle: return
		self.hover_handle = handle
		if handle is not None:
			self.last_handle = handle
			self._input.setCursor(QtGui.QCursor(handle.cursor_shape()))
		else:
			self._input.unsetCursor()
		self._set_key_capture(handle is not None or self.drag is not None)
		self.update()

	def _on_press(self, e):
		if e.button() != QtCore.Qt.LeftButton or self.mapping is None:
			e.ignore()
			return

		pos = ev_pos(e)
		handle = self._pick(pos)
		if handle is None:
			e.ignore()
			return

		e.accept()
		self.drag = Drag(pos, self.mapping.to_font(pos), modifiers_set(e.modifiers()), handle.axis)
		self.drag_handle = handle
		self.last_handle = handle
		self._update_mask(self.mapping)
		self._input.grabMouse()
		self._set_key_capture(True)
		self.update()

	def _on_move(self, e):
		pos = ev_pos(e)

		if self.drag is None:
			if self.mapping is not None:
				self._set_hover(self._pick(pos))
			return

		e.accept()
		drag = self.drag
		drag._update(pos, self.mapping, modifiers_set(e.modifiers()))

		if not drag.started:
			dvx = pos.x() - drag.press_view.x()
			dvy = pos.y() - drag.press_view.y()
			if dvx*dvx + dvy*dvy < self.DRAG_THRESHOLD_PX**2: return
			drag.started = True
			self._safe_hook('on_drag_start', self.drag_handle, drag)

		self._safe_hook('on_drag_move', self.drag_handle, drag)
		self.update()

	def _on_release(self, e):
		if self.drag is None or e.button() != QtCore.Qt.LeftButton:
			e.ignore()
			return

		e.accept()
		drag, handle = self.drag, self.drag_handle
		if self.mapping is not None:
			drag._update(ev_pos(e), self.mapping, modifiers_set(e.modifiers()))
		self._end_drag_state()

		if drag.started:
			self._safe_hook('on_drag_end', handle, drag)
		else:
			self._safe_hook('on_handle_click', handle, drag)

		self.request_repaint()
		self.update()

	def _on_double(self, e):
		if e.button() != QtCore.Qt.LeftButton or self.mapping is None:
			e.ignore()
			return
		handle = self._pick(ev_pos(e))
		if handle is None:
			e.ignore()
			return
		e.accept()
		self._safe_hook('on_handle_reset', handle)
		self.request_repaint()

	def _on_leave(self, e):
		if self.drag is None:
			self._set_hover(None)

	def _end_drag_state(self):
		self.drag = None
		self.drag_handle = None
		try:
			self._input.releaseMouse()
		except Exception:
			pass
		self._update_mask(self.mapping, force=True)
		self._set_key_capture(self.hover_handle is not None)

	def _cancel_drag(self):
		'''Esc / lost release: notify the subclass and restore state.'''
		if self.drag is None: return
		drag, handle = self.drag, self.drag_handle
		self._end_drag_state()
		if drag.started:
			self._safe_hook('on_drag_cancel', handle, drag)
		self.request_repaint()
		self.update()

	def _abort_drag(self):
		'''Drop a drag without hooks (teardown, retarget, errors).'''
		if self.drag is None: return
		self.drag = None
		self.drag_handle = None
		try:
			self._input.releaseMouse()
		except Exception:
			pass
		# Unmasked input layer would swallow every click: go transparent until relayout
		self._input.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
		self._mask_sig = None
		self._repaint_requested = True

	# - Keyboard ------------------------
	def _set_key_capture(self, on):
		'''While hovering a handle or dragging, also filter the focused widget so
		arrows/Esc are seen even when focus is not on the viewport itself.'''
		if on == self._key_capture: return
		self._key_capture = on
		if on:
			# Only when the canvas (or one of its ancestors) has focus: never
			# steal arrows from a panel's text field the user is typing in.
			fw = qv(QtGui.QApplication, 'focusWidget')
			if fw is not None and fw is not self.viewport and self._is_viewport_ancestor(fw):
				self._install_filter(fw)
		else:
			for obj in list(self._filtered):
				if obj is not self.viewport:
					self._remove_filter(obj)

	def _is_viewport_ancestor(self, widget):
		w = qv(self.viewport, 'parentWidget') if self.viewport is not None else None
		while w is not None:
			if w is widget: return True
			w = qv(w, 'parentWidget')
		return False

	def _filter_event(self, obj, ev):
		t = ev.type()

		if obj is self.viewport:
			if t in (QtCore.QEvent.Wheel, QtCore.QEvent.Resize):
				self.request_repaint()
				return False
			if t == QtCore.QEvent.Hide:
				self._orphan()
				return False

		if t not in (QtCore.QEvent.KeyPress, QtCore.QEvent.ShortcutOverride):
			return False

		key = ev.key()
		mods = modifiers_set(ev.modifiers())
		dragging = self.drag is not None

		if key == QtCore.Qt.Key_Escape:
			ours = dragging
		elif key in self._ARROWS:
			ours = dragging or (self.hover_handle is not None and self.last_handle is not None)
		else:
			ours = False

		if t == QtCore.QEvent.ShortcutOverride:
			# Claim the key from FontLab's shortcuts so the KeyPress reaches us
			if ours or self._safe_hook('wants_key', key, mods):
				ev.accept()
				return True
			return False

		if ours:
			if key == QtCore.Qt.Key_Escape:
				self._cancel_drag()
			elif self.drag is None:
				dx, dy = self._ARROWS[key]
				big = 'shift' in mods
				step = self.NUDGE_BIG if big else self.NUDGE_STEP
				self._safe_hook('on_nudge', self.last_handle, dx * step, dy * step, big)
				self.request_repaint()
			# Arrows during a drag are swallowed so FontLab does not nudge nodes
			return True

		return bool(self._safe_hook('on_key_press', key, mods))

# - Demo --------------------------------
class _DemoOverlay(CanvasOverlay):
	'''Acceptance demo: metrics box, outline bbox, 500-unit origin cross,
	one draggable handle on the bbox's top-right corner; prints the drag delta.'''
	NAME = 'demo'

	def __init__(self):
		CanvasOverlay.__init__(self)
		self.bbox = None			# (xmin, ymin, xmax, ymax) font units
		self.geometry_events = 0
		self.handles = [Handle('corner', self._corner_anchor, om.SHAPE_SQUARE, 6., om.AXIS_XY,
							   tooltip='drag: delta in font units (Shift: fine)')]

	def _corner_anchor(self, mapping):
		if self.bbox is None: return None
		return mapping.to_view(self.bbox[2], self.bbox[3])

	def _refresh_bbox(self, mapping):
		gi = self.glyph_info
		if gi is None or mapping is None:
			self.bbox = None
			return
		self.bbox = mapping.canvas_rect_to_font(qv(gi, 'shapesBoundingBoxOnCanvas'))

	def on_attach(self):
		print('Demo overlay: attached. DPR = {}'.format(qv(self.viewport, 'devicePixelRatioF') if self.viewport is not None else '?'))

	def on_target_changed(self, mapping):
		self._refresh_bbox(mapping)
		print('Demo overlay: target -> {} / {}'.format(self._sig_target[1], self._sig_target[2]))

	def on_view_changed(self, mapping):
		self._refresh_bbox(mapping)

	def on_geometry_changed(self):
		self.geometry_events += 1
		self._refresh_bbox(self.mapping)
		print('Demo overlay: on_geometry_changed #{}'.format(self.geometry_events))

	def on_drag_end(self, handle, drag):
		dx, dy = drag.delta_font
		fx, fy = drag.fine_delta_font()
		print('Demo overlay: drag {} delta font = ({:.2f}, {:.2f}); fine = ({:.2f}, {:.2f}); view px = ({:.1f}, {:.1f}); px/unit = {:.4f}'.format(
			handle.key, dx, dy, fx, fy, drag.delta_view[0], drag.delta_view[1], self.mapping.px_per_unit))

	def on_drag_cancel(self, handle, drag):
		print('Demo overlay: drag cancelled')

	def on_handle_click(self, handle, drag):
		print('Demo overlay: click on {}'.format(handle.key))

	def on_handle_reset(self, handle):
		print('Demo overlay: reset {}'.format(handle.key))

	def on_nudge(self, handle, dx, dy, big):
		print('Demo overlay: nudge {} by ({}, {}){}'.format(handle.key, dx, dy, ' big' if big else ''))

	def paint_overlay(self, p, mapping):
		c = self.colors

		# - Other glyphs (text mode): muted frames, no handles
		for gi in glyph_infos(self.canvas):
			if qv(gi, 'isActive'): continue
			p.setPen(cosmetic_pen(c['muted'], 1., QtCore.Qt.DotLine))
			p.setBrush(QtCore.Qt.NoBrush)
			p.drawRect(mapping.canvas_rect_to_view(qv(gi, 'metricsRectOnCanvas')))

		# - Metrics box
		gi = self.glyph_info
		p.setPen(cosmetic_pen(c['frame'], 1.))
		p.setBrush(QtCore.Qt.NoBrush)
		p.drawRect(mapping.canvas_rect_to_view(qv(gi, 'metricsRectOnCanvas')))

		# - Outline bbox
		if self.bbox is not None:
			self.draw_font_rect(p, *self.bbox, pen=cosmetic_pen(c['active'], 1.5, QtCore.Qt.DashLine))

		# - Origin cross: 500 units along +X and +Y
		amber = cosmetic_pen(c['stem'], 2.)
		self.draw_font_line(p, 0, 0, 500, 0, amber)
		self.draw_font_line(p, 0, 0, 0, 500, amber)
		self.draw_view_marker(p, mapping.to_view(0, 0), 4., cosmetic_pen(c['stem'], 1.5))
		self.draw_label(p, mapping.to_view(500, 0), '+X 500', 'LM', color=c['stem'])
		self.draw_label(p, mapping.to_view(0, 500), '+Y 500', 'BM', color=c['stem'])

		# - Drag feedback
		if self.drag is not None and self.drag.started:
			pen = cosmetic_pen(c['active'], 1., QtCore.Qt.DashLine)
			p.setPen(pen)
			p.drawLine(self.drag.press_view, self.drag.cur_view)
			dx, dy = self.drag.delta_font
			self.draw_label(p, self.drag.cur_view, 'dx {:.1f}  dy {:.1f}'.format(dx, dy), 'BL')

		self.draw_label(p, QtCore.QPointF(8., 8.), 'TR overlay demo  |  {}  |  {:.3f} px/u'.format(
			self._sig_target[1] if self._sig_target else '-', mapping.px_per_unit), 'TL', offset=0.)

def _demo():
	'''Toggle the demo overlay.'''
	return _DemoOverlay.toggle()

# - Manual tests ------------------------
def _count_overlay_widgets():
	n = 0
	for w in QtGui.QApplication.allWidgets():
		try:
			if str(qv(w, 'objectName')).startswith(OBJECT_NAME_PREFIX): n += 1
		except Exception:
			pass
	return n

def _stress_toggle(n=50):
	'''Toggle the demo n times, then (after the event loop has run the deferred
	deletes) report leftover overlay widgets and registry entries.'''
	before = _count_overlay_widgets() if _DemoOverlay.NAME not in _REGISTRY else None
	for _ in range(n):
		_DemoOverlay.toggle()
	running = _DemoOverlay.NAME in _REGISTRY

	def report():
		left = _count_overlay_widgets()
		expected = 2 if running else 0
		ok = left == expected
		print('Stress toggle x{}: overlay widgets alive = {} (expected {}), registry = {} -> {}'.format(
			n, left, expected, sorted(_REGISTRY.keys()), 'PASS' if ok else 'FAIL'))

	_single_shot(500, report)
	return before

_PENDING = []

def _single_shot(ms, fn):
	timer = QtCore.QTimer()
	timer.setSingleShot(True)

	def fire():
		try:
			fn()
		finally:
			if timer in _PENDING: _PENDING.remove(timer)

	timer.timeout.connect(fire)
	_PENDING.append(timer)
	timer.start(ms)

_CHECKLIST_STEPS = [
	('A1', 'Run canvas_overlay._demo(). Zoom, pan, resize the window and use split view: the cyan metrics box, magenta dashed bbox, amber 500-unit cross and the corner handle stay locked to the glyph.'),
	('A2', 'Switch glyphs, layers (masters) and glyph windows/canvases: the overlay re-targets automatically (console prints "target ->").'),
	('A3', 'At several zoom levels drag the corner handle exactly 100 units right and 100 up (watch the label). Release: the console prints delta (100 +/- 1, 100 +/- 1) with right = +X, up = +Y.'),
	('A4', 'Outside the handle: select nodes, drag a marquee, use the pen tool - FontLab works normally. Dragging the handle never starts a FontLab marquee or moves nodes underneath. Esc during a handle drag prints "drag cancelled".'),
	('A5', 'Run canvas_overlay._stress_toggle(50). After ~0.5 s it prints PASS; the console stays clean of errors.'),
	('A6', 'With the demo running, move a node with FontLab\'s own tools: the console prints "on_geometry_changed" within one tick.'),
]

class _Checklist(object):
	def __init__(self, steps):
		self.steps = steps
		self.index = 0
		self.results = []

	def show(self):
		if self.index >= len(self.steps):
			self.summary()
			return
		key, text = self.steps[self.index]
		print('\n[{}/{}] {}: {}'.format(self.index + 1, len(self.steps), key, text))
		print('    record with: canvas_overlay.check(True|False, "note")')

	def record(self, passed, note=''):
		if self.index >= len(self.steps):
			print('Checklist complete.')
			return
		key = self.steps[self.index][0]
		self.results.append((key, bool(passed), note))
		print('    {} {}{}'.format(key, 'PASS' if passed else 'FAIL', ' - ' + note if note else ''))
		self.index += 1
		self.show()

	def summary(self):
		print('\nCanvas overlay manual checklist:')
		for key, passed, note in self.results:
			print('  {}  {}{}'.format(key, 'PASS' if passed else 'FAIL', '  ' + note if note else ''))
		failed = [k for k, ok, _ in self.results if not ok]
		print('  => {}'.format('ALL PASSED' if not failed else 'FAILED: ' + ', '.join(failed)))

_CHECKLIST = []

def _manual_checklist():
	'''Print the acceptance steps one at a time; record each with check().'''
	del _CHECKLIST[:]
	_CHECKLIST.append(_Checklist(_CHECKLIST_STEPS))
	print('Canvas overlay v{} - manual acceptance checklist ({} steps)'.format(__version__, len(_CHECKLIST_STEPS)))
	_CHECKLIST[0].show()

def check(passed=True, note=''):
	'''Record the result of the current checklist step and show the next one.'''
	if not _CHECKLIST:
		print('No checklist running: call canvas_overlay._manual_checklist() first.')
		return
	_CHECKLIST[0].record(passed, note)
