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
		self.table_columns = 'Shape,Contour,X,Y,Type'.split(',')

		# -- Widgets
		self.lay_head = QtGui.QHBoxLayout()
		
		self.edt_glyphName = QtGui.QLineEdit()
		
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_refresh.clicked.connect(self.refresh)

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('G:'))
		self.lay_head.addWidget(self.edt_glyphName)
		self.lay_head.addWidget(self.btn_refresh)
		self.addLayout(self.lay_head)

		# -- Node List Table
		self.tab_nodes = trTableView(self.table_dict)
		
		self.addWidget(self.tab_nodes)
		self.refresh() # Build Table

		# -- Table Styling
		self.tab_nodes.horizontalHeader().setStretchLastSection(False)
		self.tab_nodes.resizeColumnsToContents()

	def refresh(self):
		# - Init
		self.glyph = eGlyph()
		self.edt_glyphName.setText(eGlyph().name)
				
		self.table_dict = {}
		node_count = 0

		# - Populate
		for sID, shape in enumerate(self.glyph.shapes()):
			for cID, contour in enumerate(shape.contours):
				for nID, node in enumerate(contour.nodes()):
					
					table_values = [sID, cID, round(node.x, 2), round(node.y, 2), node.type]
					
					self.table_dict[node_count] = dict(zip(self.table_columns, table_values))
					node_count += 1
		
		self.tab_nodes.setTable(self.table_dict)
		
	def doCheck(self):
		if self.glyph.fg.id != fl6.CurrentGlyph().id and self.glyph.fl.name != fl6.CurrentGlyph().name:
			print '\nERRO:\tGlyph mismatch:\n\tCurrent active glyph: %s\n\tLayers panel glyph: %s' %(fl6.CurrentGlyph(), self.glyph.fg)
			print 'WARN:\tNo action taken! Forcing refresh!' 
			self.refresh()
			return 0
		return 1

class QanchorBasic(QtGui.QVBoxLayout):
	def __init__(self, aux):
		super(QanchorBasic, self).__init__()

		# - Init
		self.aux = aux
		self.types = 'Anchor PinPoint'.split(' ')
		self.posY = 'Coord,Above,Below,Center,Baseline,Copy'.split(',')
		self.posX = 'Coord,Left,Right,Center,Highest,Lowest'.split(',')
		posYvals = (None, 'T', 'B', 'C', None)
		posXvals = (None ,'L', 'R', 'C', 'AT', 'A')
		self.posYctrl = dict(zip(self.posY, posYvals))
		self.posXctrl = dict(zip(self.posX, posXvals))

		# -- Basic Tool buttons
		self.lay_grid = QtGui.QGridLayout()
		self.btn_clearSel = QtGui.QPushButton('Clear Selected')
		self.btn_clearAll = QtGui.QPushButton('Clear All')
		self.btn_anchorAdd = QtGui.QPushButton('Add')
		self.btn_anchorMov = QtGui.QPushButton('Move')
		self.chk_italic = QtGui.QCheckBox('Use Italic Angle')

		# -- Edit fields
		self.edt_anchorName = ALineEdit()
		self.edt_simpleX = QtGui.QLineEdit()
		self.edt_simpleY = QtGui.QLineEdit()
		self.edt_autoT = QtGui.QLineEdit()

		self.edt_anchorName.setPlaceholderText('New Anchor')
		self.edt_simpleX.setText('0')
		self.edt_simpleY.setText('0')
		self.edt_autoT.setText('5')

		# -- Combo box
		self.cmb_posX = QtGui.QComboBox()
		self.cmb_posY = QtGui.QComboBox()
		self.cmb_type = QtGui.QComboBox()

		self.cmb_posX.addItems(self.posX)
		self.cmb_posY.addItems(self.posY)
		self.cmb_type.addItems(self.types)
		self.cmb_type.setEnabled(False)

		# -- Constrains
		self.btn_clearSel.setMinimumWidth(90)
		self.btn_clearAll.setMinimumWidth(90)
		self.edt_anchorName.setMinimumWidth(50)
		self.edt_simpleX.setMinimumWidth(30)
		self.edt_simpleY.setMinimumWidth(30)

		# -- Link functions
		self.btn_clearAll.clicked.connect(lambda: self.clearAnchors(True))
		self.btn_clearSel.clicked.connect(lambda: self.clearAnchors(False))
		self.btn_anchorAdd.clicked.connect(lambda: self.addAnchors(False))
		self.btn_anchorMov.clicked.connect(lambda: self.addAnchors(True))

		# - Build layout
		self.lay_grid.addWidget(QtGui.QLabel('Remove anchor:'), 0, 0, 1, 4)
		self.lay_grid.addWidget(self.btn_clearSel, 				1, 0, 1, 4)
		self.lay_grid.addWidget(self.btn_clearAll, 				1, 4, 1, 4)

		self.lay_grid.addWidget(QtGui.QLabel('Add/move anchor:'),2, 0, 1, 4)
		self.lay_grid.addWidget(QtGui.QLabel('N:'),				3, 0, 1, 1)
		self.lay_grid.addWidget(self.edt_anchorName, 			3, 1, 1, 3)
		self.lay_grid.addWidget(self.cmb_type, 					3, 4, 1, 4)

		self.lay_grid.addWidget(QtGui.QLabel('X:'),				4, 0, 1, 1)
		self.lay_grid.addWidget(self.cmb_posX, 					4, 1, 1, 2)
		self.lay_grid.addWidget(self.edt_simpleX, 				4, 3, 1, 1)
		self.lay_grid.addWidget(QtGui.QLabel('Tolerance:'),		4, 4, 1, 1)
		self.lay_grid.addWidget(self.edt_autoT, 				4, 5, 1, 3)
		
		self.lay_grid.addWidget(QtGui.QLabel('Y:'),				5, 0, 1, 1)
		self.lay_grid.addWidget(self.cmb_posY,					5, 1, 1, 2)
		self.lay_grid.addWidget(self.edt_simpleY, 				5, 3, 1, 1)
		self.lay_grid.addWidget(self.chk_italic,				5, 4, 1, 4)
		
		
		self.lay_grid.addWidget(self.btn_anchorAdd, 			6, 0, 1, 4)
		self.lay_grid.addWidget(self.btn_anchorMov, 			6, 4, 1, 4)

		# - Build
		self.addLayout(self.lay_grid)

	def clearAnchors(self, clearAll=False):
		if self.aux.doCheck():			
			if clearAll:
				for layer in self.aux.wLayers:
					self.aux.glyph.clearAnchors(layer)

			else:
				for item in self.aux.lst_anchors.selectedItems():
					cAnchorName = item.text()
					
					for layer in self.aux.wLayers:
						findAnchor = self.aux.glyph.layer(layer).findAnchor(cAnchorName)
											
						if findAnchor is not None:
							 self.aux.glyph.layer(layer).removeAnchor(findAnchor)


			self.aux.glyph.updateObject(self.aux.glyph.fl, 'Clear anchors: %s.' %'; '.join(self.aux.wLayers))
			#fl6.flItems.notifyAnchorsChanged()
			self.aux.glyph.update()
			self.aux.refresh()

	def addAnchors(self, move=False):
		if self.aux.doCheck():			
			update = False

			if self.cmb_posX.currentText == 'Coord' and self.cmb_posY.currentText == 'Coord' and len(self.edt_anchorName.text):
				for layer in self.aux.wLayers:
					coords = (int(self.edt_simpleX.text), int(self.edt_simpleY.text))
					self.aux.glyph.addAnchor(coords, self.edt_anchorName.text, layer)
				update = True
			else:
				offsetX = int(self.edt_simpleX.text)
				offsetY = int(self.edt_simpleY.text)
				autoTolerance = int(self.edt_autoT.text)

				for layer in self.aux.wLayers:
					if not move:
						if len(self.edt_anchorName.text):
							self.aux.glyph.dropAnchor(self.edt_anchorName.text, layer, (offsetX, offsetY), (self.posXctrl[self.cmb_posX.currentText], self.posYctrl[self.cmb_posY.currentText]), autoTolerance, False, self.chk_italic.isChecked())
							update = True
					else:
						cmb_sel = self.aux.lst_anchors.selectedItems()
						if len(cmb_sel):
							self.aux.glyph.dropAnchor(cmb_sel[0].text(), layer, (offsetX, offsetY), (self.posXctrl[self.cmb_posX.currentText], self.posYctrl[self.cmb_posY.currentText]), autoTolerance, True, self.chk_italic.isChecked())
							update = True

			if update:
				self.aux.glyph.updateObject(self.aux.glyph.fl, '%s anchors: %s.' %('Add' if not move else 'Move', '; '.join(self.aux.wLayers)))
				self.aux.glyph.update()
				self.aux.refresh()
		
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