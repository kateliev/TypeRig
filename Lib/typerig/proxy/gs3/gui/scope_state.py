# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — per-host masthead scope
#
# TRMainPanel broadcasts the masthead state by writing `pMode` / `pLayers`
# onto every panel module (`setattr(mod, 'pMode', …)`). That is one state
# per Glyphs session. A sidebar palette lives once per document window, so
# each palette instance owns a TRScopeState instead and passes it to its
# panels (TRPanelBase(state=…)). Panels built without a state keep reading
# the module globals, so TR Panel is unchanged.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals


class TRScopeState(object):
	'''Masthead scope owned by one host (a palette instance, later TR Panel).

	pMode   : int    — 0 glyph, 1 window, 2 selection
	pLayers : tuple  — (active, masters, selected, _) or the picker's
	                   checked-rows list; see scope.py
	font()  : GSFont — the host's font (palette: its window's font),
	                   falling back to Glyphs.font
	'''
	def __init__(self, font_resolver=None):
		self.pMode   = 0
		self.pLayers = (True, False, False, False)
		self._font_resolver = font_resolver         # callable -> GSFont or None

	def font(self):
		if self._font_resolver is not None:
			try:
				f = self._font_resolver()
				if f is not None:
					return f
			except Exception:
				pass
		try:
			from GlyphsApp import Glyphs
		except Exception:
			return None
		return Glyphs.font
