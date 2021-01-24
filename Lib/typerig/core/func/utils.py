# MODULE: TypeRig / Core / Utility (Functions)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division, unicode_literals
import math, random

# - Init --------------------------------
__version__ = '0.26.3'

# -- Units ----------------------------------------------------------------------
def getFunctionName():
	'''Return the name of current function (def)'''
	from inspect import stack
	return stack()[1][3]

def point2pixel(points):
	return points*1.333333

def pixel2point(pixels):
	return pixels*0.75

def inch2point(inches):
	return inches*71.999999999999

def point2inch(points):
	return points*0.013888888888889

def isMultiInstance(objects, types):
	return all([isinstance(obj, types) for obj in objects])