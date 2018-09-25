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
from typerig.brain import ratfrac
#from collections import OrderedDict

# - Init
app_name, app_version = 'TypeRig | Glyph Statistics', '0.02'
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
		self.edt_glyphName.setToolTip('Current Glyph Name.') 
		self.edt_glyphsSeq.setToolTip('Manual entry for Glyph names to populate stats info. Separated by SPACE') 
		
		self.cmb_query = QtGui.QComboBox()
		self.cmb_charset = QtGui.QComboBox()
		self.cmb_query.setToolTip('Select query type.')
		self.cmb_charset.setToolTip('Select character set to compare with.')

		self.cmb_query.addItems(queries)
			
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_populate = QtGui.QPushButton('&Populate')
		
		# !!! Disable for now
		self.cmb_charset.setEnabled(False)
		self.btn_populate.setEnabled(False)

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

		# -- Table
		self.tab_stats = trTableView(self.table_dict)
		self.refresh()
		
		# -- Note/Descriotion
		self.addWidget(self.tab_stats)
		
		note_msg = QtGui.QLabel('Note: Data is processed according to currently selected table row, serving as base for comparison (100%).')
		note_msg.setOpenExternalLinks(True)
		note_msg.setWordWrap(True)

		self.addWidget(note_msg)

		# -- Addons
		self.btn_refresh.clicked.connect(lambda: self.refresh())
		self.btn_populate.clicked.connect(lambda: self.populate())
		self.cmb_query.currentIndexChanged.connect(lambda: self.change_query())

		# -- Table Styling
		self.tab_stats.horizontalHeader().setStretchLastSection(False)
		self.tab_stats.resizeColumnsToContents()
		self.tab_stats.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.tab_stats.selectionModel().selectionChanged.connect(self.change_selection)

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
				
		self.table_data = {}
		self.table_proc = {}
		node_count = 0

		# - Populate table
		self.table_data[self.glyph.name] = {layer:self.glyph.getBounds(layer).width() for layer in wLayers}
		
		if len(self.edt_glyphsSeq.text):
			for glyph_name in self.edt_glyphsSeq.text.split(' '):
				wGlyph = self.font.glyph(glyph_name)
				self.table_data[glyph_name] = {layer:wGlyph.getBounds(layer).width() for layer in wLayers}
			
		self.tab_stats.setTable(self.table_data)
		self.tab_stats.resizeColumnsToContents()		
		
	def change_selection(self):
		base_index = self.tab_stats.selectionModel().selectedIndexes[0].row()
		base_name = self.tab_stats.verticalHeaderItem(base_index).text()
		
		#print selection_name, self.table_data[selection_name]

		for glyph_name, glyph_layers in self.table_data.iteritems():
			self.table_proc[glyph_name] = {layer_name:'%s %%' %round(ratfrac(layer_value, self.table_data[base_name][layer_name]),2)  for layer_name, layer_value in glyph_layers.iteritems()}

		self.tab_stats.setTable(self.table_proc)
		self.tab_stats.resizeColumnsToContents()

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