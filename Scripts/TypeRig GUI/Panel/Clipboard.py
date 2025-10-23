#FLM: TR: Clipboard
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict
from itertools import groupby
from math import radians
import random

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.node import eNode, eNodesContainer
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.contour import eContour

from typerig.core.base.message import *
from typerig.proxy.fl.actions.contour import TRContourActionCollector
from typerig.proxy.fl.actions.draw import TRDrawActionCollector
from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.application.app import pWorkspace
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, getTRIconFont, TRTransformCtrl, CustomLabel, CustomPushButton, TRFlowLayout
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark

# - Init -------------------------------
global pLayers
global pMode
pLayers = (True, False, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Contour', '1.3'

cfg_addon_reversed = ' (Reversed)'

TRToolFont_path = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont_path)
families = QtGui.QFontDatabase.applicationFontFamilies(font_loaded)
TRFont = QtGui.QFont(families[0], 20)
TRFont.setPixelSize(20)

# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

# - Sub widgets ------------------------
class TRContourCopy(QtGui.QWidget):
	# - Align Contours
	def __init__(self):
		super(TRContourCopy, self).__init__()

		# - Init
		lay_main = QtGui.QVBoxLayout()
		self.contour_clipboard = {}
		self.node_align_state = 'LT'

		# -- Listview
		self.lst_contours = QtGui.QListView()
		self.mod_contours = QtGui.QStandardItemModel(self.lst_contours)
		self.lst_contours.setMinimumHeight(350)
		self.lst_contours.setModel(self.mod_contours)
		
		# -- Quick Tool buttons
		box_contour_copy = QtGui.QGroupBox()
		box_contour_copy.setObjectName('box_group')
		
		lay_contour_copy = TRFlowLayout(spacing=7)

		tooltip_button = "Copy selected contours to bank"
		self.btn_copy_contour = CustomPushButton("clipboard_copy", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_copy_contour)
		self.btn_copy_contour.clicked.connect(self.copy_contour)

		tooltip_button = "Paste selected contours from bank\nALT + Click: Paste to mask"
		self.btn_paste_contour = CustomPushButton("clipboard_paste", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_paste_contour)
		self.btn_paste_contour.clicked.connect(lambda: self.paste_as_contours(to_mask=get_modifier()))

		tooltip_button = "Remove selected items from contour bank"
		self.btn_clear = CustomPushButton("clipboard_clear", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_clear)
		self.btn_clear.clicked.connect(self.__clear_selected)

		tooltip_button = "Paste nodes over selection"
		self.btn_paste_nodes = CustomPushButton("clipboard_paste_nodes", checkable=False, checked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_paste_nodes)
		self.btn_paste_nodes.clicked.connect(self.paste_as_nodes)
		
		tooltip_button = "Trace nodes for selected path items"
		self.btn_trace = CustomPushButton("node_trace", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_trace)
		self.btn_trace.clicked.connect(self.paste_as_path)

		tooltip_button = "Auto close traced contour"
		self.opt_trace_close = CustomPushButton("contour_close", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_contour_copy.addWidget(self.opt_trace_close)

		tooltip_button = "Reset contour bank"
		self.btn_reset = CustomPushButton("close", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_reset)
		self.btn_reset.clicked.connect(self.__reset)

		box_contour_copy.setLayout(lay_contour_copy)
		lay_main.addWidget(box_contour_copy)

		# -- Copy/Inject nodes
		box_options_copy = QtGui.QGroupBox()
		box_options_copy.setObjectName('box_group')

		lay_options_copy = TRFlowLayout(spacing=7)

		# --- Options
		grp_copy_nodes_options = QtGui.QButtonGroup()

		tooltip_button = "Node Paste: Align Top Left"
		self.chk_paste_top_left = CustomPushButton("node_align_top_left", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_top_left)
		lay_options_copy.addWidget(self.chk_paste_top_left)
		self.chk_paste_top_left.clicked.connect(lambda: self.__set_align_state('LT'))

		tooltip_button = "Node Paste: Align Top Right"
		self.chk_paste_top_right = CustomPushButton("node_align_top_right", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_top_right)
		lay_options_copy.addWidget(self.chk_paste_top_right)
		self.chk_paste_top_right.clicked.connect(lambda: self.__set_align_state('RT'))

		tooltip_button = "Node Paste: Align Center"
		self.chk_paste_center = CustomPushButton("node_center", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_center)
		lay_options_copy.addWidget(self.chk_paste_center)
		self.chk_paste_center.clicked.connect(lambda: self.__set_align_state('CE'))

		tooltip_button = "Node Paste: Align Bottom Left"
		self.chk_paste_bottom_left = CustomPushButton("node_align_bottom_left", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_bottom_left)
		lay_options_copy.addWidget(self.chk_paste_bottom_left)
		self.chk_paste_bottom_left.clicked.connect(lambda: self.__set_align_state('LB'))

		tooltip_button = "Node Paste: Align Bottom Right"
		self.chk_paste_bottom_right = CustomPushButton("node_align_bottom_right", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_bottom_right)
		lay_options_copy.addWidget(self.chk_paste_bottom_right)
		self.chk_paste_bottom_right.clicked.connect(lambda: self.__set_align_state('RB'))

		tooltip_button = "Node Paste: Flip horizontally"
		self.chk_paste_flip_h = CustomPushButton("flip_horizontal", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options_copy.addWidget(self.chk_paste_flip_h)

		tooltip_button = "Node Paste: Flip vertically"
		self.chk_paste_flip_v = CustomPushButton("flip_vertical", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options_copy.addWidget(self.chk_paste_flip_v)

		tooltip_button = "Reverse contours/nodes for selected items"
		self.btn_reverse = CustomPushButton("contour_reverse", tooltip=tooltip_button, obj_name='btn_panel')
		lay_options_copy.addWidget(self.btn_reverse)
		self.btn_reverse.clicked.connect(self.__reverse_selected)

		box_options_copy.setLayout(lay_options_copy)
		lay_main.addWidget(box_options_copy)

		# -- Add contour list widget
		lay_main.addWidget(self.lst_contours)

		# -- Save and load 
		box_contour_save = QtGui.QGroupBox()
		box_contour_save.setObjectName('box_group')
		
		lay_options_main = TRFlowLayout(spacing=7)

		tooltip_button = "Save clipboard"
		self.btn_clipboard_save = CustomPushButton("file_save", tooltip=tooltip_button, obj_name='btn_panel')
		lay_options_main.addWidget(self.btn_clipboard_save)
		self.btn_clipboard_save.clicked.connect(self.clipboard_save)

		tooltip_button = "Load clipboard"
		self.btn_clipboard_load = CustomPushButton("file_open", tooltip=tooltip_button, obj_name='btn_panel')
		lay_options_main.addWidget(self.btn_clipboard_load)
		self.btn_clipboard_load.clicked.connect(self.clipboard_load)

		tooltip_button = "Toggle view mode"
		self.btn_toggle_view = CustomPushButton("select_glyph", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options_main.addWidget(self.btn_toggle_view)
		self.btn_toggle_view.clicked.connect(self.__toggle_list_view_mode)

		box_contour_save.setLayout(lay_options_main)
		lay_main.addWidget(box_contour_save)

		# - Build
		self.__toggle_list_view_mode()
		self.setLayout(lay_main)

	# -- Helper Methods -----------------------
	def __reset(self):
		self.mod_contours.removeRows(0, self.mod_contours.rowCount())
		self.contour_clipboard = {}

	def __set_align_state(self, align_state):
		self.node_align_state = align_state

	def __clear_selected(self):
		gallery_selection = [qidx.row() for qidx in self.lst_contours.selectedIndexes()]
		
		for idx in sorted(gallery_selection, reverse=True):
			item = self.mod_contours.item(idx)
			item_uid = item.data(QtCore.Qt.UserRole + 1000)
			del self.contour_clipboard[item_uid]
			self.mod_contours.removeRow(idx)

	def __toggle_list_view_mode(self):
		if self.btn_toggle_view.isChecked():
			self.lst_contours.setViewMode(QtGui.QListView.IconMode)
			self.lst_contours.setResizeMode(QtGui.QListView.Adjust)
			self.lst_contours.setMovement(QtGui.QListView.Snap)
			self.lst_contours.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
			self.lst_contours.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
			self.lst_contours.setDropIndicatorShown(True)
			self.lst_contours.setAcceptDrops(True)
			self.lst_contours.setDefaultDropAction(QtCore.Qt.MoveAction)
			self.lst_contours.setIconSize(QtCore.QSize(48, 48))
			self.lst_contours.setGridSize(QtCore.QSize(64, 72))
			self.lst_contours.setSpacing(10)
		else:
			self.lst_contours.setViewMode(QtGui.QListView.ListMode)
			self.lst_contours.setResizeMode(QtGui.QListView.Adjust)
			self.lst_contours.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
			self.lst_contours.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
			self.lst_contours.setDefaultDropAction(QtCore.Qt.MoveAction)
			self.lst_contours.setIconSize(QtCore.QSize(18, 18))
			self.lst_contours.setGridSize(QtCore.QSize()) 
			self.lst_contours.setSpacing(1)

	def __reverse_selected(self):
		"""Reverse node order for selected clipboard items"""
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]
		
		for clipboard_item in gallery_selection:
			item_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			clipboard_data = self.contour_clipboard[item_uid]
			rev_clipboard_data = {}

			# Reverse all node containers
			for layer_name, node_container in clipboard_data.items():
				rev_clipboard_data[layer_name] = node_container.reverse()
			
			self.contour_clipboard[item_uid] = rev_clipboard_data

			# Update caption
			current_text = clipboard_item.text()
			if cfg_addon_reversed in current_text:
				new_caption = current_text.replace(cfg_addon_reversed, '')
			else:
				new_caption = current_text + cfg_addon_reversed
			
			clipboard_item.setText(new_caption)

	def __get_selected_clipboard_items(self):
		"""Helper to get selected items from gallery"""
		return [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

	def __get_or_create_shape(self, wGlyph, layer_name):
		"""Get the first shape in layer or create new one"""
		try:
			return wGlyph.shapes(layer_name)[0]
		except IndexError:
			new_shape = fl6.flShape()
			wGlyph.layer(layer_name).addShape(new_shape)
			return new_shape

	def __nodes_to_contours(self, node_container, closed=True):
		"""Convert eNodesContainer to list of flContours"""
		contours = []
		temp_contour = fl6.flContour()
		
		for node in node_container:
			temp_contour.add(node.fl.clone())
		
		temp_contour.closed = closed
		contours.append(temp_contour)
		return contours

	def __contours_to_nodes(self, contours):
		"""Convert list of flContours to eNodesContainer"""
		node_container = eNodesContainer(extend=eNode)
		
		for contour in contours:
			for node in contour.nodes():
				node_container.append(eNode(node))
		
		return node_container

	def __drawIcon(self, node_container, selection_indices=None, foreground='black', background='gray'):
		"""Draw icon from eNodesContainer"""
		# Create temporary contours for drawing
		temp_contours = self.__nodes_to_contours(node_container, closed=True)
		
		# Build shape for rendering
		new_shape = fl6.flShape()
		for contour in temp_contours:
			new_shape.addContour(contour, True)

		new_painter = QtGui.QPainter()
		new_icon = QtGui.QIcon()
		shape_bbox = new_shape.boundingBox
		draw_dimension = max(shape_bbox.width(), shape_bbox.height())
		new_pixmap = QtGui.QPixmap(draw_dimension + 32, draw_dimension + 32)
		new_pixmap.fill(QtGui.QColor('white'))

		# - Paint
		new_painter.begin(new_pixmap)
		new_painter.setRenderHint(QtGui.QPainter.Antialiasing)
		
		# Background fill
		draw_color = foreground if selection_indices is None else background
		new_painter.setBrush(QtGui.QBrush(QtGui.QColor(draw_color)))
		new_transform = new_shape.transform.translate(-shape_bbox.x(), -shape_bbox.y())
		new_shape.applyTransform(new_transform)
		new_shape.ensurePaths()
		new_painter.drawPath(new_shape.closedPath)
	
		# Draw selection if provided
		if selection_indices is not None and len(selection_indices):
			selection_contour = fl6.flContour()
			for idx in selection_indices:
				if idx < len(node_container):
					node = node_container[idx]
					new_node = node.fl.clone()
					new_node.moveBy(-shape_bbox.x(), -shape_bbox.y())
					selection_contour.add(new_node)

			# Outline
			outline_pen = QtGui.QPen(QtGui.QColor(foreground))
			outline_pen.setWidthF(8.0) 
			outline_pen.setStyle(QtCore.Qt.SolidLine)
			outline_pen.setCapStyle(QtCore.Qt.RoundCap)
			outline_pen.setJoinStyle(QtCore.Qt.RoundJoin)
			new_painter.setPen(outline_pen)
			new_painter.setBrush(QtGui.QColor(0,0,0,0))
			new_painter.drawPath(selection_contour.path())

			# Node markers
			sel_brush = QtGui.QBrush(QtGui.QColor(foreground))
			sel_pen = QtGui.QPen(QtGui.QColor(foreground))
			new_painter.setBrush(sel_brush)
			new_painter.setPen(sel_pen)

			node_size = max(2, draw_dimension * 0.08)
			half = node_size / 2.0

			for idx in selection_indices:
				if idx < len(node_container):
					node = node_container[idx]
					new_painter.drawEllipse(QtCore.QRectF(
						node.x - shape_bbox.x() - half, 
						node.y - shape_bbox.y() - half, 
						node_size, node_size
					))
		
		new_icon.addPixmap(new_pixmap.transformed(QtGui.QTransform().scale(1, -1)))
		return new_icon

	# -- Core Functionality -------------------
	def copy_contour(self):
		"""Copy selected contours/nodes to clipboard as eNodesContainer"""
		wGlyph = eGlyph()
		current_contours = wGlyph.contours()
		process_layers = wGlyph._prepareLayers(pLayers)
		
		# Get selection info
		selection_tuples = wGlyph.selectedAtContours()
		if not selection_tuples:
			return
		
		# Group by contour ID
		selection = {}
		partial_selection = False
		
		for cid, node_selection in groupby(selection_tuples, lambda x: x[0]):
			if cid >= len(current_contours):
				continue
			
			if not current_contours[cid].isAllNodesSelected():
				node_list = [node[1] for node in node_selection]
				selection[cid] = node_list
				partial_selection = True
			else:
				selection[cid] = []
		
		if not selection:
			return
		
		# Determine color for UI
		if len(process_layers) == len(wGlyph.masters()):
			conditional_color = 'green'
		elif len(process_layers) == 1:
			conditional_color = 'red'
		else:
			conditional_color = 'blue'
		
		# Build clipboard data
		export_clipboard = OrderedDict()
		
		for layer_name in process_layers:
			all_contours = wGlyph.contours(layer_name)
			node_container = eNodesContainer(extend=eNode)
			
			for cid, node_indices in selection.items():
				if cid >= len(all_contours):
					continue
				
				contour = all_contours[cid]
				
				if not node_indices:  # Full contour selected
					for node in contour.nodes():
						node_container.append(eNode(node.clone()))
				else:  # Partial selection
					contour_nodes = contour.nodes()
					for nid in node_indices:
						if nid < len(contour_nodes):
							temp_node = contour_nodes[nid].clone()
							# Ensure no start nodes
							if nid == 0 or nid == len(node_indices) - 1:
								temp_node = fl6.flNode(temp_node.position, nodeType=temp_node.type)
							node_container.append(eNode(temp_node))
			
			export_clipboard[layer_name] = node_container
		
		# Create UI item
		total_nodes = sum(len(nc) for nc in export_clipboard.values()) // len(export_clipboard)
		item_type = 'Open' if partial_selection else 'Closed'
		new_item = QtGui.QStandardItem('{} | {} Nodes ({} Contour)'.format(wGlyph.name, total_nodes, item_type))
		
		# Draw icon
		first_layer_nodes = list(export_clipboard.values())[0]
		if partial_selection:
			selection_indices = list(range(len(first_layer_nodes)))
			new_icon = self.__drawIcon(first_layer_nodes, selection_indices, foreground=conditional_color, background='LightGray')
		else:
			new_icon = self.__drawIcon(first_layer_nodes, None, foreground=conditional_color)
		
		new_item.setIcon(new_icon)
		new_item.setDropEnabled(False)
		new_item.setSelectable(True)
		
		# Store in clipboard
		copy_uid = hash(random.getrandbits(128))
		new_item.setData(copy_uid, QtCore.Qt.UserRole + 1000)
		self.contour_clipboard[copy_uid] = export_clipboard
		
		self.mod_contours.appendRow(new_item)
		output(0, app_name, 'Copy contours; Glyph: %s; Layers: %s.' % (wGlyph.name, '; '.join(process_layers)))

	def paste_as_nodes(self):
		"""Paste clipboard data using node alignment options"""
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = self.__get_selected_clipboard_items()

		if not gallery_selection:
			return
		
		clipboard_item = gallery_selection[0]
		paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
		paste_data = self.contour_clipboard[paste_uid]

		flip_options = (
			self.chk_paste_flip_h.isChecked(), 
			self.chk_paste_flip_v.isChecked(), 
			False, False, True, False
		)
		
		TRNodeActionCollector.nodes_paste(wGlyph, wLayers, paste_data, self.node_align_state, flip_options)

	def paste_as_contours(self, to_mask=False):
		"""Paste clipboard data as closed contours"""
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = self.__get_selected_clipboard_items()

		if not gallery_selection:
			return

		for clipboard_item in gallery_selection:
			paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			paste_data = self.contour_clipboard[paste_uid]

			for layer_name, node_container in paste_data.items():
				# Get target layer
				if to_mask:
					wLayer = wGlyph.mask(layer_name, force_create=True)
					layer_name = wLayer.name
				else:
					wLayer = wGlyph.layer(layer_name)
				
				if wLayer is None:
					continue
				
				# Convert nodes to contours
				contours = self.__nodes_to_contours(node_container, closed=True)
				
				# Add to shape
				selected_shape = self.__get_or_create_shape(wGlyph, layer_name)
				selected_shape.addContours(contours, True)
		
		wGlyph.updateObject(wGlyph.fl, 'Paste contours; Glyph: %s; Layers: %s' % (wGlyph.name, '; '.join(wLayers)))

	def paste_as_path(self):
		"""Paste clipboard data as open path (trace nodes)"""
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = self.__get_selected_clipboard_items()

		if not gallery_selection:
			return

		# Combine all selected items
		combined_data = {}
		for clipboard_item in gallery_selection:
			paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			paste_data = self.contour_clipboard[paste_uid]

			for layer_name, node_container in paste_data.items():
				if layer_name not in combined_data:
					combined_data[layer_name] = eNodesContainer(extend=eNode)
				# Append nodes individually
				for node in node_container:
					combined_data[layer_name].append(node)

		# Paste as open/closed contours
		for layer_name, node_container in combined_data.items():
			wLayer = wGlyph.layer(layer_name)
			
			if wLayer is None:
				continue
			
			# Convert to contour with closed option
			contours = self.__nodes_to_contours(node_container, closed=self.opt_trace_close.isChecked())
			
			# Add to shape
			selected_shape = self.__get_or_create_shape(wGlyph, layer_name)
			selected_shape.addContours(contours, True)
		
		wGlyph.updateObject(wGlyph.fl, 'Paste path; Glyph: %s; Layers: %s' % (wGlyph.name, '; '.join(wLayers)))

	def clipboard_save(self):
		"""Save clipboard to file"""
		print('Save')
		print(self.contour_clipboard)

	def clipboard_load(self):
		"""Load clipboard from file"""
		print('Load')


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)
		
		layoutV = QtGui.QVBoxLayout()
		layoutV.setContentsMargins(0, 0, 0, 0)
		
		# - Add widgets to main dialog 
		layoutV.addWidget(TRContourCopy())

		# - Build 
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()