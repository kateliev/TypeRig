#FLM: Kern: Uppercase kerning to lowercase
# VER: 1.5
#----------------------------------
# Foundry:  The FontMaker
# Typeface: Bolyar Sans
# Date:     25.01.2019
#----------------------------------

# - Dependancies
import os,json
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

import typerig.proxy as proxy
from typerig.utils import getLowercaseCodepoint, getUppercaseCodepoint

# - Strings --------------------------
fileFormats = ['TypeRig JSON Raw Classes (*.json)', 'FontLab VI JSON Classes (*.json)']

# - Functions ------------------------
def json_class_dumb_decoder(jsonData):
	retund_dict = {}
	pos_dict = {(True, False):'KernLeft', (False, True):'KernRight', (True, True):'KernBothSide'}
	getPos = lambda d: (d['1st'] if d.has_key('1st') else False , d['2nd'] if d.has_key('2nd') else False)

	if len(jsonData.keys()):
		if jsonData.has_key('masters') and len(jsonData['masters']):
			for master in jsonData['masters']:
				if len(master.keys()):
					if master.has_key('kerningClasses') and len(master['kerningClasses']):
						temp_dict = {}

						for group in master['kerningClasses']:
							if group.has_key('names'):
								temp_dict[group['name']] = (group['names'], pos_dict[getPos(group)])

						retund_dict[master['name']] = temp_dict
	return retund_dict


class load_classes(QtGui.QDialog):
	def __init__(self, font):
			super(load_classes, self).__init__()
			self.setWindowTitle('Load Classes')
			self.setGeometry(300, 300, 250, 250)
			self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
			self.classes = self.classes_fromFile(font)		
			self.close()
	
	def classes_fromFile(self, font):
			fontPath = os.path.split(font.fg.path)[0]
			fname = QtGui.QFileDialog.getOpenFileName(self, 'Load kerning classes from file', fontPath, ';;'.join(fileFormats))
			
			if fname != None:
				with open(fname, 'r') as importFile:
					source_data = json.load(importFile)

					if source_data.has_key('masters'): # A Fontlab JSON Class kerning file
						source_data = json_class_dumb_decoder(source_data)

					return source_data

# - Init -----------------------------
font = proxy.pFont()
g = proxy.pGlyph()
ws = proxy.pWorkspace()
transform = (getLowercaseCodepoint, getUppercaseCodepoint)

load_dlg = load_classes(font)
font_kerning = {layer:proxy.pKerning(font.kerning(layer), load_dlg.classes[layer]) for layer in font.masters()}

# - This will effectively copy all of the UC:UC kerning pairs to LC:LC, UC:LC, LC:UC 
# - For Bolyar Sans project
for layer, kerning in font_kerning.iteritems():
	kerning_LC2LC = kerning.getKerningForLeaders(transform[0], transform[0])
	kerning_UC2LC = kerning.getKerningForLeaders(None, transform[0])
	kerning_LC2UC = kerning.getKerningForLeaders(transform[0], None)
	pri kerning_UC2LC

	kerning.fg.setPlainPairs(kerning_LC2LC + kerning_UC2LC + kerning_LC2UC)
	
	print 'DONE: Kerning transformation for layer: %s' %layer


# - Finish ---------------------------
print 'INIT:\tKern Playground >> %s !' %font.name