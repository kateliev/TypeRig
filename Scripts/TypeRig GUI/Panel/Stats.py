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
from PythonQt import QtCore
from typerig import QtGui
from typerig.proxy import pFont, pWorkspace
from typerig.glyph import eGlyph
from typerig.gui import trTableView
from typerig.brain import ratfrac
#from collections import OrderedDict

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Glyph Statistics', '0.14'

# - Sub widgets ------------------------
class QGlyphInfo(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QGlyphInfo, self).__init__()

		# -- Init
		self.table_dict = {0:{0:None}} # Empty table

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
		#self.refresh()
		
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
		pLayers = (True, True, False, False) # !!! Quickfix: Stats crashes FL after mode switch + refresh
		wLayers = glyph._prepareLayers(pLayers)
		self.table_data, self.table_proc = {}, {}

		current_glyph_name = eGlyph().name
		self.edt_glyphName.setText(current_glyph_name)
		
		# - Populate table
		process_glyph_names = [current_glyph_name] + self.edt_glyphsSeq.text.split(' ') if len(self.edt_glyphsSeq.text) else [current_glyph_name]
		
		for glyph_name in process_glyph_names:
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

class QRatioInfo(QtGui.QGridLayout):
	# - Copy Metric properties from other glyph
	def __init__(self):
		super(QRatioInfo, self).__init__()

		# - Spin Boxes
		self.edt_part_width =  QtGui.QLineEdit()
		self.edt_ratio_width = QtGui.QLineEdit()
		self.edt_whole_width = QtGui.QLineEdit()
		self.edt_part_height =  QtGui.QLineEdit()
		self.edt_ratio_height = QtGui.QLineEdit()
		self.edt_whole_height = QtGui.QLineEdit()

		self.edt_part_width.setPlaceholderText('width')
		self.edt_whole_width.setPlaceholderText('width')
		self.edt_ratio_width.setPlaceholderText('ratio')
		self.edt_part_height.setPlaceholderText('height')
		self.edt_whole_height.setPlaceholderText('height')
		self.edt_ratio_height.setPlaceholderText('ratio')

		# - Buttons
		self.btn_part = QtGui.QPushButton('Part')
		self.btn_whole = QtGui.QPushButton('Whole')
		self.btn_ratio = QtGui.QPushButton('Ratio %')
		self.btn_part .setToolTip('Set width/height from Node Selection.')
		self.btn_whole .setToolTip('Set width/height from Node Selection.')
		self.btn_ratio .setToolTip('Get part/whole ratio in percent.')

		self.btn_part.clicked.connect(lambda: self.setFields((self.edt_part_width, self.edt_part_height)))
		self.btn_whole.clicked.connect(lambda: self.setFields((self.edt_whole_width, self.edt_whole_height)))
		self.btn_ratio.clicked.connect(self.getRatio)

		self.addWidget(QtGui.QLabel('Relation calculator:'), 	0, 0, 1, 4)
		self.addWidget(QtGui.QLabel('W:'), 		1, 0, 1, 1)
		self.addWidget(self.edt_part_width, 	1, 1, 1, 1)
		self.addWidget(self.edt_whole_width, 	1, 2, 1, 1)
		self.addWidget(self.edt_ratio_width, 	1, 3, 1, 1)

		self.addWidget(QtGui.QLabel('H:'), 		2, 0, 1, 1)
		self.addWidget(self.edt_part_height, 	2, 1, 1, 1)
		self.addWidget(self.edt_whole_height, 	2, 2, 1, 1)
		self.addWidget(self.edt_ratio_height, 	2, 3, 1, 1)

		self.addWidget(self.btn_part, 			3, 1, 1, 1)
		self.addWidget(self.btn_whole, 			3, 2, 1, 1)
		self.addWidget(self.btn_ratio, 			3, 3, 1, 1)

	def setFields(self, fieldTuple):
		glyph = eGlyph()
		selection = glyph.selectedNodes()

		if len(selection):
			x_coords, y_coords = [],[]
			for node in selection:
				x_coords.append(node.x)
				y_coords.append(node.y)

			x_coords = list(set(x_coords))
			y_coords = list(set(y_coords))
			
			width = max(x_coords) - min(x_coords)
			height = max(y_coords) - min(y_coords)
			
			fieldTuple[0].setText(width)
			fieldTuple[1].setText(height)
		else:
			fieldTuple[0].clear()
			fieldTuple[1].clear()

	def getRatio(self):
		if len(self.edt_part_width.text) and len(self.edt_whole_width.text):
			self.edt_ratio_width.setText(ratfrac(float(self.edt_part_width.text), float(self.edt_whole_width.text)))
		else:
			self.edt_ratio_width.clear()

		if len(self.edt_part_height.text) and len(self.edt_whole_height.text):
			self.edt_ratio_height.setText(ratfrac(float(self.edt_part_height.text), float(self.edt_whole_height.text)))
		else:
			self.edt_ratio_height.clear()


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.glyph_info = QGlyphInfo()
		layoutV.addLayout(self.glyph_info)
		layoutV.addLayout(QRatioInfo())
		
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