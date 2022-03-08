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
	margin: 5 10 5 10;
    padding: 0 0 2 0;
    background: none;
    border: none;
    font-size: 8pt;
    color: rgb(130, 130, 130);
    border-radius: 3px;
}

QPushButton:hover {
	background-color: white;
}

QPushButton:pressed,
QPushButton:checked {
    background-color: gray;
    border: 1px solid gray;
    color: black;
}
'''

# -- Icons and UI ---------------------------------------
def FLIcon(icon_path, icon_size):
	new_label = QtGui.QLabel()
	new_label.setPixmap(QtGui.QIcon(icon_path).pixmap(icon_size))
	return new_label

def FLPushButton(button_text, icon_path, icon_size=32):
	new_button = QtGui.QPushButton(button_text)
	new_button.setStyleSheet(css_fl_button)

	if len(icon_path):
		new_button.setIcon(QtGui.QIcon(icon_path))
		new_button.setIconSize(QtCore.QSize(icon_size,icon_size))
	return new_button