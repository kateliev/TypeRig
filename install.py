# SCR : Typerig Installer
# VER : 0.02
# -------------------------
# www.typerig.com

# Note:
# Adapted from the installer of RoboFab Library by Tal Leming, Erik van Blokland, Just van Rossum 
# RoboFab Copyright (c) 2003-2013 | http://robofab.org

# - Dependencies --------------------------
from __future__ import print_function
from distutils.sysconfig import get_python_lib
import os, sys

# - Init
moduleName = 'typerig'
moduleSubPath = 'Lib'

# - String
tr_head =
r'''
 ___ ___ ____
|   |   |   /\   TypeRig
|___|___|__/__\  
    |   | /   /  (C) Font development kit for FontLab 6 & 7
    |___|/___/   (C) Vassil Kateliev, 2017-2020 (http://www.kateliev.com)
    |   |\   \   
    |___| \___\  www.typerig.com 

'''

# - Functions --------------------------
def installModule(srcDir, modulePathName):
	sitePackDir = get_python_lib()
	fileName = os.path.join(sitePackDir, '%s.pth' %modulePathName)
	
	print(tr_head)
	print('\nINFO:\t Installing TypeRig library...\nPATH:\t%r\nFILE:\t%r\n\n' %(srcDir, fileName))

	file = open(fileName, 'w')
	file.write(srcDir)
	file.close()

	return fileName

# - Run --------------------------
intallDir = os.path.join(os.path.dirname(os.path.normpath(os.path.abspath(sys.argv[0]))), moduleSubPath)

fileName = installModule(intallDir, moduleName)

print('DONE:\tTypeRig installed!\nNOTE:\tRun script again if you change the location of the library')
