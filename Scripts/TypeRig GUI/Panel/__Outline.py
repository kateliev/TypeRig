#FLM: TAB Outline
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph
from typerig.gui import trTableView
from collections import OrderedDict

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Outline', '0.01'

# - Sub widgets ------------------------
class QContourSelect(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QContourSelect, self).__init__()

		# -- Init
		self.table_dict = {0:{0:None}} # Empty table
		self.layer_names = [] # Empty layer list
		self.table_columns = 'N,Shape,Contour,X,Y,Type'.split(',')

		# -- Widgets
		self.lay_head = QtGui.QGridLayout()
		
		self.edt_glyphName = QtGui.QLineEdit()
		self.cmb_layer = QtGui.QComboBox()
		self.cmb_layer.currentIndexChanged.connect(self.changeLayer)

		
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_apply = QtGui.QPushButton('&Apply')
		self.btn_refresh.clicked.connect(self.refresh)

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('G:'),	0,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,	0,1,1,5)
		self.lay_head.addWidget(self.btn_refresh,	0,6,1,2)
		self.lay_head.addWidget(QtGui.QLabel('L:'),	1,0,1,1)
		self.lay_head.addWidget(self.cmb_layer,		1,1,1,5)
		self.lay_head.addWidget(self.btn_apply,		1,6,1,2)

		self.addLayout(self.lay_head)

		# -- Node List Table
		self.tab_nodes = trTableView(self.table_dict)
		
		self.addWidget(self.tab_nodes)
		self.refresh() # Build Table

		# -- Table Styling
		self.tab_nodes.horizontalHeader().setStretchLastSection(False)
		self.tab_nodes.setSortingEnabled(True)
		self.tab_nodes.horizontalHeader().sortIndicatorChanged.connect(lambda: self.tab_nodes.resizeColumnsToContents())
		self.tab_nodes.verticalHeader().hide()
		self.tab_nodes.resizeColumnsToContents()

	def refresh(self, layer=None):
		# - Init
		self.glyph = eGlyph()
		self.edt_glyphName.setText(eGlyph().name)
				
		self.table_dict = {}
		node_count = 0

		# - Populate layers
		if layer is None:
			self.layer_names = [item.name for item in self.glyph.layers()]
			self.cmb_layer.clear()
			self.cmb_layer.addItems(self.layer_names)

		if len(self.layer_names):
			self.cmb_layer.setCurrentIndex(self.layer_names.index(self.glyph.activeLayer().name))

		# - Populate table
		for sID, shape in enumerate(self.glyph.shapes(layer)):
			for cID, contour in enumerate(shape.contours):
				for nID, node in enumerate(contour.nodes()):
					
					table_values = [node_count,sID, cID, round(node.x, 2), round(node.y, 2), node.type]
					
					self.table_dict[node_count] = OrderedDict(zip(self.table_columns, table_values))
					node_count += 1
		
		self.tab_nodes.setTable(self.table_dict, (False, False))
		self.tab_nodes.resizeColumnsToContents()
		
	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			print '\nERRO:\tGlyph mismatch:\n\tCurrent active glyph: %s\n\tOutline panel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg)
			print 'WARN:\tNo action taken! Forcing refresh!' 
			self.refresh()
			return 0
		return 1

	def changeLayer(self):
		if self.doCheck():
			self.refresh(self.cmb_layer.currentText)


		
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()

		self.anchorSelector = QContourSelect()
		#self.basicTools = QanchorBasic(self.anchorSelector)
		
		layoutV.addLayout(self.anchorSelector)
		#layoutV.addWidget(QtGui.QLabel('Basic Tools:'))
		#layoutV.addLayout(self.basicTools)
		
		# - Build ---------------------------
		#layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 200, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()