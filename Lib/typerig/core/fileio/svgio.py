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
import colorsys
from xml.etree import ElementTree as ET

# - Init --------------------------------
__version__ = '0.1.0'

# - Constants ---------------------------
DEFAULT_PATH_PATTERN = '{glyph}_{layer}.svg'
EXPORT_FLAT = 'flat'
EXPORT_NESTED = 'nested'

# - Color Table -------------------------
# 128 colors generated via golden-ratio hue rotation (golden angle ≈ 137.508°).
#
# Why golden ratio: the golden angle places each new hue as far as possible from
# all previous ones on the color wheel. This means:
#   - Any subset of the first N colors is maximally spread (no two close hues)
#   - Index i always maps to the same color regardless of how many contours exist
#   - Cross-layer comparison works: same contour index == same color in all layers
#
# Parameters: S=0.85 (vivid), L=0.52 (bright enough on white, not washed out)

def _build_golden_colors(n=128, saturation=0.85, lightness=0.52):
    golden_angle = 137.508  # degrees — 360° × (2 − φ), φ = golden ratio
    colors = []
    for i in range(n):
        hue = (i * golden_angle % 360) / 360.0
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        colors.append('#{:02X}{:02X}{:02X}'.format(
            int(round(r * 255)),
            int(round(g * 255)),
            int(round(b * 255)),
        ))
    return colors

SVG_COLORS = _build_golden_colors()


# - Helpers -----------------------------
def _format_float(v):
    '''Compact float: whole numbers lose the decimal, others strip trailing zeros'''
    if v == int(v):
        return str(int(v))
    return '{:.4f}'.format(v).rstrip('0').rstrip('.')


def _get_contour_style(contour_index, mode):
    '''Get fill and stroke style for a contour based on mode and index.

    BW mode: solid black fill, 1px stroke.
    Color mode (optimised for human + LLM visual debugging):
      - Stroke: fully opaque, 2px — survives thumbnail downscaling
      - Fill:   same color at 35% opacity — light tint that makes region visible
                while letting overlapping contours show through
    '''
    if mode == 'bw':
        return {
            'fill': '#000000', 'stroke': '#000000',
            'fill-opacity': '1', 'stroke-opacity': '1',
            'stroke-width': '1',
        }
    else:  # color
        color = SVG_COLORS[contour_index % 128]
        return {
            'fill': color, 'stroke': color,
            'fill-opacity': '0.5', 'stroke-opacity': '1',
            'stroke-width': '2',
        }


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
def node_to_SVG(node, scale=1.0, **kwargs):
    '''Convert Node to SVG circle element (uses raw font coordinates; caller must apply Y-flip transform)'''
    x = node.x * scale
    y = node.y * scale
    elem = ET.Element('circle', {
        'cx': _format_float(x),
        'cy': _format_float(y),
        'r': _format_float(2.0 * scale),
        'fill': '#000000'
    })
    return elem


# - Contour SVG Conversion -------------
def _contour_to_d(contour, scale=1.0):
    '''Build an SVG path data string from a contour using node_segments.

    Writes raw font coordinates (no Y-flip); the caller's <g transform> handles it.
    Returns a 'd' string, or None if the contour is empty.
    '''
    if len(contour.nodes) == 0:
        return None

    try:
        segments = contour.node_segments  # list of [on_node, ...off_nodes..., on_node]
    except (AssertionError, Exception):
        return None

    if not segments:
        return None

    d_parts = []

    # Move to start of first segment (the first on-curve node)
    first = segments[0][0]
    d_parts.append('M {} {}'.format(
        _format_float(first.x * scale),
        _format_float(first.y * scale)
    ))

    for seg in segments:
        n = len(seg)
        end = seg[-1]
        ex = _format_float(end.x * scale)
        ey = _format_float(end.y * scale)

        if n == 2:
            # Line segment: [on, on]
            d_parts.append('L {} {}'.format(ex, ey))

        elif n == 4 and seg[1].type == 'curve':
            # Cubic bezier (PostScript/CFF): [on, curve, curve, on]
            cp1 = seg[1]
            cp2 = seg[2]
            d_parts.append('C {} {} {} {} {} {}'.format(
                _format_float(cp1.x * scale), _format_float(cp1.y * scale),
                _format_float(cp2.x * scale), _format_float(cp2.y * scale),
                ex, ey
            ))

        elif n >= 3 and seg[1].type == 'off':
            # TT quadratic: [on, off, ..., on] — expand complex runs with implicit on-curves
            off_nodes = seg[1:-1]
            for i, off in enumerate(off_nodes):
                qx = _format_float(off.x * scale)
                qy = _format_float(off.y * scale)
                if i < len(off_nodes) - 1:
                    # Implicit on-curve at midpoint between this and next off-curve
                    nxt = off_nodes[i + 1]
                    px = _format_float((off.x + nxt.x) * 0.5 * scale)
                    py = _format_float((off.y + nxt.y) * 0.5 * scale)
                else:
                    px, py = ex, ey
                d_parts.append('Q {} {} {} {}'.format(qx, qy, px, py))

        else:
            # Fallback: straight line
            d_parts.append('L {} {}'.format(ex, ey))

    if contour.closed:
        d_parts.append('Z')

    return ' '.join(d_parts)


def contour_to_SVG(contour, mode='color', scale=1.0, index=0, **kwargs):
    '''Convert Contour to an SVG path element.

    Coordinates are in raw font space; place inside a Y-flip <g transform> to render correctly.
    '''
    d = _contour_to_d(contour, scale=scale)
    if d is None:
        return None

    style = _get_contour_style(index, mode)
    stroke_w = _format_float(float(style['stroke-width']) * scale)
    return ET.Element('path', {
        'd': d,
        'fill': style['fill'],
        'fill-opacity': style['fill-opacity'],
        'fill-rule': 'evenodd',
        'stroke': style['stroke'],
        'stroke-opacity': style['stroke-opacity'],
        'stroke-width': stroke_w,
    })


def _bounds_to_tuple(bounds):
    '''Convert Bounds object to (x_min, y_min, x_max, y_max) tuple'''
    if bounds is None:
        return None
    if hasattr(bounds, 'xmax'):  # Bounds object
        if bounds.width == 0 and bounds.height == 0:
            return None
        return (bounds.x, bounds.y, bounds.xmax, bounds.ymax)
    return bounds  # Already a (x_min, y_min, x_max, y_max) tuple


# - Layer SVG Conversion ----------------
def layer_to_SVG(layer, mode='color', scale=1.0, x_min=0, y_min=0, y_max=1000, **kwargs):
    '''Convert Layer to an SVG group element.

    The group carries a transform that maps raw font coordinates (y-up) to SVG
    coordinates (y-down):  translate(-x_min, y_max) scale(1, -1)

    BW mode: all contours are merged into one compound <path> with fill-rule=evenodd
    so counter-wound inner contours become transparent holes.

    Color mode: one <path> per contour, colorized by index.
    '''
    transform = 'translate({}, {}) scale(1, -1)'.format(
        _format_float(-x_min * scale),
        _format_float(y_max * scale)
    )
    group = ET.Element('g', {'id': str(layer.name), 'transform': transform})

    if mode == 'bw':
        # Single compound path — all contours joined as subpaths
        d_parts = []
        for contour in layer.contours:
            d = _contour_to_d(contour, scale=scale)
            if d:
                d_parts.append(d)

        if d_parts:
            path_elem = ET.Element('path', {
                'd': ' '.join(d_parts),
                'fill': '#000000',
                'fill-rule': 'evenodd',
                'stroke': '#000000',
                'stroke-width': _format_float(scale),
            })
            group.append(path_elem)

    else:  # color mode
        for idx, contour in enumerate(layer.contours):
            path_elem = contour_to_SVG(contour, mode=mode, scale=scale, index=idx)
            if path_elem is not None:
                group.append(path_elem)

    return group


# - Glyph SVG Conversion ----------------
def _merge_bounds(accumulated, new_bounds):
    '''Expand (x_min, y_min, x_max, y_max) accumulated bounds to include new_bounds.'''
    if accumulated is None:
        return new_bounds
    return (
        min(accumulated[0], new_bounds[0]),
        min(accumulated[1], new_bounds[1]),
        max(accumulated[2], new_bounds[2]),
        max(accumulated[3], new_bounds[3]),
    )


def glyph_to_SVG(glyph, mode='color', scale=1.0, **kwargs):
    '''Convert Glyph to full SVG document string.

    viewBox spans the union of all layer bounding boxes in SVG space (0 0 width height).
    A per-layer transform handles the font→SVG coordinate flip.
    '''
    # Compute union bounds across all layers (x_min, y_min, x_max, y_max in font coords)
    bounds = None
    for layer in glyph.layers:
        try:
            lb = _bounds_to_tuple(layer.bounds)
            if lb:
                bounds = _merge_bounds(bounds, lb)
        except (AssertionError, AttributeError):
            pass

    if not bounds:
        bounds = (0, 0, 1000, 1000)

    x_min, y_min, x_max, y_max = bounds
    width = max(x_max - x_min, 1)
    height = max(y_max - y_min, 1)

    # SVG root — viewBox in SVG space: 0,0 → width,height
    svg_elem = ET.Element('svg', {
        'xmlns': 'http://www.w3.org/2000/svg',
        'width': _format_float(width * scale),
        'height': _format_float(height * scale),
        'viewBox': '0 0 {} {}'.format(
            _format_float(width * scale),
            _format_float(height * scale)
        )
    })

    # Metadata
    metadata = ET.SubElement(svg_elem, 'metadata')
    ET.SubElement(metadata, 'fontname').text = str(getattr(glyph, 'parent', None) or 'Unknown')
    ET.SubElement(metadata, 'glyphname').text = str(glyph.name)
    if hasattr(glyph, 'unicodes') and glyph.unicodes:
        ET.SubElement(metadata, 'unicode').text = hex(glyph.unicodes[0])[2:].upper().zfill(4)

    # White background
    ET.SubElement(svg_elem, 'rect', {
        'x': '0', 'y': '0',
        'width': _format_float(width * scale),
        'height': _format_float(height * scale),
        'fill': '#FFFFFF'
    })

    # Layers (each gets a Y-flip transform)
    for layer in glyph.layers:
        layer_group = layer_to_SVG(layer, mode=mode, scale=scale,
                                   x_min=x_min, y_min=y_min, y_max=y_max)
        ET.SubElement(layer_group, 'metadata').append(
            _make_elem('layername', str(layer.name))
        )
        svg_elem.append(layer_group)

    return ET.tostring(svg_elem, encoding='unicode')


def _make_elem(tag, text):
    '''Helper: create an XML element with text content.'''
    e = ET.Element(tag)
    e.text = text
    return e


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
    '''Export each layer of a glyph to its own SVG file.

    All files for one glyph share the same bounding box (union of all layers) so
    layers are directly comparable when viewed side-by-side.
    '''
    os.makedirs(output_dir, exist_ok=True)

    glyph_name = glyph.name.replace(' ', '_').replace('/', '_')

    if structure == EXPORT_NESTED:
        glyph_output_dir = os.path.join(output_dir, glyph_name)
        os.makedirs(glyph_output_dir, exist_ok=True)
    else:
        glyph_output_dir = output_dir

    # Union bounds across all layers (x_min, y_min, x_max, y_max in font coords)
    bounds = None
    for lyr in glyph.layers:
        try:
            lb = _bounds_to_tuple(lyr.bounds)
            if lb:
                bounds = _merge_bounds(bounds, lb)
        except (AssertionError, AttributeError):
            pass

    if not bounds:
        bounds = (0, 0, 1000, 1000)

    x_min, y_min, x_max, y_max = bounds
    width = max(x_max - x_min, 1)
    height = max(y_max - y_min, 1)

    for layer_idx, layer in enumerate(glyph.layers):
        layer_name = layer.name.replace(' ', '_').replace('/', '_')

        if path_pattern:
            filename = path_pattern.format(glyph=glyph_name, layer=layer_name, index=layer_idx)
        else:
            filename = '{}_{}.svg'.format(glyph_name, layer_name)

        filepath = os.path.join(glyph_output_dir, filename)

        # SVG root
        svg_elem = ET.Element('svg', {
            'xmlns': 'http://www.w3.org/2000/svg',
            'width': _format_float(width * scale),
            'height': _format_float(height * scale),
            'viewBox': '0 0 {} {}'.format(
                _format_float(width * scale),
                _format_float(height * scale)
            )
        })

        # Metadata
        metadata = ET.SubElement(svg_elem, 'metadata')
        ET.SubElement(metadata, 'fontname').text = str(getattr(glyph, 'parent', None) or 'Unknown')
        ET.SubElement(metadata, 'glyphname').text = str(glyph.name)
        if hasattr(glyph, 'unicodes') and glyph.unicodes:
            ET.SubElement(metadata, 'unicode').text = hex(glyph.unicodes[0])[2:].upper().zfill(4)
        ET.SubElement(metadata, 'layername').text = str(layer.name)

        # White background
        ET.SubElement(svg_elem, 'rect', {
            'x': '0', 'y': '0',
            'width': _format_float(width * scale),
            'height': _format_float(height * scale),
            'fill': '#FFFFFF'
        })

        # Layer group (carries Y-flip transform)
        layer_group = layer_to_SVG(layer, mode=mode, scale=scale,
                                   x_min=x_min, y_min=y_min, y_max=y_max)
        svg_elem.append(layer_group)

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
    def node_to_SVG_method(self, scale=1.0, **kwargs):
        return ET.tostring(node_to_SVG(self, scale=scale), encoding='unicode')

    Node.to_SVG = node_to_SVG_method

    # Contour.to_SVG()
    def contour_to_SVG_method(self, mode='color', scale=1.0, index=0, **kwargs):
        path_elem = contour_to_SVG(self, mode=mode, scale=scale, index=index)
        return ET.tostring(path_elem, encoding='unicode') if path_elem else ''

    Contour.to_SVG = contour_to_SVG_method

    # Layer.to_SVG()
    def layer_to_SVG_method(self, mode='color', scale=1.0, **kwargs):
        try:
            b = _bounds_to_tuple(self.bounds)
        except (AssertionError, AttributeError):
            b = (0, 0, 1000, 1000)
        x_min, y_min, x_max, y_max = b or (0, 0, 1000, 1000)
        group = layer_to_SVG(self, mode=mode, scale=scale,
                              x_min=x_min, y_min=y_min, y_max=y_max)
        return ET.tostring(group, encoding='unicode')

    Layer.to_SVG = layer_to_SVG_method

    # Glyph.to_SVG()
    def glyph_to_SVG_method(self, mode='color', scale=1.0, **kwargs):
        return glyph_to_SVG(self, mode=mode, scale=scale)

    Glyph.to_SVG = glyph_to_SVG_method

    # Font.to_SVG()
    def font_to_SVG_method(self, output_dir='./SVG', mode='color', scale=1.0,
                            structure=EXPORT_FLAT, path_pattern=None):
        return font_to_SVG(self, output_dir=output_dir, mode=mode, scale=scale,
                            structure=structure, path_pattern=path_pattern)

    Font.to_SVG = font_to_SVG_method


# Auto-add methods when module is imported
add_svg_methods()