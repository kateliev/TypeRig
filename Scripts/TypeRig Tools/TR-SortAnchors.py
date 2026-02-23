#FLM: TypeRig: Sort Anchors
#NOTE: Sort anchor order across masters - by reference master or alphabetically
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026        (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.core.base.message import *

# - Init --------------------------------
app_name, app_version = 'TR | Sort Anchors', '1.0'

# - Interface -----------------------------
class dlg_sort_anchors(QtGui.QDialog):
	def __init__(self):
		super(dlg_sort_anchors, self).__init__()

		# - Init
		self.active_font = None

		# - Mode selection
		self.rad_mode_reference = QtGui.QRadioButton('Reference master')
		self.rad_mode_alpha = QtGui.QRadioButton('Alphabetical')
		self.rad_mode_reference.setChecked(True)

		grp_mode = QtGui.QGroupBox('Sort mode')
		layout_mode = QtGui.QVBoxLayout()
		layout_mode.addWidget(self.rad_mode_reference)
		layout_mode.addWidget(self.rad_mode_alpha)
		grp_mode.setLayout(layout_mode)

		# - Reference master selector
		self.lbl_master = QtGui.QLabel('Reference master:')
		self.cmb_master = QtGui.QComboBox()

		layout_master = QtGui.QHBoxLayout()
		layout_master.addWidget(self.lbl_master)
		layout_master.addWidget(self.cmb_master)

		# - Glyph scope
		self.rad_scope_all = QtGui.QRadioButton('All glyphs')
		self.rad_scope_selected = QtGui.QRadioButton('Selected glyphs')
		self.rad_scope_all.setChecked(True)

		grp_scope = QtGui.QGroupBox('Glyph scope')
		layout_scope = QtGui.QVBoxLayout()
		layout_scope.addWidget(self.rad_scope_all)
		layout_scope.addWidget(self.rad_scope_selected)
		grp_scope.setLayout(layout_scope)

		# - Options
		self.chk_verbose = QtGui.QCheckBox('Report glyphs with missing anchors')
		self.chk_verbose.setChecked(True)

		grp_options = QtGui.QGroupBox('Options')
		layout_options = QtGui.QVBoxLayout()
		layout_options.addWidget(self.chk_verbose)
		grp_options.setLayout(layout_options)

		# - Buttons
		self.btn_refresh = QtGui.QPushButton('Refresh font')
		self.btn_execute = QtGui.QPushButton('Sort Anchors')

		self.btn_refresh.clicked.connect(self.action_refresh)
		self.btn_execute.clicked.connect(self.action_execute)

		layout_buttons = QtGui.QHBoxLayout()
		layout_buttons.addWidget(self.btn_refresh)
		layout_buttons.addWidget(self.btn_execute)

		# - Connect mode radio to enable/disable master selector
		self.rad_mode_reference.toggled.connect(self.update_mode_state)
		self.rad_mode_alpha.toggled.connect(self.update_mode_state)

		# - Main layout
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(grp_mode)
		layout_main.addLayout(layout_master)
		layout_main.addWidget(grp_scope)
		layout_main.addWidget(grp_options)
		layout_main.addLayout(layout_buttons)

		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' % (app_name, app_version))
		self.setMinimumWidth(320)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

		# - Populate
		if self.get_active_font():
			self.populate_masters()

		self.show()

	# - Helpers --------------------------------
	def get_active_font(self):
		'''Get current font'''
		self.active_font = pFont()
		return self.active_font is not None

	def populate_masters(self):
		'''Populate master dropdown from active font'''
		self.cmb_master.clear()
		for master in self.active_font.masters():
			self.cmb_master.addItem(master)

	def update_mode_state(self):
		'''Enable/disable master selector based on mode'''
		is_reference = self.rad_mode_reference.isChecked()
		self.lbl_master.setEnabled(is_reference)
		self.cmb_master.setEnabled(is_reference)

	def get_glyphs(self):
		'''Return list of glyphs to process based on scope selection'''
		if self.rad_scope_selected.isChecked():
			return getProcessGlyphs(mode=2)
		else:
			return [self.active_font.glyph(name, extend=eGlyph) for name in self.active_font.glyphs()]

	def reorder_anchors(self, glyph, layer_name, ordered_names):
		'''Remove all anchors from a layer and re-add them in the given order.
		Anchors not present in ordered_names are appended at the end in original order.
		'''
		layer = glyph.layer(layer_name)
		if layer is None:
			return

		# Snapshot current anchors by name
		current_anchors = {a.name: a.clone() for a in glyph.anchors(layer_name)}

		if not current_anchors:
			return

		# Build final order: reference order first, then any extras not in reference
		extras = [name for name in current_anchors if name not in ordered_names]
		final_order = [name for name in ordered_names if name in current_anchors] + extras

		# No change needed if order is already correct
		current_order = list(current_anchors.keys())
		if current_order == final_order:
			return

		# Remove all anchors from layer
		for anchor in list(glyph.anchors(layer_name)):
			layer.removeAnchor(anchor)

		# Re-add in desired order
		for name in final_order:
			layer.addAnchor(current_anchors[name])

	# - Actions --------------------------------
	def action_refresh(self):
		'''Refresh font and master list'''
		if self.get_active_font():
			self.populate_masters()
			output(0, app_name, 'Font refreshed.')

	def action_execute(self):
		'''Sort anchors across masters'''
		if not self.get_active_font():
			output(2, app_name, 'No active font!')
			return

		all_masters = self.active_font.masters()
		glyphs = self.get_glyphs()
		verbose = self.chk_verbose.isChecked()
		is_reference_mode = self.rad_mode_reference.isChecked()
		reference_master = self.cmb_master.currentText

		if not glyphs:
			output(2, app_name, 'No glyphs to process!')
			return

		glyphs_sorted = 0
		glyphs_skipped = 0

		for glyph_obj in glyphs:
			# Resolve to eGlyph if needed
			if not isinstance(glyph_obj, eGlyph):
				glyph_obj = self.active_font.glyph(glyph_obj.name, extend=eGlyph)

			glyph_name = glyph_obj.name

			# --- Verbose: check for missing anchors across masters ---
			if verbose:
				# Collect all anchor names per master
				master_anchors = {}
				for master in all_masters:
					layer = glyph_obj.layer(master)
					if layer is not None:
						master_anchors[master] = set(a.name for a in glyph_obj.anchors(master))
					else:
						master_anchors[master] = set()

				all_anchor_names = set()
				for names in master_anchors.values():
					all_anchor_names.update(names)

				if all_anchor_names:
					for anchor_name in sorted(all_anchor_names):
						missing_in = [m for m in all_masters if anchor_name not in master_anchors[m]]
						if missing_in:
							output(1, app_name, 'Missing anchor [{}] in glyph [{}] | Masters: {}'.format(
								anchor_name, glyph_name, ', '.join(missing_in)))

			# --- Determine sort order ---
			if is_reference_mode:
				# Get anchor order from the reference master
				ref_layer = glyph_obj.layer(reference_master)
				if ref_layer is None:
					output(1, app_name, 'Reference master layer missing for glyph: {}'.format(glyph_name))
					glyphs_skipped += 1
					continue

				ordered_names = [a.name for a in glyph_obj.anchors(reference_master)]

				if not ordered_names:
					# Nothing to sort if reference has no anchors
					continue

				# Apply reference order to all other masters
				for master in all_masters:
					if master == reference_master:
						continue
					self.reorder_anchors(glyph_obj, master, ordered_names)

			else:
				# Alphabetical: collect all unique anchor names across all masters, sort them
				all_anchor_names = set()
				for master in all_masters:
					if glyph_obj.layer(master) is not None:
						for a in glyph_obj.anchors(master):
							all_anchor_names.add(a.name)

				if not all_anchor_names:
					continue

				ordered_names = sorted(all_anchor_names)

				# Apply alphabetical order to all masters
				for master in all_masters:
					self.reorder_anchors(glyph_obj, master, ordered_names)

			glyph_obj.update()
			glyphs_sorted += 1

		self.active_font.updateObject(self.active_font.fl, 'Sort anchors')

		mode_label = 'reference [{}]'.format(reference_master) if is_reference_mode else 'alphabetical'
		output(0, app_name, 'Done! Mode: {}; Glyphs processed: {}; Skipped: {}'.format(
			mode_label, glyphs_sorted, glyphs_skipped))


# - RUN ------------------------------
dialog = dlg_sort_anchors()
