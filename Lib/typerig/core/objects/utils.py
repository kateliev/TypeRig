# MODULE: TypeRig / Core / Utilities (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2017-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!


# - Dependencies ---------------------
from __future__ import absolute_import, print_function, division

# - Init -----------------------------
__version__ = '0.26.0'

# - Classes --------------------------
class fontFamilly():
	'''Font familly class:
	*   generates weight stems [.wt_stems] and MM weight instances [.wt_instances]
		using given masters/layers wt0, wt1, and number of weight members [wt_steps].
		Uses geometric growth (progression) algorithm to determine stem weight

	*   generates MM width instances [.wd_instances] using given number
		of width members [wd_steps]. Uses linear growth.

	*   generates all MM isntaces/vectors for instance generation [.instances]
	---
	ex: fontFamilyName = fontFamilly(wt0 = 56, wt1 = 178, wt_steps = 7, wd_steps = 3)
	'''

	def __init__(self, **kwargs):
		# - Input
		self.wt0 = kwargs.get('wt0', 1)
		self.wt1 = kwargs.get('wt1', 2)
		self.wt_steps = kwargs.get('wt_steps', 2)
		self.wd_steps = kwargs.get('wd_steps', 2)

		# - Calculate on init
		self.update()

	def update(self):
		from math import sqrt
		from typerig.brain import linspread, geospread, ratfrac

		self.wt_stems =  [int(round(item)) for item in geospread(self.wt0, self.wt1, self.wt_steps)]
		self.wt_instances = [int(ratfrac(item - self.wt0, self.wt1 - self.wt0, 1000)) for item in self.wt_stems]
		self.wd_instances = []
		
		if self.wd_steps >= 2:
			from itertools import product

			self.wd_instances = [int(item) for item in list(linspread(0,1000, self.wd_steps))]
			self.instances = list(product(self.wt_instances, self.wd_instances))
		else:
			self.instances = self.wt_instances

class linAxis(object):
	'''A linear series axis instance and stem calculator

	Usage linAxis(masterDict, instanceCount), where:
	*	masterDict = {min_axis_value:min_stem_width, max_axis_value:max_stem_width} ex: {0:50, 1000:750}
	*	instanceCount = number of instances to be calculated
	'''
	def __init__(self, masterDict, instanceCount):
		self.steps = instanceCount
		self.masters = masterDict

		self.update()			

	def update(self):
		from typerig.brain import linspread, geospread, ratfrac

		minAxisStem, maxAxisStem = min(self.masters.values()), max(self.masters.values())
		minAxisPos, maxAxisPos = min(self.masters.keys()), max(self.masters.keys())
		
		self.stems = [int(round(item)) for item in list(linspread(self.masters[minAxisPos], self.masters[maxAxisPos], self.steps))]
		self.data = { int(ratfrac(stem - minAxisPos, maxAxisStem - minAxisPos, max(self.masters.keys()))):stem for stem in self.stems}
		self.instances = sorted(self.data.keys())

class geoAxis(object):
	'''A geometric series axis instance and stem calculator

	Usage linAxis(masterDict, instanceCount), where:
	*   masterDict = {min_axis_value:min_stem_width, max_axis_value:max_stem_width} ex: {0:50, 1000:750}
	*   instanceCount = number of instances to be calculated
	'''
	def __init__(self, masterDict, instanceCount):
		self.steps = instanceCount
		self.masters = masterDict

		self.update()           

	def update(self):
		from typerig.brain import linspread, geospread, ratfrac

		minAxisStem, maxAxisStem = min(self.masters.values()), max(self.masters.values())
		minAxisPos, maxAxisPos = min(self.masters.keys()), max(self.masters.keys())
		
		self.stems = [int(round(item)) for item in list(geospread(self.masters[minAxisPos], self.masters[maxAxisPos], self.steps))]
		self.data = { int(ratfrac(stem - minAxisPos, maxAxisStem - minAxisPos, max(self.masters.keys()))):stem for stem in self.stems}
		self.instances = sorted(self.data.keys())
					
# - Bounding box object ----------------------------------
class bounds(object):
	def __init__(self, tupleList):
		self.x, self.xmax = 0, 0
		self.y, self.ymax = 0, 0
		self.width, self.height = 0, 0
		self.refresh(tupleList)

	def recalc(self, tupleList):
		from operator import itemgetter
		min_x_tup = min(tupleList,key=itemgetter(0))
		min_y_tup = min(tupleList,key=itemgetter(1))
		max_x_tup = max(tupleList,key=itemgetter(0))
		max_y_tup = max(tupleList,key=itemgetter(1))
		return (min_x_tup, min_y_tup, max_x_tup, max_y_tup)

	def refresh(self, tupleList):
		min_x_tup, min_y_tup, max_x_tup, max_y_tup = self.recalc(tupleList)
		self.x = min_x_tup[0]
		self.y = min_y_tup[1]
		self.xmax = max_x_tup[0]
		self.ymax = max_y_tup[1]
		self.width = abs(self.xmax - self.x)
		self.height = abs(self.ymax - self.y)