#FLM: TR: Export Glyph
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import print_function
import os

import fontlab as fl6
import PythonQt as pqt

from PythonQt.QtCore import Qt
from PythonQt.QtGui import QFileDialog, QMessageBox

from typerig.proxy.tr.objects.glyph import trGlyph

# - Init ---------------------------------
__version__ = '0.1.0'
app_name = 'TR | Export TR Glyph'
file_ext = '.trglyph'
xml_header = '<?xml version="1.0" encoding="UTF-8"?>\n'

# - Functions ----------------------------
def export_active_glyph():
	# - Get current glyph
	current_glyph = fl6.CurrentGlyph()

	if current_glyph is None:
		QMessageBox.warning(None, app_name, 'No active glyph! Please open a glyph first.')
		return

	# - Wrap in proxy and eject to pure core object
	tr_glyph = trGlyph(current_glyph)
	core_glyph = tr_glyph.eject()

	# - Serialize to XML
	xml_string = xml_header + core_glyph.to_XML()

	# - Build default filename
	glyph_name = core_glyph.name or 'untitled'
	default_name = glyph_name + file_ext

	# - Get save path from user
	save_path = QFileDialog.getSaveFileName(
		None,
		'{} | Save {}'.format(app_name, glyph_name),
		default_name,
		'TypeRig Glyph (*{});;All Files (*)'.format(file_ext)
	)

	if not save_path:
		return

	# - Ensure proper extension
	if not save_path.endswith(file_ext):
		save_path += file_ext

	# - Write file
	try:
		with open(save_path, 'w', encoding='utf-8') as f:
			f.write(xml_string)

		print('DONE:\t{} | Exported: {} -> {}'.format(app_name, glyph_name, save_path))

	except Exception as e:
		QMessageBox.critical(None, app_name, 'Export failed!\n{}'.format(str(e)))

# - Run ----------------------------------
export_active_glyph()
