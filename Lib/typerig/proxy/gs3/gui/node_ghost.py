# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — node add ghost (observer)
#
# While the pointer is near a path of the active layer, the edit view
# shows a ghost node at the nearest point on the path: where a new node
# would go. Ctrl + Option + right click (or Ctrl + Option + click) inserts
# it there, on the curve, as one undo step; that click does not open the
# context menu. Switched from the TR Toolbar observer row.
#
# Follows the window's Toolbar masthead (observer.scope_masters):
#   Active layer  — the node goes into the active layer only
#   Masters       — also at the same path time into the same path (by
#                   index) of every master layer whose path has the same
#                   node structure; others are skipped and listed
#
# Native GSPath nearestPointOnPath:pathTime: finds the point and its path
# time, insertNodeWithPathTime: inserts the node (Glyphs keeps the curve).
# GS3 ships no pyobjc metadata for the pathTime out-argument and GS4's does
# not mark it as output, so it is registered here.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import math

import objc
from GlyphsApp import DRAWFOREGROUND
from AppKit import (NSBezierPath, NSColor, NSMakeRect,
                    NSEventMaskMouseMoved, NSEventMaskLeftMouseDown, NSEventMaskRightMouseDown,
                    NSEventTypeMouseMoved,
                    NSEventModifierFlagControl, NSEventModifierFlagOption, NSEventModifierFlagCommand)

from .observer       import TRObserver, edit_view_at, scope_masters
from .palette_config import PALETTE

GHOST = PALETTE.GHOST
TIME_EPS = 1e-3		# path time this close to a whole number is an existing node

objc.registerMetaDataForSelector(b'GSPath', b'nearestPointOnPath:pathTime:',
                                 {'arguments': {3: {'type_modifier': objc._C_OUT}}})


def _structure(path):
	return [n.type for n in path.nodes]


def insert_targets(layer, index, masters):
	'''Paths to insert into: the active layer's path `index` first, then
	(masters=True) that path in every other master layer with the same node
	structure. Returns (paths, skipped layer names).'''
	source = layer.paths[index]
	paths, skipped = [source], []
	if not masters:
		return paths, skipped
	shape = _structure(source)
	for other in layer.parent.layers:
		if not other.isMasterLayer or other.layerId == layer.layerId:
			continue
		others = other.paths
		if index < len(others) and _structure(others[index]) == shape:
			paths.append(others[index])
		else:
			skipped.append(other.name)
	return paths, skipped


def nearest_on_path(path, point):
	'''(NSPoint, path time) of the point on path nearest to point.'''
	result = path.nearestPointOnPath_pathTime_(point, None)
	if not isinstance(result, tuple):
		raise RuntimeError('nearestPointOnPath:pathTime: returned no path time')
	return result


class NodeGhost(TRObserver):
	key        = 'com.typerig.observer.nodeGhost'
	name       = 'node add'
	event_mask = NSEventMaskMouseMoved | NSEventMaskLeftMouseDown | NSEventMaskRightMouseDown

	def __init__(self):
		self._ghost = None		# (layer, path index, point, path time)
		self._view  = None
		super(NodeGhost, self).__init__()

	def callbacks(self):
		return [(self._on_draw, DRAWFOREGROUND)]

	def removed(self):
		self._clear()

	# - Track -------------------------------------------------------------
	def _track(self, event):
		hit = edit_view_at(event)
		if hit is None:
			return self._clear()
		view, layer, pt = hit
		tol = GHOST.SNAP / max(view.scale(), 1e-6)
		best = None
		for i, path in enumerate(layer.paths):
			p, t = nearest_on_path(path, pt)
			d = math.hypot(p.x - pt.x, p.y - pt.y)
			if d <= tol and (best is None or d < best[0]):
				best = (d, i, p, t)
		if best is None or abs(best[3] - round(best[3])) < TIME_EPS:
			return self._clear()		# off the paths, or on an existing node
		self._ghost = (layer, best[1], best[2], best[3])
		self._view = view
		view.setNeedsDisplay_(True)

	def _clear(self):
		if self._ghost is not None:
			self._ghost = None
			if self._view is not None:
				self._view.setNeedsDisplay_(True)

	def _insert(self):
		layer, index, _, t = self._ghost
		glyph = layer.parent
		paths, skipped = insert_targets(layer, index, scope_masters(glyph.parent))
		glyph.beginUndo()
		try:
			for path in paths:
				path.insertNodeWithPathTime_(t)
		finally:
			glyph.endUndo()
		if skipped:
			print('[TypeRig] node add: not in %s (path %d differs)' % (', '.join(skipped), index))
		self._clear()

	# - Callbacks ---------------------------------------------------------
	def on_event(self, event):
		if event.type() == NSEventTypeMouseMoved:
			try:
				self._track(event)
			except Exception as e:
				self.report(e)
				self._clear()
			return event

		flags = event.modifierFlags()
		wanted = NSEventModifierFlagControl | NSEventModifierFlagOption
		if flags & wanted != wanted or flags & NSEventModifierFlagCommand:
			return event
		self._track(event)
		if self._ghost is None:
			return event
		self._insert()
		return None		# no context menu, no Glyphs click

	def _on_draw(self, layer, info):
		try:
			ghost = self._ghost
			if ghost is None or ghost[0] != layer:
				return
			scale = info['Scale'] if 'Scale' in info else 1.
			p, r = ghost[2], GHOST.R / scale
			dot = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(p.x - r, p.y - r, 2 * r, 2 * r))
			color = getattr(NSColor, GHOST.COLOR)()
			color.colorWithAlphaComponent_(GHOST.ALPHA).set()
			dot.fill()
			color.set()
			dot.setLineWidth_(GHOST.STROKE / scale)
			dot.stroke()
		except Exception as e:
			self.report(e)


observer = NodeGhost()
