#FLM: TR: Font IO
# NOTE: Test tool for .trfont write/read round-trip from FontLab
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Run from FontLab's scripting window:
#   exec(open('/path/to/trfont_tool.py').read())

# - Dependencies -------------------------
from __future__ import print_function
import os

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui

from typerig.proxy.tr.objects.font import trFontProxy
from typerig.core.fileio.trfont import TrFontIO

# - Init ---------------------------------
__version__ = '0.1.0'
_tool_name  = 'trFont Export / Import'

# ================================================
# Dialog
# ================================================
class TrFontTool(QtGui.QDialog):
	'''Minimal export/import dialog for the .trfont format.

	Export section:
		- checkboxes for each font property component
		- radio buttons: all glyphs vs. selected glyphs
		- path picker → writes .trfont folder

	Import section:
		- path picker → reads .trfont folder, prints summary
	'''

	def __init__(self, parent=None):
		super(TrFontTool, self).__init__(parent)
		self.setWindowTitle(_tool_name)
		self.setMinimumWidth(340)
		self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
		self._build_ui()

	# -- UI construction --------------------------------
	def _build_ui(self):
		root = QtGui.QVBoxLayout(self)
		root.setSpacing(6)
		root.setContentsMargins(10, 10, 10, 10)

		# ---- Export section ----------------------------
		root.addWidget(self._section_label('Export'))

		# Font components — only encoding + axes are wired;
		# the rest are stubs and unchecked by default
		self._chk = {}

		comp_layout = QtGui.QGridLayout()
		comp_layout.setSpacing(4)

		components = [
			# (key,          label,            checked, note)
			('info',         'Font Info',       True,   ''),
			('metrics',      'Metrics',         True,   ''),
			('axes',         'Axes / Masters',  True,   ''),
			('encoding',     'Encoding',        True,   ''),
			('kerning',      'Kerning',         False,  '(not yet bridged)'),
			('features',     'Features',        False,  '(not yet bridged)'),
			('groups',       'Groups',          False,  '(not yet bridged)'),
		]

		for row, (key, label, checked, note) in enumerate(components):
			chk = QtGui.QCheckBox(label)
			chk.setChecked(checked)
			self._chk[key] = chk
			comp_layout.addWidget(chk, row, 0)

			if note:
				note_lbl = QtGui.QLabel(note)
				note_lbl.setStyleSheet('color: #888; font-size: 10px;')
				comp_layout.addWidget(note_lbl, row, 1)

		root.addLayout(comp_layout)

		root.addSpacing(4)
		root.addWidget(self._hr())

		# Glyph scope
		root.addWidget(self._section_label('Glyphs'))
		self._rad_all      = QtGui.QRadioButton('All glyphs')
		self._rad_selected = QtGui.QRadioButton('Selected glyphs only')
		self._rad_all.setChecked(True)
		root.addWidget(self._rad_all)
		root.addWidget(self._rad_selected)

		root.addSpacing(4)
		root.addWidget(self._hr())

		# Export path + button
		root.addWidget(self._section_label('Write path'))

		exp_path_row = QtGui.QHBoxLayout()
		self._edt_export = QtGui.QLineEdit()
		self._edt_export.setPlaceholderText('Click Browse…')
		self._edt_export.setReadOnly(True)
		btn_browse_exp = QtGui.QPushButton('Browse…')
		btn_browse_exp.setFixedWidth(70)
		btn_browse_exp.clicked.connect(self._browse_export)
		exp_path_row.addWidget(self._edt_export)
		exp_path_row.addWidget(btn_browse_exp)
		root.addLayout(exp_path_row)

		btn_export = QtGui.QPushButton('Export .trfont')
		btn_export.clicked.connect(self._do_export)
		root.addWidget(btn_export)

		root.addSpacing(6)
		root.addWidget(self._hr())

		# Import section
		root.addWidget(self._section_label('Load path'))

		imp_path_row = QtGui.QHBoxLayout()
		self._edt_import = QtGui.QLineEdit()
		self._edt_import.setPlaceholderText('Click Browse…')
		self._edt_import.setReadOnly(True)
		btn_browse_imp = QtGui.QPushButton('Browse…')
		btn_browse_imp.setFixedWidth(70)
		btn_browse_imp.clicked.connect(self._browse_import)
		imp_path_row.addWidget(self._edt_import)
		imp_path_row.addWidget(btn_browse_imp)
		root.addLayout(imp_path_row)

		btn_import = QtGui.QPushButton('Load .trfont (inspect)')
		btn_import.clicked.connect(self._do_import)
		root.addWidget(btn_import)

		root.addSpacing(4)
		root.addWidget(self._hr())

		# Output log
		root.addWidget(self._section_label('Log'))
		self._log = QtGui.QTextEdit()
		self._log.setReadOnly(True)
		self._log.setFixedHeight(120)
		self._log.setStyleSheet('font-family: monospace; font-size: 10px;')
		root.addWidget(self._log)

		btn_close = QtGui.QPushButton('Close')
		btn_close.clicked.connect(self.close)
		root.addWidget(btn_close)

	# -- UI helpers -------------------------------------
	def _section_label(self, text):
		lbl = QtGui.QLabel('<b>{}</b>'.format(text))
		return lbl

	def _hr(self):
		line = QtGui.QFrame()
		line.setFrameShape(QtGui.QFrame.HLine)
		line.setFrameShadow(QtGui.QFrame.Sunken)
		return line

	def _print(self, msg):
		self._log.append(msg)

	# -- Path pickers -----------------------------------
	def _browse_export(self):
		path = QtGui.QFileDialog.getSaveFileName(
			self, 'Export .trfont — choose folder name',
			os.path.expanduser('~'),
			'TrFont folder (*.trfont)',
		)

		# getSaveFileName returns (path, filter) on PySide / Qt5-style PythonQt,
		# or just a string on older Qt4-style. Handle both.
		if isinstance(path, (tuple, list)):
			path = path[0]

		if path:
			# Ensure extension
			if not path.endswith('.trfont'):
				path += '.trfont'
			self._edt_export.setText(path)

	def _browse_import(self):
		path = QtGui.QFileDialog.getExistingDirectory(
			self, 'Load .trfont — choose folder',
			os.path.expanduser('~'),
		)

		if isinstance(path, (tuple, list)):
			path = path[0]

		if path:
			self._edt_import.setText(path)

	# -- Actions ----------------------------------------
	def _do_export(self):
		path = self._edt_export.text.strip()
		if not path:
			self._print('ERROR: No export path set.')
			return

		if not fl6.CurrentFont():
			self._print('ERROR: No font open in FontLab.')
			return

		self._print('--- Export ---')

		try:
			proxy = trFontProxy()

			# Glyph scope
			if self._rad_selected.isChecked():
				glyph_names = proxy.selected_glyph_names
				self._print('Scope: {} selected glyph(s)'.format(len(glyph_names)))
				if not glyph_names:
					self._print('WARNING: No glyphs selected — exporting nothing.')
					return
			else:
				glyph_names = None		# None = all
				self._print('Scope: all glyphs')

			font = proxy.eject(
				glyph_names      = glyph_names,
				include_encoding = self._chk['encoding'].isChecked(),
				include_axes     = self._chk['axes'].isChecked(),
				verbose          = False,
			)

			# Optionally strip components not yet bridged (they're empty anyway
			# but the flags allow for future implementation to gate them)
			if not self._chk['kerning'].isChecked():
				from typerig.core.objects.kern import Kerning
				font.kerning = Kerning()

			TrFontIO.write(font, path)

			self._print('Written: {}'.format(path))
			self._print('  Glyphs:   {}'.format(len(font)))
			self._print('  Masters:  {}'.format(len(font.masters)))
			self._print('  Encoding: {} entries'.format(len(font.encoding.entries)))
			self._print('  Axes:     {}'.format(len(font.axes)))

		except Exception as e:
			self._print('ERROR: {}'.format(e))
			import traceback
			self._print(traceback.format_exc())

	def _do_import(self):
		path = self._edt_import.text.strip()
		if not path:
			self._print('ERROR: No import path set.')
			return

		if not os.path.isdir(path):
			self._print('ERROR: Path is not a folder: {}'.format(path))
			return

		self._print('--- Load ---')

		try:
			font = TrFontIO.read(path)

			self._print('Loaded: {}'.format(path))
			self._print('  Family:   {}'.format(font.info.family_name))
			self._print('  Style:    {}'.format(font.info.style_name))
			self._print('  UPM:      {}'.format(font.metrics.upm))
			self._print('  Glyphs:   {}'.format(len(font)))
			self._print('  Masters:  {}'.format(len(font.masters)))
			self._print('  Encoding: {} entries'.format(len(font.encoding.entries)))
			self._print('  Axes:     {}'.format(len(font.axes)))
			self._print('  Kerning:  {} pairs'.format(len(font.kerning.pairs)))

			if font.masters.data:
				self._print('  Master names:')
				for m in font.masters:
					flag = ' [default]' if m.is_default else ''
					self._print('    {} → layer "{}"{}' .format(m.name, m.layer_name, flag))

			if font.glyph_names:
				preview = font.glyph_names[:8]
				suffix  = ' …' if len(font) > 8 else ''
				self._print('  Glyphs: {}{}'.format(', '.join(preview), suffix))

		except Exception as e:
			self._print('ERROR: {}'.format(e))
			import traceback
			self._print(traceback.format_exc())


# ================================================
# Entry point
# ================================================
def run():
	# Reuse an existing instance if already open (avoids duplicate windows)
	for widget in QtGui.QApplication.topLevelWidgets():
		if isinstance(widget, TrFontTool):
			widget.raise_()
			widget.activateWindow()
			return

	dlg = TrFontTool()
	dlg.show()

run()
