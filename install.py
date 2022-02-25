# TypeRig: Installer
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

# - Dependencies --------------------------
from __future__ import print_function

import os
import site
import sys
import sysconfig

# - String
tr_head = r'''
 ___ ___ ____
|   |   |   /\   TypeRig
|___|___|__/__\  
    |   | /   /  (C) Font development kit for FontLab 6, 7 and 8
    |___|/___/   (C) Vassil Kateliev, 2017-2022 (http://www.kateliev.com)
    |   |\   \   
    |___| \___\  www.typerig.com 

'''

# - Config
module_name = 'typerig'
module_path = 'Lib'
file_ext = '.pth'

current_folder = os.path.dirname(__file__)
libary_folder = os.path.normpath(os.path.join(current_folder, module_path))
python_folder = site.USER_SITE
if python_folder is None: python_folder = sysconfig.get_paths()['purelib']

# - Functions -----------------------
def copy_tree(path_source, path_destination):
	# - Make sure the destination folder does not exist.
	if os.path.exists(path_destination) and os.path.isdir(path_destination):
		print('Destination path already present! Removing existing tree: {}'.format(path_destination))
		shutil.rmtree(path_destination, ignore_errors=False)

	# - Process
	shutil.copytree(path_source, path_destination)

def install_auto_copy():
	copy_tree(os.path.join(libary_folder, module_name), os.path.join(python_folder, module_name))
	print('DONE:\tTypeRig installed in: %s' %python_folder)

def install_auto_pth():
	if not os.path.exists(python_folder):
		os.makedirs(python_folder)

	pth_file_name = os.path.join(python_folder, '%s%s' %(module_name, file_ext))

	with open(pth_file_name, 'w') as pth_file:
		pth_file.write(libary_folder)

	print('DONE:\tTypeRig installed!\nNOTE:\tRun script again if you change the location of the library')

# - Install
print(tr_head)
install_auto_pth()