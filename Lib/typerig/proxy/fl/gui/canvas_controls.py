# MODULE: TypeRig / Proxy / FontLab / GUI / Canvas Controls
# -----------------------------------------------------------
# Reusable controls drawn on a CanvasOverlay (canvas_overlay.py).
#   CanvasIconStrip - row of icon buttons (close, toggles, actions)
# Moved here from the Delta panel (DeltaNew.py) so other canvas
# tools (Stem Snap) share it.
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

from PythonQt import QtCore, QtGui

from typerig.proxy.fl.gui import canvas_overlay as co
from typerig.proxy.fl.gui import overlay_math as om
from typerig.proxy.fl.gui.widgets import getTRIconFont

# - Init --------------------------------
__version__ = '0.1.0'

# - Controls ----------------------------
class CanvasIconStrip(object):
	'''Row of icon buttons on a CanvasOverlay. Slot 0 sits at origin(mapping);
	the other slots follow in its direction (-1 = to the left). Self-contained
	(handles, layout, paint, click) so it can move to a shared module.

	Entries: (key, icon, tooltip, callback, always[, checked]). icon is a
	TypeRig Icons ligature name, or None for the close cross; always=False
	entries show only while the owner is ready; checked() -> bool makes the
	entry a toggle, drawn lit while on. Adding an icon is adding one entry.
	'''
	SLOT_PX = 24.
	RADIUS = 9.
	ICON_PX = 14

	def __init__(self, owner, origin, entries):
		self.owner = owner
		self.origin = origin		# origin(mapping) -> (x, y, direction, ready) or None
		self.entries = [tuple(e) + (None,) * (6 - len(e)) for e in entries]
		self.actions = {}			# handle key -> (icon, callback, checked)
		self.handles = []
		self._font = None

		for index, (key, icon, tooltip, callback, always, checked) in enumerate(self.entries):
			handle = co.Handle('strip_' + key, self._anchor(index), om.SHAPE_CIRCLE, self.RADIUS, om.AXIS_XY,
			                   QtCore.Qt.PointingHandCursor, 'muted', tooltip=tooltip)
			self.handles.append(handle)
			self.actions[handle.key] = (icon, callback, checked)

	def handle(self, key):
		for h in self.handles:
			if h.key == 'strip_' + key: return h
		return None

	def is_checked(self, handle):
		checked = self.actions[handle.key][2]
		if checked is None: return False
		try:
			return bool(checked())
		except Exception:
			co._log.exception('{}.strip[{}].checked'.format(self.owner.NAME, handle.key))
			return False

	def _shown(self, entry, ready):
		return ready or entry[4]

	def _anchor(self, index):
		def anchor(mapping):
			o = self.origin(mapping)
			if o is None: return None
			x, y, direction, ready = o
			if not self._shown(self.entries[index], ready): return None
			slot = sum(1 for e in self.entries[:index] if self._shown(e, ready))
			return (x + direction * slot * self.SLOT_PX, y)
		return anchor

	def owns(self, handle):
		return handle is not None and handle.key in self.actions

	def width(self, ready):
		'''Screen px taken by the visible slots.'''
		return sum(1 for e in self.entries if self._shown(e, ready)) * self.SLOT_PX

	def click(self, handle):
		if not self.owns(handle): return False
		try:
			self.actions[handle.key][1]()
		except Exception:
			co._log.exception('{}.strip[{}]'.format(self.owner.NAME, handle.key))
		return True

	def _icon_font(self):
		if self._font is None:
			try:
				self._font = getTRIconFont(self.ICON_PX)
			except Exception:
				self._font = False
		return self._font if self._font is not False else None

	def paint(self, p, handle, x, y, hot):
		if not self.owns(handle): return False
		c = self.owner.colors
		icon = self.actions[handle.key][0]
		on = handle.enabled and self.is_checked(handle)
		r = handle.radius + (1. if hot else 0.)
		accent = c['error'] if icon is None else c['active']
		rect = QtCore.QRectF(x - r, y - r, 2. * r, 2. * r)

		p.setPen(co.cosmetic_pen(accent if hot or on else c['muted'], 1.5 if on else 1.))
		p.setBrush(co.solid_brush(c['label_bg']))
		p.drawRoundedRect(rect, 4., 4.)
		if on:
			p.setBrush(co.solid_brush(accent, 70))
			p.drawRoundedRect(rect, 4., 4.)

		ink = c['muted'] if not handle.enabled else accent if hot else c['text']
		if icon is None:
			p.setPen(co.cosmetic_pen(ink, 1.5))
			k = r * .45
			p.drawLine(QtCore.QPointF(x - k, y - k), QtCore.QPointF(x + k, y + k))
			p.drawLine(QtCore.QPointF(x - k, y + k), QtCore.QPointF(x + k, y - k))
			return True

		flags = QtCore.Qt.AlignCenter
		try:
			flags = int(flags)
		except TypeError:
			pass

		font = self._icon_font()
		p.save()
		if font is not None:
			p.setFont(font)
		p.setPen(QtGui.QPen(ink))
		p.drawText(rect, flags, icon if font is not None else icon[:1].upper())
		p.restore()
		return True
