# MODULE: TypeRig / Proxy / FontLab / Devtools / Canvas
# -----------------------------------------------------------
# Glyph canvas: font <-> viewport mapping, synthetic mouse and
# key input, opening a glyph window.
#
# FontLab ignores the position carried by a QMouseEvent and
# reads the real cursor (QCursor::pos), so every event first
# moves the real pointer with QCursor.setPos. Events go to the
# widget under the pointer (FontLab's viewport, or a TypeRig
# overlay input layer), and all events of one press..release
# go to the widget that got the press, like a Qt mouse grab.
# Modifiers given to click/drag reach FontLab (Shift-drag gives
# its 45 degree constraint). FontLab snapping stays active.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only
#
# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import absolute_import, print_function

from PythonQt import QtCore, QtGui

from typerig.proxy.fl.gui import canvas_overlay as co
from typerig.proxy.fl.devtools.app import qv, app, pump, wait, action

# - Init --------------------------------
__version__ = '0.1.0'

_NO_CANVAS = 'No active glyph canvas; call devtools.open_glyph()'

_BUTTONS = {'left': 'LeftButton', 'right': 'RightButton', 'middle': 'MiddleButton'}
_MODS = {'shift': 'ShiftModifier', 'ctrl': 'ControlModifier', 'alt': 'AltModifier', 'meta': 'MetaModifier'}

# - Mapping -----------------------------
def viewport():
	'''(viewport QWidget, flCanvas) of the active glyph canvas, or (None, None).'''
	return co.find_active_viewport()

def mapping():
	'''Fresh font-units <-> viewport-px mapping (canvas_overlay.ViewMapping)
	for the active glyph. Rebuild after zoom, pan or glyph change.'''
	vp, c = co.find_active_viewport()
	if vp is None: raise RuntimeError(_NO_CANVAS)
	gi = co.active_glyph_info(c)
	if gi is None: raise RuntimeError('No active glyph on the canvas')
	m = co.ViewMapping.build(c, gi)
	if m is None: raise RuntimeError('Degenerate glyph transform')
	return m

def to_px(x, y):
	'''Font units -> viewport px (floats).'''
	return mapping().to_view_xy(x, y)

def to_font(px, py):
	'''Viewport px -> font units (floats).'''
	return co.pt(mapping().to_font(QtCore.QPointF(px, py)))

# - Input -------------------------------
def _button(name):
	return getattr(QtCore.Qt, _BUTTONS[name]) if name else QtCore.Qt.NoButton

def _modifiers(mods):
	'''None | 'shift' | 'shift+alt' | ['shift', 'alt'] -> Qt.KeyboardModifiers'''
	if not mods: return QtCore.Qt.NoModifier
	if isinstance(mods, str): mods = mods.replace(' ', '').split('+')
	flag = None
	for m in mods:
		f = getattr(QtCore.Qt, _MODS[m.lower()])
		flag = f if flag is None else flag | f
	return flag

class Pointer(object):
	'''One mouse gesture on the active canvas. Coordinates are font units,
	or viewport px with px=True. restore=True puts the real cursor back
	when done().'''
	_TYPES = None

	def __init__(self, px=False, restore=True):
		self.vp, self.c = viewport()
		if self.vp is None: raise RuntimeError(_NO_CANVAS)
		self.m = None if px else mapping()
		self.home = QtGui.QCursor.pos() if restore else None
		self.grab = None
		self.log = []

		if Pointer._TYPES is None:
			E = QtCore.QEvent
			Pointer._TYPES = {'move': E.MouseMove, 'press': E.MouseButtonPress,
							  'release': E.MouseButtonRelease, 'double': E.MouseButtonDblClick}

	def _place(self, x, y):
		vx, vy = (x, y) if self.m is None else self.m.to_view_xy(x, y)
		g = self.vp.mapToGlobal(QtCore.QPoint(int(round(vx)), int(round(vy))))
		QtGui.QCursor.setPos(g)
		pump()
		w = self.grab or app().widgetAt(g) or self.vp
		return w, QtCore.QPointF(w.mapFromGlobal(g)), QtCore.QPointF(g)

	def send(self, kind, x, y, button=None, held=None, mods=None):
		'''kind: 'move' | 'press' | 'release' | 'double'. held: button held during a move.'''
		w, lp, gp = self._place(x, y)
		ev = QtGui.QMouseEvent(self._TYPES[kind], lp, gp, _button(button), _button(held), _modifiers(mods))
		app().sendEvent(w, ev)
		pump()
		if kind == 'press': self.grab = w
		if kind == 'release': self.grab = None
		self.log.append((kind, str(qv(w, 'objectName')) or type(w).__name__))
		return w

	def done(self):
		'''Restore the cursor; return [(event kind, receiving widget)].'''
		if self.home is not None:
			QtGui.QCursor.setPos(self.home)
			pump()
		return self.log

def hover(x, y, px=False):
	'''Move the pointer to (x, y) and leave it there.'''
	p = Pointer(px, restore=False)
	p.send('move', x, y)
	return p.done()

def click(x, y, mods=None, button='left', double=False, px=False):
	'''Click at (x, y), font units (viewport px with px=True).'''
	p = Pointer(px)
	p.send('move', x, y, mods=mods)
	p.send('press', x, y, button, button, mods)
	p.send('release', x, y, button, None, mods)
	if double:
		p.send('double', x, y, button, button, mods)
		p.send('release', x, y, button, None, mods)
	return p.done()

def drag(start, end, steps=10, mods=None, button='left', px=False, hold_ms=0):
	'''Press at start, move in `steps` straight steps, release at end.
	start, end: (x, y) in font units (viewport px with px=True).
	hold_ms: pause before release, for overlay ticks or FontLab live preview.'''
	(x0, y0), (x1, y1) = start, end
	p = Pointer(px)
	p.send('move', x0, y0, mods=mods)
	p.send('press', x0, y0, button, button, mods)
	for k in range(1, steps + 1):
		t = float(k) / steps
		p.send('move', x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, None, button, mods)
	if hold_ms: wait(hold_ms)
	p.send('release', x1, y1, button, None, mods)
	return p.done()

def key(name, mods=None, target=None):
	'''Press and release a key on target, the focused widget or the canvas.
	name: Qt key suffix, e.g. 'Left', 'Delete', 'Escape', 'A'.'''
	k = getattr(QtCore.Qt, 'Key_' + name)
	w = target or app().focusWidget() or viewport()[0]
	for t in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
		app().sendEvent(w, QtGui.QKeyEvent(t, k, _modifiers(mods)))
		pump()
	return type(w).__name__

# - Glyph window ------------------------
def current():
	'''(glyph name, layer name) of the current glyph.'''
	from typerig.proxy.fl.objects.glyph import pGlyph
	g = pGlyph()
	return (g.name, g.layer().name)

def open_glyph(name=None):
	'''Make glyph `name` current (if given) and make sure a glyph window
	shows it. Returns current() or None.'''
	if name is not None:
		import fontpr		# FontLab's own tool module
		fontpr.set_active_glyph(glyph_name=name)
		pump(3)
	if viewport()[0] is None:
		action('actionEdit_Glyphs')
		wait(150)
	return None if viewport()[0] is None else current()

def glyph_box():
	'''Metrics box of the current glyph layer, font units: (0, descender, advance, ascender).'''
	from typerig.proxy.fl.objects.glyph import pGlyph
	from typerig.proxy.fl.objects.font import pFont
	g = pGlyph()
	layer_name = g.layer().name
	try:
		fm = pFont().fontMetrics()
		asc, desc = fm.getAscender(layer_name), fm.getDescender(layer_name)
	except Exception:
		asc, desc = 800, -200
	return (0, desc, g.getAdvance(), asc)
