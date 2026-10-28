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
SORT_KIND = '_tr_kind_rank'	# sort key of the dot column: kind order in the colour map


# - Colours and dots ------------------------------------------------------
def ns_color(color):
	'''NSColor from a class-method name ('systemGreenColor'), an NSColor, or None.'''
	if color is None or isinstance(color, AppKit.NSColor):
		return color
	return getattr(AppKit.NSColor, color)()


_dots = {}

_DOT_SCALE = 2		# bitmap pixels per pt (Retina)

def dot_image(color, filled=False, d=None, line=None):
	'''Cached NSImage of a circle, d x d pt: filled, or hollow with a `line`
	outline. color: as ns_color; None = an empty image (keeps the column).

	Rendered once into a bitmap, in the app's current light / dark
	appearance (part of the cache key). No drawing-handler block: AppKit
	may call such a block at any time, also while Glyphs quits, and a
	Python callback there can hang or crash the app.'''
	d = TL.DOT_D if d is None else d
	line = TL.DOT_LINE if line is None else line
	app = AppKit.NSApplication.sharedApplication()
	appearance = app.effectiveAppearance()
	key = (color if not isinstance(color, AppKit.NSColor) else id(color), bool(filled), d, line,
	       appearance.name() if appearance is not None else None)
	if key in _dots:
		return _dots[key]
	px = int(round(d * _DOT_SCALE))
	rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
		None, px, px, 8, 4, True, False, AppKit.NSDeviceRGBColorSpace, 0, 0)
	rep.setSize_((d, d))
	ns = ns_color(color)
	if ns is not None:
		previous = AppKit.NSAppearance.currentAppearance()
		AppKit.NSAppearance.setCurrentAppearance_(appearance)		# resolve system colours
		AppKit.NSGraphicsContext.saveGraphicsState()
		try:
			AppKit.NSGraphicsContext.setCurrentContext_(
				AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
			inset = line / 2. if not filled else 0.5
			oval = AppKit.NSBezierPath.bezierPathWithOvalInRect_(((inset, inset), (d - 2 * inset, d - 2 * inset)))
			if filled:
				ns.setFill()
				oval.fill()
			else:
				ns.setStroke()
				oval.setLineWidth_(line)
				oval.stroke()
		finally:
			AppKit.NSGraphicsContext.restoreGraphicsState()
			AppKit.NSAppearance.setCurrentAppearance_(previous)
	image = AppKit.NSImage.alloc().initWithSize_((d, d))
	image.addRepresentation_(rep)
	_dots[key] = image
	return image


# - Cells without Auto Layout ---------------------------------------------
# vanilla's List2 cells use Auto Layout: EditTextList2Cell pins its text
# field with "H:|[editText]|", ImageList2Cell is an "auto" view with no
# constraints. In TR Panel (a window already under Auto Layout) the text
# width then propagated up: tab view width >= content, the SplitView
# re-sized its panes and the list collapsed to 2 px; Glyphs later hung
# (seen 2026-10-18, GS4). These cells are frame-based: a plain container
# view with autoresizing masks and no constraints. List2 only needs
# _nsObject, set(), get() on a cell.
_FLEX_W  = AppKit.NSViewWidthSizable
_FLEX_TB = AppKit.NSViewMinYMargin | AppKit.NSViewMaxYMargin		# centred vertically
_FLEX_LR = AppKit.NSViewMinXMargin | AppKit.NSViewMaxXMargin		# centred horizontally


class TRTextCell(object):
	'''Read-only text cell for List2 / TRTintList, vertically centred.'''
	def __init__(self, editable=False, callback=None, **kwargs):
		field = AppKit.NSTextField.labelWithString_('')
		field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
		h = field.intrinsicContentSize().height
		pad = TL.CELL_PAD
		w = TL.CELL_W
		view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (w, h + 2 * pad)))
		field.setFrame_(((pad, pad), (w - 2 * pad, h)))
		field.setAutoresizingMask_(_FLEX_W | _FLEX_TB)
		view.addSubview_(field)
		self._nsObject, self._field = view, field

	def set(self, value):
		self._field.setStringValue_('' if value is None else str(value))

	def get(self):
		return self._field.stringValue()


class TRImageCell(object):
	'''Image cell (dot column), centred both ways, drawn at its own size.'''
	def __init__(self, editable=False, callback=None, **kwargs):
		d = TL.DOT_D
		pad = TL.CELL_PAD
		view = AppKit.NSView.alloc().initWithFrame_(((0, 0), (d + 2 * pad, d + 2 * pad)))
		image = AppKit.NSImageView.alloc().initWithFrame_(((pad, pad), (d, d)))
		image.setImageScaling_(AppKit.NSImageScaleNone)
		image.setAutoresizingMask_(_FLEX_LR | _FLEX_TB)
		view.addSubview_(image)
		self._nsObject, self._image = view, image

	def set(self, value):
		self._image.setImage_(value)

	def get(self):
		return self._image.image()


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


# The delegate only forwards to the Python wrapper (TRTintList): the ObjC
# class lives for the whole Glyphs session, the wrapper is re-imported, so
# behaviour changes made in the wrapper take effect on a module reload.
def _delegate_did_add_row_view(self, tableView, rowView, row):
	try:
		rowView.setBackgroundColor_(self.vanillaWrapper().row_tint(row))
	except Exception as error:
		print('[TRTintList] row tint:', error)


def _delegate_sort_changed(self, tableView, oldDescriptors):
	try:
		self.vanillaWrapper().sort_changed()
	except Exception as error:
		print('[TRTintList] sort:', error)
		self._updateArrangedIndexes()


# An ObjC class can be defined once per process and is reused on a module
# reload. Its name carries a version: bump _DELEGATE_VERSION whenever the
# delegate's methods change, or a running Glyphs keeps the old class (seen
# 2026-10-18: the one-column sort fix did not take effect without a restart).
_DELEGATE_VERSION = 2
_DELEGATE_NAME = str('TRTintListDelegate_v%d' % _DELEGATE_VERSION)
try:
	TRTintListDelegate = objc.lookUpClass(_DELEGATE_NAME)
except objc.nosuchclass_error:
	TRTintListDelegate = type(_DELEGATE_NAME, (VanillaList2DataSourceAndDelegate,), dict(
		initWithTableView_=_delegate_init,
		tableView_didAddRowView_forRow_=_delegate_did_add_row_view,
		tableView_sortDescriptorsDidChange_=_delegate_sort_changed,
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

	Sorting (allowsSorting, default True): clicking a column title sorts by
	it. Columns are sortable unless their description says sortable=False;
	the dot column sorts by colour: the order of the kinds in `colors`
	(unknown kinds last). One column at a time: a new column sorts
	ascending, the same column again toggles; ties keep the item order. Item indexes (get, getSelectedIndexes,
	setRowFilled) do not change when sorted; getArrangedIndexes gives the
	order on screen.
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
		# Read-only columns without their own cell get TRTextCell (no Auto
		# Layout, see above); editable columns keep vanilla's cell
		columns = []
		for desc in columnDescriptions:
			desc = dict(desc)
			if 'cellClass' not in desc and not desc.get('editable'):
				desc['cellClass'] = TRTextCell
			desc.setdefault('sortable', True)		# vanilla's default is not sortable
			columns.append(desc)
		if dots:		# sortable below, by colour: its value is an image
			columns.insert(0, dict(identifier=DOT_ID, title='', width=TL.DOT_COL_W, sortable=False,
			                       cellClass=TRImageCell, getFunction=self._dot_for_item))
		kwargs.setdefault('alternatingRowColors', False)
		kwargs.setdefault('allowsSorting', True)
		super(TRTintList, self).__init__(posSize, list(items), columnDescriptions=columns,
		                                 selectionCallback=self._on_selection, **kwargs)
		if dots and self._allowsSorting:
			# The dot column sorts by a key of its own; List2 looks a sort key
			# up in the data source's getters (no public API for that)
			self._dataSourceAndDelegate._valueGetters[SORT_KIND] = dict(function=self._kind_rank)
			column = self.getNSTableView().tableColumnWithIdentifier_(DOT_ID)
			column.setSortDescriptorPrototype_(
				AppKit.NSSortDescriptor.sortDescriptorWithKey_ascending_(SORT_KIND, True))
			column.setHeaderToolTip_('Sort by colour')

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

	def _kind_rank(self, item):
		'''Sort key of the dot column: position of the kind in the colour map.'''
		order = list(self._color_keys)
		kind = self.kind(item)
		return order.index(kind) if kind in order else len(order)

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
		# One item, not arrangedItems(): that builds a list of every item, per
		# drawn row (40k pairs in TR Kern: 74 ms a row, 2026-10-27)
		dsd = self._dataSourceAndDelegate
		item = dsd._getItemForRow(row) if 0 <= row < len(dsd.arrangedIndexes()) else None
		color = self._colors.get(self.kind(item)) if item is not None else None
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
	def sort_changed(self):
		'''A column title was clicked (table delegate). One sort column at a
		time: NSTableView keeps every column clicked before as a secondary key
		in its old direction (after Name twice and Type, masters showed Regular
		above Light). Keep the clicked column only; ties stay in item order.'''
		tableView = self.getNSTableView()
		descriptors = tableView.sortDescriptors()
		if len(descriptors) > 1:
			tableView.setSortDescriptors_(descriptors[:1])		# comes back here once more
			return
		self._dataSourceAndDelegate._updateArrangedIndexes()

	def resetSort(self):
		'''Back to item order (as given to set()): clear the column sort.'''
		self.getNSTableView().setSortDescriptors_([])		# delegate -> sort_changed -> rearrange

	def _on_selection(self, sender):
		# Not getSelectedItems(): vanilla's List2 compares item indexes with row
		# indexes there, so on a sorted list it returns the wrong items (the
		# wrong row's dot filled, 2026-10-18). getSelectedIndexes maps rows right.
		# The data source's own list, not get(): that copies every item per click
		items = self._dataSourceAndDelegate.items() if self._itemsWereDict else self.get()
		self._selected = {id(items[i]) for i in self.getSelectedIndexes()}
		self._refresh_dots()
		if self._user_selection is not None:
			self._user_selection(self)

	def setSelectedIndexes(self, indexes):
		'''Unsorted: item index = row index, select directly (vanilla maps
		every item to its row first).'''
		tableView = self.getNSTableView()
		if tableView.sortDescriptors():
			return super(TRTintList, self).setSelectedIndexes(indexes)
		rows = AppKit.NSMutableIndexSet.indexSet()
		for index in indexes:
			rows.addIndex_(index)
		tableView.selectRowIndexes_byExtendingSelection_(rows, False)

	def _refresh_dots(self):
		'''Reload the dot column of the rows that have a view (keeps selection
		and row views). Rows without one get their dot when they are drawn.'''
		tableView = self.getNSTableView()
		column = tableView.columnWithIdentifier_(DOT_ID)
		if column < 0 or tableView.numberOfRows() == 0:
			return
		rows = AppKit.NSMutableIndexSet.indexSet()
		tableView.enumerateAvailableRowViewsUsingBlock_(lambda rowView, row: row >= 0 and rows.addIndex_(row))
		if rows.count():
			tableView.reloadDataForRowIndexes_columnIndexes_(rows, AppKit.NSIndexSet.indexSetWithIndex_(column))

	def _refresh_rows(self):
		'''Re-tint the row views on screen; new ones are tinted by the delegate.'''
		tableView = getattr(self, '_tableView', None)
		if tableView is None:
			return
		tableView.enumerateAvailableRowViewsUsingBlock_(
			lambda rowView, row: rowView.setBackgroundColor_(self.row_tint(row)))
