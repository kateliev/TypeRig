# MODULE: Sci | Typerig
# VER 	: 0.01
# ----------------------------------------
# (C) Vassil Kateliev, 2018  (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# NOTE:
# A SciPy, NumPy dependent module for various math and science related functions.

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
#import math
#import numpy as np
#import scipy as sp

# - Functions -------------------------------------------------
# -- Interpolation  -------------------------------------------
def lerp1d(dataDict):
	'''1D Interpolation
	Args:
		data dict(location(int): typerig.brain.coordArray): A data container of all coordinate values to be interpolated.
	Returns:
		function(time): A one dimensional interpolation function of time. 
	'''
	from scipy.interpolate import interp1d
	from typerig.brain import coordArray

	data = zip(*[dataDict[key].flatten() for key in sorted(dataDict.keys())])

	lerp = interp1d(sorted(dataDict.keys()), data, bounds_error=False, fill_value='extrapolate')
	return lambda time: coordArray(lerp(time))
	