# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — node slide (observer)
#
# While dragging a selected on-curve node:
#   Option         the node slides along its incoming segment (it is the
#                  segment's end node)
#   Cmd + Option   it slides along its outgoing segment (its start node)
# Lines and curves; the node may run past the far end (extrapolate). The
# segment keeps its shape: it is trimmed or extended (core
# algo/node_slide.py). The node's other handle moves with it and, on a
# smooth node, turns to the new tangent. Without Option the drag is
# Glyphs' own (Shift still constrains H / V). Switched from the TR Toolbar
# observer row.
#
# The observer's AppKit event monitor sees the drag before Glyphs: on the
# first drag event it grabs the selected on-curve node nearest the mouse
# down point and keeps the original positions around it; every Option
# drag event is then swallowed and applied from those originals, so
# switching Option / Cmd mid-drag or after a free move is exact. One undo
# step per drag.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import math

from GlyphsApp import OFFCURVE, CURVE, LINE
from AppKit import (NSEventMaskLeftMouseDown, NSEventMaskLeftMouseDragged, NSEventMaskLeftMouseUp,
                    NSEventTypeLeftMouseDown, NSEventTypeLeftMouseUp,
                    NSEventModifierFlagOption, NSEventModifierFlagCommand)

from typerig.core.objects.point       import Point
from typerig.core.objects.line        import Line
from typerig.core.objects.cubicbezier import CubicBezier
from typerig.core.algo.node_slide     import (project_time, slide_end, slide_start,
                                              end_direction, start_direction, turn_handle)

from .observer       import TRObserver, edit_view_at
from .palette_config import PALETTE

SLIDE = PALETTE.SLIDE


class _Grab(object):
	'''A grabbed on-curve node: its path, original positions around it and
	its incoming / outgoing segments as (core segment, node indices).'''

	def __init__(self, path, index):
		self.path   = path
		self.nodes  = list(path.nodes)
		self.index  = index
		self.closed = bool(path.closed)
		self.node   = self.nodes[index]
		self.orig   = {}
		for k in range(-3, 4):
			j = self._at(k)
			if j is not None:
				p = self.nodes[j].position
				self.orig[j] = (p.x, p.y)
		self.incoming = self._incoming()
		self.outgoing = self._outgoing()

	def _at(self, k):
		j = self.index + k
		n = len(self.nodes)
		if self.closed:
			return j % n
		return j if 0 <= j < n else None

	def _type(self, k):
		j = self._at(k)
		return None if j is None else self.nodes[j].type

	def _seg(self, ks):
		ids = [self._at(k) for k in ks]
		pts = [self.orig[j] for j in ids]
		return ((CubicBezier(*pts) if len(pts) == 4 else Line(*pts)), ids)

	def _incoming(self):
		if self.node.type == CURVE and self._type(-1) == OFFCURVE and self._type(-2) == OFFCURVE \
				and self._type(-3) not in (None, OFFCURVE):
			return self._seg((-3, -2, -1, 0))
		if self.node.type == LINE and self._type(-1) not in (None, OFFCURVE):
			return self._seg((-1, 0))
		return None

	def _outgoing(self):
		if self._type(1) == OFFCURVE and self._type(2) == OFFCURVE and self._type(3) == CURVE:
			return self._seg((0, 1, 2, 3))
		if self._type(1) == LINE:
			return self._seg((0, 1))
		return None

	# - Apply -----------------------------------------------------------
	def apply(self, pointer, outgoing):
		'''Slide to the point of the segment nearest `pointer`.'''
		for j, xy in self.orig.items():
			self.nodes[j].position = xy
		seg = self.outgoing if outgoing else self.incoming
		if seg is None:
			return
		geom, ids = seg
		if outgoing:
			t = project_time(geom, (pointer.x, pointer.y), -SLIDE.EXTEND, 1. - SLIDE.MARGIN)
			new = slide_start(geom, t)
			node_at, other_k = new.p0, -1
			direction = start_direction(new) * -1.
		else:
			t = project_time(geom, (pointer.x, pointer.y), SLIDE.MARGIN, 1. + SLIDE.EXTEND)
			new = slide_end(geom, t)
			node_at = new.p3 if isinstance(new, CubicBezier) else new.p1
			other_k = 1
			direction = end_direction(new)

		points = (new.p0, new.p1, new.p2, new.p3) if isinstance(new, CubicBezier) else (new.p0, new.p1)
		for j, p in zip(ids, points):
			self.nodes[j].position = (p.x, p.y)

		# The node's handle on the other side moves with it; a smooth node
		# turns it to the new tangent.
		k = self._at(other_k)
		if k is not None and k not in ids and self.nodes[k].type == OFFCURVE:
			h = Point(self.orig[k]) - Point(self.orig[self.index]) + node_at
			if self.node.smooth and direction.magnitude > 0.:
				h = turn_handle(node_at, h, direction)
			self.nodes[k].position = (h.x, h.y)


class NodeSlider(TRObserver):
	key        = 'com.typerig.observer.nodeSlide'
	name       = 'node slide'
	event_mask = NSEventMaskLeftMouseDown | NSEventMaskLeftMouseDragged | NSEventMaskLeftMouseUp

	def __init__(self):
		self._down = None		# (view, layer, point) at mouse down
		self._grab = None		# _Grab, False = nothing to slide this drag, None = not decided
		self._undo = None		# glyph with an open undo group
		super(NodeSlider, self).__init__()

	def removed(self):
		self._end()

	def _end(self):
		if self._undo is not None:
			self._undo.endUndo()
			self._undo = None
		self._down = self._grab = None

	def _capture(self):
		'''Selected on-curve node nearest the mouse down point, within SLIDE.HIT.'''
		view, layer, down = self._down
		tol = SLIDE.HIT / max(view.scale(), 1e-6)
		best = None
		for path in layer.paths:
			for i, node in enumerate(path.nodes):
				if node.type == OFFCURVE or not node.selected:
					continue
				d = math.hypot(node.position.x - down.x, node.position.y - down.y)
				if d <= tol and (best is None or d < best[0]):
					best = (d, path, i)
		if best is None:
			return False
		grab = _Grab(best[1], best[2])
		return grab if grab.incoming is not None or grab.outgoing is not None else False

	def on_event(self, event):
		kind = event.type()
		if kind == NSEventTypeLeftMouseDown:
			self._end()
			self._down = edit_view_at(event)
			return event
		if kind == NSEventTypeLeftMouseUp:
			self._end()
			return event

		# Dragged
		if self._down is None:
			return event
		if self._grab is None:
			self._grab = self._capture()
		flags = event.modifierFlags()
		if not self._grab or not flags & NSEventModifierFlagOption:
			return event		# Glyphs' own drag

		view, layer, _ = self._down
		if self._undo is None:
			self._undo = layer.parent
			self._undo.beginUndo()
		self._grab.apply(view.getActiveLocation_(event), bool(flags & NSEventModifierFlagCommand))
		view.setNeedsDisplay_(True)
		return None


observer = NodeSlider()
