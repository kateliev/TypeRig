#FLM: TR: Outline
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2021 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import absolute_import, print_function
import warnings
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.proxy.fl.objects.node import eNode

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs, TRTableView

# - Init --------------------------------
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Outline', '2.00'

# - Sub widgets ------------------------
class TRContourSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(TRContourSelect, self).__init__()

		# -- Init
		self.table_dict = {0:{0:None}} # Empty table
		self.layer_names = [] # Empty layer list
		self.table_columns = 'N,Sh,Cn,X,Y,Type,Rel'.split(',')

		# -- Widgets
		self.lay_head = QtGui.QGridLayout()
		
		self.edt_glyphName = QtGui.QLineEdit()
		self.cmb_layer = QtGui.QComboBox()
			
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_apply = QtGui.QPushButton('&Apply')
		self.btn_apply.setEnabled(False)

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('G:'),	0,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,	0,1,1,5)
		self.lay_head.addWidget(self.btn_refresh,	0,6,1,2)
		self.lay_head.addWidget(QtGui.QLabel('L:'),	1,0,1,1)
		self.lay_head.addWidget(self.cmb_layer,		1,1,1,5)
		self.lay_head.addWidget(self.btn_apply,		1,6,1,2)
		self.addLayout(self.lay_head)

		# -- Node List Table
		self.tab_nodes = TRTableView(self.table_dict)
		self.addWidget(self.tab_nodes)

		self.btn_refresh.clicked.connect(lambda: self.refresh())
		self.cmb_layer.currentIndexChanged.connect(lambda: self.changeLayer())

		# -- Table Styling
		self.tab_nodes.horizontalHeader().setStretchLastSection(False)
		self.tab_nodes.setSortingEnabled(True)
		self.tab_nodes.horizontalHeader().sortIndicatorChanged.connect(lambda: self.tab_nodes.resizeColumnsToContents())
		self.tab_nodes.verticalHeader().hide()
		self.tab_nodes.resizeColumnsToContents()
		self.tab_nodes.selectionModel().selectionChanged.connect(self.selectionChanged)
		self.tab_nodes.itemChanged.connect(self.valueChanged)

	def refresh(self, layer=None):
		# - Init
		self.glyph = eGlyph()
		self.edt_glyphName.setText(eGlyph().name)
				
		self.table_dict = {}
		node_count = 0

		# - Populate layers
		if layer is None:
			self.layer_names = [item.name for item in self.glyph.layers() if '#' not in item.name]
			self.cmb_layer.clear()
			self.cmb_layer.addItems(self.layer_names)
			self.cmb_layer.setCurrentIndex(self.layer_names.index(self.glyph.activeLayer().name))			
			
		# - Populate table
		try: # Dirty Quick Fix - Solve later
			for sID, shape in enumerate(self.glyph.shapes(layer)):
				for cID, contour in enumerate(shape.contours):
					for nID, node in enumerate(contour.nodes()):
						
						table_values = [node_count, sID, cID, round(node.x, 2), round(node.y, 2), node.type, round(eNode(node).distanceToPrev(),2)]
						
						self.table_dict[node_count] = OrderedDict(zip(self.table_columns, table_values))
						node_count += 1
			
			self.tab_nodes.setTable(self.table_dict, (False, False))
			self.tab_nodes.resizeColumnsToContents()
		
		except AttributeError: 
			pass
		
	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			warnings.warn('Glyph mismatch! No action taken! Forcing refresh!', GlyphWarning)
			self.refresh()
			return 0
		return 1

	def changeLayer(self):
		if self.doCheck():
			self.refresh(self.cmb_layer.currentText)

	def selectionChanged(self):
		if self.doCheck():	
			if self.cmb_layer.currentText == self.glyph.activeLayer().name:
				# - Prepare
				self.glyph.fl.unselectAllNodes()

				# - Process
				for cel_coords in self.tab_nodes.selectionModel().selectedIndexes:
					selected_nid = int(self.tab_nodes.item(cel_coords.row(), 0).text())
					self.glyph.nodes(self.cmb_layer.currentText)[selected_nid].selected = True
				
				# - Finish
				self.glyph.updateObject(self.glyph.fl, verbose=False)

	def valueChanged(self, item):
		if self.doCheck():
			try: # Dirty Quick Fix - Solve later
				# - Init
				x_col, y_col = self.table_columns.index('X'), self.table_columns.index('Y')
				active_nid = int(self.tab_nodes.item(item.row(), 0).text())

				# - Process
				if item.column() == x_col or item.column() == y_col:
					new_x = float(self.tab_nodes.item(item.row(), x_col).text())
					new_y = float(self.tab_nodes.item(item.row(), y_col).text())

					active_node = eNode(self.glyph.nodes(self.cmb_layer.currentText)[active_nid])
					active_node.reloc(new_x, new_y)

					# -- Finish
					self.glyph.update()
					self.glyph.updateObject(self.glyph.fl, verbose=False)
			
			except AttributeError:
				pass

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.outline = TRContourSelect()
		layoutV.addLayout(self.outline)
		
		# - Build
		#layoutV.addStretch()
		self.setLayout(layoutV)

		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()