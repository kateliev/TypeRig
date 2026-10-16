# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — base class for tool sub-panels (Node, Delta, Contour, …)
#
# Every tool panel lives in its own module under Panel/ and must export a
# fixed contract that main_panel.TRMainPanel discovers at startup:
#
#   app_name    : str      — tab title (e.g. 'TypeRig | Nodes')
#   app_version : str      — '0.1', '0.2', …
#   pMode       : int      — initial masthead mode (0 glyph, 1 window, 2 selection)
#   pLayers     : tuple    — initial masthead layer scope
#   tool_tab()  : callable — returns the vanilla.Group containing the UI
#
# Historically each panel repeated this block as module-level globals,
# plus its own copies of two tiny utility functions (`_active_glyph`,
# `_get_modifiers`). TRPanelBase + @register_panel absorb both:
#
#   from gui.panel_base import TRPanelBase, register_panel
#
#   @register_panel
#   class NodePanel(TRPanelBase):
#       name    = 'TypeRig | Nodes'
#       version = '0.1'
#       # p_mode / p_layers default to 0 / (True, False, False, False).
#       # Override only if the panel needs a different initial masthead state.
#
#       def build(self):
#           # Place vanilla widgets on self.group. __init__ has already
#           # created the Group; subclasses only populate it.
#           ...
#
# The decorator reads name / version / p_mode / p_layers off the class,
# writes them to the module as app_name / app_version / pMode / pLayers
# so TRMainPanel's existing discovery is unchanged, and installs a
# tool_tab() function that instantiates the class on demand. The masthead's
# live broadcast (`_broadcast_to`) continues to mutate the module globals,
# which the base class reads back through `self.p_mode` / `self.p_layers`.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import sys
import traceback

import vanilla


class TRPanelBase(object):
	'''Base class for TypeRig Panel tool panels.

	Subclasses must set `name` and implement `build()`. Everything else is
	optional and has sensible defaults.
	'''

	# - Required contract -------------------------------------------------
	name    = None                            # subclass MUST set
	version = '0.1'

	# - Initial masthead state (TRMainPanel._broadcast_state will overwrite
	# these on the module as the user clicks the mode pills).
	p_mode    = 0
	p_layers  = (True, False, False, False)

	# - Lifecycle ---------------------------------------------------------
	def __init__(self):
		if self.name is None:
			raise TypeError(
				'%s must set a `name` class attribute' % self.__class__.__name__)
		self.group = vanilla.Group((0, 0, -0, -0))
		self.build()

	def build(self):
		'''Populate `self.group` with vanilla widgets. Required.'''
		raise NotImplementedError(
			'%s must implement build()' % self.__class__.__name__)

	# - Live masthead state ----------------------------------------------
	# TRMainPanel._broadcast_to assigns `pMode` and `pLayers` to the
	# subclass's own module every time the user flips a pill. Read them
	# back fresh — do NOT cache into self.*.
	@property
	def _module(self):
		return sys.modules[self.__class__.__module__]

	@property
	def pMode(self):
		return getattr(self._module, 'pMode', self.p_mode)

	@property
	def pLayers(self):
		return getattr(self._module, 'pLayers', self.p_layers)

	# - Common utilities (used to live as `_active_glyph` / `_get_modifiers`
	# duplicated in every panel). Call via `self.active_glyph()` etc.
	def active_glyph(self):
		'''Return the current trGlyph, or None if nothing is open/selected.'''
		try:
			from GlyphsApp import Glyphs
		except Exception:
			return None
		if Glyphs.font is None or not Glyphs.font.selectedLayers:
			return None
		gs_glyph = Glyphs.font.selectedLayers[0].parent
		if gs_glyph is None:
			return None
		from typerig.proxy.gs3.objects.glyph import trGlyph
		return trGlyph(gs_glyph)

	def modifiers(self):
		'''Live NSEvent modifier flags: dict with 'shift' / 'alt' / 'ctrl' / 'cmd'.'''
		try:
			from AppKit import (NSEvent,
				NSEventModifierFlagShift,
				NSEventModifierFlagOption,
				NSEventModifierFlagControl,
				NSEventModifierFlagCommand)
			flags = NSEvent.modifierFlags()
			return {
				'shift': bool(flags & NSEventModifierFlagShift),
				'alt':   bool(flags & NSEventModifierFlagOption),
				'ctrl':  bool(flags & NSEventModifierFlagControl),
				'cmd':   bool(flags & NSEventModifierFlagCommand),
			}
		except Exception:
			return {'shift': False, 'alt': False, 'ctrl': False, 'cmd': False}

	def scope(self):
		'''Resolve the masthead scope → (trGlyph, [layer_name, …]).

		Returns (None, None) when there is no active glyph. Returns
		(trGlyph, []) when the current scope is empty by design (user
		has Selected pill on but checked no rows).
		'''
		tr_g = self.active_glyph()
		if tr_g is None:
			return None, None
		from .scope import scope_layers
		return tr_g, scope_layers(self.pMode, self.pLayers, tr_g)

	def run(self, op):
		'''Standard dispatch: resolve scope → undo-wrap → call op → redraw.

		`op` is `callable(trGlyph, scope_layer_names)`. The subclass's
		button callbacks typically do:

		    def on_align_left(self, sender):
		        from typerig.core.actions import node_actions as A
		        from typerig.core.actions import node_panel_actions as npa
		        self.run(lambda g, sc: npa.npa_nodes_align(g, sc, A, 'L'))

		Any Exception inside `op` is caught, logged, and the undo bracket
		is still closed cleanly — the panel stays usable after a failure.
		'''
		tr_g, sc = self.scope()
		if tr_g is None or not sc:
			return
		gs_glyph = tr_g.host
		try: gs_glyph.beginUndo()
		except Exception: pass
		try:
			op(tr_g, sc)
		except Exception:
			print('[%s] op failed:' % self.name)
			print(traceback.format_exc())
		finally:
			try: gs_glyph.endUndo()
			except Exception: pass
		tr_g.update()


# - Discovery glue ----------------------------------------------------------
def register_panel(cls):
	'''Decorator: wire a TRPanelBase subclass into main_panel's discovery.

	Writes the module-level contract (`app_name`, `app_version`, `pMode`,
	`pLayers`, `tool_tab()`) that TRMainPanel._apply_panel_states reads,
	so existing discovery is unchanged. Validates the class on import —
	a typo in `name` or a missing `build()` fails loudly here rather
	than silently falling off the configurator later.
	'''
	if not issubclass(cls, TRPanelBase):
		raise TypeError(
			'@register_panel: %s must subclass TRPanelBase' % cls.__name__)
	if cls.name is None:
		raise TypeError(
			'@register_panel: %s must set `name`' % cls.__name__)

	mod = sys.modules[cls.__module__]
	mod.app_name    = cls.name
	mod.app_version = cls.version
	mod.pMode       = cls.p_mode
	mod.pLayers     = cls.p_layers

	def tool_tab():
		return cls().group
	mod.tool_tab = tool_tab

	return cls
