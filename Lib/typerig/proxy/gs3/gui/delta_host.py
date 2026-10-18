# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs — Delta host (document access for Delta engines)
#
# What a Delta engine needs from Glyphs 3 / 4: the font and its masters,
# layer names of the active glyph, glyphs by name and by scope, core
# ejects, the in-place write-back of baked layers (GS node types survive),
# undo groups, font.userData storage and font info. Shared by the Delta
# Machine plugin; TR Panel's Delta engines (gui/delta_live.GlyphsHost,
# gui/delta_bake.GlyphsBakeHost) carry the same code and are to subclass
# this one (plan_delta_machine.md, follow-up).
#
# All GlyphsApp imports are lazy: engines run headless with a fake host.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import copy
import json


def _num(value, default):
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


class GlyphsDeltaHost(object):
	'''Glyphs 3 / 4 access for Delta engines.'''

	# - Font ----------------------------------------------------------------
	def _font(self):
		from GlyphsApp import Glyphs
		return Glyphs.font

	def font_key(self):
		'''Identity of the current font (setups are kept per font).'''
		font = self._font()
		return id(font) if font is not None else None

	def font_info(self):
		'''{'family', 'version', 'file'} of the current font.'''
		font = self._font()
		if font is None:
			return {}
		import os
		version = '{}.{:03d}'.format(int(font.versionMajor or 0), int(font.versionMinor or 0))
		path = getattr(font, 'filepath', None)
		return {'family': str(font.familyName or ''), 'version': version,
		        'file': os.path.basename(path) if path else ''}

	def font_dir(self):
		import os
		font = self._font()
		path = getattr(font, 'filepath', None) if font is not None else None
		return os.path.dirname(path) if path else None

	def master_names(self):
		font = self._font()
		return [m.name for m in font.masters] if font is not None else []

	def glyph_names(self):
		font = self._font()
		return [g.name for g in font.glyphs] if font is not None else []

	def glyphs(self):
		font = self._font()
		return list(font.glyphs) if font is not None else []

	def glyph(self, name):
		font = self._font()
		return font.glyphs[name] if font is not None and name else None

	def scope_names(self, mode):
		'''Glyph names for a scope: 0 active glyph, 1 edit tab, 2 font selection.'''
		from typerig.proxy.gs3.gui.scope import scope_glyphs
		return [g.name for g in scope_glyphs(mode, self._font())]

	def open_tab(self, names):
		font = self._font()
		if font is not None and names:
			font.newTab(''.join('/' + n for n in names))

	# - Active glyph ----------------------------------------------------------
	def active_layer(self):
		font = self._font()
		if font is None or not font.selectedLayers:
			return None
		return font.selectedLayers[0]

	def layer_names(self):
		'''Layer names of the active glyph, master layers first.'''
		layer = self.active_layer()
		if layer is None or layer.parent is None:
			return []
		names = []
		for gs_layer in layer.parent.layers:
			if gs_layer.name and gs_layer.name not in names:
				names.append(gs_layer.name)
		return names

	def layer_size(self, layer_name, glyph_name=None):
		'''(width, height) of the outline of layer_name (active glyph by default).'''
		glyph = self.glyph(glyph_name) if glyph_name else None
		if glyph is None:
			layer = self.active_layer()
			glyph = layer.parent if layer is not None else None
		if glyph is None:
			return None
		for gs_layer in glyph.layers:
			if gs_layer.name == layer_name:
				size = gs_layer.bounds.size
				return (float(size.width), float(size.height)) if size.width and size.height else None
		return None

	def active_glyph_core(self):
		layer = self.active_layer()
		return self.glyph_core(layer.parent) if layer is not None and layer.parent is not None else None

	# - Core <-> Glyphs -------------------------------------------------------
	def glyph_core(self, glyph):
		from typerig.proxy.gs3.objects.glyph import trGlyph
		return trGlyph(glyph).eject()

	def italic_angle_of(self, glyph, layer_name):
		'''italicAngle of the master the layer belongs to (Glyphs sign).'''
		font = self._font()
		for gs_layer in glyph.layers:
			if gs_layer.name == layer_name:
				master_id = gs_layer.associatedMasterId or gs_layer.layerId
				for master in font.masters:
					if master.id == master_id:
						return _num(master.italicAngle, 0.)
		return 0.

	def _nodes(self, layer):
		# Path nodes in eject (point_array) order: paths -> nodes
		return [node for path in layer.paths for node in path.nodes]

	def write_layer(self, layer, core_layer, viable):
		'''Write core positions into the GS nodes in place; metrics and
		anchors when they are in viable.'''
		nodes = self._nodes(layer)
		core_nodes = core_layer.nodes
		layer.beginChanges()
		try:
			for i in range(min(len(nodes), len(core_nodes))):
				nodes[i].position = (float(core_nodes[i].x), float(core_nodes[i].y))
			if 'metric_array' in viable:
				layer.width = float(core_layer.advance_width)
			if 'anchor_array' in viable:
				for gs_anchor, core_anchor in zip(layer.anchors, core_layer.anchors):
					gs_anchor.position = (float(core_anchor.x), float(core_anchor.y))
		finally:
			layer.endChanges()

	def write_target(self, glyph, core_layer, base_name, viable):
		'''Write a baked core layer into the GS layer of the same name.
		Missing layer: duplicate the base input. Different node count: take
		the base input's shapes and anchors first. Then write in place.'''
		from typerig.proxy.gs3.objects.glyph import trGlyph
		tr_glyph = trGlyph(glyph)
		target = tr_glyph.find_layer(core_layer.name)
		if target is None:
			target = tr_glyph.duplicate_layer(base_name, core_layer.name)
			if target is None:
				raise RuntimeError('could not create layer "{}"'.format(core_layer.name))
		elif len(self._nodes(target.host)) != len(core_layer.nodes):
			base = tr_glyph.find_layer(base_name)
			target.set_shapes([copy.copy(shape) for shape in base.host.shapes])
			target.host.anchors = [copy.copy(anchor) for anchor in base.host.anchors]
		gs_layer = target.host
		if len(self._nodes(gs_layer)) != len(core_layer.nodes):
			raise RuntimeError('layer "{}" does not match the base input'.format(core_layer.name))
		self.write_layer(gs_layer, core_layer, viable)

	def begin_glyph_undo(self, glyph):
		try:
			glyph.beginUndo()
		except Exception:
			pass

	def end_glyph_undo(self, glyph):
		try:
			glyph.endUndo()
		except Exception:
			pass

	def redraw(self):
		from GlyphsApp import Glyphs
		Glyphs.redraw()

	# - Font storage ----------------------------------------------------------
	def load_data(self, key):
		'''JSON stored in font.userData[key] (None when there is none).'''
		font = self._font()
		if font is None:
			return None
		try:
			raw = font.userData[key]
			return json.loads(raw) if raw else None
		except Exception:
			return None

	def save_data(self, key, data):
		font = self._font()
		if font is None:
			return False
		try:
			font.userData[key] = json.dumps(data)
			return True
		except Exception:
			return False
