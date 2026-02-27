// ===================================================================
// TypeRig Glyph Viewer — XML Serializer
// ===================================================================
'use strict';

// -- XML escape -----------------------------------------------------
TRV.esc = function(s) {
	return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
};

// -- Glyph → XML ----------------------------------------------------
TRV.glyphToXml = function(glyph) {
	let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
	xml += `<glyph name="${TRV.esc(glyph.name)}"`;
	if (glyph.identifier) xml += ` identifier="${TRV.esc(glyph.identifier)}"`;
	if (glyph.unicodes) xml += ` unicodes="${TRV.esc(glyph.unicodes)}"`;
	if (glyph.selected) xml += ` selected="True"`;
	if (glyph.mark) xml += ` mark="${glyph.mark}"`;
	xml += '>\n';

	for (const layer of glyph.layers) {
		xml += TRV.layerToXml(layer, '  ');
	}

	xml += '</glyph>';
	return xml;
};

TRV.layerToXml = function(layer, indent) {
	let xml = `${indent}<layer name="${TRV.esc(layer.name)}"`;
	if (layer.identifier) xml += ` identifier="${TRV.esc(layer.identifier)}"`;
	xml += ` width="${layer.width}" height="${layer.height}">\n`;

	for (const shape of layer.shapes) {
		xml += TRV.shapeToXml(shape, indent + '  ');
	}

	// Anchors
	if (layer.anchors) {
		for (const a of layer.anchors) {
			xml += `${indent}  <anchor name="${TRV.esc(a.name)}" x="${a.x}" y="${a.y}"/>\n`;
		}
	}

	// Lib (stems, transform, etc)
	const libData = { ...(layer.lib || {}) };
	if (layer.stx !== undefined && layer.stx !== null) libData.stx = layer.stx;
	if (layer.sty !== undefined && layer.sty !== null) libData.sty = layer.sty;
	if (Object.keys(libData).length > 0) {
		xml += TRV.plistLibToXml(libData, indent + '  ');
	}

	xml += `${indent}</layer>\n`;
	return xml;
};

TRV.shapeToXml = function(shape, indent) {
	let xml = `${indent}<shape`;
	if (shape.name) xml += ` name="${TRV.esc(shape.name)}"`;
	if (shape.identifier) xml += ` identifier="${TRV.esc(shape.identifier)}"`;
	xml += '>\n';

	for (const contour of shape.contours) {
		xml += TRV.contourToXml(contour, indent + '  ');
	}

	// Shape lib
	if (shape.lib && Object.keys(shape.lib).length > 0) {
		xml += TRV.plistLibToXml(shape.lib, indent + '  ');
	}

	xml += `${indent}</shape>\n`;
	return xml;
};

TRV.contourToXml = function(contour, indent) {
	let xml = `${indent}<contour`;
	if (contour.name) xml += ` name="${TRV.esc(contour.name)}"`;
	if (contour.identifier) xml += ` identifier="${TRV.esc(contour.identifier)}"`;
	xml += '>\n';

	for (const node of contour.nodes) {
		xml += `${indent}  <node x="${node.x}" y="${node.y}" type="${node.type}"`;
		if (node.smooth) xml += ` smooth="True"`;
		xml += '/>\n';
	}

	// Contour lib (closed, clockwise, etc)
	const libData = { ...(contour.lib || {}) };
	if (contour.closed !== undefined) libData.closed = contour.closed;
	if (contour.clockwise !== null && contour.clockwise !== undefined) libData.clockwise = contour.clockwise;
	if (Object.keys(libData).length > 0) {
		xml += TRV.plistLibToXml(libData, indent + '  ');
	}

	xml += `${indent}</contour>\n`;
	return xml;
};

TRV.plistLibToXml = function(data, indent) {
	let xml = `${indent}<lib>\n${indent}  <dict>\n`;
	for (const [key, val] of Object.entries(data)) {
		xml += `${indent}    <key>${TRV.esc(key)}</key>\n`;
		xml += `${indent}    ${TRV.plistValueToXml(val)}\n`;
	}
	xml += `${indent}  </dict>\n${indent}</lib>\n`;
	return xml;
};

TRV.plistValueToXml = function(val) {
	if (val === true) return '<true/>';
	if (val === false) return '<false/>';
	if (typeof val === 'number') {
		return Number.isInteger(val) ? `<integer>${val}</integer>` : `<real>${val}</real>`;
	}
	if (typeof val === 'string') return `<string>${TRV.esc(val)}</string>`;
	if (Array.isArray(val)) {
		if (val.length === 0) return '<array/>';
		let xml = '<array>';
		for (const item of val) xml += TRV.plistValueToXml(item);
		xml += '</array>';
		return xml;
	}
	return `<string>${TRV.esc(String(val))}</string>`;
};

// -- Sync glyph data → XML textarea --------------------------------
TRV.syncXmlFromData = function() {
	if (!TRV.state.glyphData) return;
	const newXml = TRV.glyphToXml(TRV.state.glyphData);
	TRV.state.rawXml = newXml;

	if (TRV.state.showXml) {
		const formatted = TRV.formatXml(newXml);
		TRV.dom.xmlContent.value = formatted;
		TRV.rebuildLineMaps(formatted);
		TRV.updateNodeCount();
		TRV.setParseStatus(true);
	}
};
