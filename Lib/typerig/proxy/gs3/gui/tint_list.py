# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — colour-coded list (TRTintList)
#
# A vanilla.List2 whose rows are colour coded by a "kind" value:
#   - a dot column: a circle in the kind's colour, hollow or filled
#   - a full-row tint: the same colour at a low alpha behind the row
#
#     from typerig.proxy.gs3.gui.tint_list import TRTintList
#     self.group.layers = TRTintList((PAD, y, -PAD, LIST_H),
#         [dict(name=l.name, kind=layer_kind(l)) for l in glyph.layers],
#         columnDescriptions=[dict(identifier='name', title='Layer')])
#
# Items are dicts (or objects) with a `kind_key` value ('kind' by default);
# `colors` maps kind -> NSColor class-method name, NSColor or None
# (default UI.TINTLIST.LAYER_COLORS). Defaults (dot size, tint, filled,
# fill-on-select) live in UI.TINTLIST (config.py).
#
# Dot state per row:  shown filled = base XOR (selected and fill_on_select)
#   base     = setRowFilled(...) override, else the list default (setFilled)
#   selected = the row is selected
# With the defaults (hollow, fill on select) a selected row shows a filled
# dot and goes back to hollow when deselected.
#
# Why not willDisplayCell / cell backgrounds: that tints each text cell, not
# the row — coloured "bands" with gaps, fighting the alternating zebra rows
# and missing the check-box column (tried 2026-04, dropped). Here the tint is
# the NSTableRowView background, set in the delegate's
# tableView:didAddRowView:forRow:, with alternating row colours off.
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import types

import objc
import AppKit
import vanilla
from vanilla.vanillaList2 import VanillaList2DataSourceAndDelegate

from .config import UI

TL = UI.TINTLIST
DOT_ID = '_tr_dot'		# identifier of the dot column


# - Colours and dots ------------------------------------------------------
def ns_color(color):
	'''NSColor from a class-method name ('systemGreenColor'), an NSColor, or None.'''
	if color is None or isinstance(color, AppKit.NSColor):
		return color
	return getattr(AppKit.NSColor, color)()


_dots = {}

def dot_image(color, filled=False, d=None, line=None):
	'''Cached NSImage of a circle, d x d pt: filled, or hollow with a `line`
	outline. color: as ns_color; None = an empty image (keeps the column).
	Drawn when displayed, so system colours follow light / dark mode.'''
	d = TL.DOT_D if d is None else d
	line = TL.DOT_LINE if line is None else line
	key = (color if not isinstance(color, AppKit.NSColor) else id(color), bool(filled), d, line)
	if key in _dots:
		return _dots[key]
	ns = ns_color(color)

	def draw(rect):
		if ns is not None:
			inset = line / 2. if not filled else 0.5
			oval = AppKit.NSBezierPath.bezierPathWithOvalInRect_(AppKit.NSInsetRect(rect, inset, inset))
			if filled:
				ns.setFill()
				oval.fill()
			else:
				ns.setStroke()
				oval.setLineWidth_(line)
				oval.stroke()
		return True

	image = AppKit.NSImage.imageWithSize_flipped_drawingHandler_((d, d), False, draw)
	_dots[key] = image
	return image


# - Table delegate: row tint ----------------------------------------------
# vanilla's initWithTableView_ allocates VanillaList2DataSourceAndDelegate by
# name, so a subclass instance would be thrown away. Run the same init code
# with that name bound to the subclass.
def _init_as(cls, base_init):
	glb = dict(base_init.__globals__, VanillaList2DataSourceAndDelegate=cls)
	return types.FunctionType(base_init.__code__, glb, base_init.__name__,
	                          base_init.__defaults__, base_init.__closure__)

_BASE_INIT = VanillaList2DataSourceAndDelegate.initWithTableView_.callable


def _delegate_init(self, tableView):
	return _init_as(TRTintListDelegate, _BASE_INIT)(self, tableView)


def _delegate_did_add_row_view(self, tableView, rowView, row):
	# Logic stays on the Python wrapper (reload-safe: an ObjC class lives for
	# the whole Glyphs session, the wrapper class is re-imported)
	try:
		rowView.setBackgroundColor_(self.vanillaWrapper().row_tint(row))
	except Exception as error:
		print('[TRTintList] row tint:', error)


# An ObjC class can be defined once per process: reuse it on module reload.
try:
	TRTintListDelegate = objc.lookUpClass('TRTintListDelegate')
except objc.nosuchclass_error:
	TRTintListDelegate = type(str('TRTintListDelegate'), (VanillaList2DataSourceAndDelegate,), dict(
		initWithTableView_=_delegate_init,
		tableView_didAddRowView_forRow_=_delegate_did_add_row_view,
	))


# - Widget ----------------------------------------------------------------
class TRTintList(vanilla.List2):
	'''vanilla.List2 colour coded by kind: dot column + row tint.

	Extra arguments (None = the UI.TINTLIST default):
		colors         : {kind: NSColor name | NSColor | None}; LAYER_COLORS
		kind_key       : item key / attribute holding the kind ('kind')
		tint           : row tint alpha, 0 = off (TINT)
		filled         : default dot state, True = filled (FILLED)
		fill_on_select : selected rows flip their dot (FILL_ON_SELECT)
		dots           : False = no dot column (tint only)
	Everything else goes to vanilla.List2; alternatingRowColors defaults to
	False (zebra rows fight the tint). The dot column is added in front of
	columnDescriptions; it is not part of the items.
	'''
	dataSourceAndDelegateClass = TRTintListDelegate

	def __init__(self, posSize, items=(), columnDescriptions=(), colors=None, kind_key='kind',
	             tint=None, filled=None, fill_on_select=None, dots=True,
	             selectionCallback=None, **kwargs):
		self._colors = {}
		self.setColors(TL.LAYER_COLORS if colors is None else colors, refresh=False)
		self._kind_key       = kind_key
		self._tint           = TL.TINT if tint is None else float(tint)
		self._filled         = TL.FILLED if filled is None else bool(filled)
		self._fill_on_select = TL.FILL_ON_SELECT if fill_on_select is None else bool(fill_on_select)
		self._row_filled     = {}		# id(item) -> bool override
		self._selected       = set()	# id(item) of selected items
		self._user_selection = selectionCallback
		columns = list(columnDescriptions)
		if dots:
			columns.insert(0, dict(identifier=DOT_ID, title='', width=TL.DOT_COL_W, sortable=False,
			                       cellClass=vanilla.ImageList2Cell, cellClassArguments=dict(scale='none'),
			                       getFunction=self._dot_for_item))
		kwargs.setdefault('alternatingRowColors', False)
		super(TRTintList, self).__init__(posSize, list(items), columnDescriptions=columns,
		                                 selectionCallback=self._on_selection, **kwargs)

	# - Items ------------------------------------------------------------
	def set(self, items):
		'''Set the items; clears per-row dot overrides.'''
		self._row_filled = {}
		self._selected = set()
		super(TRTintList, self).set(list(items))

	def kind(self, item):
		if isinstance(item, dict):
			return item.get(self._kind_key)
		return getattr(item, self._kind_key, None)

	# - Colours and tint -------------------------------------------------
	def setColors(self, colors, refresh=True):
		'''{kind: NSColor name | NSColor | None}; replaces the map.'''
		self._colors = {k: ns_color(v) for k, v in colors.items()}
		self._color_keys = dict(colors)		# names keep dot_image's cache stable
		if refresh:
			self._refresh_rows()
			self._refresh_dots()

	def getColors(self):
		return dict(self._color_keys)

	def setTint(self, alpha):
		'''Row tint alpha (0 = off).'''
		self._tint = max(0., float(alpha))
		self._refresh_rows()

	def getTint(self):
		return self._tint

	def row_tint(self, row):
		'''Row background for a displayed row (used by the table delegate).'''
		items = self._dataSourceAndDelegate.arrangedItems()
		color = self._colors.get(self.kind(items[row])) if 0 <= row < len(items) else None
		if color is None or self._tint <= 0:
			return AppKit.NSColor.clearColor()
		return color.colorWithAlphaComponent_(self._tint)

	# - Dots -------------------------------------------------------------
	def setFilled(self, value):
		'''Default dot state for every row without an override.'''
		self._filled = bool(value)
		self._refresh_dots()

	def getFilled(self):
		return self._filled

	def setFillOnSelect(self, value):
		'''True: selected rows show the opposite dot state.'''
		self._fill_on_select = bool(value)
		self._refresh_dots()

	def getFillOnSelect(self):
		return self._fill_on_select

	def setRowFilled(self, indexes, value=True):
		'''Base dot state of the items at `indexes` (item indexes, as get());
		value None = back to the list default.'''
		items = self.get()
		for index in indexes:
			key = id(items[index])
			if value is None:
				self._row_filled.pop(key, None)
			else:
				self._row_filled[key] = bool(value)
		self._refresh_dots()

	def isRowFilled(self, index):
		'''Dot state as shown for the item at `index` (selection included).'''
		return self._is_filled(self.get()[index])

	def _is_filled(self, item):
		base = self._row_filled.get(id(item), self._filled)
		return base != (self._fill_on_select and id(item) in self._selected)

	def _dot_for_item(self, item):
		kind = self.kind(item)
		return dot_image(self._color_keys.get(kind), self._is_filled(item))

	def _breakCycles(self):
		# vanilla's own teardown hook (window close): drop the user callback
		self._user_selection = None
		super(TRTintList, self)._breakCycles()

	# - Refresh ----------------------------------------------------------
	def _on_selection(self, sender):
		self._selected = {id(item) for item in self.getSelectedItems()}
		self._refresh_dots()
		if self._user_selection is not None:
			self._user_selection(self)

	def _refresh_dots(self):
		'''Reload the dot column only (keeps selection and row views).'''
		tableView = self.getNSTableView()
		column = tableView.columnWithIdentifier_(DOT_ID)
		rows = tableView.numberOfRows()
		if column < 0 or rows == 0:
			return
		tableView.reloadDataForRowIndexes_columnIndexes_(
			AppKit.NSIndexSet.indexSetWithIndexesInRange_((0, rows)),
			AppKit.NSIndexSet.indexSetWithIndex_(column))

	def _refresh_rows(self):
		'''Re-tint the row views on screen; new ones are tinted by the delegate.'''
		tableView = getattr(self, '_tableView', None)
		if tableView is None:
			return
		tableView.enumerateAvailableRowViewsUsingBlock_(
			lambda rowView, row: rowView.setBackgroundColor_(self.row_tint(row)))
