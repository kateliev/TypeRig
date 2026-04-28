# MenuTitle: TypeRig: Installer
# -------------------------------------------------------------------------
#  ___ ___ ____
# |   |   |   /\   TypeRig
# |___|___|__/__\
#     |   | /   /  (C) Font development kit for GlyphsApp 3
#     |___|/___/   (C) Vassil Kateliev, 2017-2025 (http://www.kateliev.com)
#     |   |\   \
#     |___| \___\  www.typerig.com
#
# -------------------------------------------------------------------------
# (C) Vassil Kateliev, 2025  (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
# -------------------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
from __future__ import print_function

import os
import shutil
import sysconfig
import site

import vanilla
from AppKit import NSImage, NSOpenPanel, NSFloatingWindowLevel

# - Init --------------------------------
app_name, app_version = 'TR | Module Installer', '1.0'

# - Strings -----------------------------
str_auto_pth = (
	'Dynamic install via link: writes typerig.pth into your Glyphs Python\n'
	'folder. Best for GitHub sync — no reinstall needed after updates,\n'
	'only if you move the TypeRig folder.'
)
str_auto_copy = (
	'Static install via copy: copies the typerig package directly into your\n'
	'Glyphs Python folder. Re-run the installer after each update from the\n'
	'GitHub repository.'
)
str_manual = (
	'Manual install via link: pick a destination folder, save typerig.pth\n'
	'there, then copy it to the Glyphs Python path shown below.'
)
str_note = (
	'If Auto Install fails (Access Denied): check that the Glyphs Python\n'
	'folder is user-writable, or move the TypeRig folder to a user-owned\n'
	'location and try again.'
)

# - Config ------------------------------
module_name = 'typerig'
module_path = 'Lib'
file_ext    = '.pth'

# Detect Glyphs Python site-packages (most reliable when run inside Glyphs).
try:
	python_folder = sysconfig.get_paths()['purelib']
except Exception:
	python_folder = site.USER_SITE or ''

# - Helpers -----------------------------
def _detect_lib_folder():
	'''Try to find the TypeRig Lib folder relative to __file__.
	Returns the path only when it actually contains the typerig package.
	Returns '' when running from an unrelated location (e.g. Glyphs Scripts).
	'''
	try:
		candidate = os.path.normpath(
			os.path.join(os.path.dirname(os.path.abspath(__file__)), module_path))
		if os.path.isdir(os.path.join(candidate, module_name)):
			return candidate
	except Exception:
		pass
	return ''


def _validate_lib_folder(path):
	'''True when path is a directory that contains the typerig package.'''
	return bool(path) and os.path.isdir(os.path.join(path, module_name))


def copy_tree(path_source, path_destination):
	if os.path.exists(path_destination) and os.path.isdir(path_destination):
		print('Destination already exists — removing: {}'.format(path_destination))
		shutil.rmtree(path_destination, ignore_errors=False)
	shutil.copytree(path_source, path_destination)


# - Interface ---------------------------
W, H = 480, 470

# First install-option row starts below the lib-picker block.
_ROW_TOP  = 148
_ROW_STEP = 56

def _btn_y(i):
	return _ROW_TOP + i * _ROW_STEP

def _desc_y(i):
	return _ROW_TOP - 2 + i * _ROW_STEP


class dlg_install(object):
	def __init__(self):
		self.w = vanilla.Window(
			(W, H),
			'{} {}'.format(app_name, app_version),
			minSize=(W, H), maxSize=(W, H),
		)
		self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)

		# - Logo --------------------------------------------------
		logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
		                         'typerig-logo.png')
		self.w.logo = vanilla.ImageView((10, 10, -10, 64))
		if os.path.exists(logo_path):
			img = NSImage.alloc().initWithContentsOfFile_(logo_path)
			if img is not None:
				self.w.logo._nsObject.setImage_(img)
				self.w.logo._nsObject.setImageScaling_(3)

		# - TypeRig Lib path picker -------------------------------
		detected = _detect_lib_folder()

		self.w.lbl_lib = vanilla.TextBox(
			(10, 84, -10, 20), 'TypeRig Lib folder (must contain the typerig package):')

		self.w.fld_lib = vanilla.EditText(
			(10, 108, -84, 22), detected,
			callback=self._on_lib_changed)

		self.w.btn_browse = vanilla.Button(
			(-80, 108, 70, 22), 'Browse…',
			callback=self._browse_lib)

		# - Install rows ------------------------------------------
		# Row 0: Auto Link
		self.w.btn_auto_pth  = vanilla.Button(
			(10, _btn_y(0), 162, 24), 'Auto Install via Link',
			callback=self._install_auto_pth)
		self.w.lbl_auto_pth  = vanilla.TextBox(
			(178, _desc_y(0), -10, 50), str_auto_pth)

		# Row 1: Auto Copy
		self.w.btn_auto_copy = vanilla.Button(
			(10, _btn_y(1), 162, 24), 'Auto Install via Copy',
			callback=self._install_auto_copy)
		self.w.lbl_auto_copy = vanilla.TextBox(
			(178, _desc_y(1), -10, 50), str_auto_copy)

		# Row 2: Manual
		self.w.btn_manual    = vanilla.Button(
			(10, _btn_y(2), 162, 24), 'Manual Install via Link',
			callback=self._install_manual_pth)
		self.w.lbl_manual    = vanilla.TextBox(
			(178, _desc_y(2), -10, 50), str_manual)

		# - Info block --------------------------------------------
		info_y = _btn_y(3) + 4

		self.w.lbl_path_title = vanilla.TextBox(
			(10, info_y, -10, 20), 'Glyphs Python installation path:')

		self.w.fld_path = vanilla.EditText(
			(10, info_y + 24, -10, 22), python_folder)
		try:
			self.w.fld_path._nsObject.setEditable_(False)
			self.w.fld_path._nsObject.setSelectable_(True)
		except Exception:
			pass

		self.w.lbl_note = vanilla.TextBox(
			(10, info_y + 52, -10, 54), str_note)

		# - Close -------------------------------------------------
		self.w.btn_close = vanilla.Button(
			(-120, -34, 110, 24), 'Close',
			callback=lambda s: self.w.close())

		# Reflect validation state on startup
		self._refresh_buttons()
		self.w.open()

	# - Path picker -------------------------------------------
	def _browse_lib(self, sender):
		panel = NSOpenPanel.openPanel()
		panel.setTitle_('Select the TypeRig Lib folder')
		panel.setCanChooseDirectories_(True)
		panel.setCanChooseFiles_(False)
		panel.setAllowsMultipleSelection_(False)

		if panel.runModal():
			chosen = panel.URL().path()
			self.w.fld_lib.set(chosen)
			self._refresh_buttons()

	def _on_lib_changed(self, sender):
		self._refresh_buttons()

	def _refresh_buttons(self):
		'''Enable/disable install buttons based on whether the Lib path is valid.'''
		valid = _validate_lib_folder(self.w.fld_lib.get().strip())
		self.w.btn_auto_pth.enable(valid)
		self.w.btn_auto_copy.enable(valid)
		self.w.btn_manual.enable(valid)

	# - Resolved path --------------------------------------------
	def _lib_folder(self):
		'''Return the validated Lib folder path, or None with an error print.'''
		path = self.w.fld_lib.get().strip()
		if not _validate_lib_folder(path):
			print('{}: Lib folder is not set or does not contain "{}". '
			      'Use Browse to locate it.'.format(app_name, module_name))
			return None
		return path

	# - Install actions ------------------------------------------
	def _install_auto_pth(self, sender):
		lib = self._lib_folder()
		if lib is None:
			return
		try:
			if not os.path.exists(python_folder):
				os.makedirs(python_folder)
			pth_path = os.path.join(python_folder, module_name + file_ext)
			with open(pth_path, 'w') as f:
				f.write(lib)
			print('DONE:\tTypeRig installed!'
			      '\n\tpth  -> {}'
			      '\n\tlib  -> {}'
			      '\nNOTE:\tRe-run installer if you move the TypeRig folder.'.format(
			      	pth_path, lib))
		except Exception as e:
			print('FAILED:\t{}'.format(e))

	def _install_auto_copy(self, sender):
		lib = self._lib_folder()
		if lib is None:
			return
		try:
			copy_tree(
				os.path.join(lib, module_name),
				os.path.join(python_folder, module_name),
			)
			print('DONE:\tTypeRig installed in: {}'.format(python_folder))
		except Exception as e:
			print('FAILED:\t{}'.format(e))

	def _install_manual_pth(self, sender):
		lib = self._lib_folder()
		if lib is None:
			return

		panel = NSOpenPanel.openPanel()
		panel.setTitle_('Choose folder to save typerig.pth')
		panel.setCanChooseDirectories_(True)
		panel.setCanChooseFiles_(False)
		panel.setAllowsMultipleSelection_(False)

		if panel.runModal():
			chosen   = panel.URL().path()
			pth_path = os.path.join(chosen, module_name + file_ext)
			try:
				with open(pth_path, 'w') as f:
					f.write(lib)
				print('DONE:\tTypeRig link created: {}'
				      '\nNOTE:\tCopy this file to: {}'.format(pth_path, python_folder))
			except Exception as e:
				print('FAILED:\t{}'.format(e))


# - RUN ------------------------------
dlg_install()
