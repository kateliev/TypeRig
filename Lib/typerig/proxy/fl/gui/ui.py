# MODULE: Typerig / GUI / UI
# NOTE: Fontlab specific user interface elements
# ----------------------------------------
# (C) Vassil Kateliev, 2021-2022
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.0.1'

# - Dependancies -----------------------
import fontlab as fl6

from PythonQt import QtCore
from typerig.proxy.fl.gui import QtGui

# -- CSS Styling
css_fl_button = '''
QPushButton {
	background: white;
	/* border-radius: 3px; */
	border: 1px solid #c8c8c8;
	color: black;
	font-size: 8pt;
	margin: 2px 1px 2px 1px;
	min-height: 15px;
	padding: 2px 5px 2px 5px; 
}

QPushButton:hover,
QPushButton:focus{
	border-color: #1389ec;
	background-color: white;
}

QPushButton:pressed,
QPushButton:checked {
	background-color: #1389ec;
	border: 1px solid #90ceff;
	color: white;
}
'''

# -- Icons and UI ---------------------------------------
def FLIcon(icon_path, icon_size):
	new_label = QtGui.QLabel()
	new_label.setPixmap(QtGui.QIcon(icon_path).pixmap(icon_size))
	return new_label

def FLPushButton(button_text, icon_path, icon_size=32):
	new_button = QtGui.QPushButton(button_text)
	#new_button.setStyleSheet(css_fl_button)

	if len(icon_path):
		new_button.setIcon(QtGui.QIcon(icon_path))
		new_button.setIconSize(QtCore.QSize(icon_size,icon_size))
	return new_button