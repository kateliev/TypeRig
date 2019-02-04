#FLM: Glyph: Round corner
# ----------------------------------------
# (C) Vassil Kateliev, 2019 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.proxy import pFont, pGlyph
from typerig.glyph import eGlyph
from typerig.gui import trTableView
from collections import OrderedDict

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Round', '0.1'

# -- Strings
filter_name = 'Smart corner'

# - Sub widgets ------------------------
class QSmartCorner(QtGui.QVBoxLayout):
	# - Split/Break contour 
	def __init__(self):
		super(QSmartCorner, self).__init__()

		# -- Init
		self.active_font = pFont()
		self.builder = None
		self.font_masters = self.active_font.masters()
		self.empty_preset = lambda row: OrderedDict([(row, OrderedDict([('Preset', 'Preset %s' %row)] + [(master, 0) for master in self.font_masters]))])
		self.table_dict = self.empty_preset(0)

		# -- Widgets
		self.lay_head = QtGui.QGridLayout()

		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_glyphName.setPlaceholderText('Glyph name')

		self.btn_getBuilder = QtGui.QPushButton('Set &Builder')
		self.btn_findBuilder = QtGui.QPushButton('&From Font')
		self.btn_addPreset = QtGui.QPushButton('Add &Preset')
		self.btn_delPreset = QtGui.QPushButton('&Remove Preset')
		self.btn_loadPreset = QtGui.QPushButton('&Load Presets')
		self.btn_savePreset = QtGui.QPushButton('&Save Presets')
		self.btn_applyPreset = QtGui.QPushButton('&Apply Preset')

		self.btn_getBuilder.setCheckable(True)
		self.btn_getBuilder.setChecked(False)
		self.btn_findBuilder.setEnabled(False)

		self.btn_getBuilder.clicked.connect(self.getBuilder)
		self.btn_addPreset.clicked.connect(lambda: self.preset_modify(False))
		self.btn_delPreset.clicked.connect(lambda: self.preset_modify(True))
		self.btn_loadPreset.clicked.connect(lambda: self.preset_load())
		self.btn_savePreset.clicked.connect(lambda: self.preset_save())
		self.btn_applyPreset.clicked.connect(lambda: self.preset_apply())

		# -- Rounding recipe Table
		self.tab_roundValues = trTableView(None)		
		self.tab_roundValues.clear()
		self.tab_roundValues.setTable(self.table_dict, sortData=(False, False))
		self.tab_roundValues.horizontalHeader().setStretchLastSection(False)
		self.tab_roundValues.verticalHeader().hide()
		self.tab_roundValues.resizeColumnsToContents()

		# -- Build Layout
		self.lay_head.addWidget(QtGui.QLabel('Round: Smart corner'), 0,0,1,8)
		self.lay_head.addWidget(QtGui.QLabel('B: '),			1,0,1,1)
		self.lay_head.addWidget(self.edt_glyphName,				1,1,1,3)
		self.lay_head.addWidget(self.btn_getBuilder,			1,4,1,2)
		self.lay_head.addWidget(self.btn_findBuilder,			1,6,1,2)
		self.lay_head.addWidget(self.btn_loadPreset,			2,0,1,4)
		self.lay_head.addWidget(self.btn_savePreset,			2,4,1,4)
		self.lay_head.addWidget(self.btn_addPreset,				3,0,1,4)
		self.lay_head.addWidget(self.btn_delPreset,				3,4,1,4)
		self.lay_head.addWidget(self.tab_roundValues,			4,0,2,8)
		self.lay_head.addWidget(self.btn_applyPreset,			6,0,1,8)
		self.addLayout(self.lay_head)

	def getBuilder(self):
		if self.btn_getBuilder.isChecked():
			if len(self.edt_glyphName.text):
				builder_glyph = self.active_font.glyph(self.edt_glyphName.text)
			else:
				builder_glyph = pGlyph()
				self.edt_glyphName.setText(builder_glyph.name)

			if builder_glyph is not None:
				temp_builder = builder_glyph.getBuilders()

				if len(temp_builder.keys()) and filter_name in temp_builder.keys():
					self.builder = temp_builder[filter_name]
					self.btn_getBuilder.setText('Release')
		else:
			self.builder = None
			self.edt_glyphName.clear()
			self.btn_getBuilder.setText('Set Builder')			

	def preset_modify(self, delete=False):
		table_rawList = self.tab_roundValues.getTable(raw=True)
		
		if delete:
			for selection in self.tab_roundValues.selectionModel().selectedIndexes:
				table_rawList.pop(selection.row())
				print selection.row()

		new_entry = OrderedDict()
		
		for key, data in table_rawList:
			new_entry[key] = OrderedDict(data)

		if not delete: new_entry[len(table_rawList)] = self.empty_preset(len(table_rawList)).items()[0][1]
		self.tab_roundValues.setTable(new_entry, sortData=(False, False))

	
	def preset_load(self):
		pass

	def preset_save(self):
		pass

	def preset_apply(self):
		glyph = eGlyph()
		wLayers = glyph._prepareLayers(pLayers)
		table_raw = self.tab_roundValues.getTable(raw=True)
		active_preset_index = self.tab_roundValues.selectionModel().selectedIndexes[0].row()
		active_preset = dict(table_raw[active_preset_index][1][1:])
		
		for layer in wLayers:
			if layer in active_preset.keys():
				print float(active_preset[layer])
		


	
# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		self.smart_corner = QSmartCorner()
		layoutV.addLayout(self.smart_corner)
		
		# - Build
		layoutV.addStretch()
		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()