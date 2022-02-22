#FLM: TypeRig: Match Contours
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2022 		(http://www.kateliev.com)
# (C) TypeRig 						(http://www.typerig.com)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
from collections import OrderedDict
import warnings

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.glyph import eGlyph, pGlyph
from typerig.core.base.message import *

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui

# - Init -------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TR | Match Contours', '1.7'

# - Sub widgets ------------------------
class TRWContourView(QtGui.QTableWidget):
	def __init__(self, data, aux):
		super(TRWContourView, self).__init__()
		
		# - Init
		self.aux = aux
		self.set_table(data)	
		self.setIconSize(QtCore.QSize(100, 100))
		
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
		self.setIconSize(QtCore.QSize(100, 100))	

		# - Init
		column_names = []
		self.setRowCount(len(list(data.items())[0][1]))
		self.setColumnCount(len(data.keys()))
		name_row = []

		# - Populate
		for col, layer_name in enumerate(data.keys()):
			column_names.append(layer_name)

			for row, glyph_data in enumerate(data[layer_name]):
				newitem = QtGui.QTableWidgetItem()
				newitem.setIcon(glyph_data)
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
			self.aux.moveContour(layer_index, old_index, new_index)

		self.set_table(self.aux.contours_refresh())
				
class TRIconsProspect(QtGui.QDialog):
	# - Split/Break contour 
	def __init__(self):
		super(TRIconsProspect, self).__init__()

		# - Init
		self.glyph = pGlyph()
		glyph_contours = self.contours_refresh()

		# -- Buttons
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_apply = QtGui.QPushButton('&Apply')
		
		self.btn_refresh.clicked.connect(lambda: self.tab_glyphs.set_table(self.contours_refresh()))
		self.btn_apply.clicked.connect(lambda: self.glyph.updateObject(self.glyph.fl, '{} | Glyph: {}'.format(app_name, self.glyph.name)))

		# -- Table
		self.tab_glyphs = TRWContourView(glyph_contours, self)

		# - Layout
		lay_tail = QtGui.QHBoxLayout()
		lay_tail.addWidget(self.btn_refresh)
		lay_tail.addWidget(self.btn_apply)
		
		lay_main = QtGui.QVBoxLayout()
		lay_main.addWidget(self.tab_glyphs)
		lay_main.addLayout(lay_tail)
		
		# - Set 
		self.setLayout(lay_main)
		self.setMinimumSize(300, self.sizeHint.height())

	def contours_refresh(self):
		# - Init
		self.glyph = pGlyph()
		return_icons = []

		for layer in self.glyph.masters():
			return_icons.append((layer.name, self.__drawIcons(layer.getContours())))
		
		return OrderedDict(return_icons)

	def moveContour(self, lid, oid, nid):
		work_layer_name = self.glyph.masters()[lid].name
		work_shape = self.glyph.shapes(work_layer_name)[0] # Only first shape for now
		work_contours = work_shape.contours
		work_contours[oid], work_contours[nid] = work_contours[nid], work_contours[oid]
		work_shape.contours = work_contours
		work_shape.update()

	def __drawIcons(self, contours):
		# - Init
		color_foreground = QtGui.QColor('gray')
		color_background = QtGui.QColor('white')
		color_accent = QtGui.QColor('red')
		color_accent.setAlpha(100)
		color_basepen = QtGui.QColor('black')
		padding = 100
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
		draw_dimension = max(shape_bbox.width(), shape_bbox.height()) + 2*padding

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
			new_transform = other_shape.transform.translate(-shape_bbox.x() + padding, -shape_bbox.y() + padding)
			other_shape.applyTransform(new_transform)
			other_shape.ensurePaths()
			cont_painter.drawPath(other_shape.closedPath)

			# - Draw the specific contour
			cont_painter.setBrush(QtGui.QBrush(color_accent))
			cont_painter.setPen(QtGui.QPen(color_accent, 30, QtCore.Qt.SolidLine))
			new_transform = cont_shape.transform.translate(-shape_bbox.x() + padding, -shape_bbox.y() + padding)
			cont_shape.applyTransform(new_transform)
			cont_shape.ensurePaths()
			cont_painter.drawPath(cont_shape.closedPath)

			new_icon.addPixmap(cont_pixmap.transformed(QtGui.QTransform().scale(1, -1)))

			return_icons.append(new_icon)

		return return_icons


# - Test ----------------------
if __name__ == '__main__':
	test = TRIconsProspect()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 1440, 880)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()