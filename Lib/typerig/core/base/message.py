# MODULE: Typerig / Base / Messages (Objects)
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2020 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import os, warnings

# - Init -----------------------------
__version__ = '0.0.2'

# - Strings --------------------------
output_types = ['DONE', 'WARN', 'ERROR', 'ABORT', 'ADD', 'DEL', 'LOAD', 'SAVE', 'IMPORT', 'EXPORT']

# - Functions ------------------------
def output(msg_type, app_name, message):
	print('%s:\t%s | %s'%(output_types[msg_type], app_name, message))

def warning_custom(message, category, filename, lineno, file=None, line=None):
	return 'WARN:\t%s: %s: %s\n' %(os.path.split(filename)[1], category.__name__, message)

# - Warnings -------------------------
# -- Font related --------------------
class NodeWarning(UserWarning):
	pass

class ContourWarning(UserWarning):
	pass

class LayerWarning(UserWarning):
	pass

class GlyphWarning(UserWarning):
	pass

class FontWarning(UserWarning):
	pass

# -- IO Related ---------------------
class FileSaveWarning(UserWarning):
	pass

class FileOpenWarning(UserWarning):
	pass

class FileImportWarning(UserWarning):
	pass

class JSONimportWarning(UserWarning):
	pass

class TXTimportWarning(UserWarning):
	pass

class VFJimportWarning(UserWarning):
	pass

class SVGimportWarning(UserWarning):
	pass

class NAMimportWarning(UserWarning):
	pass

class NAMdataMissing(UserWarning):
	pass

# -- Panel Warning -----------------
class TRPanelWarning(UserWarning):
	pass

# - Setup ----------------------------
warnings.formatwarning = warning_custom

