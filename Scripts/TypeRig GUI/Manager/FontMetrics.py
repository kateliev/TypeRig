#FLM: MAN Font Metrics
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Font Metrics', '0.06'

# - Dependencies -----------------
import os, json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pGlyph, pFont

# - Sub widgets ------------------------
class MLineEdit(QtGui.QLineEdit):
	# - Custom QLine Edit extending the contextual menu with FL6 metric expressions
	def __init__(self, *args, **kwargs):
		super(MLineEdit, self).__init__(*args, **kwargs)
		self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.customContextMenuRequested.connect(self.__contextMenu)

	def __contextMenu(self):
		self._normalMenu = self.createStandardContextMenu()
		self._addCustomMenuItems(self._normalMenu)
		self._normalMenu.exec_(QtGui.QCursor.pos())

	def _addCustomMenuItems(self, menu):
		menu.addSeparator()
		menu.addAction(u'EQ', lambda: self.setText('=%s' %self.text))
		menu.addAction(u'LSB', lambda: self.setText('=lsb("%s")' %self.text))
		menu.addAction(u'RSB', lambda: self.setText('=rsb("%s")' %self.text))
		menu.addAction(u'ADV', lambda: self.setText('=width("%s")' %self.text))
		menu.addAction(u'L', lambda: self.setText('=l("%s")' %self.text))
		menu.addAction(u'R', lambda: self.setText('=r("%s")' %self.text))
		menu.addAction(u'W', lambda: self.setText('=w("%s")' %self.text))
		menu.addAction(u'G', lambda: self.setText('=g("%s")' %self.text))	
		
class WTableView(QtGui.QTableWidget):
	def __init__(self, data):
		super(WTableView, self).__init__()
		
		# - Init
		self.setColumnCount(max(map(len, data.values())))
		self.setRowCount(len(data.keys()))

		# - Set 
		self.setTable(data)		
		self.itemChanged.connect(self.markChange)

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		#self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data, reset=False):
		name_row, name_column = [], []
		self.blockSignals(True)

		# - Populate
		for n, layer in enumerate(sorted(data.keys())):
			name_row.append(layer)

			for m, key in enumerate(sorted(data[layer].keys())):
				name_column.append(key)
				newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
				
				if self.item(n, m) == None or reset:
					markColor = QtGui.QColor("white")
				else:
					if self.item(n, m).text() == newitem.text():
						markColor = QtGui.QColor("white")
					else:
						markColor = QtGui.QColor("aliceblue")

				self.setItem(n, m, newitem)
				self.item(n, m).setBackground(markColor)
				
		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)
		self.blockSignals(False)

	def getTable(self):
		returnDict = {}
		for row in range(self.rowCount):
			returnDict[self.verticalHeaderItem(row).text()] = {self.horizontalHeaderItem(col).text():int(self.item(row, col).text()) for col in range(self.columnCount)}

		return returnDict

	def markChange(self, item):
		print item.setBackground(QtGui.QColor("aliceblue"))


class WFontMetrics(QtGui.QGridLayout):
	def __init__(self, parentWidget):
		super(WFontMetrics, self).__init__()

		# - Init
		self.upperWidget = parentWidget
		self.activeFont = pFont()
		self.activeGlyph = pGlyph()
		self.metricData = {layer.name:self.activeFont.fontMetrics().asDict(layer.name) for layer in self.activeGlyph.masters()}

		# - Interface
		self.btn_apply = QtGui.QPushButton('Apply Changes')
		self.btn_reset = QtGui.QPushButton('Reset')
		self.btn_open = QtGui.QPushButton('Open')
		self.btn_save = QtGui.QPushButton('Save')

		self.btn_apply.clicked.connect(self.applyChanges)
		self.btn_reset.clicked.connect(self.resetChanges)
		self.btn_save.clicked.connect(self.exportMetrics)
		self.btn_open.clicked.connect(self.importMetrics)

		self.tab_fontMetrics = WTableView(self.metricData)

		# - Build
		self.addWidget(self.tab_fontMetrics,	0, 1, 5, 6)
		self.addWidget(self.btn_save,			6, 3, 1, 1)
		self.addWidget(self.btn_open,			6, 4, 1, 1)
		self.addWidget(self.btn_reset,			6, 5, 1, 1)
		self.addWidget(self.btn_apply,			6, 6, 1, 1)
	
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
		fname = QtGui.QFileDialog.getSaveFileName(self.upperWidget, 'Save Font Metrics to file', fontPath , '.json')
		
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


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		
		# - Build   
		layoutV = QtGui.QVBoxLayout()
		layoutV.addWidget(QtGui.QLabel('Font Metrics (All Masters)'))
		layoutV.addLayout(WFontMetrics(self))		
		
		 # - Build ---------------------------
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 800, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()