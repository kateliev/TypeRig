# MODULE: Typerig / GUI / QtGui
# NOTE: Application and OS specific GUI compatibility module
# ----------------------------------------
# (C) Adam Twardoch, 2019-2021
# (C) Vassil Kateliev, 2021-2022
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.1.0'

# - Keep compatibility for basestring checks
try:
	basestring
except NameError:
	basestring = (str, bytes)

# - Dependancies -----------------------
import fontlab as fl6

from PythonQt.QtGui import *
from PythonQt.QtCore import QSize
from platform import system

# - Init --------------------------------
MAC_VSPACING = 2
MAC_VMARGIN = 2

fl_runtime_platform = system()
fl_app = fl6.flWorkspace.instance()
fl_app_version = fl_app.mainWindow.windowTitle

# - Functions ----------------------------
def uiRefresh(widget):
	# - Init
	desktopHeight = QDesktopWidget().height
	fontSize = 10
	css_template = '' 
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
		QTableWidget,
		QTreeWidget,
		QFrame
	'''

	# - Set OS specific styling
	if fl_runtime_platform == 'Darwin':
		
		# - Init
		css_template = '''
			%(fontWidgets)s { 
				font-size: %(fontSize)spx;
			}
		''' 
		# - Set Styling
		if desktopHeight >= 1050:
			fontSize = 11
			css = css_template %{'fontSize': fontSize, 'fontWidgets': fontWidgets}
			
		elif desktopHeight <= 768:
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

				QToolButton {
					border: none;
					font-weight: bold;
					vertical-align: middle
					padding: 2px 3px 2px 3px; 
					margin: 2px 1px 2px 1px;
					min-height: 14px;
				}

			''' % {'fontSize': fontSize, 'fontWidgets': fontWidgets}
		
		else:
			css = css_template %{'fontSize': fontSize, 'fontWidgets': fontWidgets}

		widget.setStyleSheet(css)

	# - Set FL version specific styling
	# !!! Fix some FL8 specific problems on Windows platform until resolved
	if '8' in fl_app_version:
		if fl_runtime_platform == 'Windows':
			fontSize = 11
			css = '''
				%(fontWidgets)s { 
					font-size: %(fontSize)spx;
				}

				QPushButton { 
					padding: 2px 3px 2px 3px; 
					margin: 2px 1px 2px 1px;
					border-style: solid;
					border-color: #c8c8c8;
					border-radius: 3px;
					border-width: 1px;
					min-height: 14px;
				}

				QPushButton:pressed { 
					background-color: #1389ec;
					border-color: #90ceff;
					color: white;
				}

				QPushButton:checked{
					background-color: #1389ec;
					border-color: #1389ec;
					color: white;
				}

				QToolButton {
					border: none;
					font-weight: bold;
					vertical-align: middle
					padding: 2px 3px 2px 3px; 
					margin: 2px 1px 2px 1px;
					min-height: 14px;
				}
				
			''' % {'fontSize': fontSize, 'fontWidgets': fontWidgets}

			widget.setStyleSheet(css)

# -- Icons and UI ---------------------------------------
def FLIcon(icon_path, icon_size):
	new_label = QLabel()
	new_label.setPixmap(QIcon(icon_path).pixmap(icon_size))
	return new_label

def FLPushButton(button_text, icon_path, icon_size=32):
	new_button = QPushButton(button_text)
	if len(icon_path):
		new_button.setIcon(QIcon(icon_path))
		new_button.setIconSize(QSize(icon_size,icon_size))
	return new_button

# - Qt Classes -----------------------------------
class QDialog(QDialog):
	def __init__(self, *args, **kwargs):
		super(QDialog, self).__init__(*args, **kwargs)
		uiRefresh(self)

class QWidget(QWidget):
	def __init__(self, *args, **kwargs):
		super(QWidget, self).__init__(*args, **kwargs)
		uiRefresh(self)

class QFrame(QFrame):
	def __init__(self, *args, **kwargs):
		super(QFrame, self).__init__(*args, **kwargs)
		uiRefresh(self)

class QGridLayout(QGridLayout):
	def __init__(self, *args, **kwargs):
		super(QGridLayout, self).__init__(*args, **kwargs)

		if fl_runtime_platform == 'Darwin':
			self.setVerticalSpacing(MAC_VSPACING)
			self.setContentsMargins(10, MAC_VMARGIN, 10, MAC_VMARGIN)

class QHBoxLayout(QHBoxLayout):
	def __init__(self, *args, **kwargs):
		super(QHBoxLayout, self).__init__(*args, **kwargs)

		if fl_runtime_platform == 'Darwin':
			self.setSpacing(MAC_VSPACING)
			self.setContentsMargins(10, MAC_VMARGIN , 10, MAC_VMARGIN)

class QVBoxLayout(QVBoxLayout):
	def __init__(self, *args, **kwargs):
		super(QVBoxLayout, self).__init__(*args, **kwargs)

		if fl_runtime_platform == 'Darwin':
			self.setSpacing(MAC_VSPACING)
			self.setContentsMargins(10, MAC_VMARGIN, 10, MAC_VMARGIN)