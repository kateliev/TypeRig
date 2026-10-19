# MenuTitle: TypeRig: Installer
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------
#  ___ ___ ____
# |   |   |   /\   TypeRig
# |___|___|__/__\
#     |   | /   /  (C) Font development kit for GlyphsApp 3 & 4
#     |___|/___/   (C) Vassil Kateliev, 2017-2026 (http://www.kateliev.com)
#     |   |\   \
#     |___| \___\  www.typerig.com
#
# -------------------------------------------------------------------------
# (C) Vassil Kateliev, 2025-2026  (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
# -------------------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Self-contained: the logo is baked in, and the TypeRig / TypeRig-Glyphs
# folders are auto-detected, so the script works from anywhere -- the
# TypeRig repo or Glyphs' own Scripts folder.

# - Dependencies -----------------
from __future__ import print_function

import os
import shutil
import site
import subprocess
import sysconfig

import vanilla
from AppKit import (NSColor, NSData, NSFloatingWindowLevel, NSFont, NSImage,
                    NSOpenPanel, NSURL, NSWorkspace)

try:
	from GlyphsApp import Glyphs, GSGlyphsInfo
except ImportError:
	Glyphs = GSGlyphsInfo = None

# - Init --------------------------------
app_name, app_version = 'TypeRig Installer', '2.0'

# - Config ------------------------------
module_name = 'typerig'
module_path = 'Lib'
file_ext    = '.pth'

bundle_ext = ('.glyphsPlugin', '.glyphsTool', '.glyphsPalette',
              '.glyphsReporter', '.glyphsFilter', '.glyphsFileFormat')

key_lib     = 'com.typerig.installer.lib'
key_plugins = 'com.typerig.installer.plugins'

# Places people usually keep a GitHub checkout or an unzipped download.
search_roots = ('~/Documents/GitHub', '~/GitHub', '~/Developer', '~/Documents',
                '~/Desktop', '~/Downloads', '~/Remote', '~')
core_names   = ('TypeRig', 'TypeRig-master', 'TypeRig-main')
glyphs_names = ('TypeRig-Glyphs', 'TypeRig-Glyphs-master', 'TypeRig-Glyphs-main')

# - Strings -----------------------------
core_methods = ('Link (recommended)', 'Copy package', 'Save link file…')
core_method_info = (
	'Writes typerig.pth into the Glyphs Python folder. Updates from GitHub '
	'apply at once. Re-run only if you move the TypeRig folder.',
	'Copies the typerig package into the Glyphs Python folder. Re-run the '
	'installer after every update.',
	'Saves typerig.pth to a folder you choose. Copy it to the Glyphs Python '
	'folder yourself (use when Link fails with "Access denied").',
)

# - Baked logo (PNG, base64) ------------
logo_png = (
	'iVBORw0KGgoAAAANSUhEUgAAAQIAAAECCAYAAAAVT9lQAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA'
	'6AAAdTAAAOpgAAA6mAAAF3CculE8AAAARGVYSWZNTQAqAAAACAABh2kABAAAAAEAAAAaAAAAAAADoAEAAwAAAAEAAQAAoAIA'
	'BAAAAAEAAAECoAMABAAAAAEAAAECAAAAAMkW2e4AAAHLaVRYdFhNTDpjb20uYWRvYmUueG1wAAAAAAA8eDp4bXBtZXRhIHht'
	'bG5zOng9ImFkb2JlOm5zOm1ldGEvIiB4OnhtcHRrPSJYTVAgQ29yZSA2LjAuMCI+CiAgIDxyZGY6UkRGIHhtbG5zOnJkZj0i'
	'aHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyI+CiAgICAgIDxyZGY6RGVzY3JpcHRpb24gcmRm'
	'OmFib3V0PSIiCiAgICAgICAgICAgIHhtbG5zOmV4aWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20vZXhpZi8xLjAvIj4KICAgICAg'
	'ICAgPGV4aWY6Q29sb3JTcGFjZT4xPC9leGlmOkNvbG9yU3BhY2U+CiAgICAgICAgIDxleGlmOlBpeGVsWERpbWVuc2lvbj4y'
	'ODg8L2V4aWY6UGl4ZWxYRGltZW5zaW9uPgogICAgICAgICA8ZXhpZjpQaXhlbFlEaW1lbnNpb24+Mjg4PC9leGlmOlBpeGVs'
	'WURpbWVuc2lvbj4KICAgICAgPC9yZGY6RGVzY3JpcHRpb24+CiAgIDwvcmRmOlJERj4KPC94OnhtcG1ldGE+CvHMQOEAAC99'
	'SURBVHgB7V0HvBTV9f6W3i1UOyjYaArYgsZgDdZYUBMLENHYosQae4maiIbYYwIK9ohiQ8QWrIAFjWD5q6Bgp6pBiiLvzf87'
	's2+zhS13ZqfvOe83b9ot53z3nrPn1gGUFAFFQBFQBBQBRUARUAQUAUVAEVAEFAFFQBFQBBQBRUARUAQUAUVAEVAEFAFFQBFQ'
	'BBQBRUARUAQUAUVAEWhAIKVIxB8BC0hhETrDQjc0Qlcect2eknXgm/a8zpxb874Z75vnnQUCC6v57MeC8wreL+XzJfYZPKd4'
	'X4+FPObzeh46YSErEVlQijMCaghiVHrWIrRBY/SiEvamEvbh0Z0q2JUidOV1i1BEsfAD8xWjMJ+8zOUxm4boHdTh3VQnLA+F'
	'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'
	'AElFTkSuQmCC'
)

# - Paths -------------------------------
try:
	python_folder = sysconfig.get_paths()['purelib']
except Exception:
	python_folder = site.USER_SITE or ''

try:
	script_folder = os.path.dirname(os.path.abspath(__file__))
except NameError:
	script_folder = ''


def _glyphs_support_folder():
	'''~/Library/Application Support/Glyphs N for the running Glyphs.'''
	try:
		path = GSGlyphsInfo.applicationSupportPath()
		if path:
			return str(path)
	except Exception:
		pass

	for path, marker in ((python_folder, '/Repositories/'), (script_folder + '/', '/Scripts/')):
		if marker in path and '/Application Support/Glyphs' in path:
			return path.split(marker)[0]

	try:
		major = int(str(Glyphs.versionNumber).split('.')[0])
	except Exception:
		major = 3
	return os.path.expanduser('~/Library/Application Support/Glyphs {}'.format(major))


plugins_folder = os.path.join(_glyphs_support_folder(), 'Plugins')

# - Helpers -----------------------------
def _short(path):
	home = os.path.expanduser('~')
	return '~' + path[len(home):] if path.startswith(home) else path


def _get_default(key):
	try:
		value = Glyphs.defaults[key]
		return str(value) if value else ''
	except Exception:
		return ''


def _set_default(key, value):
	try:
		Glyphs.defaults[key] = value
	except Exception:
		pass


def _resolve_lib(path):
	'''Lib folder for path: accepts TypeRig/Lib, the TypeRig repo root or
	the typerig package itself. Returns '' when no typerig package is found.'''
	path = os.path.expanduser((path or '').strip()).rstrip(os.sep)
	if not path:
		return ''

	candidates = [path, os.path.join(path, module_path)]
	if os.path.basename(path) == module_name:
		candidates.append(os.path.dirname(path))

	for folder in candidates:
		if os.path.isdir(os.path.join(folder, module_name)):
			return os.path.normpath(folder)
	return ''


def _find_bundles(path):
	'''Glyphs bundles for path: a single bundle, a Plugins folder or the
	TypeRig-Glyphs repo root.'''
	path = os.path.expanduser((path or '').strip()).rstrip(os.sep)
	if not path or not os.path.isdir(path):
		return []
	if path.endswith(bundle_ext):
		return [path]

	for folder in (path, os.path.join(path, 'Plugins')):
		if os.path.isdir(folder):
			found = sorted(os.path.join(folder, name) for name in os.listdir(folder)
			               if name.endswith(bundle_ext))
			if found:
				return found
	return []


def _pth_target():
	'''Folder written in an existing typerig.pth, or ''.'''
	pth_path = os.path.join(python_folder, module_name + file_ext)
	try:
		with open(pth_path) as f:
			for line in f:
				line = line.strip()
				if line and not line.startswith(('#', 'import')):
					return line
	except Exception:
		pass
	return ''


def _detect_lib():
	candidates = [_get_default(key_lib), script_folder, _pth_target()]

	try:
		import importlib.util
		spec = importlib.util.find_spec(module_name)
		if spec and spec.submodule_search_locations:
			candidates.append(os.path.dirname(list(spec.submodule_search_locations)[0]))
	except Exception:
		pass

	for root in search_roots:
		candidates += [os.path.join(root, name) for name in core_names]

	for path in candidates:
		lib = _resolve_lib(path)
		if lib and os.path.normpath(lib) != os.path.normpath(python_folder):
			return lib
	return ''


def _detect_plugins(lib):
	candidates = [_get_default(key_plugins), script_folder]

	for base in filter(None, (lib and os.path.dirname(lib), script_folder)):
		candidates += [os.path.join(base, os.pardir, name) for name in glyphs_names]

	for root in search_roots:
		candidates += [os.path.join(root, name) for name in glyphs_names]

	for path in candidates:
		if path and _find_bundles(path) and \
		   os.path.realpath(path) != os.path.realpath(plugins_folder):
			path = os.path.normpath(path)
			plugins = os.path.join(path, 'Plugins')
			return plugins if os.path.isdir(plugins) else path
	return ''


def _core_state():
	package = os.path.join(python_folder, module_name)
	if os.path.isdir(package) and not os.path.islink(package):
		return 'Installed · copy'
	target = _pth_target()
	if target:
		return 'Installed · link' if _resolve_lib(target) else 'Broken link'
	return 'Not installed'


def _bundle_state(src):
	dst = os.path.join(plugins_folder, os.path.basename(src))
	if os.path.islink(dst):
		if os.path.realpath(dst) == os.path.realpath(src):
			return 'linked'
		return 'linked elsewhere' if os.path.exists(dst) else 'broken link'
	if os.path.isdir(dst):
		return 'copied'
	return '—'


def _remove(path):
	if os.path.islink(path) or os.path.isfile(path):
		os.remove(path)
	elif os.path.isdir(path):
		shutil.rmtree(path)


def _clear_quarantine(path):
	'''Bundles from a downloaded zip are quarantined; Glyphs may refuse them.'''
	try:
		with open(os.devnull, 'w') as null:
			subprocess.call(['xattr', '-dr', 'com.apple.quarantine', path],
			                stdout=null, stderr=null)
	except Exception:
		pass


def _logo_image(size):
	try:
		data = NSData.alloc().initWithBase64EncodedString_options_(logo_png, 1)
		image = NSImage.alloc().initWithData_(data)
		if image is not None:
			image.setSize_((size, size))
		return image
	except Exception:
		return None


def _choose_folder(title, start=''):
	panel = NSOpenPanel.openPanel()
	panel.setTitle_(title)
	panel.setMessage_(title)
	panel.setCanChooseDirectories_(True)
	panel.setCanChooseFiles_(False)
	panel.setTreatsFilePackagesAsDirectories_(False)
	panel.setAllowsMultipleSelection_(False)
	if start and os.path.isdir(start):
		panel.setDirectoryURL_(NSURL.fileURLWithPath_(start))
	if panel.runModal():
		return str(panel.URL().path())
	return ''


def _style(control, size=None, bold=False, color=None, truncate=False):
	field = control.getNSTextField()
	if size:
		field.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
	if color is not None:
		field.setTextColor_(color)
	if truncate:
		field.cell().setLineBreakMode_(5)  # NSLineBreakByTruncatingMiddle
	return control


def _color(name):
	try:
		return getattr(NSColor, name)()
	except Exception:
		return NSColor.grayColor()


# - Interface ---------------------------
W, H   = 540, 690
pad    = 20
small  = NSFont.smallSystemFontSize()


class dlg_install(object):
	def __init__(self):
		self.w = vanilla.Window((W, H), '{} {}'.format(app_name, app_version),
		                        minSize=(W, H), maxSize=(W, H))
		self.w.getNSWindow().setLevel_(NSFloatingWindowLevel)

		muted = _color('secondaryLabelColor')

		# - Header ------------------------------------------------
		self.w.logo = vanilla.ImageView((pad, 16, 60, 60), scale='proportional')
		logo = _logo_image(60)
		if logo is not None:
			self.w.logo.setImage(imageObject=logo)

		self.w.title = _style(vanilla.TextBox((92, 22, -pad, 30), 'TypeRig'), 24, bold=True)
		self.w.subtitle = _style(vanilla.TextBox((93, 54, -pad, 18),
			'Font development kit for Glyphs  ·  Installer {}'.format(app_version)), small, color=muted)

		self.w.line_top = vanilla.HorizontalLine((pad, 90, -pad, 1))

		# - 1. Core -----------------------------------------------
		y = 104
		self.w.hdr_core = _style(vanilla.TextBox((pad, y, 260, 20), '1   TypeRig Core'), 13, bold=True)
		self.w.state_core = _style(vanilla.TextBox((-240, y + 2, -pad - 4, 17), '', alignment='right'), small, color=muted)

		self.w.core = vanilla.Box((pad, y + 24, -pad, 198))
		box = self.w.core

		box.lbl_lib = _style(vanilla.TextBox((10, 8, -10, 16),
			'Folder that contains the typerig package  (TypeRig/Lib)'), small, color=muted)
		box.fld_lib = vanilla.EditText((10, 28, -98, 22), '', callback=self._on_lib_changed)
		box.btn_lib = vanilla.Button((-92, 27, 82, 24), 'Browse…', callback=self._browse_lib)
		box.chk_lib = _style(vanilla.TextBox((10, 55, -10, 16), ''), small)

		box.rad_method = vanilla.RadioGroup((10, 82, 170, 64), core_methods, isVertical=True,
		                                    callback=self._on_method_changed)
		box.rad_method.set(0)
		box.inf_method = _style(vanilla.TextBox((188, 84, -12, 62), ''), small, color=muted)

		box.line = vanilla.HorizontalLine((10, 152, -10, 1))
		box.lbl_python = _style(vanilla.TextBox((10, 165, -168, 16),
			'Glyphs Python:  ' + _short(python_folder)), small, color=muted, truncate=True)
		box.lbl_python.getNSTextField().setToolTip_(python_folder)
		box.btn_core = vanilla.Button((-158, 160, 148, 24), 'Install Core', callback=self._install_core)

		# - 2. Plugins --------------------------------------------
		y = 340
		self.w.hdr_plugins = _style(vanilla.TextBox((pad, y, 260, 20), '2   Glyphs Plugins'), 13, bold=True)
		self.w.state_plugins = _style(vanilla.TextBox((-300, y + 2, -pad - 4, 17),
			'→ ' + _short(plugins_folder), alignment='right'), small, color=muted, truncate=True)
		self.w.state_plugins.getNSTextField().setToolTip_(plugins_folder)

		self.w.plugins = vanilla.Box((pad, y + 24, -pad, 232))
		box = self.w.plugins

		box.lbl_src = _style(vanilla.TextBox((10, 8, -10, 16),
			'TypeRig-Glyphs Plugins folder  (or a single bundle)'), small, color=muted)
		box.fld_src = vanilla.EditText((10, 28, -98, 22), '', callback=self._on_plugins_changed)
		box.btn_src = vanilla.Button((-92, 27, 82, 24), 'Browse…', callback=self._browse_plugins)

		box.lst_bundles = vanilla.List((10, 60, -10, 118), [],
			columnDescriptions=[
				dict(title='', key='install', cell=vanilla.CheckBoxListCell(), width=22, editable=True),
				dict(title='Bundle', key='name', editable=False),
				dict(title='Status', key='state', editable=False, width=110),
			],
			showColumnTitles=False, allowsMultipleSelection=False,
			drawFocusRing=False, rowHeight=20)

		box.rad_mode = vanilla.RadioGroup((10, 190, 210, 20), ['Symlink', 'Copy'], isVertical=False)
		box.rad_mode.set(0)
		box.btn_plugins = vanilla.Button((-158, 188, 148, 24), 'Install Plugins', callback=self._install_plugins)

		# - Footer ------------------------------------------------
		self.w.line_bottom = vanilla.HorizontalLine((pad, -78, -pad, 1))
		self.w.status = _style(vanilla.TextBox((pad, -68, -pad, 30), ''), small, color=muted)

		self.w.btn_open_python  = vanilla.Button((pad, -36, 130, 22), 'Python Folder',
			sizeStyle='small', callback=lambda s: self._reveal(python_folder))
		self.w.btn_open_plugins = vanilla.Button((pad + 136, -36, 130, 22), 'Plugins Folder',
			sizeStyle='small', callback=lambda s: self._reveal(plugins_folder))
		self.w.btn_close = vanilla.Button((-110, -38, 90, 24), 'Close', callback=lambda s: self.w.close())

		# - Init state --------------------------------------------
		lib = _detect_lib()
		self.w.core.fld_lib.set(lib)
		self.w.plugins.fld_src.set(_detect_plugins(lib))

		self._on_method_changed(None)
		self._refresh_core()
		self._refresh_plugins()
		self._log('Pick what to install. Restart Glyphs afterwards.')

		self.w.setDefaultButton(self.w.core.btn_core)
		self.w.open()

	# - Feedback ----------------------------------------------
	def _log(self, message, kind=None):
		color = {'ok': 'systemGreenColor', 'error': 'systemRedColor'}.get(kind, 'secondaryLabelColor')
		self.w.status.set(message)
		self.w.status.getNSTextField().setTextColor_(_color(color))
		if kind:
			print('{}: {}'.format(app_name, message))

	def _reveal(self, path):
		if not os.path.isdir(path):
			self._log('Folder does not exist yet: {}'.format(_short(path)), 'error')
			return
		NSWorkspace.sharedWorkspace().openURL_(NSURL.fileURLWithPath_(path))

	# - Core --------------------------------------------------
	def _browse_lib(self, sender):
		chosen = _choose_folder('Select the TypeRig folder (or TypeRig/Lib)',
		                        self.w.core.fld_lib.get().strip())
		if chosen:
			self.w.core.fld_lib.set(_resolve_lib(chosen) or chosen)
			self._refresh_core()

	def _on_lib_changed(self, sender):
		self._refresh_core()

	def _on_method_changed(self, sender):
		self.w.core.inf_method.set(core_method_info[self.w.core.rad_method.get()])

	def _lib_folder(self):
		return _resolve_lib(self.w.core.fld_lib.get())

	def _refresh_core(self):
		lib = self._lib_folder()
		if lib:
			text, color = '✓  typerig package found', 'systemGreenColor'
		elif self.w.core.fld_lib.get().strip():
			text, color = '✕  No typerig package here. Use Browse… to locate TypeRig.', 'systemRedColor'
		else:
			text, color = 'TypeRig not found automatically. Use Browse… to locate it.', 'systemOrangeColor'

		self.w.core.chk_lib.set(text)
		self.w.core.chk_lib.getNSTextField().setTextColor_(_color(color))
		self.w.core.btn_core.enable(bool(lib))
		self.w.state_core.set(_core_state())

	def _install_core(self, sender):
		lib = self._lib_folder()
		if not lib:
			self._log('Select a folder that contains the typerig package first.', 'error')
			return

		method  = self.w.core.rad_method.get()
		pth     = module_name + file_ext
		package = os.path.join(python_folder, module_name)

		try:
			if method == 0:
				if not os.path.isdir(python_folder):
					os.makedirs(python_folder)
				# A copied package in site-packages shadows the link.
				if os.path.isdir(package) and not os.path.islink(package):
					shutil.rmtree(package)
				with open(os.path.join(python_folder, pth), 'w') as f:
					f.write(lib)
				message = 'TypeRig core linked → {}. Restart Glyphs to load it.'.format(_short(lib))

			elif method == 1:
				_remove(os.path.join(python_folder, pth))
				_remove(package)
				shutil.copytree(os.path.join(lib, module_name), package)
				message = 'TypeRig core copied into the Glyphs Python folder. Restart Glyphs to load it.'

			else:
				folder = _choose_folder('Choose a folder to save typerig.pth')
				if not folder:
					return
				with open(os.path.join(folder, pth), 'w') as f:
					f.write(lib)
				message = 'Saved {}. Copy it to: {}'.format(_short(os.path.join(folder, pth)), python_folder)

		except Exception as e:
			self._log('Install failed: {}. Try "Save link file…" instead.'.format(e), 'error')
			return

		_set_default(key_lib, lib)
		self._refresh_core()
		self._log(message, 'ok')

	# - Plugins -----------------------------------------------
	def _browse_plugins(self, sender):
		chosen = _choose_folder('Select the TypeRig-Glyphs folder (or its Plugins folder)',
		                        self.w.plugins.fld_src.get().strip())
		if chosen:
			self.w.plugins.fld_src.set(chosen)
			self._refresh_plugins()

	def _on_plugins_changed(self, sender):
		self._refresh_plugins()

	def _refresh_plugins(self, keep=None):
		bundles = _find_bundles(self.w.plugins.fld_src.get())
		items = []
		for src in bundles:
			name = os.path.basename(src)
			items.append(dict(
				install=keep.get(name, True) if keep else True,
				name=os.path.splitext(name)[0],
				state=_bundle_state(src),
				path=src,
			))
		self.w.plugins.lst_bundles.set(items)
		self.w.plugins.btn_plugins.enable(bool(items))

	def _install_plugins(self, sender):
		items  = self.w.plugins.lst_bundles.get()
		chosen = [str(item['path']) for item in items if item['install']]
		if not chosen:
			self._log('Tick at least one bundle to install.', 'error')
			return

		link = self.w.plugins.rad_mode.get() == 0
		done, failed = [], []

		for src in chosen:
			name = os.path.basename(src)
			dst  = os.path.join(plugins_folder, name)
			try:
				if os.path.realpath(dst) == os.path.realpath(src) and not os.path.islink(dst):
					continue  # source already lives in the Plugins folder
				if not os.path.isdir(plugins_folder):
					os.makedirs(plugins_folder)
				_clear_quarantine(src)
				_remove(dst)
				if link:
					os.symlink(src, dst)
				else:
					shutil.copytree(src, dst, symlinks=True)
				done.append(os.path.splitext(name)[0])
			except Exception as e:
				failed.append(os.path.splitext(name)[0])
				print('{}: {} failed: {}'.format(app_name, name, e))

		keep = dict((os.path.basename(str(item['path'])), bool(item['install'])) for item in items)
		self._refresh_plugins(keep)
		_set_default(key_plugins, self.w.plugins.fld_src.get().strip())

		if failed:
			self._log('Failed: {}. See the Macro panel for details.'.format(', '.join(failed)), 'error')
		else:
			self._log('{} {} plugin(s). Restart Glyphs to load them.'.format(
				'Linked' if link else 'Copied', len(done)), 'ok')


# - RUN ------------------------------
dlg_install()
