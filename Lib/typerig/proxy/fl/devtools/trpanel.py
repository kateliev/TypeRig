# MODULE: TypeRig / Proxy / FontLab / Devtools / TypeRig Panel
# -----------------------------------------------------------
# Drive the TypeRig Panel: open it, switch tabs, list, find,
# press and set controls the way a user would.
#
# Controls are found by index ('#37' or 37), text, tooltip or
# objectName (case-insensitive, exact before partial). Icon
# buttons carry an icon name as text, so their tooltip is the
# readable label; controls() shows both.
#
# The panel script is found next to the package in the repo
# layout (Scripts/TypeRig GUI/typerig-panel.py) or through the
# TYPERIG_PANEL_SCRIPT environment variable. A TypeRig Panel
# that is already open is used as is.
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026       (http://www.kateliev.com)
# (C) Karandash Type Foundry      (http://www.karandash.eu)
# -----------------------------------------------------------
# www.typerig.com
# SPDX-License-Identifier: AGPL-3.0-only
#
# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -------------------------
from __future__ import absolute_import, print_function

import os
import sys

from PythonQt import QtGui

import typerig
from typerig.proxy.fl.devtools.app import STATE, qv, app, pump, wait

# - Init --------------------------------
__version__ = '0.1.0'

PANEL_TITLE = 'TypeRig Panel'
_NOT_OPEN = 'TypeRig Panel is not open; call devtools.panel_open()'

_KINDS = ('QPushButton', 'QToolButton', 'QCheckBox', 'QRadioButton', 'QComboBox',
		  'QDoubleSpinBox', 'QSpinBox', 'QLineEdit', 'QSlider')
_INPUT_KINDS = ('ComboBox', 'SpinBox', 'DoubleSpinBox', 'Slider', 'LineEdit')

# - Locate and open ---------------------
def panel_script():
	'''Path of typerig-panel.py: $TYPERIG_PANEL_SCRIPT, else the repo layout.'''
	env = os.environ.get('TYPERIG_PANEL_SCRIPT')
	if env: return env
	lib = os.path.dirname(os.path.dirname(os.path.abspath(typerig.__file__)))
	return os.path.normpath(os.path.join(lib, '..', 'Scripts', 'TypeRig GUI', 'typerig-panel.py'))

def _alive(w):
	try:
		return w is not None and bool(qv(w, 'visible'))
	except Exception:
		return False

def panel():
	'''The open TypeRig Panel dialog (ours, or one the user opened), or None.'''
	ns = STATE.get('panel_ns')
	d = ns.get('dialog') if ns else None
	if _alive(d): return d
	for w in app().topLevelWidgets():
		if str(qv(w, 'windowTitle')).startswith(PANEL_TITLE) and hasattr(w, 'tabs') and _alive(w):
			return w
	return None

def panel_open(reopen=False):
	'''Open the TypeRig Panel from its script (once). reopen=True closes it first.'''
	if reopen: panel_close()
	d = panel()
	if d is not None: return d
	path = panel_script()
	if not os.path.isfile(path):
		raise IOError('typerig-panel.py not found at {}; set TYPERIG_PANEL_SCRIPT'.format(path))
	gui_dir = os.path.dirname(path)
	if gui_dir not in sys.path: sys.path.insert(0, gui_dir)
	ns = {'__file__': path, '__name__': '__typerig_devtools_panel__'}
	with open(path, encoding='utf-8') as fh:
		source = fh.read()
	exec(compile(source, path, 'exec'), ns)
	STATE['panel_ns'] = ns
	pump(3)
	return panel()

def panel_close():
	'''Close the TypeRig Panel (ours or the user's).'''
	d = panel()
	if d is not None:
		d.close()
		pump(3)
	STATE['panel_ns'] = None

# - Tabs --------------------------------
def tabs():
	'''Tab names of the open panel.'''
	d = panel()
	if d is None: return []
	t = d.tabs
	return [t.tabText(i) for i in range(qv(t, 'count'))]

def tab(name=None):
	'''Switch to tab `name` (case-insensitive) and return its widget; None = current tab.'''
	d = panel()
	if d is None: raise RuntimeError(_NOT_OPEN)
	t = d.tabs
	if name is None: return t.currentWidget()
	names = [t.tabText(i).lower() for i in range(qv(t, 'count'))]
	if name.lower() not in names:
		raise KeyError('No tab {!r}; tabs are {}'.format(name, tabs()))
	i = names.index(name.lower())
	t.setCurrentIndex(i)
	pump(2)
	return t.widget(i)

# - Controls ----------------------------
def _kind(w):
	for k in _KINDS:
		cls = getattr(QtGui, k, None)
		if cls is not None and isinstance(w, cls): return k[1:]
	return None

def _value(w, kind):
	try:
		if kind in ('CheckBox', 'RadioButton'): return bool(w.isChecked())
		if kind in ('PushButton', 'ToolButton'): return bool(w.isChecked()) if w.isCheckable() else None
		if kind == 'ComboBox': return str(qv(w, 'currentText'))
		if kind in ('SpinBox', 'DoubleSpinBox', 'Slider'): return qv(w, 'value')
		if kind == 'LineEdit': return str(qv(w, 'text'))
	except Exception:
		return '?'

def _is_inner_edit(w):
	'''Line edits that belong to a spin box or combo box.'''
	if str(qv(w, 'objectName')) == 'qt_spinbox_lineedit': return True
	par = w.parentWidget()
	return par is not None and _kind(par) == 'ComboBox'

def _controls(root):
	out = []
	for w in root.findChildren(QtGui.QWidget):
		k = _kind(w)
		if k is None: continue
		if k == 'LineEdit' and _is_inner_edit(w): continue
		try:
			if not w.isVisibleTo(root): continue
		except Exception:
			pass
		text = '' if k in _INPUT_KINDS else str(qv(w, 'text'))
		out.append({'i': len(out), 'kind': k, 'text': text, 'tip': str(qv(w, 'toolTip')),
					'name': str(qv(w, 'objectName')), 'value': _value(w, k),
					'enabled': bool(qv(w, 'enabled')), 'w': w})
	return out

def controls(tab_name=None, kinds=None):
	'''Table of the visible controls of a tab: index, kind, text | tooltip,
	value, enabled. kinds: e.g. ['CheckBox', 'DoubleSpinBox'].'''
	rows = []
	for c in _controls(tab(tab_name)):
		if kinds and c['kind'] not in kinds: continue
		tip = c['tip'].split('\n')[0].strip()
		label = c['text'] or c['name']
		if tip and tip.lower() != label.lower():
			label = '{} | {}'.format(label, tip[:50]) if label else tip[:60]
		value = '' if c['value'] is None else '= {!r} '.format(c['value'])
		rows.append('{:3d} {:<13} {:<60} {}{}'.format(c['i'], c['kind'], label, value,
													  '' if c['enabled'] else '(disabled)'))
	return '\n'.join(rows)

def find(tab_name, label):
	'''Control widget in a tab by index (int or '#3'), or by exact then
	partial match on text / tooltip / objectName (case-insensitive).'''
	cs = _controls(tab(tab_name))
	if isinstance(label, int) or (isinstance(label, str) and label.startswith('#')):
		return cs[int(str(label).lstrip('#'))]['w']

	q = label.lower()
	exact = lambda c: q in (c['text'].lower(), c['tip'].lower(), c['name'].lower(), c['tip'].split('\n')[0].strip().lower())
	partial = lambda c: q in c['text'].lower() or q in c['tip'].lower() or q in c['name'].lower()

	for test in (exact, partial):
		hits = [c for c in cs if test(c)]
		if len(hits) == 1: return hits[0]['w']
		if len(hits) > 1:
			by_text = [c for c in hits if c['text'].lower() == q]
			if len(by_text) == 1: return by_text[0]['w']
			raise KeyError('{!r} is ambiguous in {}: {}'.format(label, tab_name,
						   ['#{} {}'.format(c['i'], c['text'] or c['tip'][:40]) for c in hits]))
	raise KeyError('No control {!r} in tab {!r}; see devtools.controls({!r})'.format(label, tab_name, tab_name))

def press(tab_name, label, settle_ms=50):
	'''Click a panel button the way a user would, then let Qt settle.'''
	w = find(tab_name, label)
	if not qv(w, 'enabled'): raise RuntimeError('{!r} is disabled'.format(label))
	w.click()
	wait(settle_ms)
	return True

def set_value(tab_name, label, value, settle_ms=50):
	'''Set a check box, radio, checkable button, spin box, slider, combo box
	(text or index) or line edit. Returns the value read back.'''
	w = find(tab_name, label)
	k = _kind(w)
	if k in ('CheckBox', 'RadioButton', 'PushButton', 'ToolButton'):
		if bool(w.isChecked()) != bool(value): w.click()
	elif k in ('SpinBox', 'DoubleSpinBox', 'Slider'):
		w.setValue(value)
		try: w.editingFinished()
		except Exception: pass
	elif k == 'ComboBox':
		if isinstance(value, int):
			w.setCurrentIndex(value)
		else:
			i = w.findText(value)
			if i < 0: raise KeyError('{!r} not in combo box {!r}'.format(value, label))
			w.setCurrentIndex(i)
	elif k == 'LineEdit':
		w.setText(str(value))
		try: w.editingFinished()
		except Exception: pass
	else:
		raise TypeError('Cannot set a {}'.format(k))
	wait(settle_ms)
	return _value(w, k)
