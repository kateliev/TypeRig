# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Glyphs GUI — foldable report tree (TRTreeView)
#
# A vanilla.ScrollView around an NSOutlineView (vanilla has no outline
# view) for reports organised per test: one root per test, sections,
# findings — the Glyphs counterpart of the FL Icon Audit / Preflight tree.
#
#     from typerig.proxy.gs3.gui.tree_view import TRTreeView
#     self.g.tree = TRTreeView((0, 0, -0, -0), selectionCallback=self._on_select)
#     self.g.tree.set([{'title': 'Test', 'detail': '2 found', 'kind': 'warn', 'children': [...]}])
#
# Nodes are dicts: 'title' (first column, with the disclosure triangle),
# 'detail' (second column), 'kind' (colour of the title: UI.TREE.KIND_COLORS),
# 'children' (list of nodes); other keys are kept for the caller; a badge
# function adds a mark after the title
# (getSelected returns the node dicts). Roots are bold. set() opens the
# first UI.TREE.EXPAND levels; Option-click on a triangle opens a whole
# branch (AppKit). Children are wrapped on first display, so a large tree
# costs nothing until it is opened. The columns share the width (TITLE_W :
# DETAIL_W); a cut cell shows its whole text in a tooltip (AppKit).
# -------------------------------------------------------------------------

from __future__ import division, print_function, unicode_literals

import weakref

import objc
import AppKit
import vanilla

from .config import UI

TR = UI.TREE
COLUMNS = (('title', 'Finding'), ('detail', 'Detail'))


def _ns_color(color):
	if color is None or isinstance(color, AppKit.NSColor):
		return color
	return getattr(AppKit.NSColor, color)()


# - ObjC classes ------------------------------------------------------------
# Defined once per process and reused on a module reload (see tint_list.py):
# bump _VERSION whenever their methods change.
_VERSION = 2


def _children(self, item):
	'''The ObjC items under item (None = roots), wrapped on first use.'''
	tree = self._tr_tree()
	if tree is None:
		return []
	if item is None:
		return tree._roots
	if item._tr_kids is None:
		item._tr_kids = [_wrap(n) for n in item._tr_node.get('children') or ()]
	return item._tr_kids


def _number_of_children(self, outline, item):
	return len(_children(self, item))


def _child(self, outline, index, item):
	return _children(self, item)[index]


def _expandable(self, outline, item):
	return bool(item._tr_node.get('children'))


def _value(self, outline, column, item):
	ident = str(column.identifier())
	text = item._tr_node.get(ident, '')
	tree = self._tr_tree()
	if ident == 'title' and tree is not None and tree._badge is not None:
		badge = tree._badge(item._tr_node)
		if badge:
			text = '%s%s' % (text, badge)
	return text


def _will_display(self, outline, cell, column, item):
	tree = self._tr_tree()
	if tree is None:
		return
	root = outline.levelForItem_(item) == 0
	size = AppKit.NSFont.systemFontSize()
	cell.setFont_(AppKit.NSFont.boldSystemFontOfSize_(size) if root else AppKit.NSFont.systemFontOfSize_(size))
	color = tree._colors.get(item._tr_node.get('kind')) if str(column.identifier()) == 'title' else None
	selected = outline.isRowSelected_(outline.rowForItem_(item))
	cell.setTextColor_(color if color is not None and not selected else AppKit.NSColor.labelColor())


def _no_edit(self, outline, column, item):
	return False


def _selection_changed(self, notification):
	tree = self._tr_tree()
	if tree is not None and tree._selection_callback is not None:
		tree._selection_callback(tree)


def _double_click(self, sender):
	tree = self._tr_tree()
	if tree is not None and tree._double_click_callback is not None and sender.clickedRow() >= 0:
		tree._double_click_callback(tree)


_ITEM_NAME = str('TRTreeItem_v%d' % _VERSION)
_SOURCE_NAME = str('TRTreeSource_v%d' % _VERSION)
try:
	TRTreeItem = objc.lookUpClass(_ITEM_NAME)
except objc.nosuchclass_error:
	TRTreeItem = type(_ITEM_NAME, (AppKit.NSObject,), {})
try:
	TRTreeSource = objc.lookUpClass(_SOURCE_NAME)
except objc.nosuchclass_error:
	TRTreeSource = type(_SOURCE_NAME, (AppKit.NSObject,), dict(
		outlineView_numberOfChildrenOfItem_=_number_of_children,
		outlineView_child_ofItem_=_child,
		outlineView_isItemExpandable_=_expandable,
		outlineView_objectValueForTableColumn_byItem_=_value,
		outlineView_willDisplayCell_forTableColumn_item_=_will_display,
		outlineView_shouldEditTableColumn_item_=_no_edit,
		outlineViewSelectionDidChange_=_selection_changed,
		trDoubleClick_=_double_click,
	))


def _wrap(node):
	item = TRTreeItem.alloc().init()
	item._tr_node = node
	item._tr_kids = None
	return item


# - Widget ----------------------------------------------------------------
class TRTreeView(vanilla.ScrollView):
	'''Foldable tree of report nodes (see the file header).

	Arguments:
		columns              : ((identifier, title), ...); the first has the triangles
		selectionCallback    : f(sender) when the selection changes
		doubleClickCallback  : f(sender) on a double click on a row
		colors               : {kind: NSColor name | NSColor | None}; UI.TREE.KIND_COLORS
		badge                : f(node) -> text appended to the title (e.g. a mark on rows that can be fixed)
	'''
	def __init__(self, posSize, columns=COLUMNS, selectionCallback=None, doubleClickCallback=None, colors=None,
	             badge=None):
		self._badge = badge
		self._roots = []
		self._nodes = []
		self._selection_callback = selectionCallback
		self._double_click_callback = doubleClickCallback
		self._colors = dict((k, _ns_color(v)) for k, v in (TR.KIND_COLORS if colors is None else colors).items())
		outline = AppKit.NSOutlineView.alloc().initWithFrame_(((0, 0), (100, 100)))
		for i, (ident, title) in enumerate(columns):
			col = AppKit.NSTableColumn.alloc().initWithIdentifier_(ident)
			col.headerCell().setStringValue_(title)
			col.setEditable_(False)
			col.dataCell().setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
			col.setWidth_(TR.TITLE_W if i == 0 else TR.DETAIL_W)
			col.setMinWidth_(TR.TITLE_MIN if i == 0 else TR.DETAIL_MIN)
			col.setResizingMask_(AppKit.NSTableColumnAutoresizingMask | AppKit.NSTableColumnUserResizingMask)
			outline.addTableColumn_(col)
			if i == 0:
				outline.setOutlineTableColumn_(col)
		outline.setColumnAutoresizingStyle_(AppKit.NSTableViewUniformColumnAutoresizingStyle)
		outline.setIndentationPerLevel_(TR.INDENT)
		outline.setUsesAlternatingRowBackgroundColors_(True)
		outline.setAllowsMultipleSelection_(True)
		outline.setAutosaveExpandedItems_(False)
		self._source = TRTreeSource.alloc().init()
		self._source._tr_tree = weakref.ref(self)
		outline.setDataSource_(self._source)
		outline.setDelegate_(self._source)
		outline.setTarget_(self._source)
		outline.setDoubleAction_(b'trDoubleClick:')
		self._outline = outline
		super(TRTreeView, self).__init__(posSize, outline, hasHorizontalScroller=False, autohidesScrollers=True)
		outline.sizeToFit()

	def getNSOutlineView(self):
		return self._outline

	# - Data ------------------------------------------------------------------
	def set(self, nodes, expand=None):
		'''Show these root nodes; open the first `expand` levels (UI.TREE.EXPAND).'''
		self._nodes = list(nodes or [])
		self._roots = [_wrap(n) for n in self._nodes]
		self._outline.reloadData()
		levels = TR.EXPAND if expand is None else expand
		self._expand(self._roots, levels)

	def get(self):
		return list(self._nodes)

	def _expand(self, items, levels):
		if levels <= 0:
			return
		for item in items:
			if item._tr_node.get('children'):
				self._outline.expandItem_(item)
				self._expand(item._tr_kids or [], levels - 1)

	def expandAll(self):
		self._outline.expandItem_expandChildren_(None, True)

	def collapseAll(self):
		self._outline.collapseItem_collapseChildren_(None, True)

	# - Selection ---------------------------------------------------------------
	def getSelected(self):
		'''The selected node dicts, in row order.'''
		rows = self._outline.selectedRowIndexes()
		out = []
		index = rows.firstIndex()
		while index != AppKit.NSNotFound:
			item = self._outline.itemAtRow_(index)
			if item is not None:
				out.append(item._tr_node)
			index = rows.indexGreaterThanIndex_(index)
		return out

	def selectRow(self, row):
		self._outline.selectRowIndexes_byExtendingSelection_(AppKit.NSIndexSet.indexSetWithIndex_(row), False)

	def rowTitles(self):
		'''(level, title) of every visible row: tests and checks.'''
		out = []
		for row in range(self._outline.numberOfRows()):
			item = self._outline.itemAtRow_(row)
			out.append((self._outline.levelForItem_(item), item._tr_node.get('title')))
		return out
