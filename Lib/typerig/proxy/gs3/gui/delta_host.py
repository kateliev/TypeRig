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
		'''Identity of the current font (setups are kept per font).

		The ObjC pointer, not id(): Glyphs.font may hand out a new Python
		wrapper on each access, and an id() that changes made the Delta
		Machine take every Execute for a font switch (it parked the edits
		and loaded a fresh setup; seen in Glyphs 4, 2026-10-18).'''
		font = self._font()
		if font is None:
			return None
		try:
			import objc
			return objc.pyobjc_id(font)
		except Exception:
			return id(font)

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

	def selected_names(self):
		'''Glyphs selected in Glyphs: the Font view selection, or the selected
		glyphs of the edit tab (font.selectedLayers covers both).'''
		font = self._font()
		names = []
		for layer in (font.selectedLayers or []) if font is not None else []:
			glyph = getattr(layer, 'parent', None)		# GSControlLayer line breaks have none
			name = getattr(glyph, 'name', None)
			if name and name not in names:
				names.append(name)
		return names

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

	# - Composites -----------------------------------------------------------
	# A composite layer has components and no paths: nothing to interpolate.
	# The Delta Machine skips it (option Skip composites) and gives it the
	# target layer here instead, so the font stays complete, with its width
	# following the components' base glyphs.
	METRICS_KEYS = ('leftMetricsKey', 'rightMetricsKey', 'widthMetricsKey')

	def _layer_named(self, glyph, name):
		for gs_layer in glyph.layers:
			if gs_layer.name == name:
				return gs_layer
		return None

	def shape_kind(self, glyph, layer_name):
		'''outline (paths only), composite (components only), mixed, empty —
		of layer_name, else of the first layer.'''
		layer = self._layer_named(glyph, layer_name)
		if layer is None:
			layer = glyph.layers[0] if len(glyph.layers) else None
		if layer is None:
			return 'empty'
		paths, components = len(layer.paths), len(layer.components)
		if paths and components:
			return 'mixed'
		if components:
			return 'composite'
		return 'outline' if paths else 'empty'

	def bake_composite(self, glyph, base_name, target_name, metrics=True):
		'''Target layer of a composite glyph without the delta.

		The layer is made from the base input (components, anchors, width)
		when it is missing. With metrics:
		  - metrics keys (glyph or layer): Glyphs computes them, syncMetrics();
		  - auto-aligned components: Glyphs aligns them to their base glyphs;
		  - else width and component positions are scaled by the first
		    component's base glyph: its target / base advance width (x) and
		    outline height (y). The base layer is the reference, so a second
		    bake does not compound.
		Returns {'created', 'aligned', 'scale': (rx, ry) | None, 'notes': [...]}.'''
		import copy
		from typerig.proxy.gs3.objects.glyph import trGlyph
		tr_glyph = trGlyph(glyph)
		out = {'created': False, 'aligned': False, 'scale': None, 'notes': []}
		target = tr_glyph.find_layer(target_name)
		if target is None:
			target = tr_glyph.duplicate_layer(base_name, target_name)
			if target is None:
				raise RuntimeError('no layer "{}" to copy'.format(base_name))
			out['created'] = True
		layer, base = target.host, self._layer_named(glyph, base_name)
		components = list(layer.components)
		out['aligned'] = bool(components) and all(c.automaticAlignment for c in components)
		for c in components:		# a component shows its base glyph's layer of the same name, if Glyphs finds one
			shown = c.componentLayer
			if shown is not None and shown.name != target_name:
				out['notes'].append('{} shows its {} layer'.format(c.componentName, shown.name))
		if not metrics or base is None:
			return out
		if any(getattr(layer, k, None) or getattr(glyph, k, None) for k in self.METRICS_KEYS):
			layer.syncMetrics()
			out['notes'].append('metrics keys synced')
			return out
		if out['aligned'] or not components:
			return out
		first = components[0].component
		b_in = self._layer_named(first, base_name) if first is not None else None
		b_out = self._layer_named(first, target_name) if first is not None else None
		if b_in is None or b_out is None or not b_in.width or not b_in.bounds.size.height:
			out['notes'].append('{} has no {} layer: width kept'.format(components[0].componentName, target_name))
			return out
		rx = float(b_out.width) / float(b_in.width)
		ry = float(b_out.bounds.size.height) / float(b_in.bounds.size.height)
		layer.width = float(base.width) * rx
		for c, ref in zip(components, list(base.components)):
			c.position = (float(ref.position.x) * rx, float(ref.position.y) * ry)
		out['scale'] = (rx, ry)
		return out

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

	def app_info(self):
		'''"Glyphs <version> (<build>)" for logs.'''
		from GlyphsApp import Glyphs
		return 'Glyphs {} ({})'.format(getattr(Glyphs, 'versionString', '?'), getattr(Glyphs, 'buildNumber', '?'))

	# Glyphs' label colours (glyph.color index 0..11), for hosts without
	# custom glyph colours: the nearest one is used
	LABEL_RGB = ((0.97, 0.29, 0.25), (1.0, 0.58, 0.2), (0.6, 0.4, 0.2), (1.0, 0.85, 0.15),
	             (0.55, 0.9, 0.35), (0.2, 0.6, 0.25), (0.5, 0.8, 1.0), (0.15, 0.4, 0.9),
	             (0.6, 0.35, 0.85), (0.95, 0.35, 0.75), (0.75, 0.75, 0.75), (0.35, 0.35, 0.35))

	def flag_glyph(self, glyph, rgba):
		'''Colour a glyph (Font view label) with rgba in 0..1: a custom
		colour (glyph.colorObject, Glyphs 3+), else the nearest label colour.'''
		r, g, b, a = (list(rgba) + [1.])[:4]
		try:
			from AppKit import NSColor
			glyph.colorObject = NSColor.colorWithDeviceRed_green_blue_alpha_(r, g, b, a)
			return
		except Exception:
			pass
		near = min(range(len(self.LABEL_RGB)),
		           key=lambda i: sum((x - y) ** 2 for x, y in zip(self.LABEL_RGB[i], (r, g, b))))
		glyph.color = near

	# - Design space (Designspace tab) ---------------------------------------------
	# Glyphs 3.2+ keeps master coordinates in internalAxesValues (design) /
	# externalAxesValues (user), keyed by axis.axisId; earlier versions in
	# master.axes (a list in font.axes order). Axis ranges are not stored in
	# Glyphs (they follow the masters): read as the masters' span, the plan
	# keeps the user's range. Default master = font parameter
	# 'Variable Font Origin' (master id), else the first master.
	ORIGIN_PARAM = 'Variable Font Origin'

	@staticmethod
	def _axis_id(axis, index):
		return str(getattr(axis, 'axisId', None) or getattr(axis, 'id', None) or index)

	def _values(self, master, axes):
		values = getattr(master, 'internalAxesValues', None)
		if values is not None:
			out = []
			for i, axis in enumerate(axes):
				try:
					out.append(float(values[self._axis_id(axis, i)]))
				except Exception:
					out.append(0.)
			return out
		old = list(getattr(master, 'axes', []) or [])
		return [float(old[i]) if i < len(old) else 0. for i in range(len(axes))]

	def _set_values(self, master, axes, values):
		store = getattr(master, 'internalAxesValues', None)
		if store is not None:
			for i, (axis, v) in enumerate(zip(axes, values)):
				store[self._axis_id(axis, i)] = float(v)
		else:
			master.axes = [float(v) for v in values]

	def _default_master_id(self, font):
		try:
			origin = font.customParameters[self.ORIGIN_PARAM]
		except Exception:
			origin = None
		for m in font.masters:
			if origin and origin in (m.id, m.name):
				return m.id
		return font.masters[0].id if len(font.masters) else None

	def read_designspace(self):
		'''The font's axes and masters as a design space plan.'''
		font = self._font()
		plan = {'axes': [], 'masters': []}
		if font is None:
			return plan
		axes = list(font.axes)
		masters = list(font.masters)
		values = [self._values(m, axes) for m in masters]
		default_id = self._default_master_id(font)
		default_values = next((v for m, v in zip(masters, values) if m.id == default_id), values[0] if values else [])
		for i, axis in enumerate(axes):
			column = [v[i] for v in values] or [0.]
			plan['axes'].append({'key': 'a%d' % (i + 1), 'id': self._axis_id(axis, i), 'name': str(axis.name or ''),
			                     'tag': str(getattr(axis, 'axisTag', '') or ''), 'hidden': bool(getattr(axis, 'hidden', False)),
			                     'min': min(column), 'max': max(column),
			                     'default': default_values[i] if i < len(default_values) else min(column)})
		for j, (m, v) in enumerate(zip(masters, values)):
			plan['masters'].append({'key': 'm%d' % (j + 1), 'id': m.id, 'name': str(m.name or ''),
			                        'source': {'kind': 'font', 'from': ''},
			                        'location': {'a%d' % (i + 1): v[i] for i in range(len(axes))},
			                        'default': m.id == default_id, 'remove': False})
		return plan

	def _master_of_layer(self, font, layer_name):
		'''The master a (target) layer is associated with, from the first glyph that has it.'''
		for glyph in font.glyphs:
			for layer in glyph.layers:
				if layer.name == layer_name and layer.associatedMasterId:
					return next((m for m in font.masters if m.id == layer.associatedMasterId), None)
		return None

	def _copy_kerning(self, font, src_id, dst_id):
		'''All pairs of a master into another one (values as they are).'''
		n = 0
		try:
			table = font.kerning[src_id]
		except Exception:
			return 0
		if not table:
			return 0

		def key(k):
			if str(k).startswith('@'):
				return str(k)
			glyph = font.glyphForId_(k) if hasattr(font, 'glyphForId_') else None
			return glyph.name if glyph is not None else str(k)

		pairs = [(key(left), key(right), float(value)) for left, rights in table.items() for right, value in rights.items()]
		for left, right, value in pairs:
			try:
				font.setKerningForPair(dst_id, left, right, value)
				n += 1
			except Exception:
				pass
		return n

	def _fill_master(self, font, master, source, layer_name=None, progress=None):
		'''Layers of a new master for every glyph: the target layer layer_name
		when the glyph has it, else the source master's layer.'''
		from GlyphsApp import GSLayer
		from typerig.proxy.gs3.objects.layer import trLayer
		glyphs = list(font.glyphs)
		for n, glyph in enumerate(glyphs):
			src = None
			if layer_name:
				src = next((l for l in glyph.layers if l.name == layer_name), None)
			if src is None and source is not None:
				src = glyph.layers[source.id]
			dst = glyph.layers[master.id]
			if dst is None:
				dst = GSLayer()
				dst.associatedMasterId = master.id
				dst.layerId = master.id
				glyph.layers.append(dst)
			if src is not None:
				trLayer(dst).set_shapes([copy.copy(shape) for shape in src.shapes])
				dst.anchors = [copy.copy(anchor) for anchor in src.anchors]
				dst.width = src.width
			if progress is not None and n % 50 == 0:
				progress(float(n) / max(1, len(glyphs)), 'Master {}: {}/{} glyphs'.format(master.name, n, len(glyphs)))

	def apply_designspace(self, plan, progress=None):
		'''Write a design space plan to the font: axes (add, rename, remove),
		new masters (copy of a master, from a target layer: layers of every
		glyph + that master's kerning), renames, coordinates, the default
		master, then removals. Returns (plan with font ids, log lines).'''
		from GlyphsApp import GSAxis, GSFontMaster
		font = self._font()
		log = []
		if font is None:
			return plan, ['No font.']
		plan = copy.deepcopy(plan)
		try:
			font.disableUpdateInterface()
		except Exception:
			pass
		try:
			# Axes
			by_id = {self._axis_id(a, i): a for i, a in enumerate(font.axes)}
			keep = {a['id'] for a in plan['axes'] if a['id']}
			for i, axis in reversed(list(enumerate(list(font.axes)))):
				if self._axis_id(axis, i) not in keep:
					font.axes.remove(axis)
					log.append('Removed axis %s' % axis.name)
			ordered = []
			for a in plan['axes']:
				axis = by_id.get(a['id'])
				if axis is None:
					axis = GSAxis()
					font.axes.append(axis)
					log.append('Added axis %s' % a['name'])
				axis.name = a['name']
				axis.axisTag = a['tag']
				try:
					axis.hidden = bool(a['hidden'])
				except Exception:
					pass
				a['id'] = self._axis_id(axis, len(ordered))
				ordered.append(axis)
			keys = [a['key'] for a in plan['axes']]

			# New masters
			masters_by_name = {m.name: m for m in font.masters}
			for m in plan['masters']:
				if m['id'] or m['remove']:
					continue
				kind, src_name = m['source']['kind'], m['source']['from']
				if kind == 'target':
					source = self._master_of_layer(font, src_name) or font.masters[0]
				elif kind == 'copy':
					source = masters_by_name.get(src_name) or font.masters[0]
				else:
					source = None
				master = GSFontMaster()
				master.name = m['name']
				if source is not None:
					for attr in ('ascender', 'capHeight', 'xHeight', 'descender', 'italicAngle'):
						try:
							setattr(master, attr, getattr(source, attr))
						except Exception:
							pass
				font.masters.append(master)
				m['id'] = master.id
				if kind in ('copy', 'target'):
					self._fill_master(font, master, source, src_name if kind == 'target' else None, progress)
					pairs = self._copy_kerning(font, source.id, master.id)
					log.append('Added master %s (%s %s; %d kerning pairs copied, not scaled)'
					           % (m['name'], 'target layer' if kind == 'target' else 'copy of', src_name, pairs))
				else:
					log.append('Added master %s (empty)' % m['name'])

			# Names, coordinates, default
			by_mid = {gm.id: gm for gm in font.masters}
			for m in plan['masters']:
				gm = by_mid.get(m['id'])
				if gm is None or m['remove']:
					continue
				if gm.name != m['name']:
					log.append('Renamed master %s -> %s' % (gm.name, m['name']))
					gm.name = m['name']
				self._set_values(gm, ordered, [m['location'].get(k, 0.) for k in keys])
				if m['default']:
					try:
						font.customParameters[self.ORIGIN_PARAM] = gm.id
					except Exception:
						log.append('Could not set the variable font origin.')

			# Removals last
			for m in plan['masters']:
				if not m['remove'] or not m['id']:
					continue
				index = next((i for i, gm in enumerate(font.masters) if gm.id == m['id']), None)
				if index is not None:
					try:
						font.removeFontMasterAtIndex_(index)
					except Exception:
						del font.masters[index]
					log.append('Removed master %s' % m['name'])
			plan['masters'] = [m for m in plan['masters'] if not m['remove']]
		finally:
			try:
				font.enableUpdateInterface()
			except Exception:
				pass
		return plan, log

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
