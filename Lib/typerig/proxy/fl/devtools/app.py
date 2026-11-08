# MODULE: TypeRig / Proxy / FontLab / Devtools / App
# -----------------------------------------------------------
# Qt event helpers, FontLab menu actions, undo/redo and the
# History panel.
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

import sys
import time

import fontlab as fl6
from PythonQt import QtGui

# - Init --------------------------------
__version__ = '0.1.0'

# Shared state, kept on sys so it survives reload_typerig()
# (which drops every typerig.* module, this one included).
STATE = getattr(sys, '_typerig_devtools', None)
if STATE is None:
	STATE = {'panel_ns': None, 'shot_n': 0, 'out_dir': None}
	sys._typerig_devtools = STATE

# - Qt basics ---------------------------
def qv(obj, name):
	'''Property-or-method access: PythonQt exposes Qt properties as
	attributes (widget.visible) and plain methods as callables.'''
	value = getattr(obj, name)
	return value() if callable(value) else value

def app():
	return QtGui.QApplication.instance()

def pump(n=1):
	'''Process pending Qt events n times.'''
	for _ in range(n):
		app().processEvents()

def wait(ms=100):
	'''Process events for ms milliseconds. Overlays tick every 33 ms and
	re-analyse 250 ms after an edit settles.'''
	end = time.time() + ms / 1000.
	while time.time() < end:
		app().processEvents()
		time.sleep(0.005)

def main_window():
	'''FontLab main window.'''
	try:
		w = qv(fl6.flWorkspace.instance(), 'mainWindow')
		if w is not None: return w
	except Exception:
		pass
	tops = [w for w in app().topLevelWidgets() if qv(w, 'visible')]
	return max(tops, key=lambda w: qv(w, 'width') * qv(w, 'height'))

def top_level(title):
	'''Top-level widget whose window title equals title, or None.'''
	for w in app().topLevelWidgets():
		if str(qv(w, 'windowTitle')) == title:
			return w
	return None

# - Actions (FontLab menu commands) -----
def _clean(text):
	return str(text).replace('&', '').strip().lower()

def actions(query=''):
	'''[(objectName, menu text)] of FontLab QActions whose name or text contains query.'''
	q = query.lower()
	out = []
	for a in main_window().findChildren(QtGui.QAction):
		name, text = str(qv(a, 'objectName')), str(qv(a, 'text'))
		if q in name.lower() or q in _clean(text):
			out.append((name, text.replace('&', '')))
	return out

def action(name):
	'''Trigger a FontLab QAction by objectName (exact) or menu text (exact,
	without &). Returns the objectName that ran.'''
	acts = main_window().findChildren(QtGui.QAction)
	hit = [a for a in acts if str(qv(a, 'objectName')) == name]
	hit = hit or [a for a in acts if _clean(qv(a, 'text')) == _clean(name)]
	if not hit:
		raise KeyError('No FontLab action named {!r}; try devtools.actions({!r})'.format(name, name))
	hit[0].trigger()
	pump(2)
	return str(qv(hit[0], 'objectName'))

def undo(n=1):
	for _ in range(n): action('actionUndo')

def redo(n=1):
	for _ in range(n): action('actionRedo')

def history(last=12):
	'''FontLab History panel: ([(row, text)], current row).
	Undo moves the current row up; rows below it are the redo stack.
	An undo that moves the row but leaves the data changed means the
	tool did not record its change for Undo: compare snapshots, do not
	trust the row alone.'''
	w = top_level('History')
	if w is None: return [], -1
	for v in w.findChildren(QtGui.QAbstractItemView):
		m = v.model()
		if m is None: continue
		n = m.rowCount()
		rows = [(r, str(m.data(m.index(r, 0))).replace('\t', ' ')) for r in range(max(0, n - last), n)]
		return rows, v.currentIndex().row()
	return [], -1
