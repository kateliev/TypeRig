#FLM: TR: Symbol Explorer
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2026			(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

from __future__ import absolute_import, print_function
import os
import re
from pathlib import Path

import fontlab as fl6
from PythonQt import QtCore, QtGui

from typerig.proxy.fl.objects.font import pFont
from typerig.proxy.fl.objects.node import eNodesContainer
from typerig.core.objects.transform import TransformOrigin
from typerig.proxy.fl.objects.glyph import eGlyph

from typerig.core.objects.glyph import Glyph
from typerig.core.objects.layer import Layer
from typerig.core.objects.shape import Shape
from typerig.core.objects.contour import Contour
from typerig.core.objects.node import Node

from typerig.core.base.message import *
from typerig.proxy.fl.actions.node import TRNodeActionCollector
from typerig.proxy.fl.gui.widgets import getTRIconFontPath, CustomPushButton, CustomLabel
from typerig.proxy.fl.gui.styles import css_tr_button, css_tr_button_dark
from typerig.proxy.fl.gui.drawing import TRDrawIcon

# - Init --------------------------------------------
app_name, app_version = 'TypeRig | Symbol Explorer', '1.5'

pLayers = (True, True, False, False)
pMode = 0

delta_app_id_key = 'com.typerig.delta.machine.axissetup'
delta_axis_group_name = 'Virtual Axis'
base_layer = 'Regular'

# - Helpers --------------------------------------------
def flNodes_to_trContour(fl_nodes, is_closed):
	tr_nodes = []
	for fl_node in fl_nodes:
		tr_node = Node(fl_node.x, fl_node.y, type=fl_node.type, smooth=fl_node.smooth)
		tr_nodes.append(tr_node)
	return Contour(tr_nodes, closed=is_closed, proxy=False)

def trNodes_to_flContour(tr_nodes, is_closed):
	fl_nodes = []
	for tr_node in tr_nodes:
		fl_node = fl6.flNode(QtCore.QPointF(tr_node.x, tr_node.y), nodeType=tr_node.type)
		fl_node.smooth = tr_node.smooth
		fl_nodes.append(fl_node)
	
	fl_contour = fl6.flContour(fl_nodes, closed=is_closed)
	fl_contour_nodes = fl_contour.nodes()
	for nid in range(len(fl_contour_nodes)):
		if tr_nodes[nid].smooth:
			fl_contour_nodes[nid].smooth = True
	return fl_contour

def _fl_contour_to_qpath(fl_contour):
	return fl_contour.path()

# - Parts Contour Delegate ------------------------------------
_CONTOUR_COLORS = [
	QtGui.QColor(220, 70, 70),		# red
	QtGui.QColor(60, 140, 220),		# blue
	QtGui.QColor(60, 190, 90),		# green
	QtGui.QColor(220, 170, 40),		# amber
	QtGui.QColor(170, 70, 220),		# purple
	QtGui.QColor(220, 130, 50),		# orange
	QtGui.QColor(50, 195, 195),		# cyan
	QtGui.QColor(220, 90, 155),		# pink
]

class ContourPartsDelegate(QtGui.QStyledItemDelegate):
	def __init__(self, parent=None):
		QtGui.QStyledItemDelegate.__init__(self, parent)
		self.padding = 4
		self._path_data = {}

	def sizeHint(self, option, index):
		view = option.widget
		if view is not None:
			icon_size = view.iconSize
			if icon_size.width() > 0:
				return QtCore.QSize(icon_size.width(), icon_size.width())
		return QtCore.QSize(64, 64)

	def paint(self, painter, option, index):
		rect = option.rect
		row = index.row()
		model_id = id(index.model())
		
		if option.state & QtGui.QStyle.State_Selected:
			painter.fillRect(rect, option.palette.highlight())
		else:
			painter.fillRect(rect, QtCore.Qt.white)
		
		paths_data = self._path_data.get(model_id, [])
		if row >= len(paths_data):
			return
		
		all_paths, highlight_path_idx = paths_data[row]
		
		view = option.widget
		if view is not None:
			cell_size = view.iconSize.width()
		else:
			cell_size = 64
		icon_pad = self.padding
		
		if not all_paths:
			return
		
		all_bbox = all_paths[0].boundingRect()
		for path in all_paths[1:]:
			all_bbox = all_bbox.united(path.boundingRect())
		
		if all_bbox.width() == 0 or all_bbox.height() == 0:
			return
		
		glyph_w, glyph_h = all_bbox.width(), all_bbox.height()
		scale = (cell_size - icon_pad * 2) / max(glyph_w, glyph_h)
		
		glyph_cx = all_bbox.x() + glyph_w / 2.0
		glyph_cy = all_bbox.y() + glyph_h / 2.0
		cell_cx = rect.x() + cell_size / 2.0
		cell_cy = rect.y() + cell_size / 2.0
		
		tx = cell_cx - glyph_cx * scale
		ty = cell_cy + glyph_cy * scale
		
		t = QtGui.QTransform()
		t.translate(tx, ty)
		t.scale(scale, -scale)
		
		painter.save()
		painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
		painter.setTransform(t)
		
		pen_w = max(0.5, 1.0 / scale)
		gray = QtGui.QColor(225, 225, 225)
		gray_brush = QtGui.QBrush(gray)
		gray_pen = QtGui.QPen(gray, pen_w)

		for i, path in enumerate(all_paths):
			if i == highlight_path_idx:
				continue
			painter.setBrush(gray_brush)
			painter.setPen(gray_pen)
			painter.drawPath(path)

		if highlight_path_idx < len(all_paths):
			color = _CONTOUR_COLORS[highlight_path_idx % len(_CONTOUR_COLORS)]
			painter.setBrush(QtGui.QBrush(color))
			painter.setPen(QtGui.QPen(color, pen_w))
			painter.drawPath(all_paths[highlight_path_idx])
		
		painter.restore()


# ============================================================================
# Symbol Explorer Core - Tag and Category based retrieval
# ============================================================================

class SymbolCore:
	def __init__(self, tags_path=None, category_path=None):
		self.tags_path = None
		self.category_path = None
		self.tags_data = {}
		self.category_data = {}
		self.icon_to_tags = {}
		self.tag_to_icons = {}
		self.category_to_icons = {}
		
		if tags_path:
			self.load_tags(tags_path)
		if category_path:
			self.load_categories(category_path)

	def load_tags(self, tags_path):
		self.tags_path = Path(tags_path)
		if not self.tags_path.exists():
			output(3, app_name, 'Tags file not found: %s' % str(self.tags_path))
			return False
		
		self.tags_data = {}
		self.icon_to_tags = {}
		self.tag_to_icons = {}
		
		with open(str(self.tags_path), 'r', encoding='utf-8') as f:
			content = f.read()
		
		current_tag = None
		for line in content.split('\n'):
			line = line.strip()
			if line.startswith('tag {'):
				current_tag = None
			elif line.startswith('name:'):
				match = re.search(r'name:\s*"([^"]+)"', line)
				if match:
					current_tag = match.group(1)
					self.tags_data[current_tag] = {'name': current_tag, 'tags': []}
			elif line.startswith('tag:'):
				match = re.search(r'tag:\s*"([^"]+)"', line)
				if match and current_tag:
					tag_value = match.group(1).lower()
					self.tags_data[current_tag]['tags'].append(tag_value)
					self.icon_to_tags.setdefault(current_tag, set()).add(tag_value)
					self.tag_to_icons.setdefault(tag_value, set()).add(current_tag)
		
		output(0, app_name, 'Loaded %d icon definitions with tags from: %s' % (len(self.tags_data), self.tags_path.name))
		return True

	def load_categories(self, category_path):
		self.category_path = Path(category_path)
		if not self.category_path.exists():
			output(3, app_name, 'Category file not found: %s' % str(self.category_path))
			return False
		
		self.category_data = {}
		self.category_to_icons = {}
		
		with open(str(self.category_path), 'r', encoding='utf-8') as f:
			content = f.read()
		
		current_category = None
		for line in content.split('\n'):
			line = line.strip()
			if line.startswith('category {'):
				current_category = None
			elif line.startswith('name:'):
				match = re.search(r'name:\s*"([^"]+)"', line)
				if match:
					current_category = match.group(1)
					self.category_data[current_category] = {'name': current_category, 'icons': []}
			elif line.startswith('icon:'):
				match = re.search(r'icon:\s*"([^"]+)"', line)
				if match and current_category:
					icon_name = match.group(1)
					self.category_data[current_category]['icons'].append(icon_name)
					self.category_to_icons.setdefault(current_category, set()).add(icon_name)
		
		output(0, app_name, 'Loaded %d categories from: %s' % (len(self.category_data), self.category_path.name))
		return True

	def search_by_tag(self, query):
		query_lower = query.lower().strip()
		if not query_lower:
			return []
		
		matching_icons = set()
		exact_matches = set()
		
		for tag, icons in self.tag_to_icons.items():
			if query_lower in tag:
				matching_icons.update(icons)
				if tag == query_lower:
					exact_matches.update(icons)
		
		for icon_name, tags in self.icon_to_tags.items():
			if query_lower in tags:
				exact_matches.add(icon_name)
		
		priority_results = list(exact_matches)
		other_results = [i for i in matching_icons if i not in exact_matches]
		
		return priority_results + other_results

	def search_by_category(self, query):
		query_lower = query.lower().strip()
		if not query_lower:
			return list(self.category_data.keys())
		
		return [cat for cat in self.category_data if query_lower in cat.lower()]

	def get_icons_for_category(self, category_name):
		return list(self.category_to_icons.get(category_name, set()))

	def get_tags_for_icon(self, icon_name):
		return list(self.icon_to_tags.get(icon_name, set()))

	def find_similar_icons(self, icon_name, max_results=50):
		source_tags = self.icon_to_tags.get(icon_name)
		if not source_tags:
			return []
		
		similar_scores = {
			icon: len(tags & source_tags)
			for icon, tags in self.icon_to_tags.items()
			if icon != icon_name and source_tags & tags
		}
		
		return [icon for icon, _ in sorted(similar_scores.items(), key=lambda x: x[1], reverse=True)[:max_results]]

	def get_icon_details(self, icon_name):
		if icon_name not in self.tags_data:
			return None
		
		return {
			'name': icon_name,
			'tags': self.tags_data[icon_name]['tags'],
			'categories': [cat for cat, icons in self.category_to_icons.items() if icon_name in icons]
		}

	def get_all_icons(self):
		return list(self.tags_data.keys())

	def is_ready(self):
		return len(self.tags_data) > 0


# - Sub widgets ------------------------
class TRSymbolExplorer(QtGui.QWidget):
	def __init__(self):
		super(TRSymbolExplorer, self).__init__()

		# - Init
		self.active_font = pFont()
		self.source_font = None
		self.all_fonts = None
		self.font_files = []

		self.current_glyph_name = ""
		self.selected_source_glyph = None
		self.source_glyph_contours = []
		self.source_layer_names = []

		self._cached_font_idx = -1
		self._glyph_name_cache = None

		self.icon_sizes = [48, 64, 96, 128]
		self.current_icon_size_index = 0

		# - Initialize Symbol Core
		self.symbol_core = SymbolCore()
		
		# - Get icon font for browse buttons
		self._icon_font_path = getTRIconFontPath()
		self._setup_icon_font()

		lay_main = QtGui.QVBoxLayout()
		lay_main.setContentsMargins(4, 4, 4, 4)
		lay_main.setSpacing(4)

		# -- Row 1: Search Section
		box_search = QtGui.QGroupBox()
		box_search.setObjectName('box_group')
		
		lay_search = QtGui.QHBoxLayout()
		lay_search.setContentsMargins(0, 0, 0, 0)
		lay_search.setSpacing(4)
		
		tooltip_button = "Search icons by tag or name"
		lay_search.addWidget(CustomLabel('label', obj_name='lbl_panel'))
		self.txt_search = QtGui.QLineEdit()
		self.txt_search.setPlaceholderText("Search tags, icon names, or categories...")
		self.txt_search.returnPressed.connect(self._perform_search)
		lay_search.addWidget(self.txt_search)
		
		tooltip_button = "Execute search"
		self.btn_search = CustomPushButton("search", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_search.clicked.connect(self._perform_search)
		lay_search.addWidget(self.btn_search)
		
		tooltip_button = "Clear search results"
		self.btn_clear = CustomPushButton("refresh", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_clear.clicked.connect(self._clear_results)
		lay_search.addWidget(self.btn_clear)
		
		box_search.setLayout(lay_search)
		lay_main.addWidget(box_search)

		# -- Row 2: Glyph Refresh button + Glyph Name field + Zoom + Thumb
		box_glyph_refresh = QtGui.QGroupBox()
		box_glyph_refresh.setObjectName('box_group')
		
		lay_glyph_refresh = QtGui.QHBoxLayout()
		lay_glyph_refresh.setContentsMargins(0, 0, 0, 0)
		
		tooltip_button = "Refresh glyph from active editor"
		self.btn_refresh_glyph = CustomPushButton("glyph_active", tooltip=tooltip_button, obj_name='btn_panel')
		lay_glyph_refresh.addWidget(self.btn_refresh_glyph)
		self.btn_refresh_glyph.clicked.connect(self.refresh_active_glyph)
		
		tooltip_button = "Current glyph name"
		self.txt_glyph_name = QtGui.QLineEdit()
		self.txt_glyph_name.setPlaceholderText("No glyph selected")
		lay_glyph_refresh.addWidget(self.txt_glyph_name)
		
		tooltip_button = "Cycle zoom level"
		self.btn_glyph_zoom = CustomPushButton("search", tooltip=tooltip_button, obj_name='btn_panel')
		lay_glyph_refresh.addWidget(self.btn_glyph_zoom)
		self.btn_glyph_zoom.clicked.connect(lambda: self.__cycle_icon_size_glyph(1))
		
		tooltip_button = "Toggle glyph field view mode"
		self.btn_glyph_view_toggle = CustomPushButton("view_icons", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_glyph_refresh.addWidget(self.btn_glyph_view_toggle)
		self.btn_glyph_view_toggle.clicked.connect(self.__toggle_glyph_view_mode)
		
		box_glyph_refresh.setLayout(lay_glyph_refresh)
		lay_main.addWidget(box_glyph_refresh)

		# -- Row 3: Glyph Field (similar icons)
		self.lst_glyphs = QtGui.QListView()
		self.mod_glyphs = QtGui.QStandardItemModel(self.lst_glyphs)
		self.lst_glyphs.setMinimumHeight(150)
		self.lst_glyphs.setModel(self.mod_glyphs)
		self.lst_glyphs.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
		self.lst_glyphs.selectionModel().selectionChanged.connect(self.__on_glyph_selected)
		lay_main.addWidget(self.lst_glyphs)
		self.__toggle_glyph_view_mode()

		# -- Row 4: Parts Refresh button + Parts Name field + Zoom
		box_parts_refresh = QtGui.QGroupBox()
		box_parts_refresh.setObjectName('box_group')
		
		lay_parts_refresh = QtGui.QHBoxLayout()
		lay_parts_refresh.setContentsMargins(0, 0, 0, 0)
		
		tooltip_button = "Refresh parts from source font"
		self.btn_refresh_parts = CustomPushButton("glyph_active", tooltip=tooltip_button, obj_name='btn_panel')
		lay_parts_refresh.addWidget(self.btn_refresh_parts)
		self.btn_refresh_parts.clicked.connect(self.refresh_parts_from_glyph)
		
		tooltip_button = "Current source glyph"
		self.txt_parts_name = QtGui.QLineEdit()
		self.txt_parts_name.setPlaceholderText("Select a glyph above")
		lay_parts_refresh.addWidget(self.txt_parts_name)
		
		tooltip_button = "Cycle zoom level"
		self.btn_parts_zoom = CustomPushButton("search", tooltip=tooltip_button, obj_name='btn_panel')
		lay_parts_refresh.addWidget(self.btn_parts_zoom)
		self.btn_parts_zoom.clicked.connect(lambda: self.__cycle_icon_size_parts(1))
		
		box_parts_refresh.setLayout(lay_parts_refresh)
		lay_main.addWidget(box_parts_refresh)

		# -- Row 5: Parts Field (contour parts)
		self.lst_contours = QtGui.QListView()
		self.mod_contours = QtGui.QStandardItemModel(self.lst_contours)
		self.contour_delegate = ContourPartsDelegate()
		self.lst_contours.setItemDelegate(self.contour_delegate)
		self.lst_contours.setMinimumHeight(200)
		self.lst_contours.setModel(self.mod_contours)
		self.lst_contours.setViewMode(QtGui.QListView.IconMode)
		self.lst_contours.setResizeMode(QtGui.QListView.Adjust)
		self.lst_contours.setMovement(QtGui.QListView.Static)
		self.lst_contours.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.lst_contours.setDragDropMode(QtGui.QAbstractItemView.NoDragDrop)
		lay_main.addWidget(self.lst_contours)
		self.__toggle_parts_view_mode()

		# -- Row 6: Controls - Rounding, Delta Machine
		box_contour_copy = QtGui.QGroupBox()
		box_contour_copy.setObjectName('box_group')
		
		lay_contour_copy = QtGui.QHBoxLayout()
		lay_contour_copy.setContentsMargins(0, 0, 0, 0)

		tooltip_button = "Paste selected contour part"
		self.btn_paste_contour = CustomPushButton("clipboard_paste", tooltip=tooltip_button, obj_name='btn_panel')
		lay_contour_copy.addWidget(self.btn_paste_contour)
		self.btn_paste_contour.clicked.connect(self.paste_contour_part)

		tooltip_button =  "Round coordinates"
		self.opt_round = CustomPushButton("node_round", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_contour_copy.addWidget(self.opt_round)

		tooltip_button =  "Use Delta Machine to fit pasted contours into selected shape bounds"
		self.opt_delta_machine = CustomPushButton("delta_machine", checkable=True, checked=False, tooltip=tooltip_button, obj_name='btn_panel_opt')
		lay_contour_copy.addWidget(self.opt_delta_machine)

		box_contour_copy.setLayout(lay_contour_copy)
		lay_main.addWidget(box_contour_copy)

		# -- Row 7: Config Files Section
		box_config = QtGui.QGroupBox()
		box_config.setObjectName('box_group')
		
		lay_config = QtGui.QVBoxLayout()
		lay_config.setContentsMargins(4, 4, 4, 4)
		lay_config.setSpacing(4)
		
		# - Tags file row
		lay_tags_row = QtGui.QHBoxLayout()
		lay_tags_row.setSpacing(4)
		
		tooltip_button = "Browse for tags file"
		lay_tags_row.addWidget(CustomLabel('label', obj_name='lbl_panel'))
		self.txt_tags_path = QtGui.QLineEdit()
		self.txt_tags_path.setPlaceholderText(tooltip_button)
		lay_tags_row.addWidget(self.txt_tags_path)
		
		self.btn_browse_tags = CustomPushButton("file_open", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_browse_tags.clicked.connect(lambda: self._browse_file('tags'))
		lay_tags_row.addWidget(self.btn_browse_tags)
		lay_config.addLayout(lay_tags_row)
		
		# - Category file row
		lay_category_row = QtGui.QHBoxLayout()
		lay_category_row.setSpacing(4)
		
		tooltip_button = "Browse for category file"
		lay_category_row.addWidget(CustomLabel('view_list', obj_name='lbl_panel'))
		self.txt_category_path = QtGui.QLineEdit()
		self.txt_category_path.setPlaceholderText(tooltip_button)
		lay_category_row.addWidget(self.txt_category_path)
		
		self.btn_browse_category = CustomPushButton("file_open", tooltip=tooltip_button, obj_name='btn_panel')
		self.btn_browse_category.clicked.connect(lambda: self._browse_file('category'))
		lay_category_row.addWidget(self.btn_browse_category)
		lay_config.addLayout(lay_category_row)
		
		box_config.setLayout(lay_config)
		lay_main.addWidget(box_config)

		# -- Row 8: Font Selector
		box_font_selector = QtGui.QGroupBox()
		box_font_selector.setObjectName('box_group')
		
		lay_font_selector = QtGui.QHBoxLayout()
		lay_font_selector.setContentsMargins(0, 0, 0, 0)
		
		lay_font_selector.addWidget(CustomLabel('font_open', obj_name='lbl_panel'))
		self.cmb_select_font = QtGui.QComboBox()
		self.cmb_select_font.setMinimumWidth(150)
		self.cmb_select_font.currentIndexChanged.connect(self._on_font_changed)
		lay_font_selector.addWidget(self.cmb_select_font)
		
		tooltip_button = "Refresh fonts list"
		self.btn_refresh_fonts = CustomPushButton("refresh", tooltip=tooltip_button, obj_name='btn_panel')
		lay_font_selector.addWidget(self.btn_refresh_fonts)
		self.btn_refresh_fonts.clicked.connect(self.refresh_fonts_list)
		
		box_font_selector.setLayout(lay_font_selector)
		lay_main.addWidget(box_font_selector)

		# - Build
		self.refresh_fonts_list()
		self.setLayout(lay_main)

	def _setup_icon_font(self):
		if self._icon_font_path and os.path.exists(self._icon_font_path):
			self._icon_font_db_id = QtGui.QFontDatabase.addApplicationFont(self._icon_font_path)
			self._icon_font_family = QtGui.QFontDatabase.applicationFontFamilies(self._icon_font_db_id)
			if self._icon_font_family:
				self._icon_font_family = self._icon_font_family[0]

	def _browse_file(self, file_type):
		dialog = QtGui.QFileDialog()
		dialog.setNameFilter("Text Proto Files (*.textproto);;All Files (*)")
		
		if file_type == 'tags':
			dialog.setWindowTitle("Select Tags File")
			if self.symbol_core.tags_path:
				dialog.selectFile(str(self.symbol_core.tags_path))
		else:
			dialog.setWindowTitle("Select Category File")
			if self.symbol_core.category_path:
				dialog.selectFile(str(self.symbol_core.category_path))
		
		if dialog.exec_():
			file_path = dialog.selectedFiles()[0]
			if file_type == 'tags':
				self.symbol_core.load_tags(file_path)
				self.txt_tags_path.setText(file_path)
			else:
				self.symbol_core.load_categories(file_path)
				self.txt_category_path.setText(file_path)

	def _perform_search(self):
		query = self.txt_search.text.strip()

		if not query:
			self._show_all_icons()
			return

		query_lower = query.lower()
		icon_names = []
		seen = set()

		# Search glyph names in the selected font
		font_glyph_names = self._get_font_glyph_names()
		for name in font_glyph_names:
			if query_lower in name.lower() and name not in seen:
				icon_names.append(name)
				seen.add(name)

		# Also search symbol_core tags/categories if loaded
		if self.symbol_core.is_ready():
			tag_results = self.symbol_core.search_by_tag(query)
			category_results = self.symbol_core.search_by_category(query)

			for cat in category_results:
				for name in self.symbol_core.get_icons_for_category(cat):
					if name not in seen:
						icon_names.append(name)
						seen.add(name)

			for name in tag_results:
				if name not in seen:
					icon_names.append(name)
					seen.add(name)

		if not icon_names:
			output(1, app_name, 'No glyphs or icons found matching: %s' % query)
			return

		self._display_icon_results(icon_names)

	def _show_all_icons(self):
		if self.symbol_core.is_ready():
			all_icons = self.symbol_core.get_all_icons()
		else:
			all_icons = self._get_font_glyph_names()
		self._display_icon_results(all_icons)

	def _display_icon_results(self, icon_names):
		self.mod_glyphs.clear()
		
		if not icon_names:
			output(1, app_name, 'No icons found matching the search criteria.')
			return
		
		for icon_name in icon_names:
			details = self.symbol_core.get_icon_details(icon_name)
			
			item = QtGui.QStandardItem(icon_name)
			item.setData(icon_name, QtCore.Qt.UserRole + 1000)
			item.setData(icon_name, QtCore.Qt.UserRole + 1001)
			item.setDropEnabled(False)
			item.setSelectable(True)
			
			tags = details['tags'] if details else []
			categories = details['categories'] if details else []
			
			tool_tip = "Icon: %s\nTags: %s\nCategories: %s" % (
				icon_name,
				', '.join(tags[:10]) + ('...' if len(tags) > 10 else ''),
				', '.join(categories)
			)
			item.setToolTip(tool_tip)

			glyph = self.source_font.glyph(icon_name)

			if glyph is not None:
				fl_contours = glyph.contours(base_layer)
				valid_contours = [cnt for cnt in (fl_contours or []) if cnt is not None]

				if valid_contours:
					new_icon = TRDrawIcon(valid_contours, foreground='blue', background='LightGray')
					item.setIcon(new_icon)
			
			self.mod_glyphs.appendRow(item)
		
		output(0, app_name, 'Found %d icons matching search criteria.' % self.mod_glyphs.rowCount())

	def _clear_results(self):
		self.mod_glyphs.clear()
		self.txt_search.clear()
		self.txt_glyph_name.clear()
		self.txt_parts_name.clear()
		output(0, app_name, 'Search results cleared.')

	# -- Font List Functions
	def refresh_fonts_list(self):
		curr_fonts = fl6.AllFonts()
		self.cmb_select_font.clear()
		self.font_files = []
		self.all_fonts = None

		if len(curr_fonts):
			self.all_fonts = curr_fonts
			self.font_files = [os.path.split(font.path)[1] for font in self.all_fonts]
			self.cmb_select_font.addItems(self.font_files)
			if len(self.font_files) > 0:
				self.source_font = pFont(self.all_fonts[0])
			output(0, app_name, 'Font list updated!')
		else:
			output(1, app_name, 'No open font files found!')

	def _on_font_changed(self, font_idx):
		if self.all_fonts is None or font_idx < 0 or font_idx >= len(self.all_fonts):
			self.source_font = None
			self._cached_font_idx = -1
			self._glyph_name_cache = None
			return

		self._cached_font_idx = font_idx
		self.source_font = pFont(self.all_fonts[font_idx])
		self._glyph_name_cache = None

		output(0, app_name, 'Font changed: %s' % (self.font_files[font_idx]))

	def _get_font_glyph_names(self):
		if self._glyph_name_cache is not None:
			return self._glyph_name_cache

		if self.source_font is None:
			return []

		self._glyph_name_cache = [g.name for g in self.source_font.fg.glyphs if g.name]
		
		output(0, app_name, 'Glyph name cache built: %d glyphs.' % len(self._glyph_name_cache))
		return self._glyph_name_cache

	def get_source_font(self):
		if self.all_fonts is None or len(self.all_fonts) == 0:
			self.refresh_fonts_list()

		if self.all_fonts is None or len(self.all_fonts) == 0:
			return None, set()

		font_idx = self.font_files.index(self.cmb_select_font.currentText)

		if font_idx != self._cached_font_idx:
			self._on_font_changed(font_idx)

		return self.source_font

	# -- Glyph Field Functions
	def __cycle_icon_size_glyph(self, direction):
		if self.btn_glyph_view_toggle.isChecked():
			self.current_icon_size_index = (self.current_icon_size_index + direction) % len(self.icon_sizes)
			new_size = self.icon_sizes[self.current_icon_size_index]
			grid_size = new_size + 16
			self.lst_glyphs.setIconSize(QtCore.QSize(new_size, new_size))
			self.lst_glyphs.setGridSize(QtCore.QSize(grid_size, grid_size + 8))

	def __toggle_glyph_view_mode(self):
		if self.btn_glyph_view_toggle.isChecked():
			self.lst_glyphs.setViewMode(QtGui.QListView.IconMode)
			self.lst_glyphs.setResizeMode(QtGui.QListView.Adjust)
			self.lst_glyphs.setMovement(QtGui.QListView.Static)
			self.lst_glyphs.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
			self.lst_glyphs.setDragDropMode(QtGui.QAbstractItemView.NoDragDrop)
			
			current_size = self.icon_sizes[self.current_icon_size_index]
			grid_size = current_size + 16
			self.lst_glyphs.setIconSize(QtCore.QSize(current_size, current_size))
			self.lst_glyphs.setGridSize(QtCore.QSize(grid_size, grid_size + 8))
			self.lst_glyphs.setSpacing(10)
		else:
			self.lst_glyphs.setViewMode(QtGui.QListView.ListMode)
			self.lst_glyphs.setResizeMode(QtGui.QListView.Adjust)
			self.lst_glyphs.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
			self.lst_glyphs.setDragDropMode(QtGui.QAbstractItemView.NoDragDrop)
			self.lst_glyphs.setIconSize(QtCore.QSize(18, 18))
			self.lst_glyphs.setGridSize(QtCore.QSize())
			self.lst_glyphs.setSpacing(1)

	# -- Parts Field Functions
	def __cycle_icon_size_parts(self, direction):
		self.current_icon_size_index = (self.current_icon_size_index + direction) % len(self.icon_sizes)
		new_size = self.icon_sizes[self.current_icon_size_index]
		grid_size = new_size + 16
		self.lst_contours.setIconSize(QtCore.QSize(new_size, new_size))
		self.lst_contours.setGridSize(QtCore.QSize(grid_size, grid_size + 8))
		self.lst_contours.viewport().update()

	def __toggle_parts_view_mode(self):
		current_size = self.icon_sizes[self.current_icon_size_index]
		grid_size = current_size + 16
		self.lst_contours.setIconSize(QtCore.QSize(current_size, current_size))
		self.lst_contours.setGridSize(QtCore.QSize(grid_size, grid_size + 8))
		self.lst_contours.setSpacing(10)

	# -- Glyph Refresh Logic
	def refresh_active_glyph(self):
		wGlyph = eGlyph()
		self.current_glyph_name = wGlyph.name
		self.txt_glyph_name.setText(wGlyph.name)
		
		if not self.symbol_core.is_ready():
			output(2, app_name, 'No symbol data loaded. Cannot search for similar icons.')
			self.mod_glyphs.clear()
			return
		
		similar_icons = self.symbol_core.find_similar_icons(wGlyph.name, max_results=50)
		
		self.mod_glyphs.clear()
		
		if not similar_icons:
			output(1, app_name, 'No similar icons found for: %s' % wGlyph.name)
			return
		
		for icon_name in similar_icons:
			details = self.symbol_core.get_icon_details(icon_name)
			
			item = QtGui.QStandardItem(icon_name)
			item.setData(icon_name, QtCore.Qt.UserRole + 1000)
			item.setData(icon_name, QtCore.Qt.UserRole + 1001)
			item.setDropEnabled(False)
			item.setSelectable(True)
			
			tags = details['tags'] if details else []
			categories = details['categories'] if details else []
			
			tool_tip = "Icon: %s\nTags: %s\nCategories: %s" % (
				icon_name,
				', '.join(tags[:10]) + ('...' if len(tags) > 10 else ''),
				', '.join(categories)
			)
			item.setToolTip(tool_tip)

			glyph = self.source_font.glyph(icon_name, extend=eGlyph)

			if glyph:
				fl_contours = glyph.contours(base_layer)
				valid_contours = [cnt for cnt in (fl_contours or []) if cnt is not None]

				if valid_contours:
					new_icon = TRDrawIcon(valid_contours, foreground='blue', background='LightGray')
					item.setIcon(new_icon)
			
			self.mod_glyphs.appendRow(item)
		
		output(0, app_name, 'Found %d similar icons for %s' % (self.mod_glyphs.rowCount(), self.current_glyph_name))

	# -- Glyph Selection Handler
	def __on_glyph_selected(self):
		selected_indexes = self.lst_glyphs.selectedIndexes()
		if not selected_indexes:
			return

		item = self.mod_glyphs.itemFromIndex(selected_indexes[0])
		if item is None:
			return

		icon_name = item.data(QtCore.Qt.UserRole + 1000)
		self.selected_source_glyph = None

		if self.source_font is not None and icon_name:
			self.selected_source_glyph = self.source_font.glyph(icon_name, extend=eGlyph)
			self.txt_parts_name.setText(icon_name if self.selected_source_glyph else "")
			self.refresh_parts_from_glyph()

	# -- Parts Refresh Logic
	def refresh_parts_from_glyph(self):
		self.mod_contours.clear()
		self.contour_delegate._path_data = {}

		if self.selected_source_glyph is None:
			output(2, app_name, 'No glyph selected in glyph field.')
			return

		source_fl_glyph = self.selected_source_glyph.fl
		self.source_layer_names = [layer.name for layer in source_fl_glyph.layers]

		if not self.source_layer_names:
			output(2, app_name, 'No layers found in glyph: %s' % self.selected_source_glyph.name)
			return

		raw_contours = self.selected_source_glyph.contours(base_layer)
		fl_contours = [cnt for cnt in (raw_contours or []) if cnt is not None]

		if not fl_contours:
			output(2, app_name, 'No contours found in glyph: %s' % self.selected_source_glyph.name)
			return

		all_paths = []
		path_to_contour_idx = {}
		for idx, fl_contour in enumerate(fl_contours):
			try:
				qp = _fl_contour_to_qpath(fl_contour)
				if qp is not None and not qp.isEmpty():
					path_to_contour_idx[len(all_paths)] = idx
					all_paths.append(qp)
			except Exception:
				continue

		self.contour_delegate._path_data[id(self.mod_contours)] = []

		for idx, fl_contour in enumerate(fl_contours):
			try:
				contour_nodes = fl_contour.nodes()
				if contour_nodes is None:
					continue
				contour_type = 'Closed' if fl_contour.closed else 'Open'
				item_text = '%s | %d Nodes (%s)' % ('Contour %d' % (idx + 1), len(contour_nodes), contour_type)
			except Exception:
				item_text = 'Contour %d | (data unavailable)' % (idx + 1)

			new_item = QtGui.QStandardItem(item_text)
			new_item.setData(idx, QtCore.Qt.UserRole + 1000)
			new_item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
			self.mod_contours.appendRow(new_item)
			self.contour_delegate._path_data[id(self.mod_contours)].append((all_paths, idx))

		self.lst_contours.viewport().update()
		output(0, app_name, 'Loaded %d contours from glyph: %s' % (len(fl_contours), self.selected_source_glyph.name))

	# -- Delta Machine Helper
	def __prep_delta_parameters(self, tr_glyph, wGlyph, wLayers):
		try:
			font_lib = self.active_font.fl.packageLib
			raw_axis_data = font_lib[delta_app_id_key][delta_axis_group_name]
			axis_data = {layer_name : (float(stx), float(sty)) for layer_name, stx, sty, sx, sy, color in raw_axis_data}
			
		except KeyError:
			output(3, app_name, 'Delta Machine Axis setup not found in Fonts Lib.\n Please setup using < Delta panel > then save the axis data within the font!')
			return None, None
		
		for layer_name, stems in axis_data.items():
			tr_layer = tr_glyph.layer(layer_name)
			if tr_layer is not None:
				tr_layer.stems = stems

		virtual_axis = tr_glyph.virtual_axis(list(axis_data.keys()))
		target_bounds = {}

		for layer_name in wLayers:
			layer_selection = wGlyph.selectedNodes(layer_name)
			
			if len(layer_selection):
				selection_container = eNodesContainer(layer_selection)
				target_bounds[layer_name] = selection_container.bounds
			else:
				target_bounds[layer_name] = None

		return virtual_axis, target_bounds

	# -- Paste Contour Part
	def __paste_tr_glyph_to_fl(self, tr_glyph, wGlyph, wLayers, selected_shape_index, do_delta):
		if do_delta:
			virtual_axis, target_bounds = self.__prep_delta_parameters(tr_glyph, wGlyph, wLayers)
			if virtual_axis is None:
				do_delta = False

		for tr_layer in tr_glyph.layers:
			layer_name = tr_layer.name
			work_layer = wGlyph.layer(layer_name)
			
			if work_layer is not None:
				if do_delta:
					current_bounds = target_bounds.get(layer_name)
					if current_bounds is not None:
						process_layer = tr_layer.scale_with_axis(virtual_axis, current_bounds.width, current_bounds.height, transform_origin=TransformOrigin.CENTER)
						process_layer.align_to(current_bounds.center_point, mode=(TransformOrigin.CENTER, TransformOrigin.CENTER), align=(True, True))
					else:
						process_layer = tr_layer
				else:
					process_layer = tr_layer
				
				fl_contours = []
				for tr_shape in process_layer.shapes:
					for tr_cont in tr_shape.contours:
						fl_cont = trNodes_to_flContour(tr_cont.nodes, is_closed=tr_cont.closed)
						fl_contours.append(fl_cont)
				
				if len(wGlyph.shapes(layer_name)) == 0:
					selected_shape = fl6.flShape()
					work_layer.addShape(selected_shape)
				else:
					selected_shape = wGlyph.shapes(layer_name)[selected_shape_index]
				
				selected_shape.addContours(fl_contours, True)

	def paste_contour_part(self):
		gallery_selection = [self.mod_contours.itemFromIndex(qidx) for qidx in self.lst_contours.selectedIndexes()]
		
		if not gallery_selection:
			output(2, app_name, 'No contour part selected in parts field.')
			return
		
		if self.selected_source_glyph is None:
			output(2, app_name, 'No source glyph loaded.')
			return
		
		wGlyph = eGlyph()
		wLayers = wGlyph._prepareLayers(pLayers) or []
		do_delta = self.opt_delta_machine.isChecked()
		
		selection_tuples = wGlyph.selectedAtShapes()
		selected_shape_index = selection_tuples[0][0] if len(selection_tuples) else 0
		
		if not wLayers:
			output(2, app_name, 'No layers available to paste.')
			return
		
		contour_indices = [item.data(QtCore.Qt.UserRole + 1000) for item in gallery_selection]
		multi_select = len(contour_indices) > 1
		
		if multi_select:
			tr_glyph = Glyph(name='temp_contour_combined')
			
			for layer_name in wLayers:
				tr_layer = Layer(name=layer_name)
				source_layer_contours = self.selected_source_glyph.contours(layer_name)
				combined_contours = []
				
				for contour_idx in contour_indices:
					if contour_idx < len(source_layer_contours):
						fl_contour = source_layer_contours[contour_idx]
						tr_contour = flNodes_to_trContour(fl_contour.nodes(), fl_contour.closed)
						combined_contours.append(tr_contour)
				
				if combined_contours:
					tr_shape = Shape(combined_contours)
					tr_layer.append(tr_shape)
				
				tr_glyph.append(tr_layer)
			
			self.__paste_tr_glyph_to_fl(tr_glyph, wGlyph, wLayers, selected_shape_index, do_delta)
		else:
			for clipboard_item in gallery_selection:
				contour_idx = clipboard_item.data(QtCore.Qt.UserRole + 1000)
				
				tr_glyph = Glyph(name='temp_contour')
				
				for layer_name in wLayers:
					tr_layer = Layer(name=layer_name)
					source_layer_contours = self.selected_source_glyph.contours(layer_name)
					
					if contour_idx < len(source_layer_contours):
						fl_contour = source_layer_contours[contour_idx]
						tr_contour = flNodes_to_trContour(fl_contour.nodes(), fl_contour.closed)
						tr_shape = Shape([tr_contour])
						tr_layer.append(tr_shape)
					
					tr_glyph.append(tr_layer)
				
				self.__paste_tr_glyph_to_fl(tr_glyph, wGlyph, wLayers, selected_shape_index, do_delta)
		
		if self.opt_round.isChecked():
			TRNodeActionCollector.node_round(pMode, pLayers, True, True)

		wGlyph.updateObject(wGlyph.fl, 'Paste contour parts; Glyph: %s' % wGlyph.name)
		paste_mode = 'Combined' if multi_select else 'Single'
		output(0, app_name, 'Contour part pasted successfully (%s mode, %d contours).' % (paste_mode, len(contour_indices)))


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
	def __init__(self):
		super(tool_tab, self).__init__()

		set_stylesheet = css_tr_button_dark if fl6.flPreferences().isDark else css_tr_button
		self.setStyleSheet(set_stylesheet)
		
		layoutV = QtGui.QVBoxLayout()
		layoutV.setContentsMargins(0, 0, 0, 0)
		
		layoutV.addWidget(TRSymbolExplorer())

		self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
	test = tool_tab()
	test.setWindowTitle('%s %s' %(app_name, app_version))
	test.setGeometry(100, 100, 300, 600)
	test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
	
	test.show()
