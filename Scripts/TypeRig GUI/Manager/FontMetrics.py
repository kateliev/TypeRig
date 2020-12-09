#FLM: TR: Font Metrics
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Font Metrics', '0.16'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt

from typerig.proxy.fl import *

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import TRTableView

# - Sub widgets ------------------------
class TRZLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(TRZLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'Ascender', lambda: self.setText('=Ascender'))
		menu.addAction(u'Descender', lambda: self.setText('=Descender'))
		menu.addAction(u'Caps Height', lambda: self.setText('=CapsHeight'))
		menu.addAction(u'X Height', lambda: self.setText('=XHeight'))

# - Font Metrics -------------------------------------------------------
class WFontMetrics(QtGui.QWidget):
	def __init__(self, parentWidget):
		super(WFontMetrics, self).__init__()

		# - Init
		self.grid = QtGui.QGridLayout()
		self.upperWidget = parentWidget
		self.activeFont = pFont()
		self.metricData = {}
		self.refresh()

		# - Interface
		self.btn_apply = QtGui.QPushButton('Apply Changes')
		self.btn_reset = QtGui.QPushButton('Reset')
		self.btn_open = QtGui.QPushButton('Open')
		self.btn_save = QtGui.QPushButton('Save')

		self.btn_apply.clicked.connect(self.applyChanges)
		self.btn_reset.clicked.connect(self.resetChanges)
		self.btn_save.clicked.connect(self.exportMetrics)
		self.btn_open.clicked.connect(self.importMetrics)

		self.tab_fontMetrics = TRTableView(self.metricData)

		# - Build
		lbl_name = QtGui.QLabel('Font Metrics (All Masters)')
		lbl_name.setMaximumHeight(20)
		self.grid.addWidget(lbl_name,		 		0, 0, 1, 24)
		self.grid.addWidget(self.tab_fontMetrics,	1, 0, 5, 21)
		self.grid.addWidget(self.btn_save,			1, 21, 1, 3)
		self.grid.addWidget(self.btn_open,			2, 21, 1, 3)
		self.grid.addWidget(self.btn_reset,			4, 21, 1, 3)
		self.grid.addWidget(self.btn_apply,			5, 21, 1, 3)

		for i in range(1,6):
			self.grid.setRowStretch(i,2)

		self.setLayout(self.grid)
	
	def refresh(self):
		for layer in self.activeFont.masters():
			temp_metrics = self.activeFont.fontMetrics().asDict(layer)
			temp_metrics.pop('Upm', None)
			self.metricData[layer] = temp_metrics

	def applyChanges(self):
		oldMetricData = self.activeFont.fontMetrics()
		newMetricData = self.tab_fontMetrics.getTable()
		
		for layer, metrics in newMetricData.iteritems():
			oldMetricData.fromDict(metrics, layer)

		self.activeFont.fl.update()
		self.activeFont.updateObject(self.activeFont.fl, 'Font:%s; Font Metrics Updated!.' %self.activeFont.name)

	def resetChanges(self):
		self.tab_fontMetrics.setTable(self.metricData, True)
		print 'DONE:\t Font:%s; Font Metrics realoaded.' %self.activeFont.name

	def exportMetrics(self):
		fontPath = os.path.split(self.activeFont.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upperWidget, 'Save Font Metrics to file', fontPath , '*.json')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.metricData, exportFile)

			print 'SAVE:\t Font:%s; Font Metrics saved to %s.' %(self.activeFont.name, fname)

	def importMetrics(self):
		fontPath = os.path.split(self.activeFont.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upperWidget, 'Open Metric Expressions from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				loadedData = json.load(importFile)

			self.tab_fontMetrics.setTable(loadedData)

			print 'LOAD:\t Font:%s; Font Metrics loaded from %s.' %(self.activeFont.name, fname)
			print 'NOTE:\t Use < Apply > to apply loaded metrics to active Font!'

# - Font Zones -------------------------------------------------------
class WTreeWidget(QtGui.QTreeWidget):
	def __init__(self, data):
		super(WTreeWidget, self).__init__()
		
		# - Init

		# - Set 
		self.setTree(data)	
		self.itemChanged.connect(self.markChange)	

		# - Styling
		self.expandAll()
		self.setAlternatingRowColors(True)

	def setTree(self, data, reset=False):
		self.blockSignals(True)
		self.clear()
		header_row = ['Layer/Zone', 'Position', 'Width', 'Type']
		self.setHeaderLabels(header_row)

		for key, value in data.iteritems():
			master = QtGui.QTreeWidgetItem(self, [key])

			for zoneTuple in value:
				zoneData = QtGui.QTreeWidgetItem(master, [zoneTuple[2], zoneTuple[0], zoneTuple[1], ('B: %s', 'T: %s')[zoneTuple[1] > 0] %zoneTuple[0]])
				zoneData.setFlags(zoneData.flags() | QtCore.Qt.ItemIsEditable)

		self.blockSignals(False)

	def getTree(self):
		returnDict = {}
		root = self.invisibleRootItem()
		
		for i in range(root.childCount()):
			master = root.child(i)
			returnDict[master.text(0)] = [(float(master.child(n).text(1)), float(master.child(n).text(2)), master.child(n).text(0)) for n in range(master.childCount()) ]
		
		return returnDict

	def markChange(self, item):
		item.setText(3, ('B: %s', 'T: %s')[float(item.text(2)) > 0] %item.text(1))
		for col in range(item.columnCount()):			
			item.setBackground(col, QtGui.QColor('powderblue'))

class WFontZones(QtGui.QWidget):
	def __init__(self, parentWidget):
		super(WFontZones, self).__init__()

		# - Init
		self.grid = QtGui.QGridLayout()
		self.upperWidget = parentWidget
		self.activeFont = pFont()
		self.zoneData = {master:self.activeFont.zonesToTuples(master) for master in self.activeFont.masters()}

		# - Interface
		self.btn_apply = QtGui.QPushButton('Apply Changes')
		self.btn_reset = QtGui.QPushButton('Reset')
		self.btn_open = QtGui.QPushButton('Open')
		self.btn_save = QtGui.QPushButton('Save')
		self.btn_new = QtGui.QPushButton('Add New')
		self.btn_del = QtGui.QPushButton('Delete')

		self.cmb_layer = QtGui.QComboBox()
		self.cmb_layer.addItems(['All Layers'] + self.activeFont.masters())

		self.edt_pos = TRZLineEdit()
		self.edt_width = QtGui.QLineEdit()
		self.edt_name = QtGui.QLineEdit()
		
		self.edt_name.setPlaceholderText('Name')
		self.edt_pos.setPlaceholderText('Position')
		self.edt_width.setPlaceholderText('Width')

		self.btn_apply.clicked.connect(self.applyChanges)
		self.btn_reset.clicked.connect(self.resetChanges)
		self.btn_save.clicked.connect(self.exportZones)
		self.btn_open.clicked.connect(self.importZones)
		self.btn_new.clicked.connect(self.addZone)
		self.btn_del.clicked.connect(self.delZone)

		self.tree_fontZones = WTreeWidget(self.zoneData)

		# - Build
		lbl_name = QtGui.QLabel('Font Zones (Local)')
		lbl_name.setMaximumHeight(20)
		self.grid.addWidget(lbl_name, 			0, 0, 	1, 24)
		self.grid.addWidget(self.tree_fontZones,1, 0, 	15, 21)
		
		self.grid.addWidget(self.cmb_layer,		1, 21, 	1, 3)
		self.grid.addWidget(self.edt_name,		2, 21, 	1, 3)
		self.grid.addWidget(self.edt_pos,		3, 21, 	1, 3)
		self.grid.addWidget(self.edt_width,		4, 21, 	1, 3)
		self.grid.addWidget(self.btn_new,		5, 21, 	1, 3)
		self.grid.addWidget(self.btn_del,		6, 21, 	1, 3)

		self.grid.addWidget(self.btn_save,		12, 21, 1, 3)
		self.grid.addWidget(self.btn_open,		13, 21, 1, 3)
		self.grid.addWidget(self.btn_reset,		14,21, 	1, 3)
		self.grid.addWidget(self.btn_apply,		15,21, 	1, 3)
		self.setLayout(self.grid)

	def applyChanges(self):
		newZoneData = self.tree_fontZones.getTree()
		
		for layer, zones in newZoneData.iteritems():
			self.activeFont.zonesFromTuples(zones, layer, True)

		self.zoneData = {master:self.activeFont.zonesToTuples() for master in self.activeFont.masters()}
		print 'DONE:\t Font:%s; Font Zones data Updated!.' %self.activeFont.name

	def resetChanges(self):
		self.tree_fontZones.setTree(self.zoneData, True)
		print 'DONE:\t Font:%s; Font Zones data reloaded.' %self.activeFont.name

	def addZone(self):
		import copy
		fontMetrics = self.upperWidget.fontMetrics.tab_fontMetrics.getTable()
		self.newZoneData = copy.deepcopy(self.zoneData)
		
		def dataAddZone(layer):
			if '=' in self.edt_pos.text:
				self.newZoneData[layer].append((float(fontMetrics[layer][self.edt_pos.text.strip('=')]), float(self.edt_width.text), self.edt_pos.text.strip('=')))
			else:
				self.newZoneData[layer].append((float(self.edt_pos.text), float(self.edt_width.text), self.edt_name.text))

		if self.cmb_layer.currentText == 'All Layers':
			for layer in self.activeFont.masters():
				dataAddZone(layer)
		else:
			dataAddZone(self.cmb_layer.currentText)

		self.tree_fontZones.setTree(self.newZoneData)
		self.tree_fontZones.expandAll()
		
		print 'ADD:\t Font:%s;  New zone added for %s.' %(self.activeFont.name, self.cmb_layer.currentText)
		print 'NOTE:\t Use < Apply > to apply modified zones to active Font!'

	def delZone(self):
		root = self.tree_fontZones.invisibleRootItem()
		
		for item in self.tree_fontZones.selectedItems():
			(item.parent() or root).removeChild(item)

	def exportZones(self):
		fontPath = os.path.split(self.activeFont.fg.path)[0]
		fname = QtGui.QFileDialog.getSaveFileName(self.upperWidget, 'Save Font Zones to file', fontPath, '*.json')
		
		if fname != None:
			with open(fname, 'w') as exportFile:
				json.dump(self.zoneData, exportFile)

			print 'SAVE:\t Font:%s; Font Zones saved to %s.' %(self.activeFont.name, fname)

	def importZones(self):
		fontPath = os.path.split(self.activeFont.fg.path)[0]
		fname = QtGui.QFileDialog.getOpenFileName(self.upperWidget, 'Load Font Zones from file', fontPath)
		
		if fname != None:
			with open(fname, 'r') as importFile:
				loadedData = json.load(importFile)

			self.tree_fontZones.setTree(loadedData)
			self.tree_fontZones.expandAll()

			print 'LOAD:\t Font:%s; Font Zones loaded from %s.' %(self.activeFont.name, fname)
			print 'NOTE:\t Use < Apply > to apply loaded zones to active Font!'


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		
		# - Build
		'''
		main = QtGui.QVBoxLayout()
		scroll = QtGui.QScrollArea()
		scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
		scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		scroll.setWidgetResizable(True)
		
		'''
		layoutV = QtGui.QVBoxLayout()
		splitter = QtGui.QSplitter(QtCore.Qt.Vertical)
		#splitter.setHandleWidth(1)
		
		self.fontMetrics = WFontMetrics(self)
		self.fontZones = WFontZones(self)

		splitter.addWidget(self.fontMetrics)
		splitter.addWidget(self.fontZones)

		splitter.setStretchFactor(0,1)
		splitter.setStretchFactor(1,2)

		layoutV.addWidget(splitter)

						
		# - Build ---------------------------
		#layoutV.addStretch()
		#scroll.setLayout(layoutV)
		#main.addWidget(scroll)
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 900, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()