# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Toolbar — base class for TR Toolbars (Glyphs sidebar palettes)
#
# A Toolbar is a restricted, icon-only TR tool shown as a section of the
# Glyphs sidebar (a .glyphsPalette), named after the FL toolbars. Unlike a
# TR Panel tab it has a fixed width, no tabs and no dialogs; each Toolbar
# carries its own masthead and its own scope (TRScopeState), one instance
# per document window.
#
#   from typerig.proxy.gs3.gui.toolbar_base import TRToolbarBase
#
#   class MyToolbar(TRToolbarBase):
#       name    = 'TypeRig | My Toolbar'
#       version = '0.1'
#
#       def build_toolbar(self):
#           self.flow('nd_', (
#               ('node_add_mid', 'Insert node', lambda: self.run_node(
#                   lambda g, sc, NA, npa: npa.npa_insert(g, sc, NA, .5))),
#           ))
#           self.separator('node')
#           ...
#
# Layout: buttons flow left to right into PALETTE.COLS columns and wrap,
# like FL's TRFlowLayout — once, at build time (vanilla cannot reflow
# live). Every size comes from palette_config.PALETTE; Toolbar code holds
# no layout numbers. See TypeRig-Glyphs Lib/toolbar_guide.md.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import vanilla

from .panel_base     import TRPanelBase
from .masthead       import TRMasthead
from .widgets        import GridIconButton
from .palette_config import PALETTE
from .typerig_bootstrap import get_node_actions, get_curve_actions, get_contour_actions

# - Layout aliases — values live in palette_config.py. Do NOT redeclare.
BTN       = PALETTE.BTN
ICON_PT   = PALETTE.ICON_PT
GAP       = PALETTE.GAP
PAD       = PALETTE.PAD
COLS      = PALETTE.COLS
SEP       = PALETTE.SEP
MAST_H    = PALETTE.MAST_H
FLD_STYLE = PALETTE.FLD_STYLE
CELL      = BTN + GAP


class TRToolbarBase(TRPanelBase):
	'''Base class for TR Toolbars. Subclasses set `name` and implement
	build_toolbar(), placing items with flow() / field() / separator().

	show_masthead : False for a Toolbar that needs no scope pills.
	'''
	show_masthead = True

	# - Build (called once by TRPanelBase.__init__) -----------------------
	def build(self):
		self._y, self._col = 0, 0
		if self.show_masthead:
			self.group.mast = vanilla.Group((0, 0, -0, MAST_H))
			self.masthead = TRMasthead(
				self.group.mast, self.state, height=MAST_H,
				btn=BTN, gap=GAP, margin=PAD, group_gap=PALETTE.MAST_GROUP_GAP,
				icon_pt=ICON_PT, button_class=GridIconButton,
				show_selected=False, show_fold=False)
			self._y = MAST_H
			self.separator('mast')
		else:
			self._y = PAD
		self.build_toolbar()
		self.newline()
		return self._y - GAP + PAD		# content height, read by the host

	def build_toolbar(self):
		'''Place the Toolbar items. Required.'''
		raise NotImplementedError(
			'%s must implement build_toolbar()' % self.__class__.__name__)

	# - Flow grid ---------------------------------------------------------
	def _cell(self):
		return (PAD + self._col * CELL, self._y, BTN, BTN)

	def _advance(self):
		self._col += 1
		if self._col == COLS:
			self._col = 0
			self._y += CELL

	def newline(self):
		'''Finish the current row; the next item starts a new one.'''
		if self._col:
			self._col = 0
			self._y += CELL

	def flow(self, prefix, items):
		'''Place buttons in flow order.

		item: (token, tooltip, callback[, checkable[, name]])
		  token     — icon-font ligature
		  callback  — takes no arguments
		  checkable — True for a toggle
		  name      — attribute suffix when a token is used twice
		Each button is stored as self.group.<prefix><name>.
		Returns {name: GridIconButton}.
		'''
		out = {}
		for item in items:
			token, tooltip, cb = item[:3]
			checkable = len(item) > 3 and item[3]
			name = item[4] if len(item) > 4 else token
			btn = GridIconButton(self._cell(), token, tooltip=tooltip,
			                     checkable=checkable, size=ICON_PT,
			                     callback=lambda s, _c=cb: _c())
			setattr(self.group, prefix + name, btn)
			out[name] = btn
			self._advance()
		return out

	def field(self, name, value, tooltip):
		'''One-cell numeric field in flow order, stored as self.group.<name>.'''
		fld = vanilla.EditText(self._cell(), value, sizeStyle=FLD_STYLE)
		fld.getNSTextField().setToolTip_(tooltip)
		setattr(self.group, name, fld)
		self._advance()
		return fld

	def separator(self, key):
		'''Close the row and draw a thin line between sections.'''
		self.newline()
		y = self._y - GAP + SEP // 2
		#setattr(self.group, 'sep_' + key, vanilla.HorizontalLine((PAD, y, -PAD, 1)))
		self._y += SEP

	# - npa dispatchers (base .run: scope -> undo -> op -> redraw) --------
	def run_node(self, op):
		'''op(trGlyph, scope, NodeActions, npa)'''
		NodeActions, npa = get_node_actions()
		self.run(lambda g, sc: op(g, sc, NodeActions, npa))

	def run_curve(self, op):
		'''op(trGlyph, scope, NodeActions, npa, CurveActions)'''
		NodeActions, npa = get_node_actions()
		CA               = get_curve_actions()
		self.run(lambda g, sc: op(g, sc, NodeActions, npa, CA))

	def run_contour(self, op):
		'''op(trGlyph, scope, NodeActions, npa, ContourActions)'''
		NodeActions, npa = get_node_actions()
		CA               = get_contour_actions()
		self.run(lambda g, sc: op(g, sc, NodeActions, npa, CA))
