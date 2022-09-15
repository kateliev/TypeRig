#FLM: TypeRig: Match Contours
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2022 		(http://www.kateliev.com)
# (C) TypeRig 						(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from itertools import permutations
import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.shape import eShape
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, TRHTabWidget, CustomPushButton, CustomLabel
from typerig.proxy.fl.gui.styles import css_tr_button

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TR | Match Contours', '2.7'

TRToolFont = getTRIconFontPath()
font_loaded = QtGui.QFontDatabase.addApplicationFont(TRToolFont)

# - Configuration ----------------------
color_foreground = QtGui.QColor('gray')
color_background = QtGui.QColor('white')
color_basepen = QtGui.QColor('black')
colors_tuples = [(255, 0, 0, 100),
				(0, 255, 0, 100),
				(0, 0, 255, 100)]
			
colors_tuples += list(permutations(range(0,256, 32), 3))
accent_colors = [QtGui.QColor(*item) for item in colors_tuples]

color_wind_ccw = QtGui.QColor(0, 0, 255, 100)
color_wind_cw = QtGui.QColor(255, 0, 0, 100)
color_start_accent = QtGui.QColor(0, 255, 0, 255)

draw_padding = 100
draw_size = 100
draw_radius = 18

# - Sub widgets ------------------------
class TRWContourView(QtGui.QTableWidget):
	def __init__(self, data, aux):
		super(TRWContourView, self).__init__()
		
		# - Init
		self.aux = aux
		self.set_table(data)	
		self.setIconSize(QtCore.QSize(draw_size, draw_size))
		
		# - Styling
		self.setShowGrid(False)
	
	def set_table(self, data, clear=True):
		# - Fix sorting
		if clear: self.clear()
		self.setSortingEnabled(False)
		self.blockSignals(True)
		self.setDragDropMode(self.InternalMove)
		self.setDragEnabled(True)
		self.setDropIndicatorShown(True)
		self.model().sort(-1)
		self.horizontalHeader().setSortIndicator(-1, 0)
		self.setIconSize(QtCore.QSize(draw_size, draw_size))	

		# - Init
		column_names = []
		self.setRowCount(len(data[0][1]))
		self.setColumnCount(len(data))
		name_row = []

		# - Populate
		for col, layer_data in enumerate(data):
			column_names.append(layer_data[0])

			for row, draw_data in enumerate(layer_data[1]):
				newitem = QtGui.QTableWidgetItem()
				newitem.setIcon(draw_data)
				self.setItem(row, col, newitem)

		self.setHorizontalHeaderLabels(column_names)
		self.resizeRowsToContents()
		self.resizeColumnsToContents()
		self.blockSignals(False)
	
	def dropEvent(self, event):
		new_index = self.rowAt(event.pos().y())
		
		for item in self.selectedItems():
			old_index = item.row()
			layer_index = item.column()
			self.aux.drop_item(layer_index, old_index, new_index)

		self.aux.refresh()

# - Main widgets -------------------------------------------------		
class TRWContoursOrder(QtGui.QWidget):
	'''Match layers by changing the contours order via drag and drop'''
	def __init__(self, aux):
		super(TRWContoursOrder, self).__init__()

		# - Init
		self.aux = aux
		glyph_pixmaps = self.__pixmaps_refresh()

		# -- Table
		self.tab_glyphs = TRWContourView(glyph_pixmaps, self)

		# -- Buttons
		self.btn_sort_x = QtGui.QPushButton('Sort X Only')
		self.btn_sort_y = QtGui.QPushButton('Sort Y Only')
		
		self.btn_sort_LRBT = QtGui.QPushButton('Left -> Right and Bottom -> Top')
		self.btn_sort_LRTB = QtGui.QPushButton('Left -> Right and Top -> Bottom')
		
		self.btn_sort_x.setToolTip('Use ALT+CLICK to reverse order')
		self.btn_sort_y.setToolTip('Use ALT+CLICK to reverse order')
		self.btn_sort_LRBT.setToolTip('Use ALT+CLICK to reverse order')
		self.btn_sort_LRTB.setToolTip('Use ALT+CLICK to reverse order')
		
		self.btn_sort_x.clicked.connect(lambda: self.set_order((True, None)))
		self.btn_sort_y.clicked.connect(lambda: self.set_order((None, True)))
		self.btn_sort_LRBT.clicked.connect(lambda: self.set_order((True, True)))
		self.btn_sort_LRTB.clicked.connect(lambda: self.set_order((True, False)))

		# - Layout
		lay_tail = QtGui.QHBoxLayout()
		lay_tail.addWidget(self.btn_sort_x)
		lay_tail.addWidget(self.btn_sort_y)
		lay_tail.addWidget(self.btn_sort_LRBT)
		lay_tail.addWidget(self.btn_sort_LRTB)

		lay_main = QtGui.QVBoxLayout()
		lay_main.addWidget(self.tab_glyphs)
		lay_main.addLayout(lay_tail)
		
		# - Set 
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())

	# - Internal functions ------------------------
	def __pixmaps_refresh(self):
		# - Init
		return_pixmaps = []

		for layer in self.aux.glyph.masters():
			layer_shapes = []
			
			for idx, shape in enumerate(layer.shapes):
				layer_shapes.append(self.__drawIcons(shape.contours, accent_colors[idx]))

			return_pixmaps.append((layer.name, sum(layer_shapes,[])))
		
		return return_pixmaps

	def __drawIcons(self, contours, color_accent):
		# - Init
		return_icons = []
		sep_contours = []

		# -- Prepare contours
		cloned_contours = [contour.clone() for contour in contours]
		main_shape = fl6.flShape()

		for cid in range(len(cloned_contours)):
			main_shape.addContour(cloned_contours[cid], True)

		for cid in range(len(cloned_contours)):
			contour_shape = fl6.flShape()
			contour_shape.addContour(cloned_contours[cid], True)
			sep_contours.append((contour_shape, main_shape.clone()))

		# - Prepare
		main_painter = QtGui.QPainter()
		shape_bbox = main_shape.boundingBox
		draw_dimension = max(shape_bbox.width(), shape_bbox.height()) + 2*draw_padding

		for cid, draw_contours in enumerate(sep_contours):
			new_icon = QtGui.QIcon()
			cont_painter= QtGui.QPainter()
			cont_pixmap = QtGui.QPixmap(draw_dimension, draw_dimension)
			
			cont_shape, other_shape = draw_contours

			# - Draw Background
			cont_painter.begin(cont_pixmap)
			cont_painter.setBrush(QtGui.QBrush(color_background))
			cont_painter.drawRect(QtCore.QRectF(0, 0, draw_dimension, draw_dimension))

			# - Draw all other contours
			cont_painter.setBrush(QtGui.QBrush(color_foreground))
			cont_painter.setPen(QtGui.QPen(color_basepen, 10, QtCore.Qt.SolidLine))
			new_transform = other_shape.transform.translate(-shape_bbox.x() + draw_padding, -shape_bbox.y() + draw_padding)
			other_shape.applyTransform(new_transform)
			other_shape.ensurePaths()
			cont_painter.drawPath(other_shape.closedPath)

			# - Draw the specific contour
			cont_painter.setBrush(QtGui.QBrush(color_accent))
			cont_painter.setPen(QtGui.QPen(color_accent, 30, QtCore.Qt.SolidLine))
			new_transform = cont_shape.transform.translate(-shape_bbox.x() + draw_padding, -shape_bbox.y() + draw_padding)
			cont_shape.applyTransform(new_transform)
			cont_shape.ensurePaths()
			cont_painter.drawPath(cont_shape.closedPath)

			pixmap_transform = QtGui.QTransform().scale(draw_size/draw_dimension, -draw_size/draw_dimension)
			pixmap_resized = cont_pixmap.transformed(pixmap_transform, QtCore.Qt.SmoothTransformation)
			new_icon.addPixmap(pixmap_resized)

			return_icons.append(new_icon)

		return return_icons

	# - Procedures ---------------------------------------
	def refresh(self, clear=True):
		glyph_pixmaps = self.__pixmaps_refresh()
		self.tab_glyphs.set_table(glyph_pixmaps, clear)

	def drop_item(self, lid, oid, nid):
		work_layer_name = self.aux.glyph.masters()[lid].name
		work_shape = self.aux.glyph.shapes(work_layer_name)[0] # Only first shape for now
		work_contours = work_shape.contours
		work_contours[oid], work_contours[nid] = work_contours[nid], work_contours[oid]
		work_shape.contours = work_contours
		work_shape.update()

		#self.refresh()

	def set_order(self, sort_order):
		work_layers = self.aux.glyph.masters()
		modifiers = QtGui.QApplication.keyboardModifiers()
		
		reverse_order = []
		for item in sort_order:
			new_item = not item if item is not None else None
			reverse_order.append(new_item)

		for layer in work_layers:
			work_shapes = self.aux.glyph.shapes(layer.name, extend=eShape)

			for shape in work_shapes:
				if modifiers == QtCore.Qt.AltModifier:
					shape.contourOrder(reverse_order)
				else:
					shape.contourOrder(sort_order)

		self.refresh()
		

class TRWContoursWinding(QtGui.QWidget):
	'''Match layers by changing the contours winding direction via drag and drop'''
	def __init__(self, aux):
		super(TRWContoursWinding, self).__init__()

		# - Init
		self.aux = aux
		glyph_pixmaps = self.__pixmaps_refresh()

		# -- Table
		self.tab_glyphs = TRWContourView(glyph_pixmaps, self)

		# -- Buttons
		self.btn_contour_reverse = QtGui.QPushButton('Reverse')
		self.btn_contour_reverse.clicked.connect(self.reverse_items)

		# - Layout
		lay_tail = QtGui.QHBoxLayout()
		lay_tail.addWidget(self.btn_contour_reverse)

		lay_main = QtGui.QVBoxLayout()
		lay_main.addWidget(self.tab_glyphs)
		lay_main.addLayout(lay_tail)
		
		# - Set 
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())

	# - Internal functions ------------------------
	def __pixmaps_refresh(self):
		# - Init
		return_pixmaps = []

		for layer in self.aux.glyph.masters():
			return_pixmaps.append((layer.name, self.__drawIcons(layer.getContours())))
		
		return return_pixmaps

	def __drawIcons(self, contours):
		# - Init
		return_icons = []
		sep_contours = []

		# -- Prepare contours
		cloned_contours = [contour.clone() for contour in contours]
		main_shape = fl6.flShape()

		for cid in range(len(cloned_contours)):
			main_shape.addContour(cloned_contours[cid], True)

		for cid in range(len(cloned_contours)):
			contour_shape = fl6.flShape()
			contour_shape.addContour(cloned_contours[cid], True)
			sep_contours.append((contour_shape, main_shape.clone()))

		# - Prepare
		main_painter = QtGui.QPainter()
		shape_bbox = main_shape.boundingBox
		draw_dimension = max(shape_bbox.width(), shape_bbox.height()) + 2*draw_padding

		for cid, draw_contours in enumerate(sep_contours):
			new_icon = QtGui.QIcon()
			cont_painter= QtGui.QPainter()
			cont_pixmap = QtGui.QPixmap(draw_dimension, draw_dimension)
			
			cont_shape, other_shape = draw_contours

			# - Draw Background
			cont_painter.begin(cont_pixmap)
			cont_painter.setBrush(QtGui.QBrush(color_background))
			cont_painter.drawRect(QtCore.QRectF(0, 0, draw_dimension, draw_dimension))

			# - Draw all other contours
			cont_painter.setBrush(QtGui.QBrush(color_foreground))
			cont_painter.setPen(QtGui.QPen(color_basepen, 10, QtCore.Qt.SolidLine))
			new_transform = other_shape.transform.translate(-shape_bbox.x() + draw_padding, -shape_bbox.y() + draw_padding)
			other_shape.applyTransform(new_transform)
			other_shape.ensurePaths()
			cont_painter.drawPath(other_shape.closedPath)

			# - Draw the specific contour
			# -- Set different colors accents based on winding direction
			color_accent = color_wind_ccw if cont_shape.contours[0].clockwise else color_wind_cw

			cont_painter.setBrush(QtGui.QBrush(color_accent))
			cont_painter.setPen(QtGui.QPen(color_accent, 30, QtCore.Qt.SolidLine))
			new_transform = cont_shape.transform.translate(-shape_bbox.x() + draw_padding, -shape_bbox.y() + draw_padding)
			cont_shape.applyTransform(new_transform)
			cont_shape.ensurePaths()
			cont_painter.drawPath(cont_shape.closedPath)

			pixmap_transform = QtGui.QTransform().scale(draw_size/draw_dimension, -draw_size/draw_dimension)
			pixmap_resized = cont_pixmap.transformed(pixmap_transform, QtCore.Qt.SmoothTransformation)
			new_icon.addPixmap(pixmap_resized)

			return_icons.append(new_icon)

		return return_icons

	# - Procedures ---------------------------------------
	def refresh(self, clear=True):
		glyph_pixmaps = self.__pixmaps_refresh()
		self.tab_glyphs.set_table(glyph_pixmaps, clear)

	def drop_item(self, lid, oid, nid):
		work_layer_name = self.aux.glyph.masters()[lid].name
		work_layer_contours = self.aux.glyph.layer(work_layer_name).getContours()
		
		if work_layer_contours[oid].clockwise != work_layer_contours[nid].clockwise:
			work_layer_contours[nid].reverse()

		#self.refresh()

	def reverse_items(self):
		for item in self.tab_glyphs.selectedItems():
			contour_index = item.row()
			layer_index = item.column()

			work_layer_name = self.aux.glyph.masters()[layer_index].name
			work_layer_contours = self.aux.glyph.layer(work_layer_name).getContours()
			work_layer_contours[contour_index].reverse()

		self.refresh(False)

class TRWContoursStart(QtGui.QWidget):
	'''Match layers by changing the contours start point'''
	def __init__(self, aux):
		super(TRWContoursStart, self).__init__()

		# - Init
		self.aux = aux
		glyph_pixmaps = self.__pixmaps_refresh()

		# -- Table
		self.tab_glyphs = TRWContourView(glyph_pixmaps, self)

		# -- Buttons
		self.btn_BL = QtGui.QPushButton('Bottom Left')
		self.btn_TL = QtGui.QPushButton('Top Left')
		self.btn_BR = QtGui.QPushButton('Bottom Right')
		self.btn_TR = QtGui.QPushButton('Top Right')
		self.btn_next = QtGui.QPushButton('Ne&xt')
		self.btn_prev = QtGui.QPushButton('Previou&s')

		self.btn_BL.clicked.connect(lambda: self.set_start_node((0,0)))
		self.btn_TL.clicked.connect(lambda: self.set_start_node((0,1)))
		self.btn_BR.clicked.connect(lambda: self.set_start_node((1,0)))
		self.btn_TR.clicked.connect(lambda: self.set_start_node((1,1)))
		self.btn_next.clicked.connect(lambda: self.shift_start_node(True))
		self.btn_prev.clicked.connect(lambda: self.shift_start_node(False))

		# - Layout
		lay_tail = QtGui.QHBoxLayout()
		lay_tail.addWidget(self.btn_BL)
		lay_tail.addWidget(self.btn_TL)
		lay_tail.addWidget(self.btn_BR)
		lay_tail.addWidget(self.btn_TR)
		lay_tail.addWidget(self.btn_prev)
		lay_tail.addWidget(self.btn_next)

		lay_main = QtGui.QVBoxLayout()
		lay_main.addWidget(self.tab_glyphs)
		lay_main.addLayout(lay_tail)
		
		# - Set 
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())

	# - Internal functions ------------------------
	def __pixmaps_refresh(self):
		# - Init
		return_pixmaps = []

		for layer in self.aux.glyph.masters():
			return_pixmaps.append((layer.name, self.__drawIcons(layer.getContours())))
		
		return return_pixmaps

	def __drawIcons(self, contours):
		# - Init
		return_icons = []
		sep_contours = []

		# -- Prepare contours
		cloned_contours = [contour.clone() for contour in contours]
		main_shape = fl6.flShape()

		for cid in range(len(cloned_contours)):
			main_shape.addContour(cloned_contours[cid], True)

		for cid in range(len(cloned_contours)):
			contour_shape = fl6.flShape()
			contour_shape.addContour(cloned_contours[cid], True)
			sep_contours.append((contour_shape, main_shape.clone()))

		# - Prepare
		main_painter = QtGui.QPainter()
		shape_bbox = main_shape.boundingBox
		draw_dimension = max(shape_bbox.width(), shape_bbox.height()) + 2*draw_padding

		for cid, draw_contours in enumerate(sep_contours):
			new_icon = QtGui.QIcon()
			cont_painter= QtGui.QPainter()
			cont_pixmap = QtGui.QPixmap(draw_dimension, draw_dimension)
			
			cont_shape, other_shape = draw_contours

			# - Draw Background
			cont_painter.begin(cont_pixmap)
			cont_painter.setBrush(QtGui.QBrush(color_background))
			cont_painter.drawRect(QtCore.QRectF(0, 0, draw_dimension, draw_dimension))

			# - Draw all other contours
			cont_painter.setBrush(QtGui.QBrush(color_foreground))
			cont_painter.setPen(QtGui.QPen(color_basepen, 10, QtCore.Qt.SolidLine))
			new_transform = other_shape.transform.translate(-shape_bbox.x() + draw_padding, -shape_bbox.y() + draw_padding)
			other_shape.applyTransform(new_transform)
			other_shape.ensurePaths()
			cont_painter.drawPath(other_shape.closedPath)

			# - Draw the specific contour
			# -- Set different colors accents based on winding direction
			color_accent = color_wind_ccw if cont_shape.contours[0].clockwise else color_wind_cw
			
			srong_accent = QtGui.QColor(color_accent)
			weak_accent = QtGui.QColor(color_accent)
			
			weak_accent.setAlpha(50)
			srong_accent.setAlpha(255)

			cont_painter.setBrush(QtGui.QBrush(weak_accent))
			cont_painter.setPen(QtGui.QPen(srong_accent, 10, QtCore.Qt.SolidLine))
			new_transform = cont_shape.transform.translate(-shape_bbox.x() + draw_padding, -shape_bbox.y() + draw_padding)
			cont_shape.applyTransform(new_transform)
			cont_shape.ensurePaths()

			# - Draw path
			draw_path = cont_shape.closedPath
			cont_painter.drawPath(draw_path)

			# - Draw nodes
			cont_painter.setBrush(QtGui.QBrush(srong_accent))

			for i in range(draw_path.elementCount()):
				if i == 0:
					cont_painter.setBrush(QtGui.QBrush(color_start_accent))
					cont_painter.setPen(QtGui.QPen(color_start_accent, 10, QtCore.Qt.SolidLine))
				else:
					cont_painter.setBrush(QtGui.QBrush(srong_accent))
					cont_painter.setPen(QtGui.QPen(srong_accent, 10, QtCore.Qt.SolidLine))

				node_info = cont_shape.getNodeAt(i, 7)

				if node_info is not None and node_info.isOn():
					node = draw_path.elementAt(i)
					cont_painter.drawEllipse(node.x - draw_radius, node.y - draw_radius, draw_radius*2, draw_radius*2)

			pixmap_transform = QtGui.QTransform().scale(draw_size/draw_dimension, -draw_size/draw_dimension)
			pixmap_resized = cont_pixmap.transformed(pixmap_transform, QtCore.Qt.SmoothTransformation)
			new_icon.addPixmap(pixmap_resized)

			return_icons.append(new_icon)

		return return_icons

	# - Procedures ---------------------------------------
	def refresh(self, clear=True):
		glyph_pixmaps = self.__pixmaps_refresh()
		self.tab_glyphs.set_table(glyph_pixmaps, clear)

	def drop_item(self, lid, oid, nid):
		return

	def set_start_node(self, control=(0,0)):
		# - Init
		if control == (0,0): 	# BL
			criteria = lambda node : (node.y, node.x)
		elif control == (0,1): 	# TL
			criteria = lambda node : (-node.y, node.x)
		elif control == (1,0): 	# BR
			criteria = lambda node : (node.y, -node.x)
		elif control == (1,1): 	# TR
			criteria = lambda node : (-node.y, -node.x)

		# - Process selection
		for item in self.tab_glyphs.selectedItems():
			contour_index = item.row()
			layer_index = item.column()

			work_layer_name = self.aux.glyph.masters()[layer_index].name
			work_layer_contours = self.aux.glyph.layer(work_layer_name).getContours()
			work_contour = work_layer_contours[contour_index]
			onNodes = [node for node in work_contour.nodes() if node.isOn()]
			newFirstNode = sorted(onNodes, key=criteria)[0]
			work_contour.setStartPoint(newFirstNode.index)

		self.refresh(False)

	def shift_start_node(self, forward=True):
		# - Process selection
		for item in self.tab_glyphs.selectedItems():
			contour_index = item.row()
			layer_index = item.column()

			work_layer_name = self.aux.glyph.masters()[layer_index].name
			work_layer_contours = self.aux.glyph.layer(work_layer_name).getContours()
			work_contour = work_layer_contours[contour_index]
			onNodes = [node for node in work_contour.nodes() if node.isOn()]
			new_start_index = 1 if forward else len(onNodes) - 1
			work_contour.setStartPoint(new_start_index)

		self.refresh(False)
	
# - Dialogs ------------------------------------------------
class typerig_match(QtGui.QDialog):
	def __init__(self):
		super(typerig_match, self).__init__()
	
		# - Init --------------------------
		self.setStyleSheet(css_tr_button)
		self.glyph = eGlyph()

		# - Tabs --------------------------
		self.tab_tools = TRHTabWidget()
		
		self.tool_contour_order = TRWContoursOrder(self)
		self.tool_contour_wind = TRWContoursWinding(self)
		self.tool_contour_start = TRWContoursStart(self)
		
		self.tab_tools.addTab(self.tool_contour_order, 'Contour Order')
		self.tab_tools.addTab(self.tool_contour_wind, 'Contour Winding')
		self.tab_tools.addTab(self.tool_contour_start, 'Contour Start')

		# -- Spinboxes
		self.spn_icon_size = QtGui.QSpinBox()
		self.spn_icon_size.setMinimum(20)
		self.spn_icon_size.setMaximum(300)
		self.spn_icon_size.setSingleStep(20)
		self.spn_icon_size.setValue(draw_size)
		self.spn_icon_size.valueChanged.connect(self.tools_refresh)

		# -- Editing fields
		self.edt_glyph_name = QtGui.QLineEdit()
		self.edt_glyph_name.setText(self.glyph.name)
		self.edt_glyph_name.setMaximumWidth(200)

		# -- Buttons
		self.btn_refresh = CustomPushButton('refresh', obj_name='btn_mast')
		self.btn_refresh.setMinimumWidth(40)

		self.btn_apply = QtGui.QPushButton('&Apply')
		self.btn_apply.setMinimumWidth(200)
		
		self.btn_refresh.clicked.connect(self.tools_refresh)
		self.btn_apply.clicked.connect(self.tools_update)
		
		# - Layouts -------------------------------
		lay_tail = QtGui.QHBoxLayout()
		lay_tail.addWidget(CustomLabel('label', 'lbl_icon'))
		lay_tail.addWidget(self.edt_glyph_name)
		lay_tail.addWidget(self.btn_refresh)
		lay_tail.addWidget(self.btn_apply)
		lay_tail.addStretch()
		lay_tail.addWidget(CustomLabel('search','lbl_icon'))
		lay_tail.addWidget(self.spn_icon_size)

		lay_main = QtGui.QVBoxLayout() 
		lay_main.addLayout(lay_tail)
		lay_main.addWidget(self.tab_tools)

		# - Set Widget -------------------------------
		self.setLayout(lay_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(100, 100, 1440, 880)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def tools_refresh(self):
		# - Init
		global draw_size
		self.glyph = eGlyph()
		
		draw_size = self.spn_icon_size.value
		self.edt_glyph_name.setText(self.glyph.name)

		# - Refresh tabs
		self.tool_contour_order.refresh(True)
		self.tool_contour_wind.refresh(True)
		self.tool_contour_start.refresh(True)

	def tools_update(self):
		self.glyph.updateObject(self.glyph.fl, '{} | Glyph: {}'.format(app_name, self.glyph.name))

# - RUN ------------------------------
dialog = typerig_match()