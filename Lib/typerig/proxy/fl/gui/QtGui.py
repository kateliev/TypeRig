# MODULE: Typerig / GUI / QtGui
# NOTE: Mac Os GUI compatibility module
# ----------------------------------------
# (C) Adam Twardoch, 2019
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!


__version__ = '0.0.2'

from PythonQt.QtGui import *
from platform import system


if system() == 'Darwin':
	QApplication.setStyle(QStyleFactory.create('macintosh')) # Options: Windows, WindowsXP, WindowsVista, Fusion

MAC_VSPACING = 2
MAC_VMARGIN = 2

def uiRefresh(widget):
	if system() == 'Darwin':
		desktopHeight = QDesktopWidget().height
		css = ''
		fontWidgets = '''
			QCheckBox, 
			QComboBox,
			QDialog, 
			QLabel, 
			QLineEdit, 
			QPushButton, 
			QRadioButton,
			QSpinBox,
			QTabBar::tab,
			QTabWidget, 
			QTableWidget
		'''
		if desktopHeight >= 1050:
			fontSize = 11
			css = '''
				%(fontWidgets)s { 
					font-size: %(fontSize)spx;
				}
			''' % {'fontSize': fontSize, 'fontWidgets': fontWidgets}
		elif desktopHeight <= 768:
			fontSize = 10
			css = '''
				%(fontWidgets)s { 
					font-size: %(fontSize)spx;
				}
				QPushButton { 
					padding: 2px 8px 2px 8px; 
					margin: 3px 2px 3px 2px;
					border-style: solid;
					border-color: #c8c8c8;
					border-radius: 3px;
					border-width: 1px;
					background-color: white;
				}
				QPushButton:pressed { 
					color: white;
					background-color: #1c76ff;
				}
			''' % {'fontSize': fontSize, 'fontWidgets': fontWidgets}
		else:
			fontSize = 10
			css = '''
				%(fontWidgets)s { 
					font-size: %(fontSize)spx;
				}
			''' % {'fontSize': fontSize, 'fontWidgets': fontWidgets}
		widget.setStyleSheet(css)

class QDialog(QDialog):
	def __init__(self, *args, **kwargs):
		super(QDialog, self).__init__(*args, **kwargs)
		uiRefresh(self)

class QGridLayout(QGridLayout):
	def __init__(self, *args, **kwargs):
		super(QGridLayout, self).__init__(*args, **kwargs)
		if system() == 'Darwin':
			self.setVerticalSpacing(MAC_VSPACING)
			self.setContentsMargins(10,MAC_VMARGIN,10,MAC_VMARGIN)

class QHBoxLayout(QHBoxLayout):
	def __init__(self, *args, **kwargs):
		super(QHBoxLayout, self).__init__(*args, **kwargs)
		if system() == 'Darwin':
			self.setSpacing(MAC_VSPACING)
			self.setContentsMargins(10,MAC_VMARGIN,10,MAC_VMARGIN)

class QVBoxLayout(QVBoxLayout):
	def __init__(self, *args, **kwargs):
		super(QVBoxLayout, self).__init__(*args, **kwargs)
		if system() == 'Darwin':
			self.setSpacing(MAC_VSPACING)
			self.setContentsMargins(10,MAC_VMARGIN,10,MAC_VMARGIN)
