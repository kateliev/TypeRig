from PythonQt.QtGui import *
from platform import system

MAC_VSPACING = 3

class QDialog(QDialog):
	def __init__(self):
		super(QDialog, self).__init__()
		if system() == 'Darwin':
			self.setStyleSheet("font-size: 11px;")

class QGridLayout(QGridLayout):
	def __init__(self):
		super(QGridLayout, self).__init__()
		if system() == 'Darwin':
			self.setVerticalSpacing(MAC_VSPACING)
			self.setContentsMargins(10,3,10,3)

class QVBoxLayout(QVBoxLayout):
	def __init__(self):
		super(QVBoxLayout, self).__init__()
		if system() == 'Darwin':
			self.setSpacing(MAC_VSPACING)
			self.setContentsMargins(10,3,10,3)
