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

from typerig.proxy.fl.objects.glyph import eGlyph, pGlyph
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import TRHTabWidget

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TR | Match Contours', '2.1'

# - Configuration ----------------------
color_foreground = QtGui.QColor('gray')
color_background = QtGui.QColor('white')
color_basepen = QtGui.QColor('black')
colors_tuples = [(255, 0, 0, 100),
				(0, 255, 0, 100),
				(0, 0, 255, 100)]
			
colors_tuples += list(permutations(range(0,256, 32), 3))
accent_colors = [QtGui.QColor(*item) for item in colors_tuples]

color_wind_ccw = QtGui.QColor(0, 255, 0, 100)
color_wind_cw = QtGui.QColor(255, 0, 0, 100)

draw_padding = 100
draw_size = 100

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
		self.setAlternatingRowColors(True)
	
	def set_table(self, data):
		# - Fix sorting
		self.clear()
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

		# - Layout
		lay_main = QtGui.QVBoxLayout()
		lay_main.addWidget(self.tab_glyphs)
		
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

			new_icon.addPixmap(cont_pixmap.transformed(QtGui.QTransform().scale(1, -1)))

			return_icons.append(new_icon)

		return return_icons

	# - Procedures ---------------------------------------
	def refresh(self):
		glyph_pixmaps = self.__pixmaps_refresh()
		self.tab_glyphs.set_table(glyph_pixmaps)

	def drop_item(self, lid, oid, nid):
		work_layer_name = self.aux.glyph.masters()[lid].name
		work_shape = self.aux.glyph.shapes(work_layer_name)[0] # Only first shape for now
		work_contours = work_shape.contours
		work_contours[oid], work_contours[nid] = work_contours[nid], work_contours[oid]
		work_shape.contours = work_contours
		work_shape.update()

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

			new_icon.addPixmap(cont_pixmap.transformed(QtGui.QTransform().scale(1, -1)))

			return_icons.append(new_icon)

		return return_icons

	# - Procedures ---------------------------------------
	def refresh(self):
		glyph_pixmaps = self.__pixmaps_refresh()
		self.tab_glyphs.set_table(glyph_pixmaps)

	def drop_item(self, lid, oid, nid):
		work_layer_name = self.aux.glyph.masters()[lid].name
		work_layer_contours = self.aux.glyph.layer(work_layer_name).getContours()
		
		if work_layer_contours[oid].clockwise != work_layer_contours[nid].clockwise:
			work_layer_contours[nid].reverse()

		self.refresh()

	def reverse_items(self):
		for item in self.tab_glyphs.selectedItems():
			contour_index = item.row()
			layer_index = item.column()

			work_layer_name = self.aux.glyph.masters()[layer_index].name
			work_layer_contours = self.aux.glyph.layer(work_layer_name).getContours()
			work_layer_contours[contour_index].reverse()

		self.refresh()
	
# - Dialogs ------------------------------------------------
class typerig_match(QtGui.QDialog):
	def __init__(self):
		super(typerig_match, self).__init__()
	
		# - Init --------------------------
		self.glyph = pGlyph()

		# - Tabs --------------------------
		self.tab_tools = TRHTabWidget()
		
		self.tool_contour_order = TRWContoursOrder(self)
		self.tool_contour_wind = TRWContoursWinding(self)
		
		self.tab_tools.addTab(self.tool_contour_order, 'Contour Order')
		self.tab_tools.addTab(self.tool_contour_wind, 'Contour Winding')

		# -- Buttons
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_apply = QtGui.QPushButton('&Apply')
		
		self.btn_refresh.clicked.connect(self.tools_refresh)
		self.btn_apply.clicked.connect(self.tools_update)
		
		# - Layouts -------------------------------
		lay_tail = QtGui.QHBoxLayout()
		lay_tail.addWidget(self.btn_refresh)
		lay_tail.addWidget(self.btn_apply)

		lay_main = QtGui.QVBoxLayout() 
		lay_main.setContentsMargins(0,0,0,0)
		lay_main.addWidget(self.tab_tools)
		lay_main.addLayout(lay_tail)

		# - Set Widget -------------------------------
		self.setLayout(lay_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(100, 100, 1440, 880)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

	def tools_refresh(self):
		# - Init
		self.glyph = pGlyph()

		# - Match contour order
		self.tool_contour_order.refresh()
		self.tool_contour_wind.refresh()

	def tools_update(self):
		self.glyph.updateObject(self.glyph.fl, '{} | Glyph: {}'.format(app_name, self.glyph.name))

# - RUN ------------------------------
dialog = typerig_match()