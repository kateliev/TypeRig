# MODULE: TypeRig / IO / SVG
# NOTE: SVG Serialization Module
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025 		(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

'''
HELP:
SVG serialization for TypeRig objects.
Supports two modes:
- BW mode: Black filled outlines on white background (standard for type design)
- Color-separated mode: Each contour colorized with predefined color table
  for layer compatibility visualization.

Usage:
    from typerig.core.fileio.svgio import glyph_to_SVG, font_to_SVG
    
    # Single glyph to SVG
    glyph.to_SVG(mode='color')
    
    # Bulk export from font
    font.to_SVG(output_dir='./SVG', mode='color', structure='flat')
'''

# - Dependencies ------------------------
from __future__ import absolute_import, print_function, division
import os
import math
from xml.etree import ElementTree as ET

# - Init --------------------------------
__version__ = '0.1.0'

# - Constants ---------------------------
DEFAULT_PATH_PATTERN = '{glyph}_{layer}.svg'
EXPORT_FLAT = 'flat'
EXPORT_NESTED = 'nested'

# - Color Table -------------------------
# 128 predefined colors for contour visualization
# Colors are evenly distributed around the color wheel for maximum contrast
SVG_COLORS = [
    # Row 1 - Reds/Oranges
    '#FF0000', '#FF1400', '#FF2800', '#FF3C00', '#FF5000', '#FF6400', '#FF7800', '#FF8C00',
    '#FFA000', '#FFB400', '#FFC800', '#FFDC00', '#FFF000', '#DBFF00', '#B7FF00', '#93FF00',
    # Row 2 - Yellows/Limes
    '#6FFF00', '#4BFF00', '#27FF00', '#03FF00', '#00FF27', '#00FF4B', '#00FF6F', '#00FF93',
    '#00FFB7', '#00FFDB', '#00FFFF', '#00DBFF', '#00B7FF', '#0093FF', '#006FFF', '#004BFF',
    # Row 3 - Blues
    '#0000FF', '#1400FF', '#2800FF', '#3C00FF', '#5000FF', '#6400FF', '#7800FF', '#8C00FF',
    '#A000FF', '#B400FF', '#C800FF', '#DC00FF', '#F000FF', '#FF00DB', '#FF00B7', '#FF0093',
    # Row 4 - Pinks/Magentas
    '#FF006F', '#FF004B', '#FF0027', '#FF0300', '#FF1400', '#FF2800', '#FF3C00', '#FF5000',
    '#FF6400', '#FF7800', '#FF8C00', '#FFA000', '#FFB400', '#E68A00', '#CC7400', '#B25E00',
    # Row 5 - Browns/Golds
    '#984800', '#7E3200', '#641C00', '#4A0600', '#FF6B6B', '#FF8C8C', '#FFADAD', '#FFCECE',
    '#FFEFEF', '#FFD6D6', '#FFBDBD', '#FFA4A4', '#FF8B8B', '#FF7272', '#FF5959', '#FF4040',
    # Row 6 - More variation
    '#FF2727', '#FF0E0E', '#E60000', '#CC0000', '#B30000', '#990000', '#800000', '#670000',
    '#4D0000', '#330000', '#1A0000', '#FF9999', '#FFAAAA', '#FFBBBB', '#FFCCCC', '#FFDDDD',
    # Row 7 - Additional
    '#FFEEEE', '#FFFFFF', '#000000', '#1A1A1A', '#333333', '#4D4D4D', '#666666', '#808080',
    '#999999', '#B3B3B3', '#CCCCCC', '#E6E6E6', '#F2F2F2', '#0D0D0D', '#1A1A33', '#33331A',
    # Row 8 - More variation
    '#1A3333', '#331A1A', '#331A33', '#33331A', '#2D4A8C', '#4A2D8C', '#8C2D4A', '#8C4A2D',
    '#2D8C4A', '#4A8C2D', '#8C2D2D', '#2D2D8C', '#8C4A8C', '#4A8C4A', '#8C8C4A', '#4A4A8C',
]

# Ensure we have exactly 128 colors
assert len(SVG_COLORS) == 128, f"SVG_COLORS must have 128 colors, got {len(SVG_COLORS)}"


# - Helpers -----------------------------
def _format_float(v):
    '''Compact float: whole numbers lose the decimal, others strip trailing zeros'''
    if v == int(v):
        return str(int(v))
    return '{:.4f}'.format(v).rstrip('0').rstrip('.')


def _flip_y(y, height, scale=1.0):
    '''Flip Y coordinate for SVG (origin at top-left)'''
    return height - (y * scale)


def _get_contour_style(contour_index, mode):
    '''Get fill and stroke colors for a contour based on mode and index'''
    if mode == 'bw':
        return {'fill': '#000000', 'stroke': '#000000', 'fill-opacity': '1.0', 'stroke-opacity': '1.0'}
    else:  # mode == 'color'
        color = SVG_COLORS[contour_index % 128]
        return {'fill': color, 'stroke': color, 'fill-opacity': '0.4', 'stroke-opacity': '1.0'}


# - SVG Serializable Mixin -------------
class SVGSerializable:
    '''Mixin class for SVG serialization'''
    
    # Override in subclasses
    SVG_TAG = None
    
    def __init__(self, path_pattern=None):
        self._path_pattern = path_pattern or DEFAULT_PATH_PATTERN
    
    def to_SVG(self, mode='color', scale=1.0, flip_y=True, bounds=None, **kwargs):
        '''Convert object to SVG string
        mode: 'bw' for black/white or 'color' for color-separated
        scale: coordinate scaling factor
        flip_y: flip Y-axis for font tool compatibility
        bounds: (x, y, w, h) optional bounding box override
        '''
        raise NotImplementedError("Subclasses must implement to_SVG()")
    
    def _get_path_pattern(self, glyph_name=None, layer_name=None, index=0):
        '''Get output filename from pattern'''
        result = self._path_pattern
        result = result.replace('{glyph}', str(glyph_name or 'glyph'))
        result = result.replace('{layer}', str(layer_name or 'layer'))
        result = result.replace('{index}', str(index))
        return result


# - Node SVG Conversion -----------------
def node_to_SVG(node, scale=1.0, flip_y=True, height=1000):
    '''Convert Node to SVG element'''
    x = node.x * scale
    y = node.y * scale
    if flip_y:
        y = _flip_y(y, height, scale)
    
    # Node as small circle
    elem = ET.Element('circle', {
        'cx': _format_float(x),
        'cy': _format_float(y),
        'r': str(2.0 * scale),
        'fill': '#000000'
    })
    return elem


# - Contour SVG Conversion -------------
def contour_to_SVG(contour, mode='color', scale=1.0, flip_y=True, height=1000, index=0):
    '''Convert Contour to SVG path element'''
    if len(contour.nodes) == 0:
        return None
    
    nodes = list(contour.nodes)
    if not contour.closed and len(nodes) > 0:
        nodes = nodes[:-1]  # Skip closing node for open contours
    
    d_parts = []
    height_scaled = height * scale
    
    for i, node in enumerate(nodes):
        x = node.x * scale
        y = node.y * scale
        if flip_y:
            y = _flip_y(y, height, scale)
        
        # Handle in point
        if hasattr(node, 'handle_in') and node.handle_in:
            hx_in = (node.x + node.handle_in.x) * scale
            hy_in = (node.y + node.handle_in.y) * scale
            if flip_y:
                hy_in = _flip_y(hy_in, height, scale)
        
        # Handle out point
        if hasattr(node, 'handle_out') and node.handle_out:
            hx_out = (node.x + node.handle_out.x) * scale
            hy_out = (node.y + node.handle_out.y) * scale
            if flip_y:
                hy_out = _flip_y(hy_out, height, scale)
        
        if i == 0:
            d_parts.append('M {} {}'.format(_format_float(x), _format_float(y)))
        else:
            prev_node = nodes[i - 1]
            
            # Check if there's a curve
            has_handle_out = hasattr(prev_node, 'handle_out') and prev_node.handle_out
            has_handle_in = hasattr(node, 'handle_in') and node.handle_in
            
            if has_handle_out and has_handle_in:
                # Cubic bezier
                hx_out = (prev_node.x + prev_node.handle_out.x) * scale
                hy_out = (prev_node.y + prev_node.handle_out.y) * scale
                if flip_y:
                    hy_out = _flip_y(hy_out, height, scale)
                
                hx_in = (node.x + node.handle_in.x) * scale
                hy_in = (node.y + node.handle_in.y) * scale
                if flip_y:
                    hy_in = _flip_y(hy_in, height, scale)
                
                d_parts.append('C {} {} {} {} {} {}'.format(
                    _format_float(hx_out), _format_float(hy_out),
                    _format_float(hx_in), _format_float(hy_in),
                    _format_float(x), _format_float(y)
                ))
            elif has_handle_out:
                # Quadratic (one handle)
                hx_out = (prev_node.x + prev_node.handle_out.x) * scale
                hy_out = (prev_node.y + prev_node.handle_out.y) * scale
                if flip_y:
                    hy_out = _flip_y(hy_out, height, scale)
                
                d_parts.append('Q {} {} {} {}'.format(
                    _format_float(hx_out), _format_float(hy_out),
                    _format_float(x), _format_float(y)
                ))
            else:
                # Line
                d_parts.append('L {} {}'.format(_format_float(x), _format_float(y)))
    
    # Close path
    if contour.closed:
        d_parts.append('Z')
    
    # Get style
    style = _get_contour_style(index, mode)
    
    path_elem = ET.Element('path', {
        'd': ' '.join(d_parts),
        'fill': style['fill'],
        'stroke': style['stroke'],
        'fill-opacity': style['fill-opacity'],
        'stroke-opacity': style['stroke-opacity'],
        'stroke-width': str(1.0 * scale)
    })
    
    return path_elem


def _bounds_to_tuple(bounds):
    '''Convert Bounds object or tuple to (x, y, w, h) tuple'''
    if bounds is None:
        return None
    if hasattr(bounds, 'x'):  # Bounds object
        return (bounds.x, bounds.y, bounds.width, bounds.height)
    if hasattr(bounds, 'width') and bounds.width == 0 and bounds.height == 0:
        # Empty bounds
        return None
    return bounds  # Already a tuple


# - Layer SVG Conversion ----------------
def layer_to_SVG(layer, mode='color', scale=1.0, flip_y=True, bounds=None):
    '''Convert Layer to SVG group element'''
    group = ET.Element('g', {'id': str(layer.name)})
    
    # Get bounding box
    if bounds is None:
        layer_bounds = layer.bounds
        bounds = _bounds_to_tuple(layer_bounds)
    
    height = bounds[3] - bounds[1] if bounds else 1000
    
    # Add all contours
    for idx, contour in enumerate(layer.contours):
        path_elem = contour_to_SVG(contour, mode=mode, scale=scale, flip_y=flip_y, height=height, index=idx)
        if path_elem is not None:
            group.append(path_elem)
    
    return group


# - Glyph SVG Conversion ----------------
def glyph_to_SVG(glyph, mode='color', scale=1.0, flip_y=True):
    '''Convert Glyph to full SVG document'''
    # Get bounding box - calculate from layers
    bounds = None
    for layer in glyph.layers:
        layer_bounds = _bounds_to_tuple(layer.bounds)
        if layer_bounds:
            if bounds is None:
                bounds = layer_bounds
            else:
                # Expand bounds
                bounds = (
                    min(bounds[0], layer_bounds[0]),
                    min(bounds[1], layer_bounds[1]),
                    max(bounds[2], layer_bounds[2]),
                    max(bounds[3], layer_bounds[3])
                )
    
    if not bounds:
        bounds = (0, 0, 1000, 1000)
    
    x, y, w, h = bounds
    width = max(w, 1)
    height = max(h, 1)
    
    # Create SVG root
    svg_elem = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'width': _format_float(width * scale),
        'height': _format_float(height * scale),
        'viewBox': '{} {} {} {}'.format(
            _format_float(x), _format_float(y),
            _format_float(width), _format_float(height)
        )
    })
    
    # Add metadata
    metadata = ET.SubElement(svg_elem, 'metadata')
    
    fontname_elem = ET.SubElement(metadata, 'fontname')
    fontname_elem.text = str(getattr(glyph, 'parent', None) or 'Unknown')
    
    glyphname_elem = ET.SubElement(metadata, 'glyphname')
    glyphname_elem.text = str(glyph.name)
    
    if hasattr(glyph, 'unicodes') and glyph.unicodes:
        unicode_elem = ET.SubElement(metadata, 'unicode')
        unicode_elem.text = hex(glyph.unicodes[0])[2:].upper().zfill(4)
    
    # Add white background
    bg = ET.SubElement(svg_elem, 'rect', {
        'x': _format_float(x),
        'y': _format_float(y),
        'width': _format_float(width),
        'height': _format_float(height),
        'fill': '#FFFFFF'
    })
    
    # Add layers
    for layer_idx, layer in enumerate(glyph.layers):
        layer_group = layer_to_SVG(layer, mode=mode, scale=scale, flip_y=flip_y, bounds=bounds)
        
        # Add layer metadata
        layer_meta = ET.SubElement(layer_group, 'metadata')
        layername_elem = ET.SubElement(layer_meta, 'layername')
        layername_elem.text = str(layer.name)
        
        svg_elem.append(layer_group)
    
    return ET.tostring(svg_elem, encoding='unicode')


# - Font SVG Export ---------------------
def font_to_SVG(font, output_dir='./SVG', mode='color', scale=1.0, structure=EXPORT_FLAT, path_pattern=None):
    '''Export all glyphs in font to SVG files
    
    Args:
        font: trFont object
        output_dir: Base output directory
        mode: 'bw' or 'color'
        scale: Coordinate scaling
        structure: 'flat' or 'nested'
        path_pattern: Custom naming pattern (default: '{glyph}_{layer}.svg')
    '''
    os.makedirs(output_dir, exist_ok=True)
    
    font_name = getattr(font, 'info', None)
    font_name = getattr(font_name, 'family_name', 'Font') if font_name else 'Font'
    
    # Clean font name for directory
    font_dir_name = font_name.replace(' ', '_').replace('/', '_')
    
    if structure == EXPORT_NESTED:
        font_output_dir = os.path.join(output_dir, font_dir_name)
        os.makedirs(font_output_dir, exist_ok=True)
    else:
        font_output_dir = output_dir
    
    # Export each glyph
    for glyph in font.glyphs:
        glyph_to_SVG_file(glyph, font_output_dir, mode=mode, scale=scale, structure=structure, path_pattern=path_pattern)
    
    return font_output_dir


def glyph_to_SVG_file(glyph, output_dir, mode='color', scale=1.0, structure=EXPORT_FLAT, path_pattern=None):
    '''Export single glyph layers to SVG files'''
    os.makedirs(output_dir, exist_ok=True)
    
    glyph_name = glyph.name.replace(' ', '_').replace('/', '_')
    
    if structure == EXPORT_NESTED:
        glyph_output_dir = os.path.join(output_dir, glyph_name)
        os.makedirs(glyph_output_dir, exist_ok=True)
    else:
        glyph_output_dir = output_dir
    
    for layer_idx, layer in enumerate(glyph.layers):
        layer_name = layer.name.replace(' ', '_').replace('/', '_')
        
        # Generate filename
        if path_pattern:
            filename = path_pattern.format(glyph=glyph_name, layer=layer_name, index=layer_idx)
        else:
            filename = '{}_{}.svg'.format(glyph_name, layer_name)
        
        filepath = os.path.join(glyph_output_dir, filename)
        
        # Generate SVG content
        # Calculate bounds from layers
        bounds = None
        for layer in glyph.layers:
            try:
                layer_bounds = _bounds_to_tuple(layer.bounds)
                if layer_bounds:
                    if bounds is None:
                        bounds = layer_bounds
                    else:
                        bounds = (
                            min(bounds[0], layer_bounds[0]),
                            min(bounds[1], layer_bounds[1]),
                            max(bounds[2], layer_bounds[2]),
                            max(bounds[3], layer_bounds[3])
                        )
            except (AssertionError, AttributeError):
                # Skip empty layers
                pass
        
        if not bounds:
            bounds = (0, 0, 1000, 1000)
        
        x, y, w, h = bounds
        width = max(w, 1)
        height = max(h, 1)
        
        svg_elem = ET.Element('svg', {
            'xmlns': 'http://www.w3.org/2000/svg',
            'width': _format_float(width * scale),
            'height': _format_float(height * scale),
            'viewBox': '{} {} {} {}'.format(
                _format_float(x), _format_float(y),
                _format_float(width), _format_float(height)
            )
        })
        
        # Add metadata
        metadata = ET.SubElement(svg_elem, 'metadata')
        
        fontname_elem = ET.SubElement(metadata, 'fontname')
        fontname_elem.text = str(getattr(glyph, 'parent', None) or 'Unknown')
        
        glyphname_elem = ET.SubElement(metadata, 'glyphname')
        glyphname_elem.text = str(glyph.name)
        
        if hasattr(glyph, 'unicodes') and glyph.unicodes:
            unicode_elem = ET.SubElement(metadata, 'unicode')
            unicode_elem.text = hex(glyph.unicodes[0])[2:].upper().zfill(4)
        
        layername_elem = ET.SubElement(metadata, 'layername')
        layername_elem.text = str(layer.name)
        
        # Add white background
        bg = ET.SubElement(svg_elem, 'rect', {
            'x': _format_float(x),
            'y': _format_float(y),
            'width': _format_float(width),
            'height': _format_float(height),
            'fill': '#FFFFFF'
        })
        
        # Add layer contours
        height_val = height
        for idx, contour in enumerate(layer.contours):
            path_elem = contour_to_SVG(contour, mode=mode, scale=scale, flip_y=True, height=height_val, index=idx)
            if path_elem is not None:
                svg_elem.append(path_elem)
        
        # Write file
        svg_string = ET.tostring(svg_elem, encoding='unicode')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(svg_string)
    
    return glyph_output_dir


# - Add to_SVG methods to core classes --
# These will be imported and applied to core objects
def add_svg_methods():
    '''Add to_SVG methods to core objects (called at import)'''
    from typerig.core.objects.node import Node
    from typerig.core.objects.contour import Contour
    from typerig.core.objects.layer import Layer
    from typerig.core.objects.glyph import Glyph
    from typerig.core.objects.font import Font
    
    # Node.to_SVG()
    def node_to_SVG_method(self, mode='color', scale=1.0, flip_y=True, height=1000, **kwargs):
        return node_to_SVG(self, scale=scale, flip_y=flip_y, height=height)
    
    Node.to_SVG = node_to_SVG_method
    
    # Contour.to_SVG()
    def contour_to_SVG_method(self, mode='color', scale=1.0, flip_y=True, height=1000, index=0, **kwargs):
        path_elem = contour_to_SVG(self, mode=mode, scale=scale, flip_y=flip_y, height=height, index=index)
        return ET.tostring(path_elem, encoding='unicode') if path_elem else ''
    
    Contour.to_SVG = contour_to_SVG_method
    
    # Layer.to_SVG()
    def layer_to_SVG_method(self, mode='color', scale=1.0, flip_y=True, **kwargs):
        bounds = kwargs.get('bounds') or self.bounds
        bounds = _bounds_to_tuple(bounds)
        group = layer_to_SVG(self, mode=mode, scale=scale, flip_y=flip_y, bounds=bounds)
        return ET.tostring(group, encoding='unicode')
    
    Layer.to_SVG = layer_to_SVG_method
    
    # Glyph.to_SVG()
    def glyph_to_SVG_method(self, mode='color', scale=1.0, flip_y=True, **kwargs):
        return glyph_to_SVG(self, mode=mode, scale=scale, flip_y=flip_y)
    
    Glyph.to_SVG = glyph_to_SVG_method
    
    # Font.to_SVG()
    def font_to_SVG_method(self, output_dir='./SVG', mode='color', scale=1.0, structure=EXPORT_FLAT, path_pattern=None):
        return font_to_SVG(self, output_dir=output_dir, mode=mode, scale=scale, structure=structure, path_pattern=path_pattern)
    
    Font.to_SVG = font_to_SVG_method


# Auto-add methods when module is imported
add_svg_methods()