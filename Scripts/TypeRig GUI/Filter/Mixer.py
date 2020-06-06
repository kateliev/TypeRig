#FLM: TR: Mixer
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os, json
from math import radians
from collections import OrderedDict

import fontlab as fl6
import fontgate as fgt

from typerig.proxy import *

from typerig.core.func.math import linInterp, ratfrac
from typerig.core.func import transform
from typerig.core.objects.array import PointArray
from typerig.core.objects.delta import DeltaArray, DeltaScale

from PythonQt import QtCore
from typerig.gui import QtGui
from typerig.gui.widgets import getProcessGlyphs, TRSliderCtrl, TRMsgSimple

# - Init -------------------------------
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Mixer', '2.2'


# - Sub widgets ------------------------
class mixerHead(QtGui.QGridLayout):
	def __init__(self):
		super(mixerHead, self).__init__()

		self.edt_glyphName = QtGui.QLineEdit()
		self.edt_stemV0 = QtGui.QLineEdit('1')
		self.edt_stemV1 = QtGui.QLineEdit('1')
		self.edt_stemH0 = QtGui.QLineEdit('1')
		self.edt_stemH1 = QtGui.QLineEdit('1')
		
		self.btn_refresh = QtGui.QPushButton('&Refresh')
		self.btn_set_axis = QtGui.QPushButton('Set &Axis')
		self.btn_getVstem = QtGui.QPushButton('Get &V Stems')
		self.btn_getHstem = QtGui.QPushButton('Get &H Stems')

		self.addWidget(QtGui.QLabel('G:'),			0, 0, 1, 1)
		self.addWidget(self.edt_glyphName,			0, 1, 1, 6)
		self.addWidget(self.btn_refresh,			0, 7, 1, 3)
		self.addWidget(QtGui.QLabel('A:'),			1, 0, 1, 1)
		self.addWidget(self.btn_set_axis, 			1, 1, 1, 3)
		self.addWidget(self.btn_getVstem, 			1, 4, 1, 3)
		self.addWidget(self.btn_getHstem, 			1, 7, 1, 3)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
				
		# - Build panel
		self.head = mixerHead()
		self.head.btn_refresh.clicked.connect(self.refresh)
		self.head.btn_set_axis.clicked.connect(self.set_axis)
		self.head.btn_getVstem.clicked.connect(self.get_stem_y)
		self.head.btn_getHstem.clicked.connect(self.get_stem_x)
		layoutV.addLayout(self.head)
		layoutV.addSpacing(15)

		# -- Set Sliders
		# --- Mixer
		layoutV.addWidget(QtGui.QLabel('Stem Weight: X'))
		self.mixer_dx = TRSliderCtrl('1', '1000', '0', 1)
		self.mixer_dx.sld_axis.valueChanged.connect(self.execute_scale)		
		layoutV.addLayout(self.mixer_dx)
		layoutV.addSpacing(10)

		layoutV.addWidget(QtGui.QLabel('Stem Weight: Y'))
		self.mixer_dy = TRSliderCtrl('1', '1000', '0', 1)
		self.mixer_dy.sld_axis.valueChanged.connect(self.execute_scale)		
		layoutV.addLayout(self.mixer_dy)
		layoutV.addSpacing(25)

		# --- Scaler
		layoutV.addWidget(QtGui.QLabel('Compensative scaler: Width'))
		self.scalerX = TRSliderCtrl('1', '200', '100', 1)
		self.scalerX.sld_axis.valueChanged.connect(self.execute_scale)		
		layoutV.addLayout(self.scalerX)
		layoutV.addSpacing(10)

		layoutV.addWidget(QtGui.QLabel('Compensative scaler: Height'))
		self.scalerY = TRSliderCtrl('1', '200', '100', 1)
		self.scalerY.sld_axis.valueChanged.connect(self.execute_scale)		
		layoutV.addLayout(self.scalerY)
	
		# -- Initialize
		self.refresh()

		# -- Finish
		layoutV.addStretch()
		self.setLayout(layoutV)
		
		# !!! Hotfix FL7 7355 
		self.setMinimumSize(300,self.sizeHint.height())
		
	def __where(self):
		return self.master_names.index(self.glyph.layer().name)

	def refresh(self):
		# - Init
		self.axis_points = []
		self.axis_stems = []
		self.master_stems_x = []
		self.master_stems_y = []

		self.glyph = eGlyph()
		self.active_font = pFont()
		
		axis, masters = self.active_font.pMasters.locateAxis(self.glyph.layer().name, 'wght')
		self.master_names = [master.name for master in masters]
		
		self.head.edt_glyphName.setText('{} :: {}'.format(self.glyph.name, '; '.join(self.master_names)))
		self.italic_angle = self.active_font.getItalicAngle()

		self.head.edt_stemV0.setText('1')
		self.head.edt_stemV1.setText('1')
		self.head.edt_stemH0.setText('1')
		self.head.edt_stemH1.setText('1')

		self.mixer_dx.reset()
		self.mixer_dy.reset()
		self.scalerX.reset()
		self.scalerY.reset()

	def get_stem_x(self):
		for layer_name in self.master_names:
			selection = self.glyph.selectedNodes(layer_name, True)
			wt = abs(selection[0].x - selection[-1].x)
			self.master_stems_x.append(wt)

		self.head.edt_stemV0.setText(self.master_stems_x[0])
		self.head.edt_stemV1.setText(self.master_stems_x[-1])

		self.mixer_dx.edt_0.setText(round(min(self.master_stems_x)))
		self.mixer_dx.edt_1.setText(round(max(self.master_stems_x)))
		self.mixer_dx.edt_pos.setText(round(self.master_stems_x[self.master_names.index(self.glyph.layer().name)]))
		self.mixer_dx.refreshSlider()

	def get_stem_y(self):
		for layer_name in self.master_names:
			selection = self.glyph.selectedNodes(layer_name, True)
			wt = abs(selection[0].y - selection[-1].y)
			self.master_stems_y.append(wt)

		self.head.edt_stemV0.setText(self.master_stems_y[0])
		self.head.edt_stemV1.setText(self.master_stems_y[-1])

		self.mixer_dy.edt_0.setText(round(min(self.master_stems_y)))
		self.mixer_dy.edt_1.setText(round(max(self.master_stems_y)))
		self.mixer_dy.edt_pos.setText(round(self.master_stems_y[self.__where()]))
		self.mixer_dy.refreshSlider()

	def set_axis(self):
		if len(self.master_stems_x) and len(self.master_stems_y):
			# - Init
			self.axis_stems = [[item] for item in zip(self.master_stems_x, self.master_stems_y)]
			temp_points = [self.glyph._getPointArray(name) for name in self.master_names]

			# - Build
			self.axis_points = DeltaScale(temp_points, self.axis_stems)
			self.glyph.updateObject(self.glyph.fl, 'Axis Set @ %s' %self.glyph.layer().name)
	
	def execute_scale(self):
		if len(self.axis_points):
			# - Stems
			curr_sw_dx = float(self.mixer_dx.sld_axis.value)
			curr_sw_dy = float(self.mixer_dy.sld_axis.value)

			# - Scaling
			sx = 100./float(self.scalerX.edt_1.text) + float(self.scalerX.sld_axis.value)/float(self.scalerX.edt_1.text)
			sy = 100./float(self.scalerY.edt_1.text) + float(self.scalerY.sld_axis.value)/float(self.scalerY.edt_1.text)
			
			self.glyph._setPointArray(self.axis_points.scale_by_stem((curr_sw_dx, curr_sw_dy), (sx,sy), (0.,0.), (0.,0.), radians(-float(self.italic_angle))))
			
			self.glyph.update()
			fl6.Update(fl6.CurrentGlyph())

	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 280, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()