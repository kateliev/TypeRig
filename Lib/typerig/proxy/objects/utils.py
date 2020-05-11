 # MODULE: Typerig / Proxy / Misc Utils
# ------------------------------------------------------
# (C) Vassil Kateliev, 2017 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 	(http://www.karandash.eu)
#--------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from collections import defaultdict

# - Init ---------------------------------
__version__ = '0.2.3'

# - Functions ---------------------------------------------------------
def getFunctionName():
	'''Return the name of current function (def)'''
	from inspect import stack
	return stack()[1][3]

# - Classes -------------------------------------------------------
# -- Legacy FL5 related ------------------------------------------------
class fontClassesFromFile(object):
	'''Loads a Fontlab class file (.flc) and parses it. 
	Args:
		fileName (str) : a path to Fontlab class file
	Returns:
		Object with methods:
			.fontClasses (dict -> class_name:class_contents)
			.metricClasses (dict -> class_name:class_contents)
			.kernClasses (dict -> class_name:class_contents)
			.otClasses (dict -> class_name:class_contents)
			.classPosition (Left and/or Right pair(s)); Metric (Left, Width, Right)
			.classLeader (dict -> class_name:class_leader)
	
		'''
	def __init__(self, fileName):       
		# - Init
		self.fontClasses, self.metricClasses, self.kernClasses, self.otClasses, self.classPosition, self.classLeader = {}, {}, {}, {}, {}, {}

		# - Parse file
		# -- Fontlab class file internal commands
		cBegin = '%%CLASS'
		cGlyphs = '%%GLYPHS'
		cKern = '%%KERNING'
		cMetric = '%%METRICS'
		cEnd = '%%END'

		with open(fileName) as classData:
			className, classGlyphs, classPos = '', '', ''
			 
			for line in classData:
				if cBegin in line: 
					className = line.replace(cBegin, '').strip()
					
				if cGlyphs in line:
					classGlyphs = [item for item in line.replace(cGlyphs, '').strip().split(' ') if len(item)]
					self.fontClasses[className] = classGlyphs

				if cKern in line: 
					classPos = line.replace(cKern, '').strip()
					self.classPosition[className] = classPos[:-1].strip() if len(classPos) else None

				if cMetric in line: 
					classPos = line.replace(cMetric, '').strip()
					self.classPosition[className] = classPos[:-1].strip() if len(classPos) else None
			
				if cEnd in line: 
					pass
					
		# - Finish 
		for key, value in self.fontClasses.iteritems():
			findLeader = [item for item in value if "'" in item]
			self.classLeader[key] = findLeader[0].replace("'", '') if len(findLeader) else value[0]

			if key[0] is '.':
				self.metricClasses[key] = value
			elif key[0] is '_':
				self.kernClasses[key] = value
			else:
				self.otClasses[key] = value
				del self.classLeader[key]