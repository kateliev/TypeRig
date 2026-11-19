#FLM: TR: Font IO
# NOTE: Save the current font as .trfont, open a .trfont as a new FontLab font
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025-2026 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only

# No warranties. By using this you agree
# that you use it at your own risk!

# - Overview ----------------------------
# Front end for the FontLab <-> .trfont bridge (typerig.proxy.tr.objects.font.trFontProxy).
#
#   Export ........ current font -> <name>.trfont folder
#   Inspect ....... read a .trfont and print what is in it
#   Open as new ... .trfont -> a NEW FontLab font (axes, masters + metrics,
#                   instances, font info, glyphs, linked elements, OpenType
#                   classes, features, kerning). Save it with File > Save As.
#                   This is the path checked by the round-trip audit
#                   (Docs/Core/Handouts/HANDOUT-trfont-roundtrip.md): a full
#                   font comes back identical after save + reopen.
#   Update current  .trfont -> the CURRENT font: glyphs, classes, features,
#                   kerning only. Axes, masters, metrics and font info are
#                   NOT changed; layers are matched by name.
#
# Not carried yet: hinting, metric expressions, guide-to-metric bindings,
# FontLab components (flLayer.components). Damaged source data (e.g. a null
# contour) is skipped and listed in the log.
# Runs inside FontLab (no time limit). Large fonts take a while: a 754-glyph,
# 2-master font exports in ~10 s and opens in ~30 s.

# - Dependencies -------------------------
from __future__ import print_function
import os
import time
import traceback

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.tr.objects.font import trFontProxy
from typerig.core.fileio.trfont import TrFontIO

# - Init ---------------------------------
__version__ = '1.0.0'
app_name = 'TypeRig | Font IO'

# Parts the user can switch off. Outlines, metrics, font info, encoding and
# the design space always travel: they are the font.
PARTS = (
	# key,        label,                         tooltip
	('kerning',  'Kerning (pairs + classes)',   'Kerning pairs and kerning classes of every master.'),
	('groups',   'OpenType classes',            'Font classes used by the features (Classes panel).'),
	('features', 'Features',                    'OpenType feature code (prefix and feature blocks).'),
)

# - Helpers ------------------------------
def _picked(result):
	'''QFileDialog returns a str, or (str, filter) on some builds.'''
	if isinstance(result, (tuple, list)):
		result = result[0] if result else ''
	return str(result or '').strip()

def _font_dir():
	'''Folder of the current font file, else the home folder.'''
	try:
		path = fl6.flPackage(fl6.CurrentFont()).fgPackage.path
		if path:
			return os.path.dirname(path)
	except Exception:
		pass
	return os.path.expanduser('~')

def _font_stem():
	try:
		path = fl6.flPackage(fl6.CurrentFont()).fgPackage.path
		if path:
			return os.path.splitext(os.path.basename(path))[0]
	except Exception:
		pass
	return 'font'

# ================================================
# Dialog
# ================================================
class TRFontIO(QtGui.QDialog):
	def __init__(self, parent=None):
		super(TRFontIO, self).__init__(parent)
		self.setWindowTitle('{} {}'.format(app_name, __version__))
		self.setMinimumWidth(380)
		self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
		self._build_ui()

	# -- UI ----------------------------------------
	def _build_ui(self):
		root = QtGui.QVBoxLayout(self)
		root.setSpacing(6)
		root.setContentsMargins(10, 10, 10, 10)

		# - Parts (used by export, open and update)
		root.addWidget(self._label('Include'))
		self.chk = {}
		for key, label, tooltip in PARTS:
			check = QtGui.QCheckBox(label)
			check.setChecked(True)
			check.setToolTip(tooltip)
			self.chk[key] = check
			root.addWidget(check)

		note = QtGui.QLabel('Always included: outlines, elements, anchors, guides, metrics,\n'
		                    'font info, encoding, axes, masters, instances.')
		note.setStyleSheet('color: #888; font-size: 10px;')
		root.addWidget(note)
		root.addWidget(self._hr())

		# - Export
		root.addWidget(self._label('Export current font'))
		self.rad_all = QtGui.QRadioButton('All glyphs')
		self.rad_selected = QtGui.QRadioButton('Selected glyphs')
		self.rad_all.setChecked(True)
		row = QtGui.QHBoxLayout()
		row.addWidget(self.rad_all)
		row.addWidget(self.rad_selected)
		row.addStretch()
		root.addLayout(row)

		self.edt_export, row = self._path_row('Save .trfont as...', self._browse_export)
		root.addLayout(row)

		btn = QtGui.QPushButton('Export .trfont')
		btn.setToolTip('Write the current font to the .trfont folder above.')
		btn.clicked.connect(self.do_export)
		root.addWidget(btn)
		root.addWidget(self._hr())

		# - Import
		root.addWidget(self._label('Import .trfont'))
		self.edt_import, row = self._path_row('Choose a .trfont folder...', self._browse_import)
		root.addLayout(row)

		row = QtGui.QHBoxLayout()
		btn_open = QtGui.QPushButton('Open as new font')
		btn_open.setToolTip('Build a NEW FontLab font from the .trfont.\nSave it with File > Save As.')
		btn_open.clicked.connect(self.do_open_new)
		btn_inspect = QtGui.QPushButton('Inspect')
		btn_inspect.setToolTip('Read the .trfont and list what is in it. Changes nothing.')
		btn_inspect.clicked.connect(self.do_inspect)
		btn_update = QtGui.QPushButton('Update current...')
		btn_update.setToolTip('Write glyphs, classes, features and kerning into the CURRENT font.\n'
		                      'Axes, masters, metrics and font info are not changed.')
		btn_update.clicked.connect(self.do_update_current)
		row.addWidget(btn_open, 2)
		row.addWidget(btn_inspect, 1)
		row.addWidget(btn_update, 1)
		root.addLayout(row)
		root.addWidget(self._hr())

		# - Log
		self.log_view = QtGui.QPlainTextEdit()
		self.log_view.setReadOnly(True)
		self.log_view.setMinimumHeight(160)
		root.addWidget(self.log_view)

	def _label(self, text):
		return QtGui.QLabel('<b>{}</b>'.format(text))

	def _hr(self):
		line = QtGui.QFrame()
		line.setFrameShape(QtGui.QFrame.HLine)
		line.setFrameShadow(QtGui.QFrame.Sunken)
		return line

	def _path_row(self, placeholder, on_browse):
		edit = QtGui.QLineEdit()
		edit.setPlaceholderText(placeholder)
		button = QtGui.QPushButton('Browse...')
		button.setFixedWidth(80)
		button.clicked.connect(on_browse)
		row = QtGui.QHBoxLayout()
		row.addWidget(edit)
		row.addWidget(button)
		return edit, row

	# -- Log ---------------------------------------
	def log(self, text=''):
		print(text)
		self.log_view.appendPlainText(str(text))
		QtGui.QApplication.processEvents()

	def log_problems(self, problems):
		problems = list(problems or [])
		if not problems:
			self.log('Problems: none')
			return
		self.log('Problems ({}):'.format(len(problems)))
		for item in problems[:200]:
			self.log('  - {}'.format(item))
		if len(problems) > 200:
			self.log('  ... {} more (see the Output panel)'.format(len(problems) - 200))
			for item in problems[200:]:
				print('  - {}'.format(item))

	def _busy(self, on):
		if on:
			QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
		else:
			QtGui.QApplication.restoreOverrideCursor()

	def _run(self, title, fn):
		'''Run fn() with a wait cursor; log any exception instead of raising.'''
		self.log('--- {} ---'.format(title))
		self._busy(True)
		start = time.time()
		try:
			fn()
			self.log('Done in {:.1f} s.'.format(time.time() - start))
		except Exception as e:
			self.log('ERROR: {}: {}'.format(type(e).__name__, e))
			print(traceback.format_exc())
		finally:
			self._busy(False)
		self.log()

	def _flags(self):
		return dict((key, self.chk[key].isChecked()) for key, _, _ in PARTS)

	# -- Paths -------------------------------------
	def _browse_export(self):
		suggested = os.path.join(_font_dir(), _font_stem() + '.trfont')
		path = _picked(QtGui.QFileDialog.getSaveFileName(self, 'Save .trfont as', suggested, 'trFont folder (*.trfont)'))
		if path:
			if not path.endswith('.trfont'):
				path += '.trfont'
			self.edt_export.setText(path)

	def _browse_import(self):
		path = _picked(QtGui.QFileDialog.getExistingDirectory(self, 'Choose a .trfont folder', _font_dir()))
		if path:
			self.edt_import.setText(path)

	def _import_path(self):
		path = str(self.edt_import.text).strip()
		if not path:
			raise ValueError('choose a .trfont folder first')
		if not os.path.isdir(path):
			raise ValueError('not a folder: {}'.format(path))
		return path

	# -- Summary -----------------------------------
	def _summary(self, font):
		masters = [m.name for m in font.masters.data]
		self.log('Family / style: {} / {}'.format(font.info.family_name, font.info.style_name))
		self.log('UPM {} | glyphs {} | axes {} | masters {} | instances {}'.format(
			font.metrics.upm, len(font), len(font.axes), len(masters), len(font.instances.data)))
		if masters:
			self.log('Masters: {}'.format(', '.join(
				'{}{}'.format(m.name, ' (default)' if m.is_default else '') for m in font.masters.data)))
			pairs = []
			for name in masters:
				kerning = font.kerning_for(name)
				pairs.append('{} {}'.format(name, len(kerning.data) if kerning is not None else 0))
			self.log('Kerning pairs: {}'.format(', '.join(pairs)))
		kern_classes = sum(1 for g in font.groups.data if g.is_kern1 or g.is_kern2)
		self.log('Groups: {} kerning, {} OpenType | features: {} characters'.format(
			kern_classes, len(font.groups.data) - kern_classes, len(font.features or '')))

	# -- Actions -----------------------------------
	def do_export(self):
		def run():
			path = str(self.edt_export.text).strip()
			if not path:
				raise ValueError('choose where to save the .trfont first')
			if not path.endswith('.trfont'):
				path += '.trfont'
			if not fl6.CurrentFont():
				raise ValueError('no font open')

			proxy = trFontProxy()
			glyph_names = None
			if self.rad_selected.isChecked():
				glyph_names = proxy.selected_glyph_names
				if not glyph_names:
					raise ValueError('no glyphs selected')

			flags = self._flags()
			font = proxy.save(path, glyph_names=glyph_names,
			                  include_kerning=flags['kerning'],
			                  include_groups=flags['groups'],
			                  include_features=flags['features'])
			self.log('Written: {}'.format(path))
			self._summary(font)
			self.log_problems(getattr(proxy, 'problems', []))

		self._run('Export', run)

	def do_inspect(self):
		def run():
			path = self._import_path()
			font = TrFontIO.read(path)
			self.log('Read: {}'.format(path))
			self._summary(font)

		self._run('Inspect', run)

	def do_open_new(self):
		def run():
			path = self._import_path()
			font = TrFontIO.read(path)
			self.log('Read: {}'.format(path))
			self._summary(font)
			flags = self._flags()
			new = trFontProxy.create_font(font,
			                              include_kerning=flags['kerning'],
			                              include_groups=flags['groups'],
			                              include_features=flags['features'])
			self.log('New font built: {} glyphs. Save it with File > Save As.'.format(len(new.fg.glyphs)))
			self.log_problems(getattr(new, 'problems', []))

		self._run('Open as new font', run)

	def do_update_current(self):
		if not fl6.CurrentFont():
			self.log('ERROR: no font open')
			return

		box = QtGui.QMessageBox(self)
		box.setWindowTitle(app_name)
		box.setText('Write the .trfont into the CURRENT font?')
		box.setInformativeText('Glyphs in the .trfont replace the glyphs of the same name '
		                       '(layers matched by name); classes, features and kerning are replaced.\n'
		                       'Axes, masters, metrics and font info are NOT changed.\n'
		                       'For a faithful copy use "Open as new font".')
		button_yes = box.addButton('Update current font', QtGui.QMessageBox.AcceptRole)
		box.addButton('Cancel', QtGui.QMessageBox.RejectRole)
		box.exec_()
		if box.clickedButton() != button_yes:
			return

		def run():
			path = self._import_path()
			font = TrFontIO.read(path)
			self.log('Read: {}'.format(path))
			self._summary(font)
			flags = self._flags()
			proxy = trFontProxy()
			proxy.mount(font,
			            include_kerning=flags['kerning'],
			            include_groups=flags['groups'],
			            include_features=flags['features'])
			fl6.flItems.notifyPackageContentUpdated(proxy.host.fgPackage.id)
			self.log('Current font updated.')
			self.log_problems(getattr(proxy, 'problems', []))

		self._run('Update current font', run)

# ================================================
# Entry point
# ================================================
def run():
	# One window: bring an open one to the front
	for widget in QtGui.QApplication.topLevelWidgets():
		if widget.windowTitle.startswith(app_name) if isinstance(widget.windowTitle, str) else False:
			widget.raise_()
			widget.activateWindow()
			return

	dialog = TRFontIO()
	dialog.show()
	return dialog

dialog = run()
