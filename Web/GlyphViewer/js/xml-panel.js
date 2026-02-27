// ===================================================================
// TypeRig Glyph Viewer — XML Panel
// ===================================================================
'use strict';

TRV.buildXmlPanel = function() {
	if (!TRV.state.rawXml) {
		TRV.dom.xmlContent.value = '';
		TRV.dom.xmlNodeCount.textContent = '';
		return;
	}

	// Pretty-print the XML and populate textarea
	const formatted = TRV.formatXml(TRV.state.rawXml);
	TRV.dom.xmlContent.value = formatted;

	// Build bidirectional node ↔ line maps
	TRV.rebuildLineMaps(formatted);
	TRV.updateNodeCount();
	TRV.setParseStatus(true);
};

TRV.rebuildLineMaps = function(text) {
	TRV.xmlLineNodeMap = {};
	TRV.xmlNodeLineMap = {};

	const lines = text.split('\n');
	let globalContourIdx = 0;
	let nodeIdx = 0;
	let inContour = false;

	for (let i = 0; i < lines.length; i++) {
		const line = lines[i].trim();

		if (line.startsWith('<contour')) {
			inContour = true;
			nodeIdx = 0;
		} else if (line === '</contour>') {
			if (inContour) globalContourIdx++;
			inContour = false;
		} else if (inContour && line.startsWith('<node ')) {
			const id = `c${globalContourIdx}_n${nodeIdx}`;
			TRV.xmlLineNodeMap[i] = id;
			TRV.xmlNodeLineMap[id] = i;
			nodeIdx++;
		}
	}
};

TRV.updateNodeCount = function() {
	const layer = TRV.getActiveLayer();
	if (layer) {
		const allNodes = TRV.getAllNodes(layer);
		const onCount = allNodes.filter(n => n.type === 'on').length;
		const offCount = allNodes.length - onCount;
		TRV.dom.xmlNodeCount.textContent = `${onCount} on / ${offCount} off`;
	} else {
		TRV.dom.xmlNodeCount.textContent = '';
	}
};

TRV.setParseStatus = function(ok, msg) {
	const el = TRV.dom.parseStatus;
	if (ok) {
		el.textContent = 'OK';
		el.className = 'parse-status ok';
		TRV.dom.xmlContent.classList.remove('has-error');
	} else {
		el.textContent = msg || 'Error';
		el.className = 'parse-status error';
		TRV.dom.xmlContent.classList.add('has-error');
	}
};

TRV.highlightXmlNode = function(nodeId) {
	if (!TRV.state.showXml) return;
	if (!nodeId) return;

	const lineIdx = TRV.xmlNodeLineMap[nodeId];
	if (lineIdx === undefined) return;

	const textarea = TRV.dom.xmlContent;
	const text = textarea.value;
	const lines = text.split('\n');

	// Calculate character offset for the line
	let charStart = 0;
	for (let i = 0; i < lineIdx; i++) {
		charStart += lines[i].length + 1; // +1 for \n
	}
	const charEnd = charStart + (lines[lineIdx] || '').length;

	textarea.focus();
	textarea.setSelectionRange(charStart, charEnd);

	// Scroll the line into view
	const lineHeight = 12 * 1.65; // font-size * line-height
	const scrollTarget = lineIdx * lineHeight - textarea.clientHeight / 2;
	textarea.scrollTop = Math.max(0, scrollTarget);
};

// -- XML Editing → live re-parse ------------------------------------
TRV.onXmlEdit = function() {
	// Debounce: wait 400ms after last keystroke
	if (TRV.xmlEditTimer) clearTimeout(TRV.xmlEditTimer);
	TRV.xmlEditTimer = setTimeout(TRV.applyXmlEdit, 400);
};

TRV.applyXmlEdit = function() {
	const xmlString = TRV.dom.xmlContent.value;

	try {
		const newGlyph = TRV.parseGlyphXML(xmlString);

		// Success — update state
		TRV.state.glyphData = newGlyph;
		TRV.state.rawXml = xmlString;

		// Update layer selector if layers changed
		const currentLayer = TRV.state.activeLayer;
		TRV.dom.layerSelect.innerHTML = '';
		for (const layer of newGlyph.layers) {
			const opt = document.createElement('option');
			opt.value = layer.name;
			opt.textContent = layer.name || '(unnamed)';
			TRV.dom.layerSelect.appendChild(opt);
		}

		// Try to keep current layer, fallback to first
		if (newGlyph.layers.find(l => l.name === currentLayer)) {
			TRV.dom.layerSelect.value = currentLayer;
			TRV.state.activeLayer = currentLayer;
		} else if (newGlyph.layers.length > 0) {
			TRV.state.activeLayer = newGlyph.layers[0].name;
			TRV.dom.layerSelect.value = TRV.state.activeLayer;
		}

		// Update info
		let infoHtml = `<span>${newGlyph.name || '?'}</span>`;
		if (newGlyph.unicodes) infoHtml += ` U+${newGlyph.unicodes}`;
		TRV.dom.glyphInfo.innerHTML = infoHtml;

		// Rebuild line maps and redraw
		TRV.rebuildLineMaps(xmlString);
		TRV.updateNodeCount();
		TRV.setParseStatus(true);
		TRV.draw();

	} catch (e) {
		// Parse error — show status but don't lose canvas data
		TRV.setParseStatus(false, 'Parse error');
	}
};

// Handle click in textarea to detect which node line was clicked
TRV.onXmlClick = function() {
	const textarea = TRV.dom.xmlContent;
	const pos = textarea.selectionStart;
	const text = textarea.value.substring(0, pos);
	const lineIdx = text.split('\n').length - 1;
	const nodeId = TRV.xmlLineNodeMap[lineIdx];

	if (nodeId) {
		TRV.state.selectedNodeId = nodeId;
		TRV.draw();
		TRV.updateStatusSelected();
	}
};

// -- XML formatter --------------------------------------------------
TRV.formatXml = function(xml) {
	let result = '';
	let indent = 0;
	const tab = '  ';

	// Normalize whitespace between tags
	xml = xml.replace(/>\s*</g, '><').trim();

	const tokens = xml.match(/<[^>]+>|[^<]+/g) || [];

	for (const token of tokens) {
		if (token.startsWith('<?')) {
			// Processing instruction (<?xml ...?>) — no indent change
			result += tab.repeat(indent) + token + '\n';
		} else if (token.startsWith('</')) {
			indent--;
			result += tab.repeat(Math.max(0, indent)) + token + '\n';
		} else if (token.startsWith('<') && token.endsWith('/>')) {
			result += tab.repeat(indent) + token + '\n';
		} else if (token.startsWith('<')) {
			result += tab.repeat(indent) + token + '\n';
			indent++;
		} else {
			const trimmed = token.trim();
			if (trimmed) result += tab.repeat(indent) + trimmed + '\n';
		}
	}

	return result.trimEnd();
};
