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
app_name, app_version = 'TypeRig | Font Metrics', '0.01'

# - Dependencies -----------------
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

		# - Styling
		self.horizontalHeader().setStretchLastSection(True)
		self.setAlternatingRowColors(True)
		#self.resizeColumnsToContents()
		self.resizeRowsToContents()

	def setTable(self, data):
		name_row, name_column = [], []

		# - Populate
		for n, layer in enumerate(sorted(data.keys())):
			name_row.append(layer)

			for m, key in enumerate(sorted(data[layer].keys())):
				name_column.append(key)
				newitem = QtGui.QTableWidgetItem(str(data[layer][key]))
				self.setItem(n, m, newitem)
				
		self.setHorizontalHeaderLabels(name_column)
		self.setVerticalHeaderLabels(name_row)

	def getTable(self):
		returnDict = {}
		for row in range(self.rowCount):
			returnDict[self.verticalHeaderItem(row).text()] = {self.horizontalHeaderItem(col).text():int(self.item(row, col).text()) for col in range(self.columnCount)}

		return returnDict


class WFontMetrics(QtGui.QGridLayout):
	def __init__(self):
		super(WFontMetrics, self).__init__()

		# - Init
		activeFont = pFont()
		activeGlyph = pGlyph()
		self.metricData = {layer.name:activeFont.fontMetrics().asDict(layer.name) for layer in activeGlyph.masters()}

		# - Interface
		self.btn_apply = QtGui.QPushButton('Apply Changes')
		self.btn_reset = QtGui.QPushButton('Reset')

		self.btn_apply.clicked.connect(self.applyChanges)
		self.btn_reset.clicked.connect(self.resetChanges)

		self.tab_fontMetrics = WTableView(self.metricData)

		# - Build
		self.addWidget(self.tab_fontMetrics,	0, 1, 5, 6)
		self.addWidget(self.btn_reset,			6, 5, 1, 1)
		self.addWidget(self.btn_apply,			6, 6, 1, 1)
	
	def applyChanges(self):
		print self.tab_fontMetrics.getTable()

	def resetChanges(self):
		self.tab_fontMetrics.setTable(self.metricData)


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()
		
		# - Build   
		layoutV = QtGui.QVBoxLayout()
		layoutV.addWidget(QtGui.QLabel('Font Metrics (All Masters)'))
		layoutV.addLayout(WFontMetrics())		
		
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