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
import pickle

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
app_name, app_version = 'TypeRig | Contour', '1.2'
fileFormats = 'TypeRig binary data (*.dat);;'

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
		self.active_font = pFont()
		lay_main = QtGui.QVBoxLayout()
		self.contour_clipboard = {}
		self.node_align_state = 'LT'

		# -- Listview
		self.lst_contours = QtGui.QListView()
		self.mod_contours = QtGui.QStandardItemModel(self.lst_contours)
		#self.mod_contours.setItemPrototype(TRContourClipboardItem())
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
		#self.grp_paste_nodes_options.addButton(self.chk_paste_flip_h)
		lay_options_copy.addWidget(self.chk_paste_flip_h)

		tooltip_button =  "Node Paste: Flip vertically"
		self.chk_paste_flip_v = CustomPushButton("flip_vertical", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		#self.grp_paste_nodes_options.addButton(self.chk_paste_flip_v)
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

	def __set_align_state(self, align_state):
		self.node_align_state = align_state

	def act_node_copy(self):
		if self.chk_copy_nodes.isChecked():
			self.node_bank = TRNodeActionCollector.nodes_copy(eGlyph(), pLayers)
		else:
			self.node_bank = {}


	def __clear_selected(self):
		gallery_selection = [qidx.row() for qidx in self.lst_contours.selectedIndexes()]
		
		for idx in gallery_selection:
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
			#self.lst_contours.setMovement(QtGui.QListView.Static)
			
			self.lst_contours.setIconSize(QtCore.QSize(18, 18))
			self.lst_contours.setGridSize(QtCore.QSize()) 
			self.lst_contours.setSpacing(1)

	def __reverse_selected(self):
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]
		
		for clipboard_item in gallery_selection:
			item_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			clipboard_item_data = self.contour_clipboard[item_uid]
			temp_item = {}

			# - Reverse data item
			for layer, data in clipboard_item_data.items():
				temp_data = []

				if 'open' in clipboard_item.text().lower():
					temp_data = list(reversed(data))
				else:
					for contour in data:
						cloned_contour = contour.clone()
						cloned_contour.reverse()
						temp_data.append(cloned_contour)

				temp_item[layer] = temp_data

			# - Modify caption
			if cfg_addon_reversed in clipboard_item.text():
				new_caption = clipboard_item.text().replace(cfg_addon_reversed, '')
			else:
				new_caption = clipboard_item.text() + cfg_addon_reversed

			# - Set new clipboard data
			clipboard_item.setText(new_caption)
			self.contour_clipboard[item_uid] = temp_item

	def __drawIcon(self, contours, selection, foreground='black', background='gray'):
		# - Init
		# -- Prepare contours
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
			node_size = max(2, draw_dimension * 0.08)  # Size relative to icon dimension
			half = node_size / 2.0

			for node in selection:
				new_painter.drawEllipse(QtCore.QRectF(node.x - shape_bbox.x() - half, node.y - shape_bbox.y() - half, node_size, node_size))
		
		new_icon.addPixmap(new_pixmap.transformed(QtGui.QTransform().scale(1, -1)))
		
		return new_icon

	def copy_contour(self):
		# - Init
		wGlyph = eGlyph()
		current_contours = wGlyph.contours()
		process_layers = wGlyph._prepareLayers(pLayers)
		export_clipboard = OrderedDict()
		partial_path_mode = False
		
		# - Build initial contour information
		selection_tuples = wGlyph.selectedAtContours()
		selection = {}

		for cid, node_selection in groupby(selection_tuples, lambda x:x[0]):
			node_list = []

			if not current_contours[cid].isAllNodesSelected():
				node_list = [node[1] for node in node_selection]
				partial_path_mode = True

			selection[cid] = node_list

		# - Process
		if len(selection.keys()):
			
			# -- Add to gallery
			# --- Indicate layer selections
			if len(process_layers) == len(wGlyph.masters()):
				conditional_color = 'green'

			elif len(process_layers) == 1:
				conditional_color = 'red'

			else:
				conditional_color = 'blue'

			# --- Prepare icon and bank entry
			draw_contours = [wGlyph.contours()[cid] for cid in selection.keys()]
			draw_count = sum([contour.nodesCount for contour in draw_contours])
			new_item = QtGui.QStandardItem('{} | {} Nodes ({} Contour)'.format(wGlyph.name, draw_count, 'Closed ' if not partial_path_mode else 'Open'))

			if not partial_path_mode:
				new_icon = self.__drawIcon(draw_contours, selection={}, foreground=conditional_color)
			else:
				new_icon = self.__drawIcon(draw_contours, selection=wGlyph.selectedNodes(), foreground=conditional_color, background='LightGray')

			new_item.setIcon(new_icon)
			self.mod_contours.appendRow(new_item)

			# -- Add to clipboard
			for layer_name in process_layers:
				export_clipboard[layer_name] = []
				all_contours = wGlyph.contours(layer_name)

				if not partial_path_mode:
					for cid in selection.keys():
						export_clipboard[layer_name].append(all_contours[cid].clone())
				else:
					new_nodes = eNodesContainer(extend=eNode)

					for cid, node_list in selection.items():
						contour_nodes = all_contours[cid].nodes()
						
						for nid in node_list:
							temp_node = contour_nodes[nid].clone()
							
							if nid == 0 or nid == len(node_list) - 1: # Ensure no start nodes end up in the clipboard
								temp_node = fl6.flNode(temp_node.position, nodeType=temp_node.type)
							
							new_nodes.append(temp_node)
					
					export_clipboard[layer_name] = new_nodes

			# - Clipboard data item
			new_item.setDropEnabled(False)
			new_item.setSelectable(True)

			# -- Generate unique identifier
			copy_uid = hash(random.getrandbits(128))
			
			# - Set clipboard data
			self.contour_clipboard[copy_uid] = export_clipboard
			new_item.setData(copy_uid, QtCore.Qt.UserRole + 1000)

			output(0, app_name, 'Copy contours; Glyph: %s; Layers: %s.' %(wGlyph.name, '; '.join(process_layers)))
		
	def paste_nodes(self):
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

		if len(gallery_selection):
			clipboard_item = gallery_selection[0]
			paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
			paste_data = self.contour_clipboard[paste_uid]

			TRNodeActionCollector.nodes_paste(wGlyph, wLayers, paste_data, self.node_align_state, (self.chk_paste_flip_h.isChecked(), self.chk_paste_flip_v.isChecked(), False, False, True, False))
	
	def paste_contour(self, to_mask=False):
		# - Init
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

		# - Helper
		def add_new_shape(layer, contours):
			newShape = fl6.flShape()
			newShape.addContours(contours, True)
			layer.addShape(newShape)

		# - Process
		if len(gallery_selection):
			for clipboard_item in gallery_selection:
				paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
				paste_data = self.contour_clipboard[paste_uid]

				for layerName, contours in paste_data.items():
					# - Get destination layer or mask. If mask is missing create it
					wLayer = wGlyph.layer(layerName)

					if to_mask:
						wLayer = wGlyph.mask(layerName, force_create=True)
						layerName = wLayer.name

					# - Skip if wrong data type is being fed
					if not isinstance(contours[0], fl6.flContour): 
						output(3, app_name, '< Partial path > not suitable for < Paste contours > operation!')
						return
					
					if wLayer is not None:	
						# - Process transform
						cloned_contours = [contour.clone() for contour in contours]

						# - Insert contours into currently selected shape
						try:
							selected_shape = wGlyph.shapes(layerName)[0]
						
						except IndexError:
							selected_shape = fl6.flShape()
							wLayer.addShape(selected_shape)

						selected_shape.addContours(cloned_contours, True)
					
			wGlyph.updateObject(wGlyph.fl, 'Paste contours; Glyph: %s; Layers: %s' %(wGlyph.name, '; '.join(wLayers)))

	def paste_path(self):
		# - Init
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers)
		gallery_selection = [self.lst_contours.model().itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]

		# - Helper
		def add_new_shape(layer, contours):
			newShape = fl6.flShape()
			newShape.addContours(contours, True)
			layer.addShape(newShape)

		# - Process
		if len(gallery_selection):
			combined_data = {}
			
			for clipboard_item in gallery_selection:
				paste_uid = clipboard_item.data(QtCore.Qt.UserRole + 1000)
				paste_data = self.contour_clipboard[paste_uid]

				for layer_name, contours in paste_data.items():
					combined_data.setdefault(layer_name, []).extend(contours)

			for layer_name, data in combined_data.items():
				wLayer = wGlyph.layer(layer_name)
			
				if isinstance(data, list) and isinstance(data[0], eNode):
					nodes = [item.fl for item in data]
				else:
					nodes = data

				if not isinstance(nodes[0], fl6.flNode): 
						output(3, app_name, '< Contour > not suitable for < Paste partial path > operation!')
						return

				if wLayer is not None:	
					# - Process nodes
					cloned_nodes = [node.clone() for node in nodes]
					new_contour = fl6.flContour(cloned_nodes)
					new_contour.closed = self.opt_trace_close.isChecked()

					# - Insert contours into currently selected shape
					try:
						selected_shape = wGlyph.shapes(layer_name)[0]
					
					except IndexError:
						selected_shape = fl6.flShape()
						wLayer.addShape(selected_shape)

					selected_shape.addContours([new_contour], True)
					
			wGlyph.updateObject(wGlyph.fl, 'Paste contours; Glyph: %s; Layers: %s' %(wGlyph.name, '; '.join(wLayers)))

		# -- File operations
	def clipboard_save(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self, 'Save clipboard data to file', fontPath, fileFormats)

		if fname != None:
			with open(fname, 'w') as exportFile:
				pickle.dump(self.contour_clipboard, exportFile)
				output(7, app_name, 'Font: %s; Smart clipboard data saved to: %s.' %(self.active_font.name, fname))
				
	def clipboard_load(self):
		fontPath = os.path.split(self.active_font.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self, 'Load clipboard data from file', fontPath, fileFormats)
			
		if fname != None:
			with open(fname, 'r') as importFile:
				imported_data = pickle.load(importFile)
				output(6, app_name, 'Font: %s; Smart clipboard dat from: %s.' %(self.active_font.name, fname))


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