#FLM: Glyph: Statistics
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
from typerig.proxy import pFont, pWorkspace
from typerig.glyph import eGlyph
from typerig.gui import trTableView
from typerig.brain import ratfrac
#from collections import OrderedDict

# - Init
app_name, app_version = 'TypeRig | Glyph Statistics', '0.09'

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

		# --- Add queries
		self.query_list = [
							'(BBox) Bounding Box Width',
							'(BBox) Bounding Box Height',
							'(Metrics) Advance Width',
							'(Metrics) Left Side-bearing',
							'(Metrics) Right Side-bearing'
							]

		self.cmb_query.addItems(self.query_list)
			
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_populate = QtGui.QPushButton('&Populate')
		self.btn_get = QtGui.QPushButton('&Window')
		self.btn_probe = QtGui.QPushButton('Glyph')
		self.btn_units = QtGui.QPushButton('Percent')

		self.btn_refresh.setToolTip('Refresh active glyph and table.')
		self.btn_populate.setToolTip('Populate character set selector from current font.')
		self.btn_get.setToolTip('Get current string from active Glyph Window.')
		self.btn_probe.setToolTip('Toggle between Row (Glyph) or Column (Layer) based comparison.')
		self.btn_units.setToolTip('Toggle the results beeing shown as (Units) or (Percent).')

		self.btn_probe.setCheckable(True)
		self.btn_units.setCheckable(True)
		self.btn_probe.setChecked(False)
		self.btn_units.setChecked(False)
		
		# !!! Disable for now
		self.cmb_charset.setEnabled(False)
		self.btn_populate.setEnabled(False)

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('G:'),	0,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,	0,1,1,5)
		self.lay_head.addWidget(self.btn_refresh,	0,6,1,2)
		#self.lay_head.addWidget(QtGui.QLabel('C:'),	1,0,1,1)
		#self.lay_head.addWidget(self.cmb_charset,	1,1,1,5)
		#self.lay_head.addWidget(self.btn_populate,	1,6,1,2)
		self.lay_head.addWidget(QtGui.QLabel('C:'),	2,0,1,1)
		self.lay_head.addWidget(self.edt_glyphsSeq,	2,1,1,5)
		self.lay_head.addWidget(self.btn_get,		2,6,1,2)
		self.lay_head.addWidget(QtGui.QLabel('Q:'),	3,0,1,1)
		self.lay_head.addWidget(self.cmb_query,		3,1,1,5)
		self.lay_head.addWidget(self.btn_probe,		3,6,1,2)
		self.addLayout(self.lay_head)

		# -- Table
		self.tab_stats = trTableView(self.table_dict)
		self.refresh()
		
		# -- Note/Descriotion
		self.addWidget(self.tab_stats)
		self.addWidget(self.btn_units)

		# -- Addons
		self.btn_refresh.clicked.connect(self.refresh)
		self.btn_populate.clicked.connect(self.populate)
		self.btn_get.clicked.connect(self.get_string)
		self.btn_probe.clicked.connect(self.toggle_query)
		self.btn_units.clicked.connect(self.toggle_units)
		self.cmb_query.currentIndexChanged.connect(self.refresh)

		# -- Table Styling
		self.tab_stats.horizontalHeader().setStretchLastSection(False)
		self.tab_stats.resizeColumnsToContents()
		self.tab_stats.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
		self.tab_stats.selectionModel().selectionChanged.connect(self.change_selection)

	def populate(self):
		font = pFont()
		self.glyphNames = font.getGlyphNamesDict()
		self.cmb_charset.addItems(sorted(self.glyphNames.keys()))

	def get_string(self):
		workspace = pWorkspace()
		glyphsSeq = ' '.join(sorted(list(set([glyph.name for glyph in workspace.getTextBlockGlyphs()]))))
		self.edt_glyphsSeq.setText(glyphsSeq)
		
	def refresh(self, layer=None):
		# - Init
		font = pFont()
		glyph = eGlyph()
		wLayers = glyph._prepareLayers((True, True, False, False))

		self.edt_glyphName.setText(eGlyph().name)
				
		self.table_data = {}
		self.table_proc = {}

		# - Populate table
		self.table_data[glyph.name] = {layer:glyph.getBounds(layer).width() for layer in wLayers}
		
		if len(self.edt_glyphsSeq.text):
			for glyph_name in self.edt_glyphsSeq.text.split(' '):
				wGlyph = font.glyph(glyph_name)
				self.table_data[glyph_name] = {layer:self.process_query(wGlyph, layer, self.cmb_query.currentText) for layer in wLayers}
			
		self.tab_stats.setTable(self.table_data)
		self.tab_stats.resizeColumnsToContents()		
		
	def change_selection(self):
		# - Helper for avoiding ZeroDivision error
		def noZero(value):
			return value if value != 0 else 1

		# - Init
		base_index = self.tab_stats.selectionModel().selectedIndexes[0]
		base_name = self.tab_stats.verticalHeaderItem(base_index.row()).text()
		base_layer = self.tab_stats.horizontalHeaderItem(base_index.column()).text()
				
		for glyph_name, glyph_layers in self.table_data.iteritems():
			if not self.btn_probe.isChecked():
				if self.btn_units.isChecked():
					self.table_proc[glyph_name] = {layer_name: -round(self.table_data[base_name][layer_name] - layer_value, 2)  for layer_name, layer_value in glyph_layers.iteritems()}
				else:
					self.table_proc[glyph_name] = {layer_name:'%s %%' %round(ratfrac(noZero(layer_value), noZero(self.table_data[base_name][layer_name])),2)  for layer_name, layer_value in glyph_layers.iteritems()}
			else:
				if self.btn_units.isChecked():
					self.table_proc[glyph_name] = {layer_name: -round(self.table_data[glyph_name][base_layer] - layer_value, 2)  for layer_name, layer_value in glyph_layers.iteritems()}
				else:
					self.table_proc[glyph_name] = {layer_name:'%s %%' %round(ratfrac(noZero(layer_value), noZero(self.table_data[glyph_name][base_layer])),2)  for layer_name, layer_value in glyph_layers.iteritems()}

		self.tab_stats.setTable(self.table_proc)
		self.tab_stats.resizeColumnsToContents()

	def toggle_query(self):
		if self.btn_probe.isChecked():
			self.btn_probe.setText('Layer')
			self.tab_stats.setSelectionBehavior(QtGui.QAbstractItemView.SelectColumns)
		else:
			self.btn_probe.setText('Glyph')
			self.tab_stats.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

	def toggle_units(self):
		if self.btn_units.isChecked():
			self.btn_units.setText('Units')
		else:
			self.btn_units.setText('Percent')

	def process_query(self, glyph, layer, query):
		if 'bbox' in query.lower() and 'width' in query.lower(): return glyph.getBounds(layer).width()
		if 'bbox' in query.lower() and 'height' in query.lower(): return glyph.getBounds(layer).height()
		if 'metrics' in query.lower() and 'advance' in query.lower(): return glyph.getAdvance(layer)
		if 'metrics' in query.lower() and 'left' in query.lower(): return glyph.getLSB(layer)
		if 'metrics' in query.lower() and 'right' in query.lower(): return glyph.getRSB(layer)

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