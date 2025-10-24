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
'''
# - Dependencies ------------------------
from xml.etree import ElementTree as ET

# - Classes -----------------------------
class XMLSerializable:
	'''Mixin class for XML serialization'''
	
	# Override these in subclasses
	XML_TAG = None 		# e.g., 'contour', 'node', 'glyph'
	XML_ATTRS = []  	# e.g., ['identifier', 'x', 'y']
	XML_CHILDREN = {} 	# e.g., {'point': 'nodes', 'component': 'components'}
	XML_LIB_ATTRS = []  # e.g., ['transform', 'closed', 'clockwise']
	
	def to_XML(self):
		'''Convert object to XML string'''
		element = self._to_xml_element()
		return ET.tostring(element, encoding='unicode')
	
	def _to_xml_element(self):
		'''Convert object to XML Element (internal use)'''
		elem = ET.Element(self.XML_TAG)
		
		# Add XML attributes
		for attr_name in self.XML_ATTRS:
			value = getattr(self, attr_name, None)
			if value is not None:
				elem.set(attr_name, str(value))
		
		# Add child elements
		for child_tag, attr_name in self.XML_CHILDREN.items():
			children = getattr(self, attr_name, None)
			if children:
				if not isinstance(children, (list, tuple)):
					children = [children]
				for child in children:
					if hasattr(child, '_to_xml_element'):
						elem.append(child._to_xml_element())
		
		# Add lib section if needed
		lib_data = {}
		for attr_name in self.XML_LIB_ATTRS:
			value = getattr(self, attr_name, None)
			if value is not None:
				lib_data[attr_name] = value
		
		# Include custom lib data if object has it
		if hasattr(self, 'lib') and self.lib:
			lib_data.update(self.lib)
		
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
				attrs[attr_name] = value
		
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
						attrs[attr_name] = lib_data.pop(attr_name)
				
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
	
	if isinstance(value, bool):
		ET.SubElement(dict_elem, 'true' if value else 'false')
	elif isinstance(value, int):
		int_elem = ET.SubElement(dict_elem, 'integer')
		int_elem.text = str(value)
	elif isinstance(value, float):
		real_elem = ET.SubElement(dict_elem, 'real')
		real_elem.text = str(value)
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
				elem.text = str(item)
			elif isinstance(item, str):
				elem = ET.SubElement(array_elem, 'string')
				elem.text = item
	elif isinstance(value, dict):
		nested_dict = ET.SubElement(dict_elem, 'dict')
		for k, v in value.items():
			_add_plist_key_value(nested_dict, k, v)

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


# Example usage:
'''
from serialization import XMLSerializable, register_xml_class

@register_xml_class
class Node(XMLSerializable):
	XML_TAG = 'point'
	XML_ATTRS = ['x', 'y', 'type', 'smooth']
	
	def __init__(self, x, y, type='line', smooth=False, **kwargs):
		self.x = x
		self.y = y
		self.type = type
		self.smooth = smooth

@register_xml_class
class Contour(XMLSerializable):
	XML_TAG = 'contour'
	XML_ATTRS = ['identifier']
	XML_CHILDREN = {'point': 'nodes'}
	XML_LIB_ATTRS = ['transform', 'closed', 'clockwise']
	
	def __init__(self, nodes=None, identifier=None, transform=None, 
	             closed=True, clockwise=None, lib=None, **kwargs):
		self.nodes = nodes or []
		self.identifier = identifier
		self.transform = transform
		self.closed = closed
		self.clockwise = clockwise
		self.lib = lib

# Now you can serialize/deserialize:
contour = Contour(nodes=[Node(100, 200), Node(300, 400)])
xml_string = contour.to_XML()
contour2 = Contour.from_XML(xml_string)
'''