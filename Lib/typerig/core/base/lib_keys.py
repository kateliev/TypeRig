# MODULE: TypeRig / Core / Base / Font lib keys
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026			(http://www.kateliev.com)
# (C) TypeRig						(http://www.typerig.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Font lib keys (FL font package lib, Glyphs font.userData) shared by
# more than one panel, tab or host. Plain strings, no imports, so a tab
# can read another tool's data without loading that tool's engine.
# Do NOT change a key string: fonts in use store data under these keys.

# - Init -----------------------------
__version__ = '0.1.0'

# - Delta ----------------------------
# Delta panel Live Axis + options (JSON). Written by the Glyphs Delta tab
# (gui/delta_live.py), read by the Clipboard tab (clip_live_axis).
DELTA_LIVE_LIB_KEY       = 'com.typerig.panel.delta.live'

# Delta Machine bake axis setup (JSON). Same key as FL DeltaNew / Delta /
# Clipboard / Explorer and TR-DeltaPreview.
DELTA_AXISSETUP_LIB_KEY  = 'com.typerig.delta.machine.axissetup'

# Delta Italic Lab (TypeRig-Glyphs) axis, controls and italic fix options
# (JSON): a trial bench, kept apart from the Delta setups.
DELTA_LAB_LIB_KEY        = 'com.typerig.delta.italiclab'

# - Node tools -----------------------
# Per-master snap target widths {master name: value}. Shared by TR Panel
# Node and TR Toolbar (Glyphs) and FL Node, so a value saved in one
# applies in all.
NODE_COLLINEAR_LIB_KEY   = 'com.typerig.panel.node.tool.collinear'
NODE_MONOLINE_LIB_KEY    = 'com.typerig.panel.node.tool.monoline'

# Per-master keyboard nudge steps {master name: [x, y]}: TR Toolbar
# (Glyphs) keyboard observer, arrow keys move selected nodes by these.
NODE_KEY_STEPS_LIB_KEY   = 'com.typerig.toolbar.node.keysteps'
