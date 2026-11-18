#FLM: TypeRig: Probe - native panel symbol (Windows)
# TEMPORARY DIAGNOSTIC for handout T1, stage 1. READ-ONLY: it never calls a FontLab function.
# It only asks Windows whether the main module exports MainWindow::registerCustomPanel
# and lists the export table entries that look related. Delete this file once Windows is decided.
#
# Run it inside FontLab on Windows (Macro panel or the Scripts menu), then send the log:
#	%USERPROFILE%\typerig-win-probe.log

import os
import sys
import ctypes
import platform

LOG = os.path.join(os.path.expanduser('~'), 'typerig-win-probe.log')
lines = []

def log(*args):
	text = ' '.join(str(a) for a in args)
	lines.append(text)
	print(text)

def flush():
	with open(LOG, 'w') as handle:
		handle.write('\n'.join(lines) + '\n')

try:
	import fontlab as fl6
	from PythonQt import QtCore
	log('platform', platform.platform(), '| python', sys.version.split()[0], '| qt', QtCore.qVersion(), '| bits', ctypes.sizeof(ctypes.c_void_p) * 8)
	log('app.main visible:', fl6.MainWindow().isVisible())
except Exception as error:
	log('fontlab import failed:', error)

try:
	kernel = ctypes.WinDLL('kernel32')
	kernel.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
	kernel.GetModuleHandleW.restype = ctypes.c_void_p
	kernel.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
	kernel.GetProcAddress.restype = ctypes.c_void_p
	base = kernel.GetModuleHandleW(None)
	log('main module base:', hex(base or 0))

	# - 1. Direct lookup of the expected MSVC name (and a few variants)
	candidates = [
		'?registerCustomPanel@MainWindow@@QEAAXPEAVYPanelWidget@@@Z',
		'?registerCustomPanel@MainWindow@@QEAAXPEAVYPanelWidget@@_N@Z',
		'?registerCustomPanel@MainWindow@@QEAAHPEAVYPanelWidget@@@Z',
		'registerCustomPanel',
	]
	for name in candidates:
		log('GetProcAddress', name, '->', hex(kernel.GetProcAddress(base, name.encode('ascii')) or 0))

	# - 2. Walk the PE export table of the main module
	def u16(rva): return ctypes.c_uint16.from_address(base + rva).value
	def u32(rva): return ctypes.c_uint32.from_address(base + rva).value

	nt = u32(0x3C)
	magic = u16(nt + 24)
	dir_offset = 112 if magic == 0x20b else 96
	export_rva, export_size = u32(nt + 24 + dir_offset), u32(nt + 24 + dir_offset + 4)
	log('PE magic', hex(magic), '| export directory rva', hex(export_rva), 'size', export_size)

	if export_rva:
		count_names = u32(export_rva + 24)
		names_rva = u32(export_rva + 32)
		log('exported names:', count_names)
		hits = []
		for i in range(count_names):
			name = ctypes.string_at(base + u32(names_rva + 4 * i)).decode('ascii', 'replace')
			if any(key in name for key in ('registerCustomPanel', 'CustomPanel', 'YPanel')):
				hits.append(name)
		log('related exports:', len(hits))
		for name in hits[:200]: log('  ', name)
	else:
		log('the main module has NO export table - the symbol can not be resolved by name.')

except Exception as error:
	import traceback
	log('probe failed:', error)
	log(traceback.format_exc())

flush()
print('Probe log written to', LOG)
