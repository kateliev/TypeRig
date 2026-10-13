# MODULE: TypeRig / Proxy / FontLab / GUI / Canvas Overlay - tests
# -----------------------------------------------------------
# Headless tests for canvas_overlay.py and overlay_math.py - no
# FontLab needed. PythonQt is stood in for by PyQt5 (QtGui gets
# QtWidgets merged in, as in PythonQt) and fontlab by a fake
# workspace/canvas that uses the transforms measured in FontLab 8.
#   cd Lib/typerig/proxy/fl/gui && python -m pytest test_canvas_overlay.py
# (or just `python test_canvas_overlay.py` to run the asserts directly)
#
# Without PyQt5 only the overlay_math tests run; the rest skip.
# These tests cannot prove FontLab-side behaviour (event routing to
# the real canvas, shortcuts, HiDPI): see canvas_overlay._manual_checklist().
# -----------------------------------------------------------

from __future__ import absolute_import, print_function, division

import os
import sys
import time
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

_LIB = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
if _LIB not in sys.path:
	sys.path.insert(0, _LIB)

from typerig.proxy.fl.gui import overlay_math as om

# - Environment --------------------------
_ENV = {}

class SkipTest(Exception):
	pass

def _skip(reason):
	if __name__ == '__main__':
		raise SkipTest(reason)
	try:
		import pytest
	except ImportError:
		raise SkipTest(reason)
	pytest.skip(reason)

# Names FontLab 8's PythonQt build does not expose (QObject verified missing;
# the others unverified, so the overlay must not depend on them either)
PYTHONQT_MISSING = ('QObject', 'QEvent', 'QFontMetrics', 'QFontMetricsF')

def _install_fakes(QtCore, QtGui, QtWidgets):
	'''Fake PythonQt (QtGui = QtGui + QtWidgets, minus PYTHONQT_MISSING) and fontlab modules.'''
	qtcore = types.ModuleType('PythonQt.QtCore')
	qtgui = types.ModuleType('PythonQt.QtGui')
	for target, mods in ((qtcore, (QtCore,)), (qtgui, (QtGui, QtWidgets))):
		for mod in mods:
			for k in dir(mod):
				if not k.startswith('_') and k not in PYTHONQT_MISSING:
					setattr(target, k, getattr(mod, k))
	pythonqt = types.ModuleType('PythonQt')
	pythonqt.QtCore = qtcore
	pythonqt.QtGui = qtgui
	sys.modules['PythonQt'] = pythonqt
	sys.modules['PythonQt.QtCore'] = qtcore
	sys.modules['PythonQt.QtGui'] = qtgui

	ws = FakeWorkspace()
	fontlab = types.ModuleType('fontlab')

	class flWorkspace(object):
		@staticmethod
		def instance(): return ws

	fontlab.flWorkspace = flWorkspace
	sys.modules['fontlab'] = fontlab
	return ws

def _env():
	'''Lazily build the Qt app, fakes and imports; skip if PyQt5 is missing.'''
	if _ENV: return _ENV
	if 'fontlab' in sys.modules and not getattr(sys.modules['fontlab'], '_typerig_fake', False):
		_skip('running inside FontLab: use canvas_overlay._manual_checklist()')
	try:
		from PyQt5 import QtCore, QtGui, QtWidgets
	except ImportError:
		_skip('PyQt5 not installed')

	global _QC, _QG, _QW
	_QC, _QG, _QW = QtCore, QtGui, QtWidgets

	ws = _install_fakes(QtCore, QtGui, QtWidgets)
	sys.modules['fontlab']._typerig_fake = True
	app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([sys.argv[0]])

	from typerig.proxy.fl.gui import canvas_overlay as co
	_ENV.update(app=app, ws=ws, co=co)
	return _ENV

# - Fake FontLab -------------------------
# Measured on FontLab 8 (see canvas_overlay_handout.md section 1)
GLYPH_TRANSFORM = (0.540625, 0., 0., -0.540625, 129.75, 700.65)
VIEW_SCALE = 1.088
VIEW_OFFSET = (404.6, 22.7)

class FakeContour(object):
	def __init__(self, x, y, w, h): self.rect = (x, y, w, h)
	def path(self):
		p = _QG.QPainterPath()
		p.addRect(_QC.QRectF(*self.rect))
		return p

class FakeLayer(object):
	'''H-like layer: two stems, ink bbox (50, 0) - (480, 700).'''
	def __init__(self, name='Regular'):
		self.name = name
		self.contours = [FakeContour(50, 0, 80, 700), FakeContour(400, 0, 80, 700)]
		self.shapes = []
	def nodesCount(self): return 4 * len(self.contours)
	def boundingBox(self):
		r = _QC.QRectF()
		for c in self.contours: r = r.united(_QC.QRectF(*c.rect))
		return r
	def getContours(self): return self.contours

class FakeGlyph(object):
	def __init__(self): self.activeLayer = FakeLayer()

class FakeGlyphInfo(object):
	def __init__(self, name='H', active=True):
		self.name = name
		self.glyph = FakeGlyph()
		self.transform = _QG.QTransform(*GLYPH_TRANSFORM)
		self.isActive = active
	@property
	def shapesBoundingBoxOnCanvas(self): return self.transform.mapRect(self.glyph.activeLayer.boundingBox())
	@property
	def metricsRectOnCanvas(self): return self.transform.mapRect(_QC.QRectF(0, -200, 530, 1000))

class FakeTextBlock(object):
	def __init__(self, infos): self.infos = infos
	def getGlyphsInLine(self, i): return self.infos if i == 0 else []

class FakeCanvas(object):
	'''canvas -> viewport is scale + offset, like FontLab's.'''
	def __init__(self, scale=VIEW_SCALE, offset=VIEW_OFFSET):
		self.scale = scale
		self.offset = offset
		self.gi = FakeGlyphInfo()
		self.others = []
	def textBlocks(self): return [FakeTextBlock([self.gi] + self.others)]
	def mapToViewportF(self, p): return _QC.QPointF(p.x()*self.scale + self.offset[0], p.y()*self.scale + self.offset[1])
	def mapFromViewport(self, p): return _QC.QPointF((p.x() - self.offset[0])/self.scale, (p.y() - self.offset[1])/self.scale)

class FakeWorkspace(object):
	def __init__(self):
		self.viewports = []			# [(widget, canvas)]
		self.active = None
	def getCanvasForViewport(self, w):
		for vp, c in self.viewports:
			if vp is w: return c
		return None
	def isActiveCanvas(self, c): return c is self.active
	def getActiveCanvas(self): return self.active

# - Session ------------------------------
class Session(object):
	'''One window + viewport + canvas and a running overlay; close() tears down.'''
	def __init__(self, overlay_cls=None, **kwargs):
		env = _env()
		self.app, self.ws, self.co = env['app'], env['ws'], env['co']
		self.errors = []
		self.printed = []
		self.co._log = om.LogOnce(interval=10., printer=self.errors.append)
		self.co.print = lambda *a, **k: self.printed.append(' '.join(str(x) for x in a))

		self.window = _QW.QWidget()
		self.window.resize(900, 700)
		self.viewport, self.canvas = self.add_viewport(0, 0, 900, 700)
		self.ws.active = self.canvas
		self.window.show()
		self.app.processEvents()

		cls = overlay_cls or _recorder_class()
		self.ov = cls.start(**kwargs)
		self.tick()

	def add_viewport(self, x, y, w, h, scale=VIEW_SCALE, offset=VIEW_OFFSET):
		vp = _QW.QWidget(self.window)
		vp.setGeometry(x, y, w, h)
		vp.show()
		canvas = FakeCanvas(scale, offset)
		self.ws.viewports.append((vp, canvas))
		return vp, canvas

	def tick(self, n=1):
		for _ in range(n):
			self.ov._refind.reset()
			self.ov._tick()
			self.app.processEvents()

	def view(self, x, y):
		return self.ov.mapping.to_view(x, y)

	def mouse(self, kind, pos, buttons=None, mods=None):
		types_ = {'press': _QC.QEvent.MouseButtonPress, 'move': _QC.QEvent.MouseMove,
				  'release': _QC.QEvent.MouseButtonRelease, 'double': _QC.QEvent.MouseButtonDblClick}
		left = _QC.Qt.LeftButton
		if buttons is None:
			buttons = _QC.Qt.NoButton if kind == 'release' else left
		button = _QC.Qt.NoButton if kind == 'move' else left
		e = _QG.QMouseEvent(types_[kind], _QC.QPointF(pos), button, buttons, mods if mods is not None else _QC.Qt.NoModifier)
		_QW.QApplication.sendEvent(self.ov._input, e)

	def hover(self, pos):
		self.mouse('move', pos, buttons=_QC.Qt.NoButton)

	def drag(self, font_from, font_by, mods=None, steps=7, release=True):
		'''Press at a font point, move by a font-unit delta in steps, release.'''
		m = self.ov.mapping
		p0 = m.to_view(*font_from)
		p1 = m.to_view(font_from[0] + font_by[0], font_from[1] + font_by[1])
		self.mouse('press', p0, mods=mods)
		for i in range(1, steps + 1):
			self.mouse('move', p0 + (p1 - p0) * (i / steps), mods=mods)
		if release:
			self.mouse('release', p1, mods=mods)
		return p1

	def key(self, key, mods=None, kind='press', target=None):
		t = _QC.QEvent.KeyPress if kind == 'press' else _QC.QEvent.ShortcutOverride
		e = _QG.QKeyEvent(t, key, mods if mods is not None else _QC.Qt.NoModifier)
		return self.ov._filter.eventFilter(target if target is not None else self.viewport, e)

	def flush_deletes(self):
		_QW.QApplication.sendPostedEvents(None, _QC.QEvent.DeferredDelete)
		self.app.processEvents()

	def close(self):
		for name in list(self.co._REGISTRY):
			self.co._REGISTRY[name].__class__.stop()
		self.ws.viewports = []
		self.ws.active = None
		self.window.deleteLater()
		self.flush_deletes()

	def __enter__(self): return self
	def __exit__(self, *exc): self.close()

def session(overlay_cls=None, **kwargs):
	return Session(overlay_cls, **kwargs)

def _recorder_class():
	'''Build the recording overlay once the fake PythonQt is in place.'''
	co = _env()['co']
	if 'cls' in _ENV: return _ENV['cls']

	class _Recorder(co.CanvasOverlay):
		'''Records every hook call; handles: 'corner' (xy) at the ink bbox
		top-right, 'right' (x-only bar) at the right edge middle.'''
		NAME = 'test_recorder'

		def __init__(self):
			co.CanvasOverlay.__init__(self)
			self.events = []
			self.handles = [
				co.Handle('corner', lambda m: m.to_view(480, 700), om.SHAPE_SQUARE, 6., om.AXIS_XY, tooltip='corner'),
				co.Handle('right', lambda m: m.to_view(480, 350), om.SHAPE_BAR_V, 6., om.AXIS_X),
			]

		def names(self): return [e[0] for e in self.events]
		def last(self, name):
			for e in reversed(self.events):
				if e[0] == name: return e
			return None

		def on_attach(self): self.events.append(('attach',))
		def on_kill(self): self.events.append(('kill',))
		def on_target_changed(self, mapping): self.events.append(('target', self._sig_target[1:]))
		def on_view_changed(self, mapping): self.events.append(('view',))
		def on_geometry_changed(self): self.events.append(('geometry',))
		def on_drag_start(self, h, d): self.events.append(('start', h.key))
		def on_drag_move(self, h, d): self.events.append(('move', h.key, d.delta_font))
		def on_drag_end(self, h, d): self.events.append(('end', h.key, d.delta_font, d.fine_delta_font(), d.delta_view))
		def on_drag_cancel(self, h, d): self.events.append(('cancel', h.key))
		def on_handle_click(self, h, d): self.events.append(('click', h.key))
		def on_handle_reset(self, h): self.events.append(('reset', h.key))
		def on_nudge(self, h, dx, dy, big): self.events.append(('nudge', h.key, dx, dy, big))
		def on_key_press(self, key, mods):
			self.events.append(('key', key))
			return key == _QC.Qt.Key_F12		# consume F12 only
		def wants_key(self, key, mods): return key == _QC.Qt.Key_F12

	_ENV['cls'] = _Recorder
	return _Recorder

def _close(a, b, tol=1e-6):
	return abs(a - b) <= tol

def _close_pt(p, q, tol=1e-6):
	return _close(p[0], q[0], tol) and _close(p[1], q[1], tol)

# - overlay_math (pure) ------------------
def test_overlay_math_affine(): om._test_affine()
def test_overlay_math_drag(): om._test_drag()
def test_overlay_math_hit(): om._test_hit()
def test_overlay_math_contour_ops(): om._test_contour_ops()
def test_overlay_math_core_layer_ops(): om._test_core_layer_ops()
def test_overlay_math_runtime(): om._test_runtime()

# - Attach and mapping -------------------
def test_attach_and_mapping():
	with session(_recorder_class()) as s:
		ov = s.ov
		assert ov.parent() is s.viewport and ov._input.parent() is s.viewport
		assert ov.geometry() == s.viewport.rect() and ov._input.geometry() == s.viewport.rect()
		assert ov.testAttribute(_QC.Qt.WA_TransparentForMouseEvents)	# paint layer never takes input
		assert s.ov.names()[:3] == ['attach', 'target', 'view'], s.ov.names()

		m = ov.mapping
		assert m.ok and _close(m.px_per_unit, 0.540625 * VIEW_SCALE, 1e-9)
		# Explicit two-step chain agrees with the composed mapping
		for x, y in [(0, 0), (480, 700), (-123.4, 56.7)]:
			c = s.canvas.mapToViewportF(_QG.QTransform(*GLYPH_TRANSFORM).map(_QC.QPointF(x, y)))
			assert _close_pt(m.to_view_xy(x, y), (c.x(), c.y()), 1e-6)
			assert _close_pt(m.to_font(m.to_view(x, y)), (x, y), 1e-6)
		# Y flip: font up is screen up
		assert m.to_view(0, 100).y() < m.to_view(0, 0).y()
		assert not s.errors, s.errors

def test_mapping_fallback_matches_fast_path():
	with session(_recorder_class()) as s:
		co = s.co
		fast = co.ViewMapping.build(s.canvas, s.canvas.gi)
		slow = co.ViewMapping.build(s.canvas, s.canvas.gi)
		slow.ok = False
		for x, y in [(0, 0), (123.4, -56.7), (1000, 800)]:
			assert _close_pt(fast.to_view_xy(x, y), slow.to_view_xy(x, y))
			assert _close_pt(slow.to_font(slow.to_view(x, y)), (x, y))
		path = co.core_layer_to_path(_core_test_layer())
		a, b = fast.path_to_view(path), slow.path_to_view(path)
		assert a.elementCount() == b.elementCount()
		for i in range(a.elementCount()):
			ea, eb = a.elementAt(i), b.elementAt(i)
			assert ea.type == eb.type and _close_pt((ea.x, ea.y), (eb.x, eb.y))

def test_mapping_degenerate_transform_is_none():
	with session(_recorder_class()) as s:
		s.canvas.gi.transform = _QG.QTransform(0, 0, 0, 0, 1, 1)
		assert s.co.ViewMapping.build(s.canvas, s.canvas.gi) is None

# - Painting -----------------------------
def test_paint_all_handle_shapes_without_errors():
	with session(_recorder_class()) as s:
		co = s.co
		s.ov.handles += [co.Handle(shape, (lambda k: lambda m: m.to_view(100 * k, 100))(i), shape, role=role)
						 for i, (shape, role) in enumerate(zip(om.HANDLE_SHAPES, ['primary', 'secondary', 'muted', 'primary', 'secondary']))]
		s.ov.handles[-1].enabled = False
		s.hover(s.view(480, 700))				# hovered: tooltip label path
		s.ov.grab()
		s.drag((480, 700), (30, 30), release=False)	# dragging: drag colours
		s.ov.grab()
		s.mouse('release', s.view(510, 730))
		assert not s.errors, s.errors

def test_paint_skipped_without_active_glyph():
	with session(_recorder_class()) as s:
		s.canvas.gi.isActive = False
		s.tick()
		assert s.ov.glyph_info is None and s.ov.mapping is None
		s.ov.grab()
		assert not s.errors, s.errors

def test_demo_overlay_paints_and_reports_delta():
	with session(_env()['co']._DemoOverlay) as s:
		s.ov.grab()
		s.drag((480, 700), (100, -40))
		s.ov.grab()
		line = [l for l in s.printed if 'delta font' in l][-1]
		assert 'delta font = (100.00, -40.00)' in line, line
		assert not s.errors, s.errors

# - Mask ---------------------------------
def test_mask_covers_enabled_handles_only():
	with session(_recorder_class()) as s:
		mask = s.ov._input.mask()
		assert not s.ov._input.testAttribute(_QC.Qt.WA_TransparentForMouseEvents)
		assert mask.contains(s.view(480, 700).toPoint())
		assert mask.contains(s.view(480, 350).toPoint())
		assert not mask.contains(s.view(250, 350).toPoint())		# counter of the H
		assert not mask.contains(_QC.QPoint(5, 5))

		s.ov.handles[1].enabled = False
		s.ov.request_repaint(); s.tick()
		assert not s.ov._input.mask().contains(s.view(480, 350).toPoint())

def test_no_handles_makes_input_transparent():
	with session(_recorder_class()) as s:
		saved = s.ov.handles
		s.ov.handles = []
		s.ov.request_repaint(); s.tick()
		assert s.ov._input.testAttribute(_QC.Qt.WA_TransparentForMouseEvents)
		s.ov.handles = saved
		s.ov.request_repaint(); s.tick()
		assert not s.ov._input.testAttribute(_QC.Qt.WA_TransparentForMouseEvents)

def test_mask_follows_zoom_and_pan():
	with session(_recorder_class()) as s:
		s.canvas.scale = 2.5
		s.canvas.offset = (-300., -900.)
		s.tick()
		assert s.ov._input.mask().contains(s.view(480, 700).toPoint())

# - Drag protocol ------------------------
def test_drag_100_units_at_any_zoom():
	with session(_recorder_class()) as s:
		for scale in (0.37, VIEW_SCALE, 3.2):
			s.canvas.scale = scale
			s.tick()
			p0 = s.view(480, 700)
			s.drag((480, 700), (100, 100), release=False)
			assert s.ov.drag.started and s.ov._mask_sig == 'drag' and s.ov._input.mask().isEmpty()
			s.mouse('release', s.view(580, 800))
			end = s.ov.last('end')
			assert end[1] == 'corner' and _close_pt(end[2], (100., 100.), 1e-6), (scale, end)
			assert end[4][0] > 0 and end[4][1] < 0				# right and up on screen
			assert s.ov.drag is None and s.ov._input.mask().contains(p0.toPoint())
		assert s.ov.names().count('start') == 3 and s.ov.names().count('end') == 3

def test_drag_delta_is_from_press_not_accumulated():
	with session(_recorder_class()) as s:
		p0 = s.view(480, 700)
		s.mouse('press', p0)
		for dx, dy in [(40, -10), (-70, 33), (5, 5), (12, -20)]:
			s.mouse('move', s.view(480 + dx, 700 + dy))
		s.mouse('release', s.view(492, 680))
		assert _close_pt(s.ov.last('end')[2], (12., -20.))

def test_axis_constraint():
	with session(_recorder_class()) as s:
		s.drag((480, 350), (60, 200))
		end = s.ov.last('end')
		assert end[1] == 'right' and _close_pt(end[2], (60., 0.)), end

def test_shift_fine_mode():
	with session(_recorder_class()) as s:
		s.drag((480, 700), (100, -50), mods=_QC.Qt.ShiftModifier)
		end = s.ov.last('end')
		assert _close_pt(end[2], (100., -50.)) and _close_pt(end[3], (10., -5.)), end

def test_click_below_threshold_and_double_click_reset():
	with session(_recorder_class()) as s:
		p = s.view(480, 700)
		s.mouse('press', p)
		s.mouse('move', p + _QC.QPointF(1., 0.))			# under the 2 px threshold
		s.mouse('release', p)
		s.mouse('double', p)
		names = s.ov.names()
		assert 'click' in names and 'reset' in names and 'start' not in names and 'end' not in names, names

def test_press_outside_handles_is_ignored():
	with session(_recorder_class()) as s:
		e = _QG.QMouseEvent(_QC.QEvent.MouseButtonPress, _QC.QPointF(5, 5), _QC.Qt.LeftButton, _QC.Qt.LeftButton, _QC.Qt.NoModifier)
		_QW.QApplication.sendEvent(s.ov._input, e)
		assert not e.isAccepted() and s.ov.drag is None

def test_right_button_is_ignored():
	with session(_recorder_class()) as s:
		e = _QG.QMouseEvent(_QC.QEvent.MouseButtonPress, s.view(480, 700), _QC.Qt.RightButton, _QC.Qt.RightButton, _QC.Qt.NoModifier)
		_QW.QApplication.sendEvent(s.ov._input, e)
		assert not e.isAccepted() and s.ov.drag is None

def test_escape_cancels_drag():
	with session(_recorder_class()) as s:
		s.drag((480, 700), (50, 50), release=False)
		assert s.key(_QC.Qt.Key_Escape, kind='override')
		assert s.key(_QC.Qt.Key_Escape)
		assert s.ov.drag is None and s.ov.last('cancel') == ('cancel', 'corner')
		assert 'end' not in s.ov.names()
		assert not s.ov._input.mask().isEmpty()

def test_arrows_swallowed_during_drag():
	with session(_recorder_class()) as s:
		s.drag((480, 700), (50, 50), release=False)
		assert s.key(_QC.Qt.Key_Left)
		assert 'nudge' not in s.ov.names()
		s.mouse('release', s.view(530, 750))

# - Keyboard -----------------------------
def test_hover_nudge_and_key_passthrough():
	with session(_recorder_class()) as s:
		s.hover(s.view(480, 700))
		assert s.ov.hover_handle is not None and s.ov.hover_handle.key == 'corner'
		assert s.key(_QC.Qt.Key_Right, _QC.Qt.ShiftModifier, kind='override')
		assert s.key(_QC.Qt.Key_Up)
		assert s.key(_QC.Qt.Key_Left, _QC.Qt.ShiftModifier)
		nudges = [e for e in s.ov.events if e[0] == 'nudge']
		assert nudges == [('nudge', 'corner', 0., 1., False), ('nudge', 'corner', -10., 0., True)], nudges

		assert not s.key(_QC.Qt.Key_Escape)				# idle Esc goes to the subclass, not consumed
		assert not s.key(_QC.Qt.Key_A)
		assert s.key(_QC.Qt.Key_F12)						# subclass consumes F12
		assert s.key(_QC.Qt.Key_F12, kind='override')		# and claims it from shortcuts

		_QW.QApplication.sendEvent(s.ov._input, _QC.QEvent(_QC.QEvent.Leave))
		assert s.ov.hover_handle is None
		assert not s.key(_QC.Qt.Key_Up) and not s.key(_QC.Qt.Key_Up, kind='override')

def test_key_capture_never_filters_unrelated_focus_widget():
	with session(_recorder_class()) as s:
		panel = _QW.QLineEdit(s.window)
		panel.show(); panel.setFocus(); s.app.processEvents()
		s.hover(s.view(480, 700))
		assert not any(o is panel for o in s.ov._filtered)
		_QW.QApplication.sendEvent(s.ov._input, _QC.QEvent(_QC.QEvent.Leave))

# - Change detection ---------------------
def test_geometry_change_fires_within_one_tick():
	with session(_recorder_class()) as s:
		s.tick(3)
		assert 'geometry' not in s.ov.names()
		s.canvas.gi.glyph.activeLayer.contours[0].rect = (50, 0, 90, 700)
		s.tick()
		assert s.ov.names().count('geometry') == 1
		s.tick(3)
		assert s.ov.names().count('geometry') == 1

def test_target_change_on_layer_and_glyph():
	with session(_recorder_class()) as s:
		s.canvas.gi.glyph.activeLayer.name = 'Bold'; s.tick()
		s.canvas.gi.name = 'O'; s.tick()
		targets = [e[1] for e in s.ov.events if e[0] == 'target']
		assert targets == [('H', 'Regular'), ('H', 'Bold'), ('O', 'Bold')], targets
		assert 'geometry' not in s.ov.names()

def test_view_change_on_zoom_only():
	with session(_recorder_class()) as s:
		n = s.ov.names().count('view')
		s.tick(3)
		assert s.ov.names().count('view') == n
		s.canvas.scale = 2.
		s.tick()
		assert s.ov.names().count('view') == n + 1 and s.ov.names().count('target') == 1

def test_only_active_glyph_in_text_mode():
	with session(_recorder_class()) as s:
		other = FakeGlyphInfo('A', active=False)
		s.canvas.others = [other]
		s.canvas.gi.isActive = False
		other.isActive = True
		s.tick()
		assert str(s.ov.glyph_info.name) == 'A'
		assert s.ov.last('target')[1][0] == 'A'

# - Following canvases -------------------
def test_canvas_switch_retargets():
	with session(_recorder_class()) as s:
		vp2, cv2 = s.add_viewport(450, 0, 450, 700, 0.5, (10., 5.))
		s.ws.active = cv2
		s.tick()
		assert s.ov.parent() is vp2 and s.ov.geometry() == vp2.rect() and s.ov.isVisible()
		assert s.ov._filtered == [vp2]
		s.ws.active = s.canvas
		s.tick()
		assert s.ov.parent() is s.viewport and s.ov._filtered == [s.viewport]

def test_viewport_resize_syncs_geometry():
	with session(_recorder_class()) as s:
		s.viewport.resize(600, 400)
		s.tick()
		assert s.ov.geometry() == s.viewport.rect() and s.ov._input.geometry() == s.viewport.rect()

def test_hidden_viewport_orphans_then_rebinds():
	with session(_recorder_class()) as s:
		vp2, cv2 = s.add_viewport(450, 0, 450, 700)
		s.viewport.hide(); s.app.processEvents()
		assert s.ov.parent() is None and s.ov.viewport is None and not s.ov.isVisible()
		s.ws.active = cv2
		s.tick()
		assert s.ov.parent() is vp2 and s.ov.isVisible()
		# The hidden viewport can now be destroyed without taking the overlay along
		s.viewport.deleteLater(); s.flush_deletes()
		assert s.ov.qt_alive()

def test_retarget_during_drag_leaves_clicks_working():
	with session(_recorder_class()) as s:
		vp2, cv2 = s.add_viewport(450, 0, 450, 700)
		s.drag((480, 700), (30, 0), release=False)
		s.ws.active = cv2
		s.tick()
		assert s.ov.drag is None
		assert not s.ov._input.mask().isEmpty()			# masked again, not capturing everything

def test_no_canvas_waits_then_attaches():
	env = _env()
	co, ws = env['co'], env['ws']
	errors = []
	co._log = om.LogOnce(printer=errors.append)
	co.print = lambda *a, **k: None
	ws.viewports, ws.active = [], None
	win = None
	ov = _recorder_class().start()
	try:
		ov._refind.reset(); ov._tick()
		assert ov.viewport is None
		win = _QW.QWidget(); vp = _QW.QWidget(win); win.show()
		cv = FakeCanvas(); ws.viewports.append((vp, cv)); ws.active = cv
		ov._refind.reset(); ov._tick()
		assert ov.parent() is vp and not errors, errors
	finally:
		_recorder_class().stop()
		ws.viewports, ws.active = [], None
		if win is not None: win.deleteLater()
		_QW.QApplication.sendPostedEvents(None, _QC.QEvent.DeferredDelete)

# - Robustness ---------------------------
def test_exceptions_contained_and_rate_limited():
	co = _env()['co']

	class Boom(_recorder_class()):
		NAME = 'test_boom'
		def paint_overlay(self, p, mapping): raise RuntimeError('paint boom')
		def on_view_changed(self, mapping): raise RuntimeError('view boom')
		def on_drag_move(self, h, d): raise RuntimeError('move boom')

	with session(Boom) as s:
		for _ in range(3): s.ov.grab()
		s.drag((480, 700), (40, 40))
		assert sum('paint boom' in e for e in s.errors) == 1
		assert sum('view boom' in e for e in s.errors) == 1
		assert sum('move boom' in e for e in s.errors) == 1
		assert s.ov.last('end') is not None				# the drag still completed

def test_registry_never_stacks():
	with session(_recorder_class()) as s:
		cls = _recorder_class()
		first = s.ov
		second = cls.start()
		assert cls.instance() is second and not first.alive and 'kill' in first.names()
		s.ov = second

def test_toggle_50_times_leaves_nothing():
	with session(_recorder_class()) as s:
		cls = _recorder_class()
		cls.stop(); s.flush_deletes()
		assert s.co._count_overlay_widgets() == 0
		for _ in range(50): cls.toggle()
		s.flush_deletes()
		assert s.co._count_overlay_widgets() == 0 and cls.NAME not in s.co._REGISTRY
		for _ in range(51): cls.toggle()
		s.flush_deletes()
		assert s.co._count_overlay_widgets() == s.co.WIDGETS_PER_OVERLAY and cls.NAME in s.co._REGISTRY
		s.ov = cls.instance()
		cls.stop(); s.flush_deletes()
		assert s.co._count_overlay_widgets() == 0
		assert not [t for t in s.app.findChildren(_QC.QTimer) if t.isActive()]
		assert not s.errors, s.errors

def test_detach_and_reattach():
	with session(_recorder_class()) as s:
		s.ov.detach()
		assert not s.ov.isVisible() and not s.ov._timer.isActive() and not s.ov._filtered
		assert s.ov.attach()
		assert s.ov.isVisible() and s.ov._timer.isActive() and s.ov._filtered == [s.viewport]

# - Extension hooks ----------------------
def test_target_attribute():
	with session(_recorder_class()) as s:
		assert s.ov.target == ('H', 'Regular')
		s.canvas.gi.isActive = False
		s.tick()
		assert s.ov.target is None

def test_accept_geometry_hides_own_edits():
	with session(_recorder_class()) as s:
		s.canvas.gi.glyph.activeLayer.contours[0].rect = (50, 0, 95, 700)		# "tool" edit
		s.ov.fl_layer = s.canvas.gi.glyph.activeLayer
		s.ov.accept_geometry()
		s.tick()
		assert 'geometry' not in s.ov.names()
		s.canvas.gi.glyph.activeLayer.contours[1].rect = (390, 0, 90, 700)		# outside edit
		s.tick()
		assert s.ov.names().count('geometry') == 1

def test_on_tick_and_paint_handle_hooks():
	base = _recorder_class()

	class Custom(base):
		NAME = 'test_custom'
		def __init__(self):
			base.__init__(self)
			self.ticks = 0
			self.custom_painted = []
			self.handles[1].role = 'stem'				# colour role from self.colors
		def on_tick(self): self.ticks += 1
		def paint_handle(self, p, h, x, y, hot):
			if h.key == 'corner':
				self.custom_painted.append(h.key)
				return True
			if h.key == 'right': raise RuntimeError('handle boom')
			return False

	with session(Custom) as s:
		s.tick(3)
		assert s.ov.ticks >= 3
		assert s.ov._handle_colors(s.ov.handles[1]).name() == s.ov.colors['stem'].lighter(100).name()
		s.ov.grab()
		assert s.ov.custom_painted and set(s.ov.custom_painted) == {'corner'}
		assert sum('handle boom' in e for e in s.errors) == 1		# failed custom paint falls back, logged once
		s.errors[:] = []

# - Paths --------------------------------
def _core_test_layer():
	from typerig.core.objects.node import Node
	from typerig.core.objects.contour import Contour
	from typerig.core.objects.shape import Shape
	from typerig.core.objects.layer import Layer
	return Layer([Shape([Contour([Node(0, 0), Node(0, 100), Node(50, 150, type='curve'),
								  Node(100, 150, type='curve'), Node(100, 0)], closed=True)])])

def test_import_without_pythonqt_extras():
	co = _env()['co']
	pq = sys.modules['PythonQt']
	for name in PYTHONQT_MISSING:
		assert not hasattr(pq.QtCore, name) and not hasattr(pq.QtGui, name), name
	assert co.EV_KEY_PRESS == _QC.QEvent.KeyPress and co.EV_SHORTCUT_OVERRIDE == _QC.QEvent.ShortcutOverride
	assert co.EV_HIDE == _QC.QEvent.Hide and co.EV_WHEEL == _QC.QEvent.Wheel and co.EV_RESIZE == _QC.QEvent.Resize

def test_label_size_fallback():
	co = _env()['co']
	class Broken(object):
		def boundingRect(self, *a): raise TypeError('no overload')
	w, h = co._text_size(Broken(), 'abc\nabcdef', 9.)
	assert w > 0 and h > 0 and h > 9.

def test_core_layer_to_path():
	co = _env()['co']
	path = co.core_layer_to_path(_core_test_layer())
	# move, line, cubic (3 elements), closing line back to the start
	assert path.elementCount() == 6, path.elementCount()
	assert path.controlPointRect() == _QC.QRectF(0, 0, 100, 150)
	assert path.fillRule() == _QC.Qt.WindingFill

if __name__ == '__main__':
	failures = skipped = 0
	for name, fn in sorted(globals().items()):
		if name.startswith('test_') and callable(fn):
			try:
				t = time.perf_counter()
				fn()
				print('PASS', name, '%.2fs' % (time.perf_counter() - t))
			except SkipTest as e:
				skipped += 1
				print('SKIP', name, '-', e)
			except AssertionError as e:
				failures += 1
				print('FAIL', name, '-', repr(e))
			except Exception as e:
				failures += 1
				import traceback; traceback.print_exc()
				print('ERROR', name, '-', repr(e))
	print('\n{} failed, {} skipped'.format(failures, skipped))
	sys.exit(1 if failures else 0)
