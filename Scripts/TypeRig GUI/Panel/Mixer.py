#FLM: Glyph: Mixer
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# TODO: Anisotropic in Y direction is not precise - investigate!!!

# - Init
global pLayers
global pMode
pLayers = None
pMode = 0
app_name, app_version = 'TypeRig | Mixer', '1.15'

useFortran = False
warnMessage = 'This Panel requires some precompiled FontRig | TypeRig modules.'

# - Dependencies -----------------
from math import radians

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore
from typerig import QtGui

from typerig.proxy import pFont
from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.brain import coordArray, linInterp, ratfrac
from typerig.gui import trSliderCtrl, trMsgSimple

# -- Check for MathRig instalaltion
try:
    if useFortran:
    	import fontrig.transform as transform			# Fortran 95 code
    else:
    	import fontrig.numpy.transform as transform 	# Numpy reimplementation of original Fortran 95 code.
    sysReady = True

except ImportError:
    sysReady = False

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

		self.spb_compV = QtGui.QDoubleSpinBox()
		self.spb_compH = QtGui.QDoubleSpinBox()
		self.spb_compV.setValue(0.)
		self.spb_compH.setValue(0.)
		self.spb_compV.setSingleStep(.01)
		self.spb_compH.setSingleStep(.01)

		self.cmb_0 = QtGui.QComboBox()
		self.cmb_1 = QtGui.QComboBox()

		self.chk_italic = QtGui.QPushButton('Italic')
		self.chk_single = QtGui.QPushButton('Anisotropic')
		self.chk_preview = QtGui.QPushButton('Live Preview')
		
		self.chk_single.setToolTip('Active: Use X and Y sliders to control interpolation.')
		self.chk_single.setCheckable(True)
		self.chk_italic.setCheckable(True)
		self.chk_preview.setCheckable(True)

		self.chk_single.setChecked(False)
		self.chk_italic.setChecked(False)
		self.chk_preview.setChecked(False)

		self.addWidget(QtGui.QLabel('Glyph:'),		0, 0, 1, 1)
		self.addWidget(self.edt_glyphName,			0, 1, 1, 6)
		self.addWidget(self.btn_refresh,			0, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Axis:'),		1, 0, 1, 1)
		self.addWidget(self.cmb_0, 					1, 1, 1, 3)
		self.addWidget(self.cmb_1, 					1, 4, 1, 3)
		self.addWidget(self.btn_set_axis, 			1, 7, 1, 1)
		self.addWidget(QtGui.QLabel('V Stems:'),	2, 0, 1, 1)
		self.addWidget(self.edt_stemV0,				2, 1, 1, 3)
		self.addWidget(self.edt_stemV1,				2, 4, 1, 3)
		self.addWidget(self.btn_getVstem, 			2, 7, 1, 1)
		self.addWidget(QtGui.QLabel('H Stems:'),	3, 0, 1, 1)
		self.addWidget(self.edt_stemH0,				3, 1, 1, 3)
		self.addWidget(self.edt_stemH1,				3, 4, 1, 3)
		self.addWidget(self.btn_getHstem, 			3, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Adj.V/H:'),	4, 0, 1, 1)
		self.addWidget(self.spb_compV,				4, 1, 1, 3)
		self.addWidget(self.spb_compH,				4, 4, 1, 3)
		self.addWidget(self.chk_italic,				4, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Control:'),	5, 0, 1, 1)
		self.addWidget(self.chk_single,				5, 1, 1, 4)
		self.addWidget(self.chk_preview,			5, 5, 1, 3)

class mixerTail(QtGui.QGridLayout):
	def __init__(self):
		super(mixerTail, self).__init__()

		self.edt_width_0 = QtGui.QLineEdit()
		self.edt_width_1 = QtGui.QLineEdit()
		self.edt_width_t = QtGui.QLineEdit()
		self.edt_height_0 = QtGui.QLineEdit()
		self.edt_height_1 = QtGui.QLineEdit()
		self.edt_height_t = QtGui.QLineEdit()

		self.edt_width_0.setReadOnly(True) 
		self.edt_width_1.setReadOnly(True)
		self.edt_width_t.setReadOnly(True)
		self.edt_height_0.setReadOnly(True)
		self.edt_height_1.setReadOnly(True)
		self.edt_height_t.setReadOnly(True)

		self.edt_width_0.setPlaceholderText('BBox width') 
		self.edt_width_1.setPlaceholderText('BBox width')
		self.edt_width_t.setPlaceholderText('BBox width')
		self.edt_height_0.setPlaceholderText('BBox height')
		self.edt_height_1.setPlaceholderText('BBox height')
		self.edt_height_t.setPlaceholderText('BBox height')
		
		self.addWidget(QtGui.QLabel(''),			0, 0, 1, 1)
		self.addWidget(QtGui.QLabel('Master 0'),	0, 1, 1, 3)
		self.addWidget(QtGui.QLabel('Master 1'),	0, 4, 1, 3)
		self.addWidget(QtGui.QLabel('Result'),		0, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Width:'),		1, 0, 1, 1)
		self.addWidget(self.edt_width_0,			1, 1, 1, 3)
		self.addWidget(self.edt_width_1,			1, 4, 1, 3)
		self.addWidget(self.edt_width_t, 			1, 7, 1, 1)
		self.addWidget(QtGui.QLabel('Height'),		2, 0, 1, 1)
		self.addWidget(self.edt_height_0,			2, 1, 1, 3)
		self.addWidget(self.edt_height_1,			2, 4, 1, 3)
		self.addWidget(self.edt_height_t, 			2, 7, 1, 1)

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		# - Init
		layoutV = QtGui.QVBoxLayout()
		layoutH = QtGui.QHBoxLayout()

		# - Build panel
		if sysReady:			
			self.head = mixerHead()
			self.tail = mixerTail()
			self.head.btn_refresh.clicked.connect(self.refresh)
			self.head.btn_set_axis.clicked.connect(self.set_axis)
			self.head.btn_getVstem.clicked.connect(self.get_v_stems)
			self.head.btn_getHstem.clicked.connect(self.get_h_stems)
			layoutV.addLayout(self.head)
			layoutV.addSpacing(15)

			# -- Set Sliders
			# --- Mixer
			layoutV.addWidget(QtGui.QLabel('Interpolate: X (Vertical Stems)'))
			self.mixer_dx = trSliderCtrl('1', '1000', '0', 10)
			self.mixer_dx.sld_axis.valueChanged.connect(lambda: self.process_scale(self.head.chk_single.isChecked(), self.head.chk_preview.isChecked()))		
			layoutV.addLayout(self.mixer_dx)

			layoutV.addWidget(QtGui.QLabel('Interpolate: Y (Horizontal Stems)'))
			self.mixer_dy = trSliderCtrl('1', '1000', '0', 10)
			self.mixer_dy.sld_axis.valueChanged.connect(lambda: self.process_scale(self.head.chk_single.isChecked(), self.head.chk_preview.isChecked()))		
			layoutV.addLayout(self.mixer_dy)

			# - Constant width Button
			#self.btn_revWidth = QtGui.QPushButton('Constant width for weight')
			#self.btn_revWidth.setCheckable(True)
			#layoutV.addWidget(self.btn_revWidth)
			layoutV.addSpacing(15)

			# --- Scaler
			layoutV.addWidget(QtGui.QLabel('Compensative scaler: Width'))
			self.scaler_dx = trSliderCtrl('1', '200', '100', 10)
			self.scaler_dx.sld_axis.valueChanged.connect(lambda: self.process_scale(self.head.chk_single.isChecked(), self.head.chk_preview.isChecked()))		
			layoutV.addLayout(self.scaler_dx)
			layoutV.addSpacing(15)

			layoutV.addWidget(QtGui.QLabel('Compensative scaler: Height'))
			self.scaler_dy = trSliderCtrl('1', '200', '100', 10)
			self.scaler_dy.sld_axis.valueChanged.connect(lambda: self.process_scale(self.head.chk_single.isChecked(), self.head.chk_preview.isChecked()))		
			layoutV.addLayout(self.scaler_dy)
			layoutV.addSpacing(25)
		
			layoutV.addLayout(self.tail)
			# - Process Button
			self.btn_process = QtGui.QPushButton('Process Transformation')
			self.btn_process.clicked.connect(lambda: self.process_scale(self.head.chk_single.isChecked(), True, True))
			layoutV.addWidget(self.btn_process)

			# -- Initialize
			self.refresh()

			# -- Finish
			layoutV.addStretch()

		else:
			# - Throw an error
			layoutV.addLayout(trMsgSimple(warnMessage))

		# - Set panel
		self.setLayout(layoutV)

	def refresh(self):
		# - Init
		layerBanList = ['#', 'img']
		self.glyph = eGlyph()
		self.head.edt_glyphName.setText(eGlyph().name)
		self.italic_angle = pFont().getItalicAngle()
		
		self.layers = sorted([layer.name for layer in self.glyph.layers() if all([item not in layer.name for item in layerBanList])])
		
		self.head.cmb_0.clear()
		self.head.cmb_1.clear()
		self.head.cmb_0.addItems(self.layers)
		self.head.cmb_1.addItems(self.layers)
		self.head.cmb_0.setCurrentIndex(0)
		self.head.cmb_1.setCurrentIndex(0)
		self.axis = []

		self.head.edt_stemV0.setText('1')
		self.head.edt_stemV1.setText('2')
		self.head.edt_stemH0.setText('1')
		self.head.edt_stemH1.setText('2')

		self.tail.edt_width_0.clear()
		self.tail.edt_width_1.clear()
		self.tail.edt_width_t.clear()
		self.tail.edt_height_0.clear()
		self.tail.edt_height_1.clear()
		self.tail.edt_height_t.clear()

		self.mixer_dx.reset()
		self.mixer_dy.reset()
		self.scaler_dx.reset()
		self.scaler_dy.reset()

	def get_v_stems(self):
		stemNodes0 = self.glyph.selectedNodes(self.head.cmb_0.currentText, True)
		stemNodes1 = self.glyph.selectedNodes(self.head.cmb_1.currentText, True)
		wt_0 = abs(stemNodes0[0].x - stemNodes0[-1].x)
		wt_1 = abs(stemNodes1[0].x - stemNodes1[-1].x)
		self.head.edt_stemV0.setText(wt_0)
		self.head.edt_stemV1.setText(wt_1)
		self.mixer_dx.edt_0.setText(min(wt_0, wt_1))
		self.mixer_dx.edt_1.setText(max(wt_0, wt_1))
		self.mixer_dx.edt_pos.setText(wt_0)
		self.mixer_dx.refreshSlider()

	def get_h_stems(self):
		stemNodes0 = self.glyph.selectedNodes(self.head.cmb_0.currentText, True)
		stemNodes1 = self.glyph.selectedNodes(self.head.cmb_1.currentText, True)
		wt_0 = abs(stemNodes0[0].y - stemNodes0[-1].y)
		wt_1 = abs(stemNodes1[0].y - stemNodes1[-1].y)
		self.head.edt_stemH0.setText(wt_0)
		self.head.edt_stemH1.setText(wt_1)
		self.mixer_dy.edt_0.setText(min(wt_0, wt_1))
		self.mixer_dy.edt_1.setText(max(wt_0, wt_1))
		self.mixer_dy.edt_pos.setText(wt_0)
		self.mixer_dy.refreshSlider()

	def set_axis(self):
		self.axis = [self.glyph._getCoordArray(self.head.cmb_0.currentText), self.glyph._getCoordArray(self.head.cmb_1.currentText)]
		axis_0_bounds = self.glyph.getBounds(self.head.cmb_0.currentText)
		axis_1_bounds = self.glyph.getBounds(self.head.cmb_1.currentText)
		self.tail.edt_width_0.setText(axis_0_bounds.width())
		self.tail.edt_width_1.setText(axis_1_bounds.width())
		self.tail.edt_height_0.setText(axis_0_bounds.height())
		self.tail.edt_height_1.setText(axis_1_bounds.height())
		self.glyph.updateObject(self.glyph.fl, 'Mixer Snapshot @ %s' %self.glyph.layer().name)
	
	def process_scale(self, anisotropic=False, process=False, true_update=False):
		if len(self.axis):
			# - Axis
			a = self.axis[0]
			b = self.axis[1]
			
			# - Compensation
			scmp = float(self.head.spb_compH.value), float(self.head.spb_compV.value)
			
			# - Italic Angle
			if self.head.chk_italic.isChecked():
				angle = radians(-float(self.italic_angle))
			else:
				angle = 0
			
			# - Stems
			sw_dx = (float(self.head.edt_stemV0.text), float(self.head.edt_stemV1.text))
			sw_dy = (float(self.head.edt_stemH0.text), float(self.head.edt_stemH1.text))

			curr_sw_dx = float(self.mixer_dx.sld_axis.value)
			curr_sw_dy = float(self.mixer_dy.sld_axis.value)
			
			sw_dx0, sw_dx1 = min(*sw_dx), max(*sw_dx)
			sw_dy0, sw_dy1 = min(*sw_dy), max(*sw_dy)
			
			# - Interpolation
			tx = ((curr_sw_dx - sw_dx0)/(sw_dx1 - sw_dx0))*(1,-1)[sw_dx[0] > sw_dx[1]] + (0,1)[sw_dx[0] > sw_dx[1]]
			ty = ((curr_sw_dy - sw_dy0)/(sw_dy1 - sw_dy0))*(1,-1)[sw_dy[0] > sw_dy[1]] + (0,1)[sw_dy[0] > sw_dx[1]]

			# - Scaling
			sx = 100./float(self.scaler_dx.edt_1.text) + float(self.scaler_dx.sld_axis.value)/float(self.scaler_dx.edt_1.text)
			sy = 100./float(self.scaler_dy.edt_1.text) + float(self.scaler_dy.sld_axis.value)/float(self.scaler_dy.edt_1.text)
			dx, dy = 0.0, 0.0

			# - Build
			if useFortran: # Original Fortran 95 implementation
				mm_scaler = lambda sx, sy, tx, ty : transform.adaptive_scale([a.x, a.y], [b.x, b.y], [sw_dx[0], sw_dy[0]], [sw_dx[1], sw_dy[1]], [sx, sy], [dx, dy], [tx, ty], scmp, angle)

			else: # NumPy implementation
				mm_scaler = lambda sx, sy, tx, ty : transform.adaptive_scale([a.x, a.y], [b.x, b.y], sx, sy, dx, dy, tx, ty, scmp[0], scmp[1], angle, sw_dx0, sw_dx1)

			if process:	
				'''
				# - Keep width constant for weight change
				if self.btn_revWidth.isChecked(): 
					glyph_width = self.glyph.getBounds().width()
					scale_result = mm_scaler(sx, sy, tx, ty)

					max_width = scale_result.T[0].max() - scale_result.T[0].min()
					sx = float(glyph_width)/max_width #ratfrac(min(max_width, glyph_width), max(max_width, glyph_width), 1.)
				'''
				# - Process
				if anisotropic:
					# - Single axis mixer
					self.glyph._setCoordArray(mm_scaler(sx, sy, tx, ty))
				else:
					# - Dual axis mixer - anisotropic 
					self.glyph._setCoordArray(mm_scaler(sx, sy, tx, tx))
				
				if not true_update:
					self.glyph.update()
				 	fl6.Update(fl6.CurrentGlyph())
				else:
					self.glyph.update()
					self.glyph.updateObject(self.glyph.fl, 'Glyph: %s | Mixer | sx: %s; sy: %s; tx: %s; ty: %s.' %(self.glyph.name, sx, sy, tx, ty))

			else:
				# - Just return output
				#return mm_scaler(sx, sy, tx, ty)
				scale_result = mm_scaler(sx, sy, tx, ty)
				self.tail.edt_width_t.setText(scale_result.T[0].max() - scale_result.T[0].min())
				self.tail.edt_height_t.setText(scale_result.T[1].max() - scale_result.T[1].min())

	
# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(300, 300, 280, 400)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
	
	test.show()