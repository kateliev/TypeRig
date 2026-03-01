// ===================================================================
// TypeRig Glyph Viewer — XML Serializer
// ===================================================================
'use strict';

// -- XML escape -----------------------------------------------------
TRV.esc = function(s) {
	return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
};

// -- Compact float: drop .0 for integers, strip trailing zeros ------
TRV.fmtFloat = function(v) {
	if (Number.isInteger(v)) return String(v);
	// Up to 6 decimal places, strip trailing zeros
	return parseFloat(v.toFixed(6)).toString();
};

// -- Format a 6-element transform array as matrix() string ----------
// Returns null when the transform is identity (skip writing)
TRV.fmtTransform = function(t) {
	if (!Array.isArray(t) || t.length !== 6) return null;
	// Identity check: [1, 0, 0, 1, 0, 0]
	if (t[0] === 1 && t[1] === 0 && t[2] === 0 && t[3] === 1 && t[4] === 0 && t[5] === 0) return null;
	return 'matrix(' + t.map(TRV.fmtFloat).join(' ') + ')';
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
	xml += ` width="${layer.width}" height="${layer.height}"`;
	// stx/sty as direct attributes, only when present
	if (layer.stx !== undefined && layer.stx !== null) xml += ` stx="${TRV.fmtFloat(layer.stx)}"`;
	if (layer.sty !== undefined && layer.sty !== null) xml += ` sty="${TRV.fmtFloat(layer.sty)}"`;
	xml += '>\n';

	for (const shape of layer.shapes) {
		xml += TRV.shapeToXml(shape, indent + '  ');
	}

	if (layer.anchors) {
		for (const a of layer.anchors) {
			xml += `${indent}  <anchor name="${TRV.esc(a.name)}" x="${a.x}" y="${a.y}"/>\n`;
		}
	}

	// Only write lib for truly custom data — stx/sty no longer go here
	const libData = {};
	for (const [k, v] of Object.entries(layer.lib || {})) {
		if (k !== 'stx' && k !== 'sty') libData[k] = v;
	}
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
	// transform as matrix() attribute, skipped when identity or absent
	const tx = TRV.fmtTransform(shape.transform);
	if (tx) xml += ` transform="${TRV.esc(tx)}"`;
	xml += '>\n';

	for (const contour of shape.contours) {
		xml += TRV.contourToXml(contour, indent + '  ');
	}

	// Only write lib for truly custom data — transform no longer goes here
	const libData = {};
	for (const [k, v] of Object.entries(shape.lib || {})) {
		if (k !== 'transform') libData[k] = v;
	}
	if (Object.keys(libData).length > 0) {
		xml += TRV.plistLibToXml(libData, indent + '  ');
	}

	xml += `${indent}</shape>\n`;
	return xml;
};

TRV.contourToXml = function(contour, indent) {
	let xml = `${indent}<contour`;
	if (contour.name) xml += ` name="${TRV.esc(contour.name)}"`;
	if (contour.identifier) xml += ` identifier="${TRV.esc(contour.identifier)}"`;
	// closed only written when true (false is default, no need to write it)
	if (contour.closed) xml += ` closed="True"`;
	// clockwise only written when not null
	if (contour.clockwise !== null && contour.clockwise !== undefined) {
		xml += ` clockwise="${contour.clockwise ? 'True' : 'False'}"`;
	}
	xml += '>\n';

	for (const node of contour.nodes) {
		xml += `${indent}  <node x="${node.x}" y="${node.y}" type="${node.type}"`;
		if (node.smooth) xml += ` smooth="True"`;
		xml += '/>\n';
	}

	// Only write lib for truly custom data — closed/clockwise no longer go here
	const libData = {};
	for (const [k, v] of Object.entries(contour.lib || {})) {
		if (k !== 'closed' && k !== 'clockwise') libData[k] = v;
	}
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
		return Number.isInteger(val) ? `<integer>${val}</integer>` : `<real>${TRV.fmtFloat(val)}</real>`;
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

	// Always update textarea when XML panel is visible
	if (TRV.state.showXml) {
		const formatted = TRV.formatXml(newXml);
		TRV.dom.xmlContent.value = formatted;
		TRV.rebuildLineMaps(formatted);
		TRV.updateNodeCount();
		TRV.setParseStatus(true);
	}
};

// Debounced version for use during continuous drag
TRV.syncXmlFromDataDebounced = function() {
	if (TRV.xmlSyncTimer) clearTimeout(TRV.xmlSyncTimer);
	TRV.xmlSyncTimer = setTimeout(function() {
		TRV.syncXmlFromData();
	}, 80);
};
