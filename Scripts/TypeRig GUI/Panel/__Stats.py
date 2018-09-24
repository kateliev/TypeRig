#FLM: TAB Glyph Stats 
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
from typerig.proxy import pFont
from typerig.glyph import eGlyph
from typerig.gui import trTableView
from collections import OrderedDict

# - Init
app_name, app_version = 'TypeRig | Glyph Statistics', '0.01'
queries = ['Boundig Box Width (BBox)', 'Advance Width']

# - Sub widgets ------------------------
class QGlyphInfo(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QGlyphInfo, self).__init__()

		# -- Init
		self.table_dict = {0:{0:None}} # Empty table
		self.layer_names = [] # Empty layer list
		self.table_columns = 'N,Sh,Cn,X,Y,Type,Rel'.split(',')

		# -- Widgets
		self.lay_head = QtGui.QGridLayout()
		
		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_glyphsSeq = QtGui.QLineEdit()
		
		self.cmb_query = QtGui.QComboBox()
		self.cmb_charset = QtGui.QComboBox()

		self.cmb_query.addItems(queries)
			
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_populate = QtGui.QPushButton('&Populate')
		#self.btn_populate.setEnabled(False)

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('G:'),	0,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,	0,1,1,5)
		self.lay_head.addWidget(self.btn_refresh,	0,6,1,2)
		self.lay_head.addWidget(QtGui.QLabel('C:'),	1,0,1,1)
		self.lay_head.addWidget(self.cmb_charset,	1,1,1,5)
		self.lay_head.addWidget(self.btn_populate,	1,6,1,2)
		self.lay_head.addWidget(QtGui.QLabel('C:'),	2,0,1,1)
		self.lay_head.addWidget(self.edt_glyphsSeq,	2,1,1,7)
		self.lay_head.addWidget(QtGui.QLabel('Q:'),	3,0,1,1)
		self.lay_head.addWidget(self.cmb_query,		3,1,1,7)
		self.addLayout(self.lay_head)

		# -- Node List Table
		self.tab_stats = trTableView(self.table_dict)
		
		self.addWidget(self.tab_stats)
		#self.refresh() # Build Table

		self.btn_refresh.clicked.connect(lambda: self.refresh())
		self.btn_populate.clicked.connect(lambda: self.populate())
		self.cmb_query.currentIndexChanged.connect(lambda: self.change_query())

		# -- Table Styling
		self.tab_stats.horizontalHeader().setStretchLastSection(False)
		self.tab_stats.resizeColumnsToContents()
		#self.tab_stats.selectionModel().selectionChanged.connect(self.change_selection())

	def populate(self):
		self.font = pFont()
		self.glyphNames = self.font.getGlyphNamesDict()
		self.cmb_charset.addItems(sorted(self.glyphNames.keys()))
		
	def refresh(self, layer=None):
		# - Init
		self.font = pFont()
		self.glyph = eGlyph()
		self.edt_glyphName.setText(eGlyph().name)
		wLayers = self.glyph._prepareLayers((True, True, False, False))
				
		self.table_dict = {}
		node_count = 0

		# - Populate table
		self.table_dict[self.glyph.name] = {layer:self.glyph.getBounds(layer).width() for layer in wLayers}
		
		if len(self.edt_glyphsSeq.text):
			for glyph_name in self.edt_glyphsSeq.text.split(' '):
				wGlyph = self.font.glyph(glyph_name)
				self.table_dict[glyph_name] = {layer:wGlyph.getBounds(layer).width() for layer in wLayers}
			
		self.tab_stats.setTable(self.table_dict)
		self.tab_stats.resizeColumnsToContents()		
		
	def changeLayer(self):
		if self.doCheck():
			self.refresh(self.cmb_query.currentText)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.glyph_info = QGlyphInfo()
		layoutV.addLayout(self.glyph_info)
		
		# - Build
		#layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()