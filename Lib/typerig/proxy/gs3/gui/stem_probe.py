# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — live stem probe (observer)
#
# While the pointer is inside the outline of the active layer, the edit
# view shows one chord through the pointer along the normal of the nearest
# outline: the stem width, square to the stem, on straight, diagonal and
# curved stems (core algo/chord_probe.py). The chord is a line with end
# dots and a value badge. Switched from the TR Toolbar observer row.
#
#   from typerig.proxy.gs3.gui.stem_probe import observer
#   observer.restore(); observer.bind_button(btn); observer.toggle(btn)
#   (see observer.py, TRObserver)
#
# The pointer comes from the observer's AppKit event monitor (mouse moved,
# left mouse down clears), not Glyphs' MOUSEMOVED: one path for GS3 and GS4.
# Rays are native layer.intersectionsBetweenPoints; a layer with
# components is measured on a decomposed copy. The per-layer cache is
# dropped on UPDATEINTERFACE (edits). DRAWFOREGROUND draws in glyph space.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

from GlyphsApp import UPDATEINTERFACE, DRAWFOREGROUND
from AppKit import (NSBezierPath, NSColor, NSFont, NSMakeRect,
                    NSAttributedString, NSFontAttributeName, NSForegroundColorAttributeName,
                    NSEventMaskMouseMoved, NSEventMaskLeftMouseDown, NSEventTypeLeftMouseDown)

from typerig.core.algo.chord_probe import normal_chord

from .observer       import TRObserver, edit_view_at
from .palette_config import PALETTE

PROBE        = PALETTE.PROBE
ALIGN_CENTER = 4		# Glyphs NSAttributedString.drawAtPoint:alignment: centre (plugins.py)


def _xy(hit):
	'''(x, y) of an intersection: NSValue (GS) or NSPoint.'''
	p = hit.pointValue() if hasattr(hit, 'pointValue') else hit
	return (p.x, p.y)


def _color(name):
	return getattr(NSColor, name)()


def _has_components(layer):
	try:
		return len(layer.components) > 0
	except Exception:
		return True		# unknown: measure decomposed


class StemProbe(TRObserver):
	key        = 'com.typerig.observer.stemProbe'
	name       = 'stem probe'
	event_mask = NSEventMaskMouseMoved | NSEventMaskLeftMouseDown

	def __init__(self):
		self._result = None		# (layer, chord) under the pointer
		self._view   = None		# graphic view to redraw
		self._src    = None		# (layer, measured layer, fill path, reach)
		super(StemProbe, self).__init__()

	def callbacks(self):
		return [(self._on_update, UPDATEINTERFACE),
		        (self._on_draw,   DRAWFOREGROUND)]

	def removed(self):
		self._clear()
		self._src = None

	# - Measure -----------------------------------------------------------
	def _source(self, layer):
		'''The layer to cast rays on (decomposed copy if it has components),
		its fill path and the ray half-length.'''
		if self._src is None or self._src[0] != layer:
			src = layer.copyDecomposedLayer() if _has_components(layer) else layer
			bounds = src.bounds
			reach = bounds.size.width + bounds.size.height + 1.	# longer than any chord
			self._src = (layer, src, src.bezierPath, reach)
		return self._src

	def _measure(self, event):
		hit = edit_view_at(event)
		if hit is None:
			return self._clear()
		view, layer, pt = hit

		_, src, path, reach = self._source(layer)
		if path is None or not path.containsPoint_(pt):
			return self._clear()

		cast = lambda p0, p1: [_xy(h) for h in src.intersectionsBetweenPoints(p0, p1, False)]
		chord = normal_chord(cast, pt.x, pt.y, reach, PROBE.STEPS, PROBE.REFINE)
		if chord is None:
			return self._clear()
		self._result = (layer, chord)
		self._view = view
		view.setNeedsDisplay_(True)

	def _clear(self):
		if self._result is not None:
			self._result = None
			if self._view is not None:
				self._view.setNeedsDisplay_(True)

	# - Callbacks ---------------------------------------------------------
	def on_event(self, event):
		try:
			if event.type() == NSEventTypeLeftMouseDown:
				self._clear()
			else:
				self._measure(event)
		except Exception as e:
			self.report(e)
			self._clear()
		return event

	def _on_update(self, notification=None):
		self._src = None		# outline may have changed

	def _on_draw(self, layer, info):
		try:
			result = self._result
			if result is None or result[0] != layer:
				return
			scale = info['Scale'] if 'Scale' in info else 1.
			self._draw(result[1], scale)
		except Exception as e:
			self.report(e)

	# - Draw --------------------------------------------------------------
	def _draw(self, chord, scale):
		color = _color(PROBE.COLOR)
		color.set()
		line = NSBezierPath.bezierPath()
		line.moveToPoint_(chord.a)
		line.lineToPoint_(chord.b)
		line.setLineWidth_(PROBE.STROKE / scale)
		line.stroke()
		r = PROBE.DOT / scale
		for x, y in (chord.a, chord.b):
			NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(x - r, y - r, 2 * r, 2 * r)).fill()
		self._draw_badge(self._fmt(chord.length), chord.mid, color, scale)

	@staticmethod
	def _fmt(value):
		text = '%.*f' % (PROBE.DECIMALS, value)
		return text.rstrip('0').rstrip('.') if '.' in text else text

	@staticmethod
	def _draw_badge(text, at, color, scale):
		attrs = {
			NSFontAttributeName            : NSFont.boldSystemFontOfSize_(PROBE.FONT_PT / scale),
			NSForegroundColorAttributeName : _color(PROBE.TEXT),
		}
		label = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
		size = label.size()
		px, py, r = PROBE.PAD_X / scale, PROBE.PAD_Y / scale, PROBE.RADIUS / scale
		x, y = at
		rect = NSMakeRect(x - size.width / 2 - px, y - size.height / 2 - py,
		                  size.width + 2 * px, size.height + 2 * py)
		color.set()
		NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, r, r).fill()
		try:
			label.drawAtPoint_alignment_(at, ALIGN_CENTER)		# Glyphs category
		except AttributeError:
			label.drawAtPoint_((x - size.width / 2, y - size.height / 2))


observer = StemProbe()
