# MODULE: TypeRig / Proxy / FontLab / Devtools / Shots
# -----------------------------------------------------------
# Screenshots of FontLab widgets via QWidget.grab(): the glyph
# canvas (with nodes, metrics and any overlay), the TypeRig
# Panel or the main window. Saved as PNG files; default folder
# is <system temp>/typerig_devtools.
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
import tempfile

from PythonQt import QtCore

from typerig.proxy.fl.devtools.app import STATE, main_window
from typerig.proxy.fl.devtools import canvas as dtc
from typerig.proxy.fl.devtools import trpanel as dtp

# - Init --------------------------------
__version__ = '0.1.0'

# - Output folder -----------------------
def output_dir():
	'''Folder where shot() saves PNG files.'''
	return STATE.get('out_dir') or os.path.join(tempfile.gettempdir(), 'typerig_devtools')

def set_output_dir(path):
	STATE['out_dir'] = path
	return output_dir()

# - Shots -------------------------------
def _widget(what):
	if what in (None, 'main'): return main_window()
	if what == 'canvas':
		vp = dtc.viewport()[0]
		if vp is None: raise RuntimeError('No active glyph canvas; call devtools.open_glyph()')
		return vp
	if what == 'panel':
		d = dtp.panel()
		if d is None: raise RuntimeError('TypeRig Panel is not open; call devtools.panel_open()')
		return d
	return what

def _crop_rect(pixmap, box, margin):
	m = dtc.mapping()
	(x0, y0), (x1, y1) = m.to_view_xy(box[0], box[3]), m.to_view_xy(box[2], box[1])
	r = QtCore.QRect(int(min(x0, x1) - margin), int(min(y0, y1) - margin),
					 int(abs(x1 - x0) + 2 * margin), int(abs(y1 - y0) + 2 * margin))
	return r.intersected(QtCore.QRect(0, 0, pixmap.width(), pixmap.height()))

def shot(what='canvas', name=None, crop=None, margin=40):
	'''Grab a widget to PNG; returns the file path.
	what: 'canvas' | 'panel' | 'main' | any QWidget
	crop (canvas only): 'glyph' for the current glyph's metrics box, or
		(xmin, ymin, xmax, ymax) in font units. margin: px around the crop.'''
	w = _widget(what)
	pm = w.grab()
	if crop is not None and what == 'canvas':
		box = dtc.glyph_box() if crop == 'glyph' else crop
		pm = pm.copy(_crop_rect(pm, box, margin))

	folder = output_dir()
	if not os.path.isdir(folder): os.makedirs(folder)
	STATE['shot_n'] += 1
	if name is None:
		name = '{}_{:03d}'.format(what if isinstance(what, str) else 'widget', STATE['shot_n'])
	path = os.path.join(folder, name if name.endswith('.png') else name + '.png')
	if not pm.save(path):
		raise IOError('Could not save {}'.format(path))
	return path
