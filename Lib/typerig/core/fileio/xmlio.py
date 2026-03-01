# MODULE: Typerig / IO / XML
# NOTE: Universal XML(UFO) Serialization Module
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

'''
HELP:
Each class defines its XML schema using class attributes:
- XML_TAG: The XML element tag name
- XML_ATTRS: List of attributes to serialize as XML attributes
- XML_CHILDREN: Dict mapping child element names to attribute names
- XML_LIB_ATTRS: List of attributes to store in <lib> section
- XML_ATTR_DEFAULTS: Dict of attr_name -> default value or predicate(value)->bool
  If a callable predicate returns True the attribute is skipped (not written).
  If a plain value, the attribute is skipped when equal to that value.
'''
# - Dependencies ------------------------
from xml.etree import ElementTree as ET

# - Init --------------------------------
__version__ = '0.5.0'

_SENTINEL = object()  # Unique sentinel for XML_ATTR_DEFAULTS miss

# - Helpers -----------------------------
def _format_float(v):
	'''Compact float: whole numbers lose the decimal, others strip trailing zeros'''
	if v == int(v):
		return str(int(v))
	return '{:.6f}'.format(v).rstrip('0').rstrip('.')

# - Classes -----------------------------
class XMLSerializable:
	'''Mixin class for XML serialization'''
	
	# Override these in subclasses
	XML_TAG = None  # e.g., 'contour', 'node', 'glyph'
	XML_ATTRS = []  # e.g., ['identifier', 'x', 'y']
	XML_CHILDREN = {}  # e.g., {'point': 'nodes', 'component': 'components'}
	XML_LIB_ATTRS = []  # e.g., ['closed', 'clockwise'] - plist lib section
	XML_ATTR_DEFAULTS = {}  # e.g., {'closed': False} - skip when value matches default
	
	def to_XML(self, exclude_attrs=[]):
		'''Convert object to XML string
		exclude_attrs - list of element attributes to be excluded
		'''
		element = self._to_xml_element(exclude_attrs)
		return ET.tostring(element, encoding='unicode')
	
	def _to_xml_element(self, exclude_attrs):
		'''Convert object to XML Element (internal use)'''
		elem = ET.Element(self.XML_TAG)
		
		# Add XML attributes
		for attr_name in self.XML_ATTRS:
			if attr_name in exclude_attrs: continue

			value = getattr(self, attr_name, None)
			if value is None: continue

			# Skip if value matches declared default
			default = self.XML_ATTR_DEFAULTS.get(attr_name, _SENTINEL)
			if default is not _SENTINEL:
				if callable(default):
					if default(value): continue
				elif value == default:
					continue

			formatted = _format_xml_attr(value)
			if formatted is not None:
				elem.set(attr_name, formatted)
		
		# Add child elements
		for child_tag, attr_name in self.XML_CHILDREN.items():
			children = getattr(self, attr_name, None)
			if children:
				if not isinstance(children, (list, tuple)):
					children = [children]
				for child in children:
					if hasattr(child, '_to_xml_element'):
						elem.append(child._to_xml_element(exclude_attrs))
		
		# Add lib section if needed
		lib_data = {}
		for attr_name in self.XML_LIB_ATTRS:
			if attr_name in exclude_attrs: continue

			value = getattr(self, attr_name, None)
			# Only include non-default/non-None values
			if value is not None:
				lib_data[attr_name] = value
		
		# Include custom lib data if object has it
		if hasattr(self, 'lib') and self.lib:
			for key, value in self.lib.items():
				if key not in lib_data:  # Don't override extracted attrs
					lib_data[key] = value
		
		if lib_data:
			lib_elem = _create_lib_element(lib_data)
			elem.append(lib_elem)
		
		return elem
	
	@classmethod
	def from_XML(cls, element):
		'''Parse object from XML element or string'''
		if isinstance(element, str):
			element = ET.fromstring(element)
		
		# Parse XML attributes
		attrs = {}
		for attr_name in cls.XML_ATTRS:
			value = element.get(attr_name)
			if value is not None:
				# Type conversion - _convert_xml_attr handles Transform matrix() strings
				attrs[attr_name] = _convert_xml_attr(value)
		
		# Parse child elements
		for child_tag, attr_name in cls.XML_CHILDREN.items():
			child_elements = element.findall(child_tag)
			if child_elements:
				# Find the class that handles this tag
				child_class = _find_class_for_tag(child_tag)
				if child_class:
					children = [child_class.from_XML(elem) for elem in child_elements]
					attrs[attr_name] = children
		
		# Parse lib section
		lib_elem = element.find('lib')
		if lib_elem is not None:
			dict_elem = lib_elem.find('dict')
			if dict_elem is not None:
				lib_data = _parse_plist_dict(dict_elem)
				
				# Extract known lib attributes
				for attr_name in cls.XML_LIB_ATTRS:
					if attr_name in lib_data:
						value = lib_data.pop(attr_name)
						attrs[attr_name] = value
				
				# Store remaining lib data
				if lib_data:
					attrs['lib'] = lib_data
		
		return cls(**attrs)


# Global registry for tag -> class mapping
_XML_REGISTRY = {}

def register_xml_class(cls):
	'''Decorator to register a class for XML deserialization'''
	if hasattr(cls, 'XML_TAG') and cls.XML_TAG:
		_XML_REGISTRY[cls.XML_TAG] = cls
	return cls

def _find_class_for_tag(tag):
	'''Find registered class for a given XML tag'''
	return _XML_REGISTRY.get(tag)

def _convert_xml_attr(value):
	'''Convert XML attribute string to appropriate Python type'''
	# Try boolean
	if value in ('True', 'true', 'yes'):
		return True
	if value in ('False', 'false', 'no'):
		return False
	
	# Try Transform matrix string: 'matrix(a b c d e f)'
	if value.startswith('matrix(') and value.endswith(')'):
		parts = value[7:-1].split()
		if len(parts) == 6:
			try:
				from typerig.core.objects.transform import Transform
				return Transform(*map(float, parts))
			except (ImportError, ValueError):
				pass
	
	# Try integer
	try:
		if '.' not in value:
			return int(value)
	except ValueError:
		pass
	
	# Try float
	try:
		return float(value)
	except ValueError:
		pass
	
	# Try to parse as list (e.g., "[12032, 19968]")
	if value.startswith('[') and value.endswith(']'):
		try:
			import ast
			return ast.literal_eval(value)
		except:
			pass
	
	# Return as string
	return value

def _format_xml_attr(value):
	'''Format Python value as XML attribute string. Returns None to skip.'''
	# Guard against str/bytes — both have __len__ and __getitem__
	if (not isinstance(value, (str, bytes)) and
			hasattr(value, '__len__') and hasattr(value, '__getitem__') and len(value) == 6):
		try:
			vals = [value[i] for i in range(6)]
			return 'matrix({})'.format(' '.join(_format_float(v) for v in vals))
		except (TypeError, IndexError, ValueError):
			pass
	
	if isinstance(value, bool):
		return str(value)
	elif isinstance(value, float):
		return _format_float(value)
	elif isinstance(value, (list, tuple)):
		return str(value)
	else:
		return str(value)


# Plist helpers
def _create_lib_element(data):
	'''Create a <lib><dict>...</dict></lib> element from a dictionary'''
	lib_elem = ET.Element('lib')
	dict_elem = ET.SubElement(lib_elem, 'dict')
	
	for key, value in data.items():
		_add_plist_key_value(dict_elem, key, value)
	
	return lib_elem

def _add_plist_key_value(dict_elem, key, value):
	'''Add a key-value pair to a plist dict element'''
	key_elem = ET.SubElement(dict_elem, 'key')
	key_elem.text = key
	
	if value is None:
		# Skip None values - don't add anything
		dict_elem.remove(key_elem)
		return
	elif isinstance(value, bool):
		ET.SubElement(dict_elem, 'true' if value else 'false')
	elif isinstance(value, int):
		int_elem = ET.SubElement(dict_elem, 'integer')
		int_elem.text = str(value)
	elif isinstance(value, float):
		real_elem = ET.SubElement(dict_elem, 'real')
		real_elem.text = _format_float(value)
	elif isinstance(value, str):
		string_elem = ET.SubElement(dict_elem, 'string')
		string_elem.text = value
	elif isinstance(value, (list, tuple)):
		array_elem = ET.SubElement(dict_elem, 'array')
		for item in value:
			if isinstance(item, bool):
				ET.SubElement(array_elem, 'true' if item else 'false')
			elif isinstance(item, int):
				elem = ET.SubElement(array_elem, 'integer')
				elem.text = str(item)
			elif isinstance(item, float):
				elem = ET.SubElement(array_elem, 'real')
				elem.text = _format_float(item)
			elif isinstance(item, str):
				elem = ET.SubElement(array_elem, 'string')
				elem.text = item
	elif isinstance(value, dict):
		nested_dict = ET.SubElement(dict_elem, 'dict')
		for k, v in value.items():
			_add_plist_key_value(nested_dict, k, v)
	else:
		# Unknown type - remove the key element to avoid malformed XML
		dict_elem.remove(key_elem)

def _parse_plist_dict(dict_elem):
	'''Parse a plist dict element into a Python dict'''
	result = {}
	children = list(dict_elem)
	
	i = 0
	while i < len(children):
		if children[i].tag == 'key':
			key = children[i].text
			i += 1
			if i < len(children):
				value_elem = children[i]
				result[key] = _parse_plist_value(value_elem)
		i += 1
	
	return result

def _parse_plist_value(elem):
	'''Parse a plist value element'''
	if elem.tag == 'true':
		return True
	elif elem.tag == 'false':
		return False
	elif elem.tag == 'integer':
		return int(elem.text)
	elif elem.tag == 'real':
		return float(elem.text)
	elif elem.tag == 'string':
		return elem.text or ''
	elif elem.tag == 'array':
		return [_parse_plist_value(child) for child in elem]
	elif elem.tag == 'dict':
		return _parse_plist_dict(elem)
	return None
