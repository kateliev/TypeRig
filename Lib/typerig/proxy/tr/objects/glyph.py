# MODULE: Typerig / Proxy / Glyph (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2019-2022 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import math 

import fontlab as fl6
import fontgate as fgt
import PythonQt as pqt

from typerig.core.func.string import is_hex, hue_to_hex, hex_to_hue

from typerig.proxy.tr.objects.layer import trLayer
from typerig.proxy.tr.objects.guideline import _build_fl_guideline
from typerig.core.objects.glyph import Glyph

# - Init --------------------------------
__version__ = '0.1.2'

# - Classes -----------------------------
class trGlyph(Glyph):
	'''Proxy to flLayer object

	Constructor:
		trGlyph(flLayer)

	Attributes:
		.host (flLayer): Original flLayer 
	'''
	# - Metadata and proxy model
	#__slots__ = ('name', 'unicodes', 'identifier', 'parent')
	__meta__ = {'name':'name'}
	__meta_keys = frozenset(__meta__.keys())
		
	# -- Some hardcoded properties
	active_layer = property(lambda self: self.host.activeLayer.name)
		
	# - Initialize 
	def __init__(self, *argv, **kwargs):

		if len(argv) == 0:
			self.host = fl6.flGlyph(fl6.CurrentGlyph(), fl6.CurrentFont())
		
		elif len(argv) == 1 and isinstance(argv[0], fl6.flGlyph):
			#font, glyph = argv[0].fgPackage, argv[0].fgPackage[argv[0].name]
			self.host = argv[0]

		elif len(argv) == 1 and isinstance(argv[0], fgt.fgGlyph):
			font, glyph = argv[0].parent, argv[0]
			self.host = fl6.flGlyph(glyph, font)

		elif len(argv) == 2 and isinstance(argv[0], fgt.fgFont) and isinstance(argv[1], fgt.fgGlyph):
			font, glyph = argv
			self.host = fl6.flGlyph(glyph, font)

		elif len(argv) == 2 and isinstance(argv[1], fgt.fgFont) and isinstance(argv[0], fgt.fgGlyph):
			glyph, font = argv
			self.host = fl6.flGlyph(glyph, font)

		super(trGlyph, self).__init__(self.host.layers, default_factory=trLayer, proxy=True, **kwargs)

	# - Internals ------------------------------
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
	
	# - Properties --------------------------
	@property
	def mark(self):
		return hue_to_hex(self.host.mark)

	@mark.setter
	def mark(self, value):
		if isinstance(value, int):
			self.host.mark = value
		elif is_hex(value):
			self.host.mark = hex_to_hue(value)

	@property
	def unicodes(self):
		return self.host.fgGlyph.unicodes

	@unicodes.setter
	def unicodes(self, other):
		if isinstance(other, list):
			self.host.fgGlyph.unicodes = other

	@property
	def note(self):
		'''Free-text glyph note (UFO-style). Backed by fgGlyph.note in FL.'''
		fg = self.host.fgGlyph
		value = getattr(fg, 'note', None)
		return value if value else None

	@note.setter
	def note(self, value):
		fg = self.host.fgGlyph
		if hasattr(fg, 'note'):
			fg.note = value if value is not None else ''

	# - Functions ---------------------------
	def update(self):
		fl6.flItems.notifyChangesApplied(self.name, self.host, True)

	# - Layer management ------------------------
	def add_layer(self, layer_name):
		'''Create a new empty FL layer and add it to the host glyph.

		Args:
			layer_name (str): Name for the new layer.

		Returns:
			trLayer: Proxy wrapping the newly created flLayer.
		'''
		new_fl_layer = fl6.flLayer()
		new_fl_layer.name = str(layer_name)
		self.host.addLayer(new_fl_layer)
		return trLayer(new_fl_layer)

	def find_layer(self, layer_name):
		'''Find an FL layer by name and return its proxy, or None.

		Args:
			layer_name (str): Layer name to search for.

		Returns:
			trLayer or None: Proxy if found, None otherwise.
		'''
		for fl_layer in self.host.layers:
			if fl_layer.name == layer_name:
				return trLayer(fl_layer)

		return None

	# - Eject/mount ----------------------------
	def eject(self):
		'''Detach from host: return a pure core Glyph with current FL values.
		The returned Glyph has no FL bindings and can be freely manipulated.

		Returns:
			Glyph: Pure core Glyph with all layers, geometry and metadata.

		Example:
			>>> tr_g = trGlyph()
			>>> core_g = tr_g.eject()
			>>> layer = core_g.layer('Regular')
			>>> layer.shift(10, 20)
			>>> tr_g.layer('Regular').mount(layer)  # mount at layer level
			>>> tr_g.update()
		'''
		core_layers = [trLayer(l).eject() for l in self.host.layers]

		return Glyph(
			core_layers,
			name=self.name,
			mark=self.mark,
			unicodes=list(self.unicodes),
			note=self.note,
			# guidelines on Glyph stay empty — FL only has per-layer guides;
			# anything ejected from FL ends up on Layer.guidelines.
			guidelines=[],
		)

	def mount(self, core_glyph, layer_names=None):
		'''Push core Glyph metadata + geometry back into the FL host.

		Mounts each matching layer's shapes / anchors / guidelines via
		trLayer.mount, and copies glyph-level metadata (note, unicodes, mark).

		Glyph-level guidelines (UFO allows them on <glyph> as well as on
		layers) have no direct FL equivalent — FL only stores guidelines
		per layer. They are pushed into every matching FL layer so no data
		is silently lost. A subsequent eject will return them as per-layer
		guides; this asymmetry is FL's data model, not ours.

		Args:
			core_glyph (Glyph)         : pure core glyph to push
			layer_names (list or None) : restrict mount to these layers;
			                             None means all layers in core_glyph
		'''
		# - Per-layer mount
		target = layer_names or [l.name for l in core_glyph.layers]
		extra_guides = list(getattr(core_glyph, 'guidelines', None) or [])

		for layer_name in target:
			core_layer = core_glyph.layer(layer_name)
			if core_layer is None:
				continue

			fl_layer = None
			for fl in self.host.layers:
				if fl.name == layer_name:
					fl_layer = fl
					break
			if fl_layer is None:
				continue

			# Stash extra guides on the core_layer briefly so trLayer.mount
			# writes them alongside the layer's own guides. Restore after.
			original = list(getattr(core_layer, 'guidelines', None) or [])
			if extra_guides:
				core_layer.guidelines = original + extra_guides
			try:
				trLayer(fl_layer).mount(core_layer)
			finally:
				core_layer.guidelines = original

		# - Glyph-level metadata
		if getattr(core_glyph, 'note', None) is not None:
			self.note = core_glyph.note

		if core_glyph.unicodes:
			# Only overwrite when source has unicodes — preserves FL state
			# in the (rare) case the core glyph was constructed without any.
			self.unicodes = list(core_glyph.unicodes)

		if getattr(core_glyph, 'mark', None) is not None:
			self.mark = core_glyph.mark
