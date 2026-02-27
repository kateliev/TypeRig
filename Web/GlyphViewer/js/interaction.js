// ===================================================================
// TypeRig Glyph Viewer — Interaction Helpers
// ===================================================================
'use strict';

// -- Selection (multi-node) -----------------------------------------
TRV.clearSelection = function() {
	TRV.state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// Select a single node (replaces selection unless shift is held)
TRV.selectNode = function(nodeId, additive) {
	const sel = TRV.state.selectedNodeIds;

	if (!nodeId) {
		if (!additive) sel.clear();
	} else if (additive) {
		// Toggle: add if missing, remove if present
		if (sel.has(nodeId)) {
			sel.delete(nodeId);
		} else {
			sel.add(nodeId);
		}
	} else {
		sel.clear();
		sel.add(nodeId);
	}

	// Highlight first selected in XML panel
	if (sel.size > 0) {
		const first = sel.values().next().value;
		TRV.highlightXmlNode(first);
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

// Select multiple nodes (from rect/lasso), replacing or adding
TRV.selectNodes = function(nodeIds, additive) {
	const sel = TRV.state.selectedNodeIds;

	if (!additive) sel.clear();
	for (const id of nodeIds) {
		sel.add(id);
	}

	if (sel.size > 0) {
		const first = sel.values().next().value;
		TRV.highlightXmlNode(first);
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

TRV.updateStatusSelected = function() {
	const sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) {
		TRV.dom.statusSelected.textContent = '–';
		return;
	}

	if (sel.size === 1) {
		const nodeId = sel.values().next().value;
		const ref = TRV.findNodeById(nodeId);
		if (ref) {
			TRV.dom.statusSelected.textContent =
				`${nodeId} (${ref.node.x}, ${ref.node.y}) ${ref.node.type}`;
		}
	} else {
		TRV.dom.statusSelected.textContent = `${sel.size} nodes`;
	}
};

// -- Fit to view ----------------------------------------------------
TRV.fitToView = function() {
	const layer = TRV.getActiveLayer();
	if (!layer) return;

	const canvasW = TRV.dom.canvasWrap.clientWidth;
	const canvasH = TRV.dom.canvasWrap.clientHeight;

	// Joined multi-view: fit the entire joined layout
	if (TRV.state.multiView && TRV.state.joinedView) {
		const layout = TRV.getJoinedLayout();

		const padding = 40;
		const scaleX = (canvasW - padding * 2) / layout.totalW;
		const scaleY = (canvasH - padding * 2) / layout.totalH;
		TRV.state.zoom = Math.min(scaleX, scaleY);

		// Center of the joined layout in glyph space
		const cx = layout.totalW / 2;
		const cy = layout.totalH / 2;
		TRV.state.pan.x = canvasW / 2 - cx * TRV.state.zoom;
		TRV.state.pan.y = canvasH / 2 + cy * TRV.state.zoom;

		TRV.updateZoomStatus();
		TRV.draw();
		return;
	}

	// Split multi-view: fit to cell dimensions
	let w, h;
	if (TRV.state.multiView) {
		const cell = TRV.getCellRect(TRV.state.activeCell.row, TRV.state.activeCell.col);
		w = cell.w;
		h = cell.h;
	} else {
		w = canvasW;
		h = canvasH;
	}

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

	minX = Math.min(minX, 0);
	maxX = Math.max(maxX, layer.width);
	minY = Math.min(minY, 0);
	maxY = Math.max(maxY, layer.height);

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

	const padding = TRV.state.multiView ? 30 : 60;
	const scaleX = (w - padding * 2) / glyphW;
	const scaleY = (h - padding * 2) / glyphH;
	TRV.state.zoom = Math.min(scaleX, scaleY);

	const cx = (minX + maxX) / 2;
	const cy = (minY + maxY) / 2;
	TRV.state.pan.x = w / 2 - cx * TRV.state.zoom;
	TRV.state.pan.y = h / 2 + cy * TRV.state.zoom;

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

		const g = TRV.state.glyphData;
		let infoHtml = `<span>${g.name || '?'}</span>`;
		if (g.unicodes) infoHtml += ` U+${g.unicodes}`;
		TRV.dom.glyphInfo.innerHTML = infoHtml;

		TRV.dom.emptyState.classList.add('hidden');
		TRV.state.selectedNodeIds.clear();

		// Re-init grid if multi-view is active
		if (TRV.state.multiView) TRV.initMultiGrid();

		TRV.fitToView();
		TRV.buildXmlPanel();
	} catch (e) {
		alert('Error loading XML: ' + e.message);
	}
};

TRV.saveXml = function() {
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
	const state = TRV.state;
	if (state.spaceDown) {
		wrap.style.cursor = state.isPanning ? 'grabbing' : 'grab';
	} else if (state.isDragging) {
		wrap.style.cursor = 'move';
	} else if (state.isSelecting) {
		wrap.style.cursor = state.selectMode === 'lasso' ? 'default' : 'crosshair';
	} else {
		wrap.style.cursor = 'default';
	}
};

// -- Node movement by keyboard (moves all selected) -----------------
TRV.ARROW_STEP = 1;
TRV.ARROW_STEP_SHIFT = 10;
TRV.ARROW_STEP_CTRL = 100;

TRV.moveSelectedNodes = function(dx, dy) {
	const sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) return;

	for (const nodeId of sel) {
		const ref = TRV.findNodeById(nodeId);
		if (!ref) continue;
		ref.node.x = Math.round((ref.node.x + dx) * 10) / 10;
		ref.node.y = Math.round((ref.node.y + dy) * 10) / 10;
	}

	TRV.syncXmlFromData();
	TRV.draw();
	TRV.updateStatusSelected();
};
