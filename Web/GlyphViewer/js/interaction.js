// ===================================================================
// TypeRig Glyph Viewer — Interaction Helpers
// ===================================================================
'use strict';

// -- Selection ------------------------------------------------------
TRV.selectNode = function(nodeId) {
	TRV.state.selectedNodeId = nodeId;
	TRV.highlightXmlNode(nodeId);
	TRV.draw();
	TRV.updateStatusSelected();
};

TRV.updateStatusSelected = function() {
	if (!TRV.state.selectedNodeId) {
		TRV.dom.statusSelected.textContent = '–';
		return;
	}

	const ref = TRV.findNodeById(TRV.state.selectedNodeId);
	if (ref) {
		TRV.dom.statusSelected.textContent =
			`${TRV.state.selectedNodeId} (${ref.node.x}, ${ref.node.y}) ${ref.node.type}`;
	}
};

// -- Fit to view ----------------------------------------------------
TRV.fitToView = function() {
	const layer = TRV.getActiveLayer();
	if (!layer) return;

	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;

	// Find bounding box
	let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			for (const node of contour.nodes) {
				minX = Math.min(minX, node.x);
				minY = Math.min(minY, node.y);
				maxX = Math.max(maxX, node.x);
				maxY = Math.max(maxY, node.y);
			}
		}
	}

	// Include metrics
	minX = Math.min(minX, 0);
	maxX = Math.max(maxX, layer.width);
	minY = Math.min(minY, 0);
	maxY = Math.max(maxY, layer.height);

	// Include anchors
	if (layer.anchors) {
		for (const a of layer.anchors) {
			minX = Math.min(minX, a.x);
			minY = Math.min(minY, a.y);
			maxX = Math.max(maxX, a.x);
			maxY = Math.max(maxY, a.y);
		}
	}

	const glyphW = maxX - minX || 1;
	const glyphH = maxY - minY || 1;

	const padding = 60;
	const scaleX = (w - padding * 2) / glyphW;
	const scaleY = (h - padding * 2) / glyphH;
	TRV.state.zoom = Math.min(scaleX, scaleY);

	// Center: glyph center in screen coords
	const cx = (minX + maxX) / 2;
	const cy = (minY + maxY) / 2;
	TRV.state.pan.x = w / 2 - cx * TRV.state.zoom;
	TRV.state.pan.y = h / 2 + cy * TRV.state.zoom; // flip Y

	TRV.updateZoomStatus();
	TRV.draw();
};

TRV.updateZoomStatus = function() {
	TRV.dom.statusZoom.textContent = Math.round(TRV.state.zoom * 100) + '%';
};

// -- File I/O -------------------------------------------------------
TRV.loadXmlString = function(xmlString, filename) {
	try {
		TRV.state.glyphData = TRV.parseGlyphXML(xmlString);
		TRV.state.rawXml = xmlString;

		// Populate layer selector
		TRV.dom.layerSelect.innerHTML = '';
		for (const layer of TRV.state.glyphData.layers) {
			const opt = document.createElement('option');
			opt.value = layer.name;
			opt.textContent = layer.name || '(unnamed)';
			TRV.dom.layerSelect.appendChild(opt);
		}

		if (TRV.state.glyphData.layers.length > 0) {
			TRV.state.activeLayer = TRV.state.glyphData.layers[0].name;
			TRV.dom.layerSelect.value = TRV.state.activeLayer;
		}

		// Update info
		const g = TRV.state.glyphData;
		let infoHtml = `<span>${g.name || '?'}</span>`;
		if (g.unicodes) infoHtml += ` U+${g.unicodes}`;
		TRV.dom.glyphInfo.innerHTML = infoHtml;

		TRV.dom.emptyState.classList.add('hidden');
		TRV.state.selectedNodeId = null;

		TRV.fitToView();
		TRV.buildXmlPanel();
	} catch (e) {
		alert('Error loading XML: ' + e.message);
	}
};

TRV.saveXml = function() {
	// Use textarea content if XML panel is open, otherwise use stored rawXml
	const xmlString = TRV.state.showXml ? TRV.dom.xmlContent.value : TRV.state.rawXml;
	if (!xmlString) return;

	const blob = new Blob([xmlString], { type: 'application/xml' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	const name = TRV.state.glyphData ? TRV.state.glyphData.name : 'glyph';
	a.download = `${name}.trglyph`;
	a.click();
	URL.revokeObjectURL(url);
};

// -- Cursor helpers -------------------------------------------------
TRV.updateCanvasCursor = function() {
	const wrap = TRV.dom.canvasWrap;
	if (TRV.state.spaceDown) {
		wrap.style.cursor = TRV.state.isPanning ? 'grabbing' : 'grab';
	} else if (TRV.state.isDragging) {
		wrap.style.cursor = 'move';
	} else {
		wrap.style.cursor = 'default';
	}
};

// -- Node movement by keyboard --------------------------------------
TRV.ARROW_STEP = 1;
TRV.ARROW_STEP_SHIFT = 10;
TRV.ARROW_STEP_CTRL = 100;

TRV.moveSelectedNode = function(dx, dy) {
	if (!TRV.state.selectedNodeId) return;
	const ref = TRV.findNodeById(TRV.state.selectedNodeId);
	if (!ref) return;

	ref.node.x = Math.round((ref.node.x + dx) * 10) / 10;
	ref.node.y = Math.round((ref.node.y + dy) * 10) / 10;

	TRV.syncXmlFromData();
	TRV.draw();
	TRV.updateStatusSelected();
	if (TRV.state.showXml) TRV.highlightXmlNode(TRV.state.selectedNodeId);
};
