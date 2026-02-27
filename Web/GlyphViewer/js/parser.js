// ===================================================================
// TypeRig Glyph Viewer — XML Parser
// ===================================================================
'use strict';

TRV.parseGlyphXML = function(xmlString) {
	const parser = new DOMParser();
	const doc = parser.parseFromString(xmlString, 'text/xml');
	const parseError = doc.querySelector('parsererror');
	if (parseError) throw new Error('XML parse error: ' + parseError.textContent);

	const glyphEl = doc.querySelector('glyph');
	if (!glyphEl) throw new Error('No <glyph> element found');

	const glyph = {
		name: glyphEl.getAttribute('name') || '',
		identifier: glyphEl.getAttribute('identifier') || '',
		unicodes: glyphEl.getAttribute('unicodes') || '',
		mark: parseInt(glyphEl.getAttribute('mark') || '0'),
		selected: glyphEl.getAttribute('selected') === 'True',
		layers: [],
	};

	for (const layerEl of glyphEl.querySelectorAll(':scope > layer')) {
		glyph.layers.push(TRV.parseLayer(layerEl));
	}

	return glyph;
};

TRV.parseLayer = function(el) {
	const layer = {
		name: el.getAttribute('name') || '',
		identifier: el.getAttribute('identifier') || '',
		width: parseFloat(el.getAttribute('width') || '0'),
		height: parseFloat(el.getAttribute('height') || '1000'),
		shapes: [],
		anchors: [],
		lib: {},
	};

	// Parse lib for stems, transform etc
	const libEl = el.querySelector(':scope > lib');
	if (libEl) {
		layer.lib = TRV.parsePlistDict(libEl.querySelector('dict'));
	}

	if (layer.lib.stx !== undefined) layer.stx = layer.lib.stx;
	if (layer.lib.sty !== undefined) layer.sty = layer.lib.sty;

	for (const shapeEl of el.querySelectorAll(':scope > shape')) {
		layer.shapes.push(TRV.parseShape(shapeEl));
	}

	// Parse anchors if present
	for (const anchorEl of el.querySelectorAll(':scope > anchor')) {
		layer.anchors.push({
			name: anchorEl.getAttribute('name') || '',
			x: parseFloat(anchorEl.getAttribute('x') || '0'),
			y: parseFloat(anchorEl.getAttribute('y') || '0'),
		});
	}

	return layer;
};

TRV.parseShape = function(el) {
	const shape = {
		name: el.getAttribute('name') || '',
		identifier: el.getAttribute('identifier') || '',
		contours: [],
		lib: {},
	};

	const libEl = el.querySelector(':scope > lib');
	if (libEl) {
		shape.lib = TRV.parsePlistDict(libEl.querySelector('dict'));
	}

	for (const contourEl of el.querySelectorAll(':scope > contour')) {
		shape.contours.push(TRV.parseContour(contourEl));
	}

	return shape;
};

TRV.parseContour = function(el) {
	const contour = {
		name: el.getAttribute('name') || '',
		identifier: el.getAttribute('identifier') || '',
		closed: true,
		clockwise: null,
		nodes: [],
		lib: {},
	};

	const libEl = el.querySelector(':scope > lib');
	if (libEl) {
		const libData = TRV.parsePlistDict(libEl.querySelector('dict'));
		if (libData.closed !== undefined) contour.closed = libData.closed;
		if (libData.clockwise !== undefined) contour.clockwise = libData.clockwise;
		contour.lib = libData;
	}

	for (const nodeEl of el.querySelectorAll(':scope > node')) {
		contour.nodes.push({
			x: parseFloat(nodeEl.getAttribute('x') || '0'),
			y: parseFloat(nodeEl.getAttribute('y') || '0'),
			type: nodeEl.getAttribute('type') || 'on',
			smooth: nodeEl.getAttribute('smooth') === 'True',
		});
	}

	return contour;
};

TRV.parsePlistDict = function(dictEl) {
	if (!dictEl) return {};
	const result = {};
	const children = Array.from(dictEl.children);
	let i = 0;
	while (i < children.length) {
		if (children[i].tagName === 'key') {
			const key = children[i].textContent;
			i++;
			if (i < children.length) {
				result[key] = TRV.parsePlistValue(children[i]);
			}
		}
		i++;
	}
	return result;
};

TRV.parsePlistValue = function(el) {
	switch (el.tagName) {
		case 'true': return true;
		case 'false': return false;
		case 'integer': return parseInt(el.textContent);
		case 'real': return parseFloat(el.textContent);
		case 'string': return el.textContent || '';
		case 'array': return Array.from(el.children).map(TRV.parsePlistValue);
		case 'dict': return TRV.parsePlistDict(el);
		default: return null;
	}
};
