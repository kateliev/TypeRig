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
from typerig.proxy.fl.objects.node import eNode, eNodesContainer
from typerig.core.objects.transform import Transform, TransformOrigin
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
from typerig.proxy.fl.gui.drawing import TRDrawIcon

# - Init -------------------------------
global pLayers
global pMode
pLayers = (True, True, False, False)
pMode = 0
app_name, app_version = 'TypeRig | Contour', '3.9'

fileFormats = 'TypeRig XML data (*.xml);;'
delta_app_id_key = 'com.typerig.delta.machine.axissetup'
delta_axis_group_name = 'Virtual Axis'
delta_axis_target_name = 'Target Layers'
exclude_attrs = ['transform', 'g2'] # Exclude some elements for more compact files

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
		tr_node = Node(fl_node.x, fl_node.y, type=fl_node.type, smooth=fl_node.smooth)
		tr_nodes.append(tr_node)
	
	return Contour(tr_nodes, closed=is_closed, proxy=False)

def trNodes_to_flContour(tr_nodes, is_closed):
	'''Convert trContour (core Contour object) back to flContour'''
	fl_nodes = []
	
	for tr_node in tr_nodes:
		fl_node = fl6.flNode(QtCore.QPointF(tr_node.x, tr_node.y), nodeType=tr_node.type)
		fl_node.smooth = tr_node.smooth
		fl_nodes.append(fl_node)
	
	fl_contour = fl6.flContour(fl_nodes, closed=is_closed)
	fl_contour_nodes = fl_contour.nodes()

	# - Accurately transfer the smooth flag: 
	# -- It seems FL requires this to be done,
	# -- when nodes are organized in contour,
	# -- not standalone.
	for nid in range(len(fl_contour_nodes)):
		if tr_nodes[nid].smooth:
			fl_contour_nodes[nid].smooth = True

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
		
		# Icon size cycling for grid mode
		self.icon_sizes = [48, 64, 96, 128]
		self.current_icon_size_index = 0

		# -- Listview
		self.lst_contours = QtGui.QListView()
		self.mod_contours = QtGui.QStandardItemModel(self.lst_contours)
		self.lst_contours.setMinimumHeight(350)
		self.lst_contours.setModel(self.mod_contours)
		self.mod_contours.itemChanged.connect(self.__on_item_renamed)
		
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

		tooltip_button =  "Paste nodes over selection\nALT + Click: Overwrite"
		self.btn_paste_nodes = CustomPushButton("clipboard_paste_nodes", checkable=False, checked=False, tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_paste_nodes)
		self.btn_paste_nodes.clicked.connect(lambda: self.paste_nodes(overwrite=get_modifier()))
		
		tooltip_button =  "Trace nodes for selected path items"
		self.btn_trace = CustomPushButton("node_trace", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_trace)
		self.btn_trace.clicked.connect(self.paste_path)

		tooltip_button =  "Auto close traced contour"
		self.opt_trace_close = CustomPushButton("contour_close", checkable=True, checked=True, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_contour_copy.addWidget(self.opt_trace_close)

		tooltip_button =  "Round coordinates"
		self.opt_round = CustomPushButton("node_round", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_contour_copy.addWidget(self.opt_round)

		tooltip_button =  "Use Delta Machine to fit pasted contours into selected shape bounds"
		self.opt_delta_machine = CustomPushButton("delta_machine", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_contour_copy.addWidget(self.opt_delta_machine)

		

		box_contour_copy.setLayout(lay_contour_copy)
		lay_main.addWidget(box_contour_copy)

		# -- Copy/Inject nodes
		box_options_copy = QtGui.QGroupBox()
		box_options_copy.setObjectName('box_group')

		lay_options_copy = TRFlowLayout(spacing=7)

		# --- Options
		grp_copy_nodes_options = QtGui.QButtonGroup(self)
		grp_copy_nodes_options.setExclusive(True)

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

		tooltip_button = "Reset contour bank"
		self.btn_reset = CustomPushButton("close", tooltip=tooltip_button, obj_name='btn_panel')
		lay_options_main.addWidget(self.btn_reset)
		self.btn_reset.clicked.connect(self.__reset)

		tooltip_button = "Toggle view mode"
		self.btn_toggle_view = CustomPushButton("view_icons", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_options_main.addWidget(self.btn_toggle_view)
		self.btn_toggle_view.clicked.connect(self.__toggle_list_view_mode)

		tooltip_button = "Cycle icon size (Grid mode only)"
		self.btn_icon_size = CustomPushButton("search", tooltip=tooltip_button, obj_name='btn_panel')
		lay_options_main.addWidget(self.btn_icon_size)
		self.btn_icon_size.clicked.connect(self.__cycle_icon_size)

		box_contour_save.setLayout(lay_options_main)
		lay_main.addWidget(box_contour_save)

		# - Build
		self.__toggle_list_view_mode()
		self.setLayout(lay_main)

	# -- Functions --------------------------
	def __reset(self):
		self.mod_contours.removeRows(0, self.mod_contours.rowCount())
		self.contour_clipboard = {}

	def __set_align_state(self, align_state):
		self.node_align_state = align_state

	def __prep_delta_parameters(self, tr_glyph, wGlyph, wLayers):
		# -- Look for Delta Machine Axis data in font's lib
		try:
			font_lib = self.active_font.fl.packageLib
			raw_axis_data = font_lib[delta_app_id_key][delta_axis_group_name]
			axis_data = {layer_name : (float(stx), float(sty)) for layer_name, stx, sty, sx, sy, color in raw_axis_data}
			
		except KeyError:
			output(3, app_name, 'Delta Machine Axis setup not found in Fonts Lib.\n Please setup using < Delta panel > then save the axis data within the font!')
			return None, None
		
		# -- Prepare virtual axis
		for layer_name, stems in axis_data.items():
			tr_glyph.layer(layer_name).stems = stems

		virtual_axis = tr_glyph.virtual_axis(list(axis_data.keys()))
		target_bounds = {}

		for layer_name in wLayers:
			layer_selection = wGlyph.selectedNodes(layer_name)
			
			if len(layer_selection):
				selection_container = eNodesContainer(layer_selection)
				target_bounds[layer_name] = selection_container.bounds
			else:
				target_bounds[layer_name] = None

		return virtual_axis, target_bounds

	def __clear_selected(self):
		gallery_selection = [qidx.row() for qidx in self.lst_contours.selectedIndexes()]
		
		# - Get UIDs before removing to clean up clipboard
		uids_to_remove = []
		for idx in gallery_selection:
			item = self.mod_contours.item(idx)
			if item:
				uid = item.data(QtCore.Qt.UserRole + 1000)
				uids_to_remove.append(uid)
		
		# - Remove from model
		for idx in sorted(gallery_selection, reverse=True):
			self.mod_contours.removeRow(idx)
		
		# - Clean up clipboard
		for uid in uids_to_remove:
			if uid in self.contour_clipboard:
				del self.contour_clipboard[uid]

	def __cycle_icon_size(self):
		'''Cycle through icon sizes in grid mode only'''
		if self.btn_toggle_view.isChecked():
			# Advance to next size
			self.current_icon_size_index = (self.current_icon_size_index + 1) % len(self.icon_sizes)
			new_size = self.icon_sizes[self.current_icon_size_index]
			
			# Calculate grid size (icon size + padding)
			grid_size = new_size + 16
			
			# Apply new sizes
			self.lst_contours.setIconSize(QtCore.QSize(new_size, new_size))
			self.lst_contours.setGridSize(QtCore.QSize(grid_size, grid_size + 8))

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
			
			# Use current icon size from cycling
			current_size = self.icon_sizes[self.current_icon_size_index]
			grid_size = current_size + 16
			self.lst_contours.setIconSize(QtCore.QSize(current_size, current_size))
			self.lst_contours.setGridSize(QtCore.QSize(grid_size, grid_size + 8))
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

	def __on_item_renamed(self, item):
		uid = item.data(QtCore.Qt.UserRole + 1000)
		
		if uid in self.contour_clipboard:
			# Extract the new name from item text
			item_text = item.text()
			
			# Parse format: "Name | N Nodes (Type)"
			if '|' in item_text:
				new_name = item_text.split('|')[0].strip()
			else:
				new_name = item_text.strip()
			
			# Update tr_glyph name
			tr_glyph = self.contour_clipboard[uid]
			tr_glyph.name = new_name

	def __create_list_item(self, uid, tr_glyph, fl_glyph=None, selection_dict=None):
		# - Extract data from first layer (all layers are isomorphic)
		first_layer = tr_glyph.layers[0]
		first_shape = first_layer.shapes[0]
		first_contour = first_shape.contours[0]
		
		# - Determine if partial from first contour
		is_partial = not first_contour.closed
		
		# - Calculate node count from first layer
		draw_count = len(first_layer.nodes)
		
		# - Determine color based on layer count
		masters_count = len(self.active_font.masters())
		layer_count = len(tr_glyph.layers)
		
		if layer_count == masters_count:
			conditional_color = 'green'
		elif layer_count == 1:
			conditional_color = 'red'
		else:
			conditional_color = 'blue'
		
		# - Create text label
		contour_type = 'Partial' if is_partial else 'Closed'
		new_item = QtGui.QStandardItem('{} | {} Nodes ({} Contour)'.format(tr_glyph.name, draw_count, contour_type))
		
		# - Create icon
		if fl_glyph is not None and selection_dict is not None:
			# - Copy operation: use current glyph contours
			draw_contours = [fl_glyph.contours()[cid] for cid in selection_dict.keys()]
			use_selection = fl_glyph.selectedNodes() if is_partial else None
		else:
			# - Load operation: convert tr_glyph to flContours
			draw_contours = []
			open_contours = []

			for shape in first_layer.shapes:
				for tr_contour in shape.contours:
					fl_contour = trNodes_to_flContour(tr_contour.nodes, is_closed=tr_contour.closed)
					
					if not tr_contour.closed:
						fl_contour.closed = True
						open_contours += fl_contour.nodes()
					
					draw_contours.append(fl_contour)

			use_selection = open_contours
		
		# Draw icon
		use_background = 'LightGray'
		new_icon = TRDrawIcon(draw_contours, selection=use_selection, foreground=conditional_color,	background=use_background)
		new_item.setIcon(new_icon)
		
		# Set item data
		new_item.setData(uid, QtCore.Qt.UserRole + 1000)
		new_item.setData(is_partial, QtCore.Qt.UserRole + 1001)
		new_item.setDropEnabled(False)
		new_item.setSelectable(True)
		
		return new_item

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

			# -- Create trGlyph structure for storage
			tr_glyph = Glyph(name=wGlyph.name)
			
			for layer_name in process_layers:
				# Create layer
				tr_layer = Layer(name=layer_name)
				
				# Get all contours from this layer
				all_contours = wGlyph.contours(layer_name)
				
				if not is_partial:
					stored_contours = []

					# - Store whole contours
					for cid in selection.keys():
						fl_contour = all_contours[cid]
						tr_contour = flNodes_to_trContour(fl_contour.nodes(), True)
						stored_contours.append(tr_contour)
						
					# - Create a shape containing the contours
					tr_shape = Shape(stored_contours)
					tr_layer.append(tr_shape)
				else:
					# - Store partial path as a single contour
					partial_nodes = []
					for cid, node_list in selection.items():
						contour_nodes = all_contours[cid].nodes()
						
						for nid in node_list:
							fl_node = contour_nodes[nid]
							# Ensure no start nodes end up in the clipboard
							if nid == 0 or nid == len(node_list) - 1:
								fl_node = fl6.flNode(fl_node.position, nodeType=fl_node.type)
							
							partial_nodes.append(fl_node)
					
					# - Create single contour from partial nodes
					tr_contour = flNodes_to_trContour(partial_nodes, False)
					tr_shape = Shape([tr_contour])
					tr_layer.append(tr_shape)
				
				tr_glyph.append(tr_layer)

			# - Generate unique identifier and store
			copy_uid = hash(random.getrandbits(128))
			self.contour_clipboard[copy_uid] = tr_glyph
						
			new_item =  self.__create_list_item(uid=copy_uid, tr_glyph=tr_glyph, fl_glyph=wGlyph, selection_dict=selection)
			self.mod_contours.appendRow(new_item)

			output(0, app_name, 'Copy contours; Glyph: %s; Layers: %s;' %(wGlyph.name, '; '.join(process_layers)))
		
	def paste_nodes(self, overwrite=False):
		'''Paste nodes over selection using node action collector.'''
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]
		do_delta = self.opt_delta_machine.isChecked()

		if len(gallery_selection):
			clipboard_item = gallery_selection[0]
			paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			tr_glyph = self.contour_clipboard[paste_uid]

			# - Paste with Delta Machine enabled
			if do_delta:
				virtual_axis, target_bounds = self.__prep_delta_parameters(tr_glyph, wGlyph, wLayers)
				if virtual_axis is None: do_delta = False
				
			# - Paste
			paste_data = {}
			for tr_layer in tr_glyph.layers:
				# - Paste with Delta Machine enabled
				if do_delta:
					print(f'{app_name}: Working in < Delta Machine > mode')
					current_bounds = target_bounds[tr_layer.name]
					process_layer = tr_layer.scale_with_axis(virtual_axis, current_bounds.width, current_bounds.height)
				else:
					process_layer = tr_layer

				fl_contour = trNodes_to_flContour(process_layer.nodes, is_closed=False)
				paste_data[tr_layer.name] = eNodesContainer(fl_contour.nodes())

			TRNodeActionCollector.nodes_paste(wGlyph, list(paste_data.keys()), paste_data, self.node_align_state, (self.chk_paste_flip_h.isChecked(), self.chk_paste_flip_v.isChecked(), False, False, overwrite, False))
			
			if self.opt_round.isChecked():
				TRNodeActionCollector.node_round(pMode, pLayers, True, True)
	
	def paste_contour(self, to_mask=False):
		'''Paste whole contours from clipboard.'''
		# - Init
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]
		do_delta = self.opt_delta_machine.isChecked()

		# - Process
		if len(gallery_selection):
			for clipboard_item in gallery_selection:
				paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
				is_partial = clipboard_item.data(QtCore.Qt.UserRole + 1001)
				tr_glyph = self.contour_clipboard[paste_uid]

				# - Paste with Delta Machine enabled
				if do_delta:
					virtual_axis, target_bounds = self.__prep_delta_parameters(tr_glyph, wGlyph, wLayers)
					if virtual_axis is None: do_delta = False

				if is_partial:
					output(3, app_name, '< Partial path > not suitable for < Paste contours > operation!')
					continue

				for tr_layer in tr_glyph.layers:
					layer_name = tr_layer.name
					
					work_layer = wGlyph.layer(layer_name) # Get destination layer or mask

					if to_mask:
						work_layer = wGlyph.mask(layer_name, force_create=True)
						layer_name = work_layer.name
					
					if work_layer is not None:
						fl_contours = []

						if do_delta:
							print(f'{app_name}: Working in < Delta Machine > mode')
							current_bounds = target_bounds[tr_layer.name]
							process_layer = tr_layer.scale_with_axis(virtual_axis, current_bounds.width, current_bounds.height, transform_origin=TransformOrigin.CENTER)
							process_layer.align_to(current_bounds.center_point, mode=(TransformOrigin.CENTER, TransformOrigin.CENTER), align=(True, True))
						else:
							process_layer = tr_layer
						
						for tr_shape in process_layer.shapes:
							for tr_contour in tr_shape.contours:
								fl_contour = trNodes_to_flContour(tr_contour.nodes, is_closed=tr_contour.closed)
								fl_contours.append(fl_contour)

						try:
							selected_shape = wGlyph.shapes(layer_name)[0]
						
						except IndexError:
							selected_shape = fl6.flShape()
							work_layer.addShape(selected_shape)

						selected_shape.addContours(fl_contours, True)
			
			if self.opt_round.isChecked():
				TRNodeActionCollector.node_round(pMode, pLayers, True, True)

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
					combined_data.setdefault(tr_layer.name, []).extend(tr_layer.nodes)

			for layer_name, tr_nodes in combined_data.items():
				work_layer = wGlyph.layer(layer_name)

				if work_layer is not None:
					new_contour = trNodes_to_flContour(tr_nodes, is_closed=self.opt_trace_close.isChecked())

					try:
						selected_shape = wGlyph.shapes(layer_name)[0]
					
					except IndexError:
						selected_shape = fl6.flShape()
						work_layer.addShape(selected_shape)

					selected_shape.addContours([new_contour], True)
			
			if self.opt_round.isChecked():
				TRNodeActionCollector.node_round(pMode, pLayers, True, True)

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
						xml_data += tr_glyph.to_XML(exclude_attrs)
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
						'''
						glyph_name = tr_glyph.name if tr_glyph.name else 'Unnamed'
						layer_count = len(tr_glyph.layers)
						contour_count = sum(len(shape.contours) for layer in tr_glyph.layers for shape in layer.shapes)
						
						new_item = QtGui.QStandardItem('{} | {} Layers | {} Contours'.format(glyph_name, layer_count, contour_count))
						new_item.setData(uid, QtCore.Qt.UserRole + 1000)
						new_item.setDropEnabled(False)
						new_item.setSelectable(True)
						'''

						new_item = self.__create_list_item(uid=uid, tr_glyph=tr_glyph)
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