#FLM: TR: Import Glyph
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
from typerig.proxy.tr.objects.layer import trLayer
from typerig.core.objects.glyph import Glyph

# - Init ---------------------------------
__version__ = '0.1.1'
app_name = 'TR | Import TR Glyph'
file_ext = '.trglyph'

# - Functions ----------------------------
def import_active_glyph():
	# - Get current glyph
	current_glyph = fl6.CurrentGlyph()

	if current_glyph is None:
		QMessageBox.warning(None, app_name, 'No active glyph! Please open a glyph first.')
		return

	# - Get file path from user
	load_path = QFileDialog.getOpenFileName(
		None,
		'{} | Open'.format(app_name),
		'',
		'TypeRig Glyph (*{});;All Files (*)'.format(file_ext)
	)

	if not load_path:
		return

	# - Read file
	try:
		with open(load_path, 'r', encoding='utf-8') as f:
			xml_string = f.read()

	except Exception as e:
		QMessageBox.critical(None, app_name, 'Could not read file!\n{}'.format(str(e)))
		return

	# - Deserialize from XML
	try:
		core_glyph = Glyph.from_XML(xml_string)

	except Exception as e:
		QMessageBox.critical(None, app_name, 'Failed to parse glyph XML!\n{}'.format(str(e)))
		return

	# - Wrap active glyph in proxy
	tr_glyph = trGlyph(current_glyph)

	# - Mount each imported layer onto matching FL layer
	imported_count = 0
	created_count = 0

	for core_layer in core_glyph.layers:
		# - Find existing FL layer by name
		fl_layer_proxy = tr_glyph.find_layer(core_layer.name)

		# - Create missing layer
		if fl_layer_proxy is None:
			fl_layer_proxy = tr_glyph.add_layer(core_layer.name)
			created_count += 1
			print('NEW:\t{} | Created layer: {}'.format(app_name, core_layer.name))

		# - Mount core layer data into FL layer
		try:
			fl_layer_proxy.mount(core_layer)
			imported_count += 1

		except Exception as e:
			print('ERROR:\t{} | Failed to mount layer {}: {}'.format(app_name, core_layer.name, str(e)))

	# - Notify FL of changes
	tr_glyph.update()

	glyph_name = core_glyph.name or 'untitled'
	print('DONE:\t{} | Imported: {} ({} layers, {} new) <- {}'.format(app_name, glyph_name, imported_count, created_count, load_path))

# - Run ----------------------------------
import_active_glyph()
