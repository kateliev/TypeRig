# MODULE: Typerig / Proxy / GS3 / Glyph (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function

import GlyphsApp

from typerig.proxy.gs3.objects.layer import trLayer
from typerig.core.objects.glyph import Glyph
from typerig.core.func.string import is_hex

# - Init ---------------------------------
__version__ = '0.1.0'

# GS3 uses integer color indices 0-12 (0 = no colour).
# These align with the Core MARK_COLORS palette in declaration order.
_GS3_COLOR_TO_HEX = {
	0:  None,
	1:  '#FF3B30',  # Red
	2:  '#FF9500',  # Orange
	3:  '#A2845E',  # Brown
	4:  '#FFCC00',  # Yellow
	5:  '#34C759',  # Light Green
	6:  '#00796B',  # Dark Green
	7:  '#5AC8FA',  # Cyan
	8:  '#007AFF',  # Blue
	9:  '#AF52DE',  # Purple
	10: '#FF2D55',  # Pink
	11: '#AEAEB2',  # Light Gray
	12: '#636366',  # Dark Gray
}
_HEX_TO_GS3_COLOR = {v: k for k, v in _GS3_COLOR_TO_HEX.items() if v is not None}

# - Classes ------------------------------
class trGlyph(Glyph):
	'''Proxy to GSGlyph object.

	Constructor:
		trGlyph()              — wraps current glyph in the active edit tab
		trGlyph(GSGlyph)       — wraps a specific GSGlyph
		trGlyph(GSFont, name)  — looks up glyph by name in a font
		trGlyph(name, GSFont)  — same, arguments in either order

	Attributes:
		.host (GSGlyph): wrapped GlyphsApp glyph
	'''
	__meta__ = {'name': 'name'}
	__meta_keys = frozenset(__meta__.keys())

	# - Initialize ---------------------------
	def __init__(self, *argv, **kwargs):

		if len(argv) == 0:
			# Current glyph from the active edit tab
			font  = GlyphsApp.Glyphs.font
			layer = font.selectedLayers[0] if font and font.selectedLayers else None
			self.host = layer.parent if layer else None

		elif len(argv) == 1 and isinstance(argv[0], GlyphsApp.GSGlyph):
			self.host = argv[0]

		elif len(argv) == 2:
			font_arg  = next((a for a in argv if isinstance(a, GlyphsApp.GSFont)),  None)
			name_arg  = next((a for a in argv if isinstance(a, str)),               None)

			if font_arg is not None and name_arg is not None:
				self.host = font_arg.glyphs[name_arg]
			else:
				raise TypeError('Two-argument form expects (GSFont, str) or (str, GSFont)')

		else:
			raise TypeError('Unexpected arguments: {}'.format(argv))

		super(trGlyph, self).__init__(self.host.layers, default_factory=trLayer, proxy=True, **kwargs)

	# - Internals ----------------------------
	def __getattribute__(self, name):
		if name in trGlyph.__meta_keys:
			return self.host.__getattribute__(trGlyph.__meta__[name])
		else:
			return Glyph.__getattribute__(self, name)

	def __setattr__(self, name, value):
		if name in trGlyph.__meta_keys:
			self.host.__setattr__(trGlyph.__meta__[name], value)
		else:
			Glyph.__setattr__(self, name, value)

	# - Properties ---------------------------
	@property
	def mark(self):
		'''Glyph flag colour as a hex string (e.g. '#FF3B30') or None.'''
		return _GS3_COLOR_TO_HEX.get(self.host.color, None)

	@mark.setter
	def mark(self, value):
		if isinstance(value, int):
			self.host.color = max(0, min(12, value))
		elif value is None:
			self.host.color = 0
		elif is_hex(value):
			self.host.color = _HEX_TO_GS3_COLOR.get(value.upper(), 0)

	@property
	def unicodes(self):
		'''Unicode values as a list of integers.'''
		return [int(u, 16) for u in self.host.unicodes if u]

	@unicodes.setter
	def unicodes(self, other):
		if isinstance(other, (list, tuple)):
			self.host.unicodes = ['{:04X}'.format(int(u)) for u in other]

	@property
	def active_layer(self):
		'''Name of the layer currently active in the editor, with sane fallbacks.

		Resolution order:
		  1. font.selectedLayers[0] if its parent is this glyph — the editor's
		     truly-active layer (works in font window AND edit tab).
		  2. font.currentTab.activeLayer if its parent is this glyph — covers
		     edit-tab focus when selectedLayers is somehow stale.
		  3. First layer whose layerId belongs to a font master — avoids
		     returning a stray brace/bracket/colour layer that happens to be
		     stored first.
		  4. host.layers[0] — last resort.
		'''
		font = None
		try:
			font = self.host.parent
		except Exception:
			pass

		# 1. Editor-active layer for this glyph.
		try:
			if font and font.selectedLayers:
				active = font.selectedLayers[0]
				if active is not None and active.parent == self.host:
					return active.name
		except Exception:
			pass

		# 2. Edit-tab activeLayer for this glyph.
		try:
			if font and font.currentTab:
				active = font.currentTab.activeLayer
				if active is not None and active.parent == self.host:
					return active.name
		except Exception:
			pass

		# 3. First master layer.
		try:
			if font and self.host.layers:
				master_ids = {m.id for m in font.masters}
				for layer in self.host.layers:
					if layer.layerId in master_ids:
						return layer.name
		except Exception:
			pass

		# 4. First layer in storage order.
		if self.host.layers:
			return self.host.layers[0].name
		return None

	# - Functions ----------------------------
	def update(self):
		'''Notify GlyphsApp that changes have been applied.'''
		try:
			self.host.parent.updateChangeCount_(0)
		except Exception:
			pass
		try:
			GlyphsApp.Glyphs.redraw()
		except Exception:
			pass

	# - Layer management ---------------------
	def add_layer(self, layer_name):
		'''Create a new empty GSLayer and add it to the host glyph.

		Args:
			layer_name (str): Name for the new layer.

		Returns:
			trLayer: Proxy wrapping the newly created GSLayer.
		'''
		new_layer      = GlyphsApp.GSLayer()
		new_layer.name = str(layer_name)
		self.host.layers.append(new_layer)
		return trLayer(new_layer)

	def find_layer(self, layer_name):
		'''Find a layer by name and return its proxy, or None.

		Args:
			layer_name (str): Layer name to search for.

		Returns:
			trLayer or None
		'''
		for gs_layer in self.host.layers:
			if gs_layer.name == layer_name:
				return trLayer(gs_layer)
		return None

	# - Eject / mount -------------------------
	def eject(self):
		'''Detach from host: return a pure core Glyph with all layers and metadata.

		Returns:
			Glyph: Core Glyph with no GlyphsApp bindings.

		Example:
			>>> tr_g = trGlyph()
			>>> core_g = tr_g.eject()
			>>> core_g.layer('Regular').shift(10, 20)
			>>> tr_g.layer('Regular').mount(core_g.layer('Regular'))
			>>> tr_g.update()
		'''
		core_layers = [trLayer(l).eject() for l in self.host.layers]

		return Glyph(
			core_layers,
			name=self.name,
			mark=self.mark,
			unicodes=list(self.unicodes),
		)
