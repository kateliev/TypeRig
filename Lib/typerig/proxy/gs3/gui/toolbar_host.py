# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Toolbar — host a TRToolbarBase in a Glyphs sidebar palette
#
# Each Toolbar bundle (.glyphsPalette) keeps only a tiny PalettePlugin
# subclass (its own NSPrincipalClass name); everything else is here:
#
#   from GlyphsApp.plugins import PalettePlugin
#
#   class TypeRigMyToolbar(PalettePlugin):
#       @objc.python_method
#       def settings(self):
#           from typerig.proxy.gs3.gui.toolbar_host import install_toolbar
#           from my_toolbar import MyToolbar
#           install_toolbar(self, MyToolbar, 'TR My Toolbar')
#
#       @objc.python_method
#       def __file__(self):
#           return __file__
#
# Glyphs makes one palette instance per document window and calls
# settings() from init(), before it sets the window controller — so the
# Toolbar's font is resolved lazily, on each click. No per-Toolbar Glyphs
# callbacks: an unremoved callback can crash Glyphs on quit. Observers on
# the observer row (observer.py) are one per session and remove their
# callbacks on NSApplicationWillTerminate.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import traceback

import vanilla
from AppKit import NSViewWidthSizable

from .palette_config import PALETTE
from .icon_font      import register_icon_font
from .scope_state    import TRScopeState

# Glyphs orders sidebar palettes by sortID(), lowest first. PalettePlugin.init
# sets 0 (top) before calling settings(); Glyphs' own palette IDs are not
# published. A Toolbar goes after them by default; Toolbars order among
# themselves by passing e.g. SORT_LAST + 10, + 20.
SORT_LAST = 10000


def window_font(plugin):
	'''The font of the document window the palette instance lives in, or None.'''
	wc = plugin.windowController()
	doc = wc.document() if wc is not None else None
	return doc.font if doc is not None else None


def install_toolbar(plugin, toolbar_cls, title, trace=None, sort_id=SORT_LAST):
	'''Build `toolbar_cls` (a TRToolbarBase) into `plugin` (a PalettePlugin)
	from inside its settings(). Sets plugin.name / sortId / dialog / min / max and
	keeps the Python owners alive on the plugin (state, toolbar,
	paletteView). Returns True on success; on failure prints the traceback
	(and passes it to `trace`) and leaves plugin.dialog None, which Glyphs
	shows as an empty section.
	'''
	plugin.name = title
	plugin.sortId = sort_id		# sidebar position: lower = higher up
	try:
		register_icon_font()
		plugin.state = TRScopeState(font_resolver=lambda: window_font(plugin))

		W = PALETTE.W
		toolbar = toolbar_cls(state=plugin.state, posSize=(0, 0, -0, -0))
		H = toolbar.content_h

		plugin.paletteView = vanilla.Window((W, H))		# never shown; vanilla needs a parent
		plugin.paletteView.group = vanilla.Group((0, 0, W, H))
		plugin.paletteView.group.toolbar = toolbar.group
		plugin.toolbar = toolbar		# keeps button callbacks alive

		plugin.dialog = plugin.paletteView.group.getNSView()
		plugin.dialog.setAutoresizingMask_(NSViewWidthSizable)
		plugin.min = min(PALETTE.MIN_H, H)
		plugin.max = H
		if trace is not None:
			trace('install_toolbar OK: %s %dx%d' % (title, W, H))
		return True
	except Exception:
		msg = '[%s] install_toolbar failed:\n%s' % (title, traceback.format_exc())
		print(msg)
		if trace is not None:
			trace(msg)
		return False
