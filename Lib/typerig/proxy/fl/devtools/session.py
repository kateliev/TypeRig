# MODULE: TypeRig / Proxy / FontLab / Devtools / Session
# -----------------------------------------------------------
# Session-level helpers: running canvas overlays, reloading
# TypeRig code in place, and a short status summary.
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

from typerig.proxy.fl.devtools.app import pump
from typerig.proxy.fl.devtools import canvas as dtc
from typerig.proxy.fl.devtools import trpanel as dtp
from typerig.proxy.fl.devtools import shots as dts

# - Init --------------------------------
__version__ = '0.1.0'

_OVERLAY_MODULE = 'typerig.proxy.fl.gui.canvas_overlay'

# - Overlays ----------------------------
def _registry():
	co = sys.modules.get(_OVERLAY_MODULE)
	return getattr(co, '_REGISTRY', None) if co else None

def overlays():
	'''Names of running TypeRig canvas overlays.'''
	return sorted((_registry() or {}).keys())

def stop_overlays():
	'''Kill every running TypeRig canvas overlay; returns their names.'''
	reg = _registry()
	if not reg: return []
	names = list(reg.keys())
	for name in names:
		inst = reg.pop(name, None)
		try:
			inst.kill()
		except Exception as e:
			print('TypeRig Devtools: could not stop overlay {}: {!r}'.format(name, e))
	pump(3)
	return names

# - Reload ------------------------------
def reload_typerig(reopen_panel=True):
	'''Pick up code edits without restarting FontLab: stop overlays, close
	the TypeRig Panel, drop every typerig.* and Panel.* module (devtools
	included; its state lives on sys), then reopen the panel if it was open.
	Objects made before the reload keep running old code.
	Returns the number of modules dropped.'''
	was_open = dtp.panel() is not None
	stop_overlays()
	dtp.panel_close()

	drop = [m for m in list(sys.modules)
			if m == 'typerig' or m.startswith('typerig.') or m == 'Panel' or m.startswith('Panel.')]
	for m in drop:
		del sys.modules[m]

	if reopen_panel and was_open:
		from typerig.proxy.fl.devtools import trpanel as fresh_panel
		fresh_panel.panel_open()
	return len(drop)

# - Summary -----------------------------
def info():
	'''Short status: font, canvas, panel, overlays, shot folder.'''
	from typerig.proxy.fl.objects.font import pFont
	lines = []
	try:
		f = pFont()
		lines.append('font: {} ({})'.format(f.name, f.path))
	except Exception as e:
		lines.append('font: none ({!r})'.format(e))

	if dtc.viewport()[0] is None:
		lines.append('canvas: none (no glyph window)')
	else:
		try:
			g, l = dtc.current()
			lines.append('canvas: {} / {}, {:.3f} px/unit'.format(g, l, dtc.mapping().px_per_unit))
		except Exception as e:
			lines.append('canvas: ? ({!r})'.format(e))

	lines.append('panel: {}'.format('open, tabs {}'.format(dtp.tabs()) if dtp.panel() else 'closed'))
	lines.append('overlays: {}'.format(overlays() or 'none'))
	lines.append('shots: {}'.format(dts.output_dir()))
	return '\n'.join(lines)
