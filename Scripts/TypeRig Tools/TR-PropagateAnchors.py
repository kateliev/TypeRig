#FLM: TypeRig: Propagate Anchors
#NOTE: Copy anchors from source glyphs to destination glyphs with table-based UI
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025        (http://www.kateliev.com)
# (C) TypeRig                      (http://www.typerig.com)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os
import json

import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore

from typerig.proxy.fl.gui import QtGui
from typerig.proxy.fl.gui.widgets import getProcessGlyphs
from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.glyph import eGlyph
from typerig.core.base.message import *

# - Init --------------------------------
app_name, app_version = 'TR | Propagate Anchors', '1.5'

# - Anchor Selection Dialog --------------------------------
class dlg_select_anchors(QtGui.QDialog):
	def __init__(self, anchor_info, selected_anchors, parent=None):
		super(dlg_select_anchors, self).__init__(parent)
		
		# - Init
		self.anchor_info = anchor_info  # dict: {anchor_name: exists_on_all_layers}
		self.selected_anchors = set(selected_anchors)
		
		# - Widgets
		self.list_widget = QtGui.QListWidget()
		
		# - Add anchors with checkboxes
		for anchor_name in sorted(self.anchor_info.keys()):
			item = QtGui.QListWidgetItem(anchor_name)
			item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
			
			if anchor_name in self.selected_anchors:
				item.setCheckState(QtCore.Qt.Checked)
			else:
				item.setCheckState(QtCore.Qt.Unchecked)
			
			# - Color based on layer compatibility
			if self.anchor_info[anchor_name]:
				item.setForeground(QtGui.QBrush(QtGui.QColor(0, 150, 0)))
			else:
				item.setForeground(QtGui.QBrush(QtGui.QColor(200, 0, 0)))
			
			self.list_widget.addItem(item)
		
		# - Buttons
		btn_select_all = QtGui.QPushButton('Select All')
		btn_deselect_all = QtGui.QPushButton('Deselect All')
		btn_ok = QtGui.QPushButton('OK')
		btn_cancel = QtGui.QPushButton('Cancel')
		
		btn_select_all.clicked.connect(self.select_all)
		btn_deselect_all.clicked.connect(self.deselect_all)
		btn_ok.clicked.connect(lambda: self.accept())
		btn_cancel.clicked.connect(lambda: self.reject())
		
		# - Layout
		layout_buttons = QtGui.QGridLayout()
		layout_buttons.addWidget(btn_select_all, 0, 0)
		layout_buttons.addWidget(btn_deselect_all, 0, 1)
		layout_buttons.addWidget(btn_ok, 1, 0)
		layout_buttons.addWidget(btn_cancel, 1, 1)
		
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(QtGui.QLabel('Select anchors to copy:'))
		layout_main.addWidget(self.list_widget)
		layout_main.addWidget(QtGui.QLabel('<b>Green:</b> Present in all layers; <b>Red:</b> Not present in all layers\n'))
		layout_main.addLayout(layout_buttons)
		
		self.setLayout(layout_main)
		self.setWindowTitle('Select Anchors')
		self.setMinimumSize(300, 400)
	
	def select_all(self):
		for i in range(self.list_widget.count):
			self.list_widget.item(i).setCheckState(QtCore.Qt.Checked)
	
	def deselect_all(self):
		for i in range(self.list_widget.count):
			self.list_widget.item(i).setCheckState(QtCore.Qt.Unchecked)
	
	def get_selected_anchors(self):
		'''Returns list of selected anchor names'''
		selected = []
		for i in range(self.list_widget.count):
			item = self.list_widget.item(i)
			if item.checkState() == QtCore.Qt.Checked:
				selected.append(item.text())
		return selected


# - Copy Options Dialog --------------------------------
class dlg_copy_options(QtGui.QDialog):
	def __init__(self, options, parent=None):
		super(dlg_copy_options, self).__init__(parent)
		
		# - Init
		self.options = options
		
		# - Widgets
		# -- Location
		self.rad_location_absolute = QtGui.QRadioButton('Absolute')
		self.rad_location_relative = QtGui.QRadioButton('Relative')
		
		if self.options.get('location', 'absolute') == 'absolute':
			self.rad_location_absolute.setChecked(True)
		else:
			self.rad_location_relative.setChecked(True)
		
		# -- Relative mode dropdown
		self.lbl_relative_mode = QtGui.QLabel('Relative to:')
		self.cmb_relative_mode = QtGui.QComboBox()
		self.cmb_relative_mode.addItems(['Advance', 'LSB', 'RSB'])
		
		# Set current relative mode
		relative_mode = self.options.get('relative_mode', 'advance')
		if relative_mode == 'lsb':
			self.cmb_relative_mode.setCurrentIndex(1)
		elif relative_mode == 'rsb':
			self.cmb_relative_mode.setCurrentIndex(2)
		else:
			self.cmb_relative_mode.setCurrentIndex(0)
		
		# Enable/disable based on radio selection
		self.update_relative_mode_state()
		self.rad_location_absolute.toggled.connect(self.update_relative_mode_state)
		self.rad_location_relative.toggled.connect(self.update_relative_mode_state)
		
		# -- Collision handling
		self.rad_collide_overwrite = QtGui.QRadioButton('Overwrite')
		self.rad_collide_rename = QtGui.QRadioButton('Rename')
		
		if self.options.get('collision', 'overwrite') == 'overwrite':
			self.rad_collide_overwrite.setChecked(True)
		else:
			self.rad_collide_rename.setChecked(True)
		
		# -- Rename target
		self.rad_rename_incoming = QtGui.QRadioButton('Incoming')
		self.rad_rename_destination = QtGui.QRadioButton('Destination')
		
		if self.options.get('rename_target', 'incoming') == 'incoming':
			self.rad_rename_incoming.setChecked(True)
		else:
			self.rad_rename_destination.setChecked(True)
		
		# -- Suffix
		self.edt_suffix = QtGui.QLineEdit()
		self.edt_suffix.setText(self.options.get('suffix', '.bak'))
		self.edt_suffix.setPlaceholderText('Examples: .new, .bak, .1')
		
		# - Buttons
		btn_ok = QtGui.QPushButton('OK')
		btn_cancel = QtGui.QPushButton('Cancel')
		
		# Set equal button widths
		btn_width = 100
		btn_ok.setMinimumWidth(btn_width)
		btn_cancel.setMinimumWidth(btn_width)
		
		btn_ok.clicked.connect(lambda: self.accept())
		btn_cancel.clicked.connect(lambda: self.reject())
		
		# - Layout
		grp_location = QtGui.QGroupBox('Location')
		layout_location = QtGui.QVBoxLayout()
		layout_location.addWidget(self.rad_location_absolute)
		layout_location.addWidget(self.rad_location_relative)
		
		# Add relative mode dropdown
		layout_relative_mode = QtGui.QHBoxLayout()
		layout_relative_mode.addSpacing(20)  # Indent
		layout_relative_mode.addWidget(self.lbl_relative_mode)
		layout_relative_mode.addWidget(self.cmb_relative_mode)
		layout_location.addLayout(layout_relative_mode)
		
		grp_location.setLayout(layout_location)
		
		grp_collision = QtGui.QGroupBox('Handle Collision')
		layout_collision = QtGui.QVBoxLayout()
		layout_collision.addWidget(self.rad_collide_overwrite)
		layout_collision.addWidget(self.rad_collide_rename)
		grp_collision.setLayout(layout_collision)
		
		grp_rename = QtGui.QGroupBox('Rename Target')
		layout_rename = QtGui.QVBoxLayout()
		layout_rename.addWidget(self.rad_rename_incoming)
		layout_rename.addWidget(self.rad_rename_destination)
		grp_rename.setLayout(layout_rename)
		
		layout_suffix = QtGui.QHBoxLayout()
		layout_suffix.addWidget(QtGui.QLabel('Suffix:'))
		layout_suffix.addWidget(self.edt_suffix)
		
		layout_buttons = QtGui.QHBoxLayout()
		layout_buttons.addWidget(btn_ok)
		layout_buttons.addWidget(btn_cancel)
		
		layout_main = QtGui.QVBoxLayout()
		layout_main.addWidget(grp_location)
		layout_main.addWidget(grp_collision)
		layout_main.addWidget(grp_rename)
		layout_main.addLayout(layout_suffix)
		layout_main.addLayout(layout_buttons)
		
		self.setLayout(layout_main)
		self.setWindowTitle('Copy Options')
		self.setMinimumWidth(300)
	
	def update_relative_mode_state(self):
		'''Enable/disable relative mode dropdown based on radio selection'''
		is_relative = self.rad_location_relative.isChecked()
		self.lbl_relative_mode.setEnabled(is_relative)
		self.cmb_relative_mode.setEnabled(is_relative)
	
	def get_options(self):
		'''Returns dict with selected options'''
		options = {}
		
		options['location'] = 'absolute' if self.rad_location_absolute.isChecked() else 'relative'
		
		# Get relative mode from dropdown
		if options['location'] == 'relative':
			current_text = self.cmb_relative_mode.currentText
			if current_text == 'LSB':
				options['relative_mode'] = 'lsb'
			elif current_text == 'RSB':
				options['relative_mode'] = 'rsb'
			else:
				options['relative_mode'] = 'advance'
		else:
			options['relative_mode'] = 'advance'  # Default
		
		options['collision'] = 'overwrite' if self.rad_collide_overwrite.isChecked() else 'rename'
		options['rename_target'] = 'incoming' if self.rad_rename_incoming.isChecked() else 'destination'
		options['suffix'] = self.edt_suffix.text.strip()
		
		return options


# - Interface -----------------------------
class dlg_copy_anchors_table(QtGui.QDialog):
	def __init__(self):
		super(dlg_copy_anchors_table, self).__init__()
		
		# - Init
		self.active_font = None
		self.row_data = {}  # Store row data: {row_index: {'anchor_info': {}, 'selected_anchors': [], 'options': {}}}
		
		# - Top Button Row
		self.btn_add_row = QtGui.QPushButton('Add action')
		self.btn_save = QtGui.QPushButton('Save actions')
		self.btn_load = QtGui.QPushButton('Load actions')
		self.btn_execute = QtGui.QPushButton('Execute Actions')
		
		# - Table Widget
		self.table_widget = QtGui.QTableWidget()
		self.table_widget.setColumnCount(5)
		self.table_widget.setHorizontalHeaderLabels(['Source', 'Anchors', 'Destination', 'Options', 'Action'])
		
		# Set column widths
		self.table_widget.setColumnWidth(0, 150)
		self.table_widget.setColumnWidth(1, 200)
		self.table_widget.setColumnWidth(2, 250)
		self.table_widget.setColumnWidth(3, 100)
		self.table_widget.setColumnWidth(4, 80)
		
		# - Connect signals
		self.btn_add_row.clicked.connect(self.action_add_source_dialog)
		self.btn_save.clicked.connect(self.action_save)
		self.btn_load.clicked.connect(self.action_load)
		self.btn_execute.clicked.connect(self.action_execute)
		
		# - Build layouts
		# -- Top button row
		layout_top_buttons = QtGui.QHBoxLayout()
		layout_top_buttons.addWidget(self.btn_add_row)
		layout_top_buttons.addWidget(self.btn_save)
		layout_top_buttons.addWidget(self.btn_load)
		layout_top_buttons.addWidget(self.btn_execute)
		
		# -- Main layout
		layout_main = QtGui.QVBoxLayout()
		layout_main.addLayout(layout_top_buttons)
		layout_main.addWidget(self.table_widget)
		
		# - Set Widget
		self.setLayout(layout_main)
		self.setWindowTitle('%s %s' %(app_name, app_version))
		self.setGeometry(300, 300, 900, 600)
		self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
		
		# - Initialize with one empty row
		if self.get_active_font():
			self.add_empty_row()
		
		self.show()
	
	# - Helper Functions --------------------------------
	def get_active_font(self):
		'''Get current font'''
		self.active_font = pFont()
		return self.active_font is not None
	
	def get_anchor_info(self, glyph_name):
		'''Get anchor information for a glyph
		Returns dict with anchor names as keys and layer availability as values
		'''
		if not self.get_active_font():
			return {}
		
		if not self.active_font.hasGlyph(glyph_name):
			return {}
		
		glyph = self.active_font.glyph(glyph_name, extend=eGlyph)
		all_masters = self.active_font.masters()
		
		# Collect all unique anchor names across all layers
		all_anchors = set()
		for master in all_masters:
			layer = glyph.layer(master)
			if layer is not None:
				for anchor in glyph.anchors(master):
					all_anchors.add(anchor.name)
		
		# Check which anchors exist on all layers
		anchor_info = {}
		for anchor_name in all_anchors:
			exists_on_all = True
			for master in all_masters:
				layer = glyph.layer(master)
				if layer is None:
					exists_on_all = False
					break
				
				found = False
				for anchor in glyph.anchors(master):
					if anchor.name == anchor_name:
						found = True
						break
				
				if not found:
					exists_on_all = False
					break
			
			anchor_info[anchor_name] = exists_on_all
		
		return anchor_info
	
	def create_source_cell_widget(self, row, glyph_name=''):
		'''Create widget for source cell with editable field and pick button'''
		widget = QtGui.QWidget()
		layout = QtGui.QVBoxLayout()
		layout.setContentsMargins(2, 2, 2, 2)
		layout.setSpacing(2)
		
		# Editable text edit (multi-line like destination)
		edt_source = QtGui.QTextEdit()
		if glyph_name:
			edt_source.setPlainText('/' + glyph_name)
		edt_source.setPlaceholderText('/glyphname')
		edt_source.setMaximumHeight(50)
		
		# Pick button
		btn_pick = QtGui.QPushButton('Pick source')
		btn_pick.clicked.connect(lambda: self.action_pick_source_for_row(row))
		
		layout.addWidget(edt_source)
		layout.addWidget(btn_pick)
		widget.setLayout(layout)
		
		return widget
	
	def create_destination_cell_widget(self, row):
		'''Create widget for destination cell with editable field and pick button'''
		widget = QtGui.QWidget()
		layout = QtGui.QVBoxLayout()
		layout.setContentsMargins(2, 2, 2, 2)
		layout.setSpacing(2)
		
		# Editable text edit for multiple glyphs
		edt_dest = QtGui.QTextEdit()
		edt_dest.setPlaceholderText('/a/b/c')
		edt_dest.setMaximumHeight(50)
		
		# Pick button
		btn_pick = QtGui.QPushButton('Pick destination')
		btn_pick.clicked.connect(lambda: self.action_pick_destination_for_row(row))
		
		layout.addWidget(edt_dest)
		layout.addWidget(btn_pick)
		widget.setLayout(layout)
		
		return widget
	
	def create_anchor_cell_widget(self, row, anchor_info, selected_anchors):
		'''Create widget for anchor cell with editable field and button'''
		# Store data in row_data dict
		if row not in self.row_data:
			self.row_data[row] = {}
		self.row_data[row]['anchor_info'] = anchor_info
		self.row_data[row]['selected_anchors'] = selected_anchors
		
		widget = QtGui.QWidget()
		layout = QtGui.QVBoxLayout()
		layout.setContentsMargins(2, 2, 2, 2)
		layout.setSpacing(2)
		
		# Editable text edit for comma-separated anchor names
		edt_anchors = QtGui.QTextEdit()
		edt_anchors.setPlaceholderText('top, bottom, left')
		edt_anchors.setMaximumHeight(50)
		
		if selected_anchors:
			edt_anchors.setPlainText(', '.join(selected_anchors))
		
		# Button to select anchors
		btn_select = QtGui.QPushButton('Select Anchors')
		btn_select.clicked.connect(lambda: self.action_select_anchors(row))
		
		layout.addWidget(edt_anchors)
		layout.addWidget(btn_select)
		widget.setLayout(layout)
		
		return widget
	
	def create_options_cell_widget(self, row, options):
		'''Create widget for options cell with button and info label'''
		# Store options in row_data dict
		if row not in self.row_data:
			self.row_data[row] = {}
		self.row_data[row]['options'] = options
		
		widget = QtGui.QWidget()
		layout = QtGui.QVBoxLayout()
		layout.setContentsMargins(2, 2, 2, 2)
		layout.setSpacing(2)
		
		# Label showing current options
		lbl_options = QtGui.QLabel()
		lbl_options.setWordWrap(True)
		lbl_options.setStyleSheet('font-size: 9px; color: #666;')
		self.update_options_label(lbl_options, options)
		
		# Button to edit options
		btn_options = QtGui.QPushButton('Copy Options')
		btn_options.clicked.connect(lambda: self.action_copy_options(row))
		
		layout.addWidget(lbl_options)
		layout.addWidget(btn_options)
		widget.setLayout(layout)
		
		return widget
	
	def update_options_label(self, label, options):
		'''Update options label with compact info'''
		location = options.get('location', 'absolute')
		
		if location == 'relative':
			rel_mode = options.get('relative_mode', 'advance')
			if rel_mode == 'lsb':
				location_text = 'Rel:LSB'
			elif rel_mode == 'rsb':
				location_text = 'Rel:RSB'
			else:
				location_text = 'Rel:Adv'
		else:
			location_text = 'Abs'
		
		collision = 'Rename' if options.get('collision') == 'rename' else 'Overwrite'
		
		opt_text = '{}, {}'.format(location_text, collision)
		
		if options.get('collision') == 'rename':
			target = 'Inc' if options.get('rename_target') == 'incoming' else 'Dst'
			suffix = options.get('suffix', '.bak')
			opt_text += '\n({}, {})'.format(target, suffix)
		
		label.setText(opt_text)
	
	def create_delete_cell_widget(self, row):
		'''Create widget for delete cell with button'''
		btn_delete = QtGui.QPushButton('Delete')
		btn_delete.clicked.connect(lambda: self.action_delete_row(row))
		
		return btn_delete
	
	def update_anchor_field(self, row):
		'''Update the anchor field in a row'''
		if row not in self.row_data:
			return
		
		widget = self.table_widget.cellWidget(row, 1)
		if widget:
			# Find the text edit widget
			text_edit = widget.findChild(QtGui.QTextEdit)
			if text_edit:
				selected = self.row_data[row].get('selected_anchors', [])
				if selected:
					text_edit.setPlainText(', '.join(selected))
				else:
					text_edit.setPlainText('')
	
	# - Action Functions --------------------------------
	def add_empty_row(self):
		'''Add an empty row to the table'''
		row = self.table_widget.rowCount
		self.table_widget.insertRow(row)
		
		# Column 0: Source (widget with field and pick button)
		source_widget = self.create_source_cell_widget(row)
		self.table_widget.setCellWidget(row, 0, source_widget)
		
		# Column 1: Anchors (editable field with button)
		anchor_widget = self.create_anchor_cell_widget(row, {}, [])
		self.table_widget.setCellWidget(row, 1, anchor_widget)
		
		# Column 2: Destinations (widget with field and pick button)
		dest_widget = self.create_destination_cell_widget(row)
		self.table_widget.setCellWidget(row, 2, dest_widget)
		
		# Column 3: Options (button) - with default options
		default_options = {
			'location': 'absolute',
			'collision': 'overwrite',
			'rename_target': 'incoming',
			'suffix': '.bak',
			'relative_mode': 'advance'
		}
		options_widget = self.create_options_cell_widget(row, default_options)
		self.table_widget.setCellWidget(row, 3, options_widget)
		
		# Column 4: Actions (delete button)
		delete_widget = self.create_delete_cell_widget(row)
		self.table_widget.setCellWidget(row, 4, delete_widget)
		
		# Set row height
		self.table_widget.setRowHeight(row, 80)
		
		return row
	
	def action_add_source_dialog(self):
		'''Add a new empty row'''
		self.add_empty_row()
		output(0, app_name, 'Added new copy action.')
	
	def action_pick_source_for_row(self, row):
		'''Pick current glyph as source for specific row'''
		if not self.get_active_font():
			output(2, app_name, 'No active font!')
			return
		
		current_glyph = fl6.CurrentGlyph()
		if current_glyph is None:
			output(2, app_name, 'No glyph selected!')
			return
		
		glyph_name = current_glyph.name
		
		# Update source widget
		source_widget = self.table_widget.cellWidget(row, 0)
		if source_widget:
			text_edit = source_widget.findChild(QtGui.QTextEdit)
			if text_edit:
				text_edit.setPlainText('/' + glyph_name)
		
		output(0, app_name, 'Source picked for row {}: {}'.format(row + 1, glyph_name))
	
	def action_pick_destination_for_row(self, row):
		'''Pick selected glyphs as destinations for specific row'''
		if not self.get_active_font():
			output(2, app_name, 'No active font!')
			return
		
		selected_glyphs = getProcessGlyphs(mode=2)  # mode 2 = selected glyphs
		if not selected_glyphs:
			output(2, app_name, 'No glyphs selected!')
			return
		
		# Update destination widget
		dest_widget = self.table_widget.cellWidget(row, 2)
		if dest_widget:
			text_edit = dest_widget.findChild(QtGui.QTextEdit)
			if text_edit:
				glyph_names = ['/' + g.name for g in selected_glyphs]
				text_edit.setPlainText(''.join(glyph_names))
		
		output(0, app_name, 'Picked {} destinations for action {}'.format(len(selected_glyphs), row + 1))
	
	def action_select_anchors(self, row):
		'''Open dialog to select anchors for a row'''
		if not self.get_active_font():
			output(2, app_name, 'No active font!')
			return
		
		# Get source glyph name from the table
		source_widget = self.table_widget.cellWidget(row, 0)
		if not source_widget:
			output(2, app_name, 'No source for action found!')
			return
		
		text_edit = source_widget.findChild(QtGui.QTextEdit)
		if not text_edit:
			output(2, app_name, 'No source field found!')
			return
		
		source_name = text_edit.toPlainText().strip().lstrip('/')
		if not source_name:
			output(2, app_name, 'No source glyph specified!')
			return
		
		# Check if glyph exists
		if not self.active_font.hasGlyph(source_name):
			output(2, app_name, 'Source glyph not found: {}'.format(source_name))
			return
		
		# Get anchor info from the source glyph
		anchor_info = self.get_anchor_info(source_name)
		
		if not anchor_info:
			output(1, app_name, 'No anchors found in glyph: {}'.format(source_name))
			return
		
		# Get currently selected anchors from the text field
		anchor_widget = self.table_widget.cellWidget(row, 1)
		current_anchors = []
		if anchor_widget:
			anchor_text_edit = anchor_widget.findChild(QtGui.QTextEdit)
			if anchor_text_edit:
				anchor_text = anchor_text_edit.toPlainText().strip()
				current_anchors = [a.strip() for a in anchor_text.split(',') if a.strip()]
		
		# If no anchors selected, select all available
		if not current_anchors:
			current_anchors = list(anchor_info.keys())
		
		# Store anchor info in row_data
		if row not in self.row_data:
			self.row_data[row] = {}
		self.row_data[row]['anchor_info'] = anchor_info
		self.row_data[row]['selected_anchors'] = current_anchors
		
		# Open dialog
		dialog = dlg_select_anchors(anchor_info, current_anchors, self)
		if dialog.exec_():
			# Update selected anchors in row_data
			self.row_data[row]['selected_anchors'] = dialog.get_selected_anchors()
			self.update_anchor_field(row)
			output(0, app_name, 'Anchors updated for action {}'.format(row + 1))
	
	def action_copy_options(self, row):
		'''Open dialog to set copy options for a row'''
		if row not in self.row_data:
			return
		
		options = self.row_data[row].get('options', {})
		
		# Open dialog
		dialog = dlg_copy_options(options, self)
		if dialog.exec_():
			# Update options in row_data
			self.row_data[row]['options'] = dialog.get_options()
			
			# Update the options label
			widget = self.table_widget.cellWidget(row, 3)
			if widget:
				label = widget.findChild(QtGui.QLabel)
				if label:
					self.update_options_label(label, self.row_data[row]['options'])
			
			output(0, app_name, 'Options updated for action {}'.format(row + 1))
	
	def action_delete_row(self, row):
		'''Delete a row from the table'''
		# Remove from table
		self.table_widget.removeRow(row)
		
		# Clean up row_data - reindex all rows after the deleted one
		new_row_data = {}
		for old_row, data in self.row_data.items():
			if old_row < row:
				new_row_data[old_row] = data
			elif old_row > row:
				new_row_data[old_row - 1] = data
		self.row_data = new_row_data
		
		output(0, app_name, 'Action {} removed'.format(row + 1))
	
	def action_save(self):
		'''Save table data to JSON file'''
		if self.table_widget.rowCount == 0:
			output(2, app_name, 'No data to save!')
			return
		
		# Open file dialog
		file_path = QtGui.QFileDialog.getSaveFileName(self, 'Save Copy Actions Data', '', 'JSON Files (*.json)')
		
		if not file_path:
			return
		
		# Collect all table data
		table_data = []
		
		for row in range(self.table_widget.rowCount):
			row_info = {}
			
			# Get source
			source_widget = self.table_widget.cellWidget(row, 0)
			if source_widget:
				text_edit = source_widget.findChild(QtGui.QTextEdit)
				if text_edit:
					row_info['source'] = text_edit.toPlainText().strip()
			
			# Get anchors
			anchor_widget = self.table_widget.cellWidget(row, 1)
			if anchor_widget:
				anchor_text_edit = anchor_widget.findChild(QtGui.QTextEdit)
				if anchor_text_edit:
					row_info['anchors'] = anchor_text_edit.toPlainText().strip()
			
			# Get destinations
			dest_widget = self.table_widget.cellWidget(row, 2)
			if dest_widget:
				dest_text_edit = dest_widget.findChild(QtGui.QTextEdit)
				if dest_text_edit:
					row_info['destinations'] = dest_text_edit.toPlainText().strip()
			
			# Get options
			if row in self.row_data:
				row_info['options'] = self.row_data[row].get('options', {})
			else:
				row_info['options'] = {
					'location': 'absolute',
					'collision': 'overwrite',
					'rename_target': 'incoming',
					'suffix': '.bak',
					'relative_mode': 'advance'
				}
			
			table_data.append(row_info)
		
		# Save to JSON
		try:
			with open(file_path, 'w') as f:
				json.dump(table_data, f, indent=2)
			output(0, app_name, 'Saved {} actions to: {}'.format(len(table_data), file_path))
		except Exception as e:
			output(3, app_name, 'Error saving file: {}'.format(str(e)))
	
	def action_load(self):
		'''Load table data from JSON file'''
		# Open file dialog
		file_path = QtGui.QFileDialog.getOpenFileName(self, 'Load Copy Actions Data', '', 'JSON Files (*.json)')
		
		if not file_path:
			return
		
		# Load from JSON
		try:
			with open(file_path, 'r') as f:
				table_data = json.load(f)
		except Exception as e:
			output(3, app_name, 'Error loading file: {}'.format(str(e)))
			return
		
		# Clear existing table
		while self.table_widget.rowCount > 0:
			self.table_widget.removeRow(0)
		self.row_data = {}
		
		# Populate table with loaded data
		for row_info in table_data:
			row = self.add_empty_row()
			
			# Set source
			if 'source' in row_info:
				source_widget = self.table_widget.cellWidget(row, 0)
				if source_widget:
					text_edit = source_widget.findChild(QtGui.QTextEdit)
					if text_edit:
						text_edit.setPlainText(row_info['source'])
			
			# Set anchors
			if 'anchors' in row_info:
				anchor_widget = self.table_widget.cellWidget(row, 1)
				if anchor_widget:
					anchor_text_edit = anchor_widget.findChild(QtGui.QTextEdit)
					if anchor_text_edit:
						anchor_text_edit.setPlainText(row_info['anchors'])
			
			# Set destinations
			if 'destinations' in row_info:
				dest_widget = self.table_widget.cellWidget(row, 2)
				if dest_widget:
					dest_text_edit = dest_widget.findChild(QtGui.QTextEdit)
					if dest_text_edit:
						dest_text_edit.setPlainText(row_info['destinations'])
			
			# Set options
			if 'options' in row_info:
				self.row_data[row] = {'options': row_info['options']}
				
				# Update options label
				widget = self.table_widget.cellWidget(row, 3)
				if widget:
					label = widget.findChild(QtGui.QLabel)
					if label:
						self.update_options_label(label, row_info['options'])
		
		output(0, app_name, 'Loaded {} actions from: {}'.format(len(table_data), file_path))
	
	def action_execute(self):
		'''Execute anchor copying based on table data'''
		if not self.get_active_font():
			output(2, app_name, 'No active font!')
			return
		
		if self.table_widget.rowCount == 0:
			output(2, app_name, 'No rows in table!')
			return
		
		# Collect all copy operations
		operations = []
		
		for row in range(self.table_widget.rowCount):
			# Get source from widget
			source_widget = self.table_widget.cellWidget(row, 0)
			if not source_widget:
				continue
			
			text_edit = source_widget.findChild(QtGui.QTextEdit)
			if not text_edit:
				continue
			
			source_name = text_edit.toPlainText().strip().lstrip('/')
			if not source_name:
				continue
			
			# Get selected anchors from anchors field (comma-separated)
			anchor_widget = self.table_widget.cellWidget(row, 1)
			if not anchor_widget:
				continue
			
			anchor_text_edit = anchor_widget.findChild(QtGui.QTextEdit)
			if not anchor_text_edit:
				continue
			
			anchor_text = anchor_text_edit.toPlainText().strip()
			selected_anchors = [a.strip() for a in anchor_text.split(',') if a.strip()]
			
			if not selected_anchors:
				continue
			
			# Get destinations from widget
			dest_widget = self.table_widget.cellWidget(row, 2)
			if not dest_widget:
				continue
			
			dest_text_edit = dest_widget.findChild(QtGui.QTextEdit)
			if not dest_text_edit:
				continue
			
			dest_text = dest_text_edit.toPlainText().strip()
			dest_glyphs = [g.strip().lstrip('/') for g in dest_text.split('/') if g.strip()]
			
			# Get options from row_data
			options = self.row_data.get(row, {}).get('options', {
				'location': 'absolute',
				'collision': 'overwrite',
				'rename_target': 'incoming',
				'suffix': '.bak',
				'relative_mode': 'advance'
			})
			
			if source_name and selected_anchors and dest_glyphs:
				operations.append({
					'source': source_name,
					'anchors': selected_anchors,
					'destinations': dest_glyphs,
					'options': options
				})
		
		if not operations:
			output(2, app_name, 'No valid operations to execute!')
			return
		
		# Execute operations
		total_copied = 0
		
		for op in operations:
			if not self.active_font.hasGlyph(op['source']):
				output(1, app_name, 'Source glyph not found: {}'.format(op['source']))
				continue
			
			source_glyph = self.active_font.glyph(op['source'], extend=eGlyph)
			options = op['options']
			
			for dest_name in op['destinations']:
				if not self.active_font.hasGlyph(dest_name):
					output(1, app_name, 'Destination glyph not found: {}'.format(dest_name))
					continue
				
				dest_glyph = self.active_font.glyph(dest_name, extend=eGlyph)
				
				# Process all layers
				for layer_name in self.active_font.masters():
					if source_glyph.layer(layer_name) is None or dest_glyph.layer(layer_name) is None:
						continue
					
					# Copy selected anchors
					for anchor_name in op['anchors']:
						# Find anchor in source
						found_anchor = None
						for anchor in source_glyph.anchors(layer_name):
							if anchor.name == anchor_name:
								found_anchor = anchor
								break
						
						if found_anchor is None:
							output(1, app_name, 'Anchor not found in source: {}; Glyph: {}; Layer: {}'.format(anchor_name, op['source'], layer_name))
							continue
						
						tmp_anchor = found_anchor.clone()
						
						# Handle relative positioning
						if options.get('location') == 'relative':
							try:
								relative_mode = options.get('relative_mode', 'advance')
								
								if relative_mode == 'lsb':
									# LSB mode - keep same distance from left side bearing (effectively absolute)
									# LSB is at x=0, so the anchor position stays the same
									pass  # No change needed, position stays absolute
								
								elif relative_mode == 'rsb':
									# RSB mode - keep same distance from right side bearing
									src_advance = source_glyph.getAdvance(layer_name)
									dst_advance = dest_glyph.getAdvance(layer_name)
									
									# Calculate distance from RSB in source
									distance_from_rsb = src_advance - tmp_anchor.point.x()
									
									# Apply same distance from RSB in destination
									new_x = dst_advance - distance_from_rsb
									tmp_anchor.point = QtCore.QPointF(new_x, tmp_anchor.point.y())
								
								else:  # advance mode (default)
									# Proportional to advance width
									src_advance = source_glyph.getAdvance(layer_name)
									dst_advance = dest_glyph.getAdvance(layer_name)
									
									if src_advance > 0:
										location_prop = tmp_anchor.point.x() / src_advance
										tmp_anchor.point = QtCore.QPointF(location_prop * dst_advance, tmp_anchor.point.y())
									else:
										output(1, app_name, 'Source has zero advance! Fallback to absolute. Glyph: {}; Layer: {}'.format(op['source'], layer_name))
							
							except Exception as e:
								output(1, app_name, 'Error calculating relative position: {}'.format(str(e)))
						
						# Handle collision
						existing = dest_glyph.layer(layer_name).findAnchor(tmp_anchor.name)
						
						if existing is not None:
							if options.get('collision') == 'rename':
								# Rename mode
								if options.get('rename_target') == 'incoming':
									tmp_anchor.name += options.get('suffix', '.bak')
								else:
									# Rename destination
									existing.name += options.get('suffix', '.bak')
							else:
								# Overwrite mode
								dest_glyph.layer(layer_name).removeAnchor(existing)
						
						# Add anchor
						dest_glyph.layer(layer_name).addAnchor(tmp_anchor)
						total_copied += 1
				
				# Update destination glyph
				dest_glyph.update()
		
		self.active_font.updateObject(self.active_font.fl, 'Copied anchors')
		output(0, app_name, 'Executed! Total anchors copied: {}'.format(total_copied))

# - RUN ------------------------------
dialog = dlg_copy_anchors_table()
