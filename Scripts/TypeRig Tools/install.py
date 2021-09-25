#FLM: TypeRig: Installer
# -------------------------------------------------------------------------
#  ___ ___ ____
# |   |   |   /\   TypeRig
# |___|___|__/__\  
#     |   | /   /  (C) Font development kit for FontLab
#     |___|/___/   (C) Vassil Kateliev, 2017-2021 (http://www.kateliev.com)
#     |   |\   \   
#     |___| \___\  www.typerig.com 
# 
# -------------------------------------------------------------------------
# (C) Vassil Kateliev, 2021  (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#--------------------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import print_function

import os
import sys

from distutils.sysconfig import get_python_lib

from PythonQt import QtCore, QtGui

# - Init --------------------------------
app_name, app_version = 'TR | Module Installer', '1.1'

# - String ------------------------------
str_manual_label = '''Attempt manual installation via *.pth link.
This installer will generate a *.pth file containing a link pointing to your current TypeRig library folder.
Please save the generated file in a folder of your choosing and then copy it to the python installation path shown below in the Information field.
'''

str_auto_pth_label = '''Attempt automatic installation. 
Please note that if both automatic options fail due to OS security reasons (access denied) you should use the manual installer below.

Dynamic installation via link: This option will generate a special *.pth file containing a link pointing to your current TypeRig library folder and copy it into your FontLab Python folder. 
This is the best option if you want to keep your TypeRig folder outside your FontLab installation and sync it regularly to the TypeRig GitHub repository. Regular updates will not require running the installer again, unless you move the TypeRig folder.'''

str_auto_copy_label = '''Static installation via copy: This option will copy all the necessary files from TypeRig library folder into into your FontLab Python folder. Best if you are not planning to update TypeRig from GitHub repository. For each update/sync to GitHub repo you will need to run this script again.'''

str_auto_copy_label
# - Config ------------------------------
moduleName = 'typerig'
moduleSubPath = 'Lib'
file_ext = '.pth'

# - Functions --------------------------
def installModule(srcDir, modulePathName):
	sitePackDir = get_python_lib()
	fileName = os.path.join(sitePackDir, '%s%s' %(modulePathName, file_ext))
	
	print(tr_head)
	print('\nINFO:\t Installing TypeRig library...\nPATH:\t%r\nFILE:\t%r\n\n' %(srcDir, fileName))

	file = open(fileName, 'w')
	file.write(srcDir)
	file.close()

	return fileName

# - Widgets ---------------------
class dlg_install(QtGui.QDialog):
	def __init__(self):
		super(dlg_install, self).__init__()
	
		# - Labels
		self.lbl_auto_pth = QtGui.QLabel(str_auto_pth_label)
		self.lbl_auto_pth.setWordWrap(True) 
		self.lbl_auto_copy = QtGui.QLabel(str_auto_copy_label)
		self.lbl_auto_copy.setWordWrap(True)
		self.lbl_manual = QtGui.QLabel(str_manual_label)
		self.lbl_manual.setWordWrap(True) 

		# - Init
		self.python_folder = get_python_lib()
		
		# - Group box
		self.box_auto = QtGui.QGroupBox('Automatic')
		self.box_manual = QtGui.QGroupBox('Manual')
		self.box_info = QtGui.QGroupBox('Information')

		# - Edit
		self.edt_python_path = QtGui.QLineEdit()
		self.edt_python_path.setText(self.python_folder)
		
		# - Buttons 
		self.btn_install_auto_pth = QtGui.QPushButton('Auto Install via link')
		self.btn_install_auto_copy = QtGui.QPushButton('Auto Install via copy')
		self.btn_install_manual_pth = QtGui.QPushButton('Manual Install via link')

				
		# - Build layouts 
		# -- Auto install 
		layout_auto = QtGui.QVBoxLayout() 
		layout_auto.addWidget(self.lbl_auto_pth)
		layout_auto.addWidget(self.btn_install_auto_pth)
		layout_auto.addWidget(self.lbl_auto_copy)
		layout_auto.addWidget(self.btn_install_auto_copy)
		self.box_auto.setLayout(layout_auto)
		
		# -- Manual install 
		layout_manual = QtGui.QVBoxLayout() 
		layout_manual.addWidget(self.lbl_manual)
		layout_manual.addWidget(self.btn_install_manual_pth)
		self.box_manual.setLayout(layout_manual)

		# -- Info box
		layout_info = QtGui.QVBoxLayout() 
		layout_info.addWidget(QtGui.QLabel('FontLab Python installation path:'))
		layout_info.addWidget(self.edt_python_path)
		self.box_info.setLayout(layout_info)

		
		# -- Main
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(self.box_auto)
		layout_main.addWidget(self.box_manual)
		layout_main.addWidget(self.box_info)

		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 300, 200)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
		self.show()

# - RUN ------------------------------
dialog = dlg_install()