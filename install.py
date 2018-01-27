# SCR : Typerig Installer
# VER : 0.01
# -------------------------
# www.typerig.com

# Note:
# Adapted from the installer of RoboFab Library by Tal Leming, Erik van Blokland, Just van Rossum 
# RoboFab Copyright (c) 2003-2013 | http://robofab.org

# - Dependencies --------------------------
from distutils.sysconfig import get_python_lib
import os, sys

# - Init
moduleName = 'typerig'
moduleSubPath = 'Lib'

# - Functions --------------------------
def installModule(srcDir, modulePathName):
	sitePackDir = get_python_lib()
	fileName = os.path.join(sitePackDir, '%s.pth' %modulePathName)
	
	print '\nINFO:\t Installing TypeRig library...\nPATH:\t%r\nFILE:\t%r\n\n' %(srcDir, fileName)

	file = open(fileName, 'w')
	file.write(srcDir)
	file.close()

	return fileName

# - Run --------------------------
intallDir = os.path.join(os.path.dirname(os.path.normpath(os.path.abspath(sys.argv[0]))), moduleSubPath)

fileName = installModule(intallDir, moduleName)

print 'DONE:\tTypeRig installed!\nNOTE:\tRun script again if you change the location of the library'
