#FLM: TR: Clipboard
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2025 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import os
import random
from math import radians
from itertools import groupby
from collections import OrderedDict

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.node import eNode
from typerig.proxy.fl.objects.glyph import eGlyph

# - Core TypeRig objects for storage
from typerig.core.objects.glyph import Glyph
from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node

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
app_name, app_version = 'TypeRig | Contour', '2.1'
fileFormats = 'TypeRig XML data (*.xml);;'

cfg_addon_reversed = ' (Reversed)'
cfg_addon_partial = ' (Partial)'

TRToolFont_path = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont_path)
families = QtGui.QFontDatabase.applicationFontFamilies(font_loaded)
TRFont = QtGui.QFont(families[0], 20)
TRFont.setPixelSize(20)

# -- Helpers ------------------------------
def get_modifier(keyboard_modifier=QtCore.Qt.AltModifier):
	modifiers = QtGui.QApplication.keyboardModifiers()
	return modifiers == keyboard_modifier

def flNodes_to_trContour(fl_nodes, is_closed):
	'''Convert list of flNodes to trContour (core Contour object) for partial paths'''
	tr_nodes = []
	for fl_node in fl_nodes:
		tr_node = Node(fl_node.x, fl_node.y, type=fl_node.type)
		tr_nodes.append(tr_node)
	
	return Contour(tr_nodes, closed=is_closed, proxy=False)

def trContour_to_flContour(tr_contour):
	'''Convert trContour (core Contour object) back to flContour'''
	fl_nodes = []
	for tr_node in tr_contour.nodes:
		fl_node = fl6.flNode(QtCore.QPointF(tr_node.x, tr_node.y), nodeType=tr_node.type)
		fl_nodes.append(fl_node)
	
	fl_contour = fl6.flContour(fl_nodes)
	print(tr_contour.closed)
	fl_contour.closed = tr_contour.closed
	return fl_contour

# - Sub widgets ------------------------
class TRContourCopy(QtGui.QWidget):
	# - Align Contours
	def __init__(self):
		super(TRContourCopy, self).__init__()

		# - Init
		self.active_font = pFont()
		lay_main = QtGui.QVBoxLayout()
		self.contour_clipboard = {}  # Stores trGlyph objects
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
		self.btn_paste_contour.clicked.connect(lambda: self.paste_contour(to_mask=get_modifier()))

		tooltip_button = "Remove selected items from contour bank"
		self.btn_clear = CustomPushButton("clipboard_clear", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_clear)
		self.btn_clear.clicked.connect(self.__clear_selected)

		tooltip_button =  "Paste nodes over selection"
		self.btn_paste_nodes = CustomPushButton("clipboard_paste_nodes", checkable=False, checked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_paste_nodes)
		self.btn_paste_nodes.clicked.connect(lambda: self.paste_nodes())
		
		tooltip_button =  "Trace nodes for selected path items"
		self.btn_trace = CustomPushButton("node_trace", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_trace)
		self.btn_trace.clicked.connect(self.paste_path)

		tooltip_button =  "Auto close traced contour"
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

		tooltip_button =  "Node Paste: Align Top Left"
		self.chk_paste_top_left = CustomPushButton("node_align_top_left", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_top_left)
		lay_options_copy.addWidget(self.chk_paste_top_left)
		self.chk_paste_top_left.clicked.connect(lambda: self.__set_align_state('LT'))

		tooltip_button =  "Node Paste: Align Top Right"
		self.chk_paste_top_right = CustomPushButton("node_align_top_right", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_top_right)
		lay_options_copy.addWidget(self.chk_paste_top_right)
		self.chk_paste_top_right.clicked.connect(lambda: self.__set_align_state('RT'))

		tooltip_button =  "Node Paste: Align Center"
		self.chk_paste_center = CustomPushButton("node_center", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_center)
		lay_options_copy.addWidget(self.chk_paste_center)
		self.chk_paste_center.clicked.connect(lambda: self.__set_align_state('CE'))

		tooltip_button =  "Node Paste: Align Bottom Left"
		self.chk_paste_bottom_left = CustomPushButton("node_align_bottom_left", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_bottom_left)
		lay_options_copy.addWidget(self.chk_paste_bottom_left)
		self.chk_paste_bottom_left.clicked.connect(lambda: self.__set_align_state('LB'))

		tooltip_button =  "Node Paste: Align Bottom Right"
		self.chk_paste_bottom_right = CustomPushButton("node_align_bottom_right", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		grp_copy_nodes_options.addButton(self.chk_paste_bottom_right)
		lay_options_copy.addWidget(self.chk_paste_bottom_right)
		self.chk_paste_bottom_right.clicked.connect(lambda: self.__set_align_state('RB'))

		tooltip_button =  "Node Paste: Flip horizontally"
		self.chk_paste_flip_h = CustomPushButton("flip_horizontal", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options_copy.addWidget(self.chk_paste_flip_h)

		tooltip_button =  "Node Paste: Flip vertically"
		self.chk_paste_flip_v = CustomPushButton("flip_vertical", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options_copy.addWidget(self.chk_paste_flip_v)

		tooltip_button =  "Reverse contours/nodes for selected items"
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

	def __reset(self):
		self.mod_contours.removeRows(0, self.mod_contours.rowCount())
		self.contour_clipboard = {}

	def __set_align_state(self, align_state):
		self.node_align_state = align_state

	def __clear_selected(self):
		gallery_selection = [qidx.row() for qidx in self.lst_contours.selectedIndexes()]
		
		# Get UIDs before removing to clean up clipboard
		uids_to_remove = []
		for idx in gallery_selection:
			item = self.mod_contours.item(idx)
			if item:
				uid = item.data(QtCore.Qt.UserRole + 1000)
				uids_to_remove.append(uid)
		
		# Remove from model
		for idx in sorted(gallery_selection, reverse=True):
			self.mod_contours.removeRow(idx)
		
		# Clean up clipboard
		for uid in uids_to_remove:
			if uid in self.contour_clipboard:
				del self.contour_clipboard[uid]

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
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]
		
		for clipboard_item in gallery_selection:
			item_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			clipboard_glyph = self.contour_clipboard[item_uid]
			
			# Reverse all contours in all layers
			for layer in clipboard_glyph.layers:
				for shape in layer.shapes:
					for contour in shape.contours:
						contour.reverse()

			# Modify caption
			if cfg_addon_reversed in clipboard_item.text():
				new_caption = clipboard_item.text().replace(cfg_addon_reversed, '')
			else:
				new_caption = clipboard_item.text() + cfg_addon_reversed

			clipboard_item.setText(new_caption)

	def __drawIcon(self, contours, selection, foreground='black', background='gray'):
		'''Draw icon for gallery. Handles both full contours and partial paths.'''
		# - Init
		cloned_contours = [contour.clone() for contour in contours]
		new_shape = fl6.flShape()

		for contour in cloned_contours:
			new_shape.addContour(contour, True)

		new_painter = QtGui.QPainter()
		new_icon = QtGui.QIcon()
		shape_bbox = new_shape.boundingBox
		draw_dimension = max(shape_bbox.width(), shape_bbox.height())
		new_pixmap = QtGui.QPixmap(draw_dimension + 32, draw_dimension + 32)
		new_pixmap.fill(QtGui.QColor('white'))

		# - Paint
		new_painter.begin(new_pixmap)
		
		# -- Foreground
		draw_color = foreground if not len(selection) else background
		new_painter.setBrush(QtGui.QBrush(QtGui.QColor(draw_color)))
		new_transform = new_shape.transform.translate(-shape_bbox.x(), -shape_bbox.y())
		new_shape.applyTransform(new_transform)
		new_shape.ensurePaths()
		new_painter.drawPath(new_shape.closedPath)
	
		if len(selection):
			selection_contour = fl6.flContour()
			for node in selection:
				new_node = node.clone()
				new_node.moveBy(-shape_bbox.x(), -shape_bbox.y())
				selection_contour.add(new_node)

			# --- Setup pen for outline ---
			outline_pen = QtGui.QPen(QtGui.QColor(foreground))
			outline_pen.setWidthF(8.0) 
			outline_pen.setStyle(QtCore.Qt.SolidLine)
			outline_pen.setCapStyle(QtCore.Qt.RoundCap)
			outline_pen.setJoinStyle(QtCore.Qt.RoundJoin)

			new_painter.setPen(outline_pen)
			new_painter.setBrush(QtGui.QColor(0,0,0,0))

			# --- Draw the closed contour ---
			new_painter.drawPath(selection_contour.path())

			# --- Draw selected nodes as individual squares ---
			sel_brush = QtGui.QBrush(QtGui.QColor(foreground))
			sel_pen = QtGui.QPen(QtGui.QColor(foreground))
			new_painter.setBrush(sel_brush)
			new_painter.setPen(sel_pen)

			# - Draw marks at each selected point
			node_size = max(2, draw_dimension * 0.08)
			half = node_size / 2.0

			for node in selection:
				new_painter.drawEllipse(QtCore.QRectF(node.x - shape_bbox.x() - half, node.y - shape_bbox.y() - half, node_size, node_size))
		
		new_icon.addPixmap(new_pixmap.transformed(QtGui.QTransform().scale(1, -1)))
		
		return new_icon

	def copy_contour(self):
		'''Copy selected contours or partial paths to clipboard as trGlyph objects.'''
		# - Init
		wGlyph = eGlyph()
		current_contours = wGlyph.contours()
		process_layers = wGlyph._prepareLayers(pLayers)
		
		# - Build initial contour information
		selection_tuples = wGlyph.selectedAtContours()
		selection = {}
		is_partial = False
		
		for cid, node_selection in groupby(selection_tuples, lambda x:x[0]):
			node_list = []

			if not current_contours[cid].isAllNodesSelected():
				node_list = [node[1] for node in node_selection]
				is_partial = True

			selection[cid] = node_list

		# - Process
		if len(selection.keys()):
			
			# -- Prepare display info
			if len(process_layers) == len(wGlyph.masters()):
				conditional_color = 'green'
			elif len(process_layers) == 1:
				conditional_color = 'red'
			else:
				conditional_color = 'blue'

			# --- Prepare icon and bank entry
			draw_contours = [wGlyph.contours()[cid] for cid in selection.keys()]
			draw_count = sum([contour.nodesCount for contour in draw_contours])
			contour_type = 'Partial' if is_partial else 'Closed'
			new_item = QtGui.QStandardItem('{} | {} Nodes ({} Contour)'.format(wGlyph.name, draw_count, contour_type))

			if not is_partial:
				new_icon = self.__drawIcon(draw_contours, selection={}, foreground=conditional_color)
			else:
				new_icon = self.__drawIcon(draw_contours, selection=wGlyph.selectedNodes(), foreground=conditional_color, background='LightGray')

			new_item.setIcon(new_icon)
			self.mod_contours.appendRow(new_item)

			# -- Create trGlyph structure for storage
			tr_glyph = Glyph(name=wGlyph.name)
			
			for layer_name in process_layers:
				# Create layer
				tr_layer = Layer(name=layer_name)
				
				# Get all contours from this layer
				all_contours = wGlyph.contours(layer_name)
				
				if not is_partial:
					# Store whole contours
					for cid in selection.keys():
						fl_contour = all_contours[cid]
						tr_contour = flNodes_to_trContour(fl_contour.nodes(), True)
						
						# Create shape with single contour
						tr_shape = Shape([tr_contour])
						tr_layer.append(tr_shape)
				else:
					# Store partial path as a single contour
					partial_nodes = []
					for cid, node_list in selection.items():
						contour_nodes = all_contours[cid].nodes()
						
						for nid in node_list:
							fl_node = contour_nodes[nid]
							# Ensure no start nodes end up in the clipboard
							if nid == 0 or nid == len(node_list) - 1:
								fl_node = fl6.flNode(fl_node.position, nodeType=fl_node.type)
							
							partial_nodes.append(fl_node)
					
					# Create single contour from partial nodes
					tr_contour = flNodes_to_trContour(partial_nodes, False)
					tr_shape = Shape([tr_contour])
					tr_layer.append(tr_shape)
				
				tr_glyph.append(tr_layer)

			# - Generate unique identifier and store
			copy_uid = hash(random.getrandbits(128))
			self.contour_clipboard[copy_uid] = tr_glyph
			new_item.setData(copy_uid, QtCore.Qt.UserRole + 1000)
			new_item.setData(is_partial, QtCore.Qt.UserRole + 1001)  # Store partial flag
			new_item.setDropEnabled(False)
			new_item.setSelectable(True)

			output(0, app_name, 'Copy contours; Glyph: %s; Layers: %s; Type: %s' %(wGlyph.name, '; '.join(process_layers), contour_type))
		
	def paste_nodes(self):
		'''Paste nodes over selection using node action collector.'''
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

		if len(gallery_selection):
			clipboard_item = gallery_selection[0]
			paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			tr_glyph = self.contour_clipboard[paste_uid]

			# Convert trGlyph to format expected by TRNodeActionCollector
			# This creates a dict with layer_name: list_of_nodes structure
			paste_data = {}
			
			for tr_layer in tr_glyph.layers:
				all_nodes = []
				for tr_shape in tr_layer.shapes:
					for tr_contour in tr_shape.contours:
						# Convert nodes to eNode for the action collector
						for tr_node in tr_contour.nodes:
							node_type = fl6.nOn if tr_node.type == 'on' else fl6.nCurve
							fl_node = fl6.flNode(fl6.flPoint(tr_node.x, tr_node.y), nodeType=node_type)
							all_nodes.append(eNode(fl_node))
				
				paste_data[tr_layer.name] = all_nodes

			TRNodeActionCollector.nodes_paste(wGlyph, wLayers, paste_data, self.node_align_state, 
				(self.chk_paste_flip_h.isChecked(), self.chk_paste_flip_v.isChecked(), False, False, True, False))
	
	def paste_contour(self, to_mask=False):
		'''Paste whole contours from clipboard.'''
		# - Init
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

		# - Process
		if len(gallery_selection):
			for clipboard_item in gallery_selection:
				paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
				is_partial = clipboard_item.data(QtCore.Qt.UserRole + 1001)
				tr_glyph = self.contour_clipboard[paste_uid]

				if is_partial:
					output(3, app_name, '< Partial path > not suitable for < Paste contours > operation!')
					continue

				for tr_layer in tr_glyph.layers:
					layer_name = tr_layer.name
					
					# Get destination layer or mask
					wLayer = wGlyph.layer(layer_name)

					if to_mask:
						wLayer = wGlyph.mask(layer_name, force_create=True)
						layer_name = wLayer.name
					
					if wLayer is not None:
						# Convert trContours back to flContours
						fl_contours = []
						for tr_shape in tr_layer.shapes:
							for tr_contour in tr_shape.contours:
								fl_contour = trContour_to_flContour(tr_contour)
								fl_contours.append(fl_contour)

						# Insert contours into currently selected shape
						try:
							selected_shape = wGlyph.shapes(layer_name)[0]
						except IndexError:
							selected_shape = fl6.flShape()
							wLayer.addShape(selected_shape)

						selected_shape.addContours(fl_contours, True)
			
			wGlyph.updateObject(wGlyph.fl, 'Paste contours; Glyph: %s; Layers: %s' %(wGlyph.name, '; '.join(wLayers)))

	def paste_path(self):
		'''Paste partial path (trace nodes).'''
		# - Init
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

		# - Process
		if len(gallery_selection):
			combined_data = {}
			
			for clipboard_item in gallery_selection:
				paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
				tr_glyph = self.contour_clipboard[paste_uid]

				for tr_layer in tr_glyph.layers:
					layer_name = tr_layer.name
					
					# Collect all nodes from all contours
					for tr_shape in tr_layer.shapes:
						for tr_contour in tr_shape.contours:
							# Convert to flNodes
							fl_nodes = []
							for tr_node in tr_contour.nodes:
								fl_node = fl6.flNode(QtCore.QPointF(tr_node.x, tr_node.y), nodeType=tr_node.type)
								fl_nodes.append(fl_node)
							
							combined_data.setdefault(layer_name, []).extend(fl_nodes)

			for layer_name, nodes in combined_data.items():
				wLayer = wGlyph.layer(layer_name)

				if wLayer is not None:
					# Create new contour from nodes
					cloned_nodes = [node.clone() for node in nodes]
					new_contour = fl6.flContour(cloned_nodes)
					new_contour.closed = self.opt_trace_close.isChecked()

					# Insert contour into currently selected shape
					try:
						selected_shape = wGlyph.shapes(layer_name)[0]
					except IndexError:
						selected_shape = fl6.flShape()
						wLayer.addShape(selected_shape)

					selected_shape.addContours([new_contour], True)
			
			wGlyph.updateObject(wGlyph.fl, 'Paste path; Glyph: %s; Layers: %s' %(wGlyph.name, '; '.join(wLayers)))

	# -- File operations
	def clipboard_save(self):
		'''Save clipboard to XML or binary file.'''
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save clipboard data to file', fontPath, fileFormats)

		if fname != None:
			try:
				# Save as XML
				with open(fname, 'w') as exportFile:
					# Create root structure
					xml_data = '<?xml version="1.0" encoding="UTF-8"?><clipboard>'
					
					for uid, tr_glyph in self.contour_clipboard.items():
						xml_data += '<item uid="{}">'.format(uid)
						xml_data += tr_glyph.to_XML()
						xml_data += '</item>'
					
					xml_data += '</clipboard>'
					exportFile.write(xml_data)
				
				output(7, app_name, 'Font: %s; Clipboard data saved to XML: %s.' %(self.active_font.name, fname))
				
			except Exception as e:
				output(4, app_name, 'Error saving clipboard: %s' % str(e))
				
	def clipboard_load(self):
		'''Load clipboard from XML'''
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load clipboard data from file', fontPath, fileFormats)
			
		if fname != None:
			try:
				# Load from XML
				with open(fname, 'r') as importFile:
					xml_content = importFile.read()
				
				# Parse XML (simplified parsing)
				import xml.etree.ElementTree as ET
				root = ET.fromstring(xml_content)
				
				self.contour_clipboard = {}
				
				for item in root.findall('item'):
					uid = int(item.get('uid'))
					glyph_elem = item.find('glyph')
					
					if glyph_elem is not None:
						# Reconstruct trGlyph from XML
						tr_glyph = Glyph.from_XML(ET.tostring(glyph_elem, encoding='unicode'))
						self.contour_clipboard[uid] = tr_glyph
						
						# Add to gallery
						glyph_name = tr_glyph.name if tr_glyph.name else 'Unnamed'
						layer_count = len(tr_glyph.layers)
						contour_count = sum(len(shape.contours) for layer in tr_glyph.layers for shape in layer.shapes)
						
						new_item = QtGui.QStandardItem('{} | {} Layers | {} Contours'.format(glyph_name, layer_count, contour_count))
						new_item.setData(uid, QtCore.Qt.UserRole + 1000)
						new_item.setDropEnabled(False)
						new_item.setSelectable(True)
						self.mod_contours.appendRow(new_item)
				
				output(6, app_name, 'Font: %s; Clipboard loaded from XML: %s.' %(self.active_font.name, fname))
			
			except Exception as e:
				output(4, app_name, 'Error loading clipboard: %s' % str(e))


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