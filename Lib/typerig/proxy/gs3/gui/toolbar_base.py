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
#
# Folding: each captioned section gets a disclosure arrow. A section runs
# from its caption to the next caption; every control on self.group falls
# into the section that holds its vertical centre, so builders need no
# fold code. Folding hides the section body, moves later sections up and
# calls on_height(h) so the host can resize the sidebar section. Folded
# sections are kept per Toolbar class in NSUserDefaults.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import vanilla
from AppKit import NSColor, NSUserDefaults, NSDisclosureBezelStyle, NSPushOnPushOffButton

from .panel_base     import TRPanelBase
from .masthead       import TRMasthead
from .widgets        import GridIconButton
from .palette_config import PALETTE
from .typerig_bootstrap import get_node_actions, get_curve_actions, get_contour_actions, get_cut_actions

# - Layout aliases — values live in palette_config.py. Do NOT redeclare.
BTN       = PALETTE.BTN
ICON_PT   = PALETTE.ICON_PT
GAP       = PALETTE.GAP
PAD       = PALETTE.PAD
COLS      = PALETTE.COLS
SEP       = PALETTE.SEP
MAST_H    = PALETTE.MAST_H
ENTRY     = PALETTE.ENTRY
CAP       = PALETTE.CAPTION
CELL      = BTN + GAP


class _FoldArrow(vanilla.Button):
	'''Disclosure triangle before a section caption: on = open.'''
	frameAdjustments = None		# draw exactly posSize

	def __init__(self, posSize, callback):
		super().__init__(posSize, '', callback=callback)
		ns = self.getNSButton()
		ns.setBezelStyle_(NSDisclosureBezelStyle)
		ns.setButtonType_(NSPushOnPushOffButton)
		ns.setState_(1)


class TRToolbarBase(TRPanelBase):
	'''Base class for TR Toolbars. Subclasses set `name` and implement
	build_toolbar(), placing items with flow() / field() / separator().

	show_masthead : False for a Toolbar that needs no scope pills.
	foldable      : False for no fold arrows on the section captions.
	on_height     : set by the host; on_height(h) runs after a fold
	                changes content_h.
	'''
	show_masthead = True
	foldable      = True
	on_height     = None

	# - Build (called once by TRPanelBase.__init__) -----------------------
	def build(self):
		self._y, self._col = 0, 0
		self._sections, self._section_top = [], None
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
		self._full_h = self._y - GAP + PAD
		self._collect_sections()
		return self._place_sections()		# content height, read by the host

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

	# - Entry fields (presets in palette_config.PALETTE.ENTRY) ------------
	def entry(self, name, preset, factory, tooltip=None, cells=None):
		'''Place any non-button control on the grid. Shared by every entry
		kind so they size and align the same way.

		preset  : a PALETTE.ENTRY.<KIND> namespace (STYLE / CELLS / H)
		factory : callable(posSize, sizeStyle) -> vanilla control
		cells   : width override in grid cells; None = preset.CELLS
		          (preset.CELLS None = the full row)
		Starts a new row when the entry does not fit the current one; height
		is preset.H or the control's natural height, centred vertically on
		the button row. Stored as self.group.<name>; returns the control.
		'''
		cells = cells or preset.CELLS or COLS
		cells = min(cells, COLS)
		if self._col + cells > COLS:
			self.newline()
		x, y, _, _ = self._cell()
		w = cells * BTN + (cells - 1) * GAP
		ctrl = factory((x, y, w, BTN), preset.STYLE)
		h = preset.H or self._natural_height(ctrl)
		ctrl.setPosSize((x, y + (BTN - h) / 2., w, h))
		if tooltip:
			ctrl.setToolTip(tooltip)
		setattr(self.group, name, ctrl)
		for _ in range(cells):
			self._advance()
		return ctrl

	@staticmethod
	def _natural_height(ctrl):
		h = ctrl._nsObject.intrinsicContentSize().height		# vanilla has no common public NSView accessor
		return h if h > 0 else BTN		# no intrinsic height -> button height

	def field(self, name, value, tooltip=None, cells=None):
		'''Numeric EditText (ENTRY.NUM). Read with self.group.<name>.get().'''
		return self.entry(name, ENTRY.NUM,
			lambda ps, st: vanilla.EditText(ps, value, sizeStyle=st), tooltip, cells)

	def text(self, name, value='', tooltip=None, cells=None, callback=None):
		'''Free-text EditText (ENTRY.TEXT); full row by default.'''
		return self.entry(name, ENTRY.TEXT,
			lambda ps, st: vanilla.EditText(ps, value, sizeStyle=st, callback=callback), tooltip, cells)

	def popup(self, name, items, tooltip=None, cells=None, callback=None):
		'''PopUpButton (ENTRY.POPUP). Read the index with self.group.<name>.get().'''
		return self.entry(name, ENTRY.POPUP,
			lambda ps, st: vanilla.PopUpButton(ps, items, sizeStyle=st, callback=callback), tooltip, cells)

	def combo(self, name, items, tooltip=None, cells=None, callback=None):
		'''ComboBox (ENTRY.COMBO): pick from items or type a value.'''
		return self.entry(name, ENTRY.COMBO,
			lambda ps, st: vanilla.ComboBox(ps, items, sizeStyle=st, callback=callback), tooltip, cells)

	def checkbox(self, name, title, value=False, tooltip=None, cells=None, callback=None):
		'''CheckBox with a short title (ENTRY.CHECK).'''
		return self.entry(name, ENTRY.CHECK,
			lambda ps, st: vanilla.CheckBox(ps, title, value=value, sizeStyle=st, callback=callback), tooltip, cells)

	def slider(self, name, min_value, max_value, value, tooltip=None, cells=None, callback=None):
		'''Slider (ENTRY.SLIDER).'''
		return self.entry(name, ENTRY.SLIDER,
			lambda ps, st: vanilla.Slider(ps, minValue=min_value, maxValue=max_value, value=value,
			                              sizeStyle=st, callback=callback), tooltip, cells)

	def label(self, name, title, tooltip=None, cells=None):
		'''Short caption TextBox (ENTRY.LABEL).'''
		return self.entry(name, ENTRY.LABEL,
			lambda ps, st: vanilla.TextBox(ps, title, sizeStyle=st), tooltip, cells)

	def separator(self, key, title=None):
		'''Close the row and leave SEP space before the next section, with a
		thin line when PALETTE.SEP_LINE is on, then the section caption
		`title` (see caption()). `key` must be unique.'''
		self.newline()
		if title:
			self._section_top = self._y - GAP		# bottom of the last row
		if PALETTE.SEP_LINE:
			y = self._y - GAP + SEP // 2
			setattr(self.group, 'sep_' + key, vanilla.HorizontalLine((PAD, y, -PAD, 1)))
		self._y += SEP
		if title:
			self.caption(key, title)

	def caption(self, key, title):
		'''Section caption at the start of a new row (PALETTE.CAPTION): small
		secondary-colour text, stored as self.group.cap_<key>. Use it directly
		for the first section, which follows the masthead separator.
		With CAP.FOLD a disclosure arrow (self.group.fold_<key>) folds the
		section that starts here.'''
		if not CAP.SHOW:
			return None
		self.newline()
		top, self._section_top = self._section_top, None
		fold = self.foldable and CAP.FOLD
		x = PAD + CAP.INDENT + (CAP.FOLD_W if fold else 0)
		box = vanilla.TextBox((x, self._y, -PAD, BTN), title, sizeStyle=CAP.STYLE)
		ns = box.getNSTextField()
		ns.setTextColor_(NSColor.secondaryLabelColor())
		h = CAP.H or ns.intrinsicContentSize().height
		box.setPosSize((x, self._y, -PAD, h))
		setattr(self.group, 'cap_' + key, box)
		if fold:
			setattr(self.group, 'fold_' + key, _FoldArrow(
				(PAD + CAP.INDENT, self._y + (h - CAP.FOLD_W) / 2., CAP.FOLD_W, CAP.FOLD_W),
				callback=lambda s, k=key: self.set_folded(k, not s.getNSButton().state())))
			self._open_section(key, self._y if top is None else top, self._y + h)
		self._y += h + CAP.GAP
		return box

	# - Folding sections --------------------------------------------------
	def _open_section(self, key, top, cap_bottom):
		if self._sections:
			self._sections[-1]['end'] = top
		self._sections.append(dict(key=key, top=top, cap_bottom=cap_bottom,
			end=None, folded=False, head=[], body=[], was_hidden=[]))

	def _collect_sections(self):
		'''Sort every control on self.group into its section by its vertical
		centre: the caption row is the head (always shown), the rest the body.'''
		if not self._sections:
			return
		self._sections[-1]['end'] = self._y - GAP
		for obj in list(vars(self.group).values()):
			if not isinstance(obj, vanilla.VanillaBaseObject):
				continue
			pos = obj.getPosSize()
			if pos[1] < 0 or pos[3] <= 0:
				continue		# bottom-anchored or stretching: not in the flow
			c = pos[1] + pos[3] / 2.
			for s in reversed(self._sections):
				if c >= s['top']:
					s['head' if c < s['cap_bottom'] else 'body'].append((obj, tuple(pos)))
					break
		folded = self._load_folds()
		for s in self._sections:
			if s['key'] in folded:
				self._fold(s, True)

	def _fold(self, s, folded):
		s['folded'] = folded
		if folded:
			s['was_hidden'] = [obj._nsObject.isHidden() for obj, _ in s['body']]
			for obj, _ in s['body']:
				obj.show(False)
		else:
			for (obj, _), hidden in zip(s['body'], s['was_hidden']):
				obj.show(not hidden)
		arrow = getattr(self.group, 'fold_' + s['key'], None)
		if arrow is not None:
			arrow.getNSButton().setState_(0 if folded else 1)

	def _place_sections(self):
		'''Move each section up by the height folded above it; returns the
		content height.'''
		shift = 0
		for s in self._sections:
			for obj, (x, y, w, h) in s['head'] + s['body']:
				obj.setPosSize((x, y - shift, w, h))
			if s['folded']:
				shift += s['end'] - s['cap_bottom'] - CAP.FOLD_GAP
		return self._full_h - shift

	def set_folded(self, key, folded):
		'''Fold or unfold section `key`, remember it, and tell the host the
		new height through on_height.'''
		for s in self._sections:
			if s['key'] == key:
				break
		else:
			return
		if s['folded'] != bool(folded):
			self._fold(s, bool(folded))
			self._save_folds()
		self.content_h = self._place_sections()
		if self.on_height is not None:
			self.on_height(self.content_h)

	def folded_sections(self):
		return [s['key'] for s in self._sections if s['folded']]

	def _fold_key(self):
		return 'TypeRig.Toolbar.%s.folded' % self.__class__.__name__

	def _load_folds(self):
		try:
			return set(NSUserDefaults.standardUserDefaults().arrayForKey_(self._fold_key()) or ())
		except Exception:
			return set()

	def _save_folds(self):
		NSUserDefaults.standardUserDefaults().setObject_forKey_(self.folded_sections(), self._fold_key())

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

	def run_cut(self, op):
		'''op(trGlyph, scope, NodeActions, ContourActions, cut_npa)'''
		NodeActions, _ = get_node_actions()
		CA             = get_contour_actions()
		cut_npa        = get_cut_actions()
		self.run(lambda g, sc: op(g, sc, NodeActions, CA, cut_npa))
