# MODULE: TypeRig | IMPEX Actions
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from PythonQt import QtCore
from typerig.gui import QtGui

# - Imports ----------------------
import afm

# - Action Objects ---------------
class action_empty(QtGui.QWidget):
	'''Empty placeholder'''
	def __init__(self):
		super(action_empty, self).__init__()
		
		# - Init
		self.active_font = None
		self.file_format = None

		# - Interface
		# ...

		# - Build
		lay_wgt = QtGui.QGridLayout()
		# ...
		self.setLayout(lay_wgt)
		
		print 'WARN:\t Action Not Implemented...'