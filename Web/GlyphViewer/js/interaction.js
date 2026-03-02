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

	// Highlight first selected in XML panel (canvas → XML, one way)
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
		TRV.dom.statusSelected.textContent = '\u2013';
		return;
	}

	if (sel.size === 1) {
		const nodeId = sel.values().next().value;
		const ref = TRV.findNodeById(nodeId);
		if (ref) {
			TRV.dom.statusSelected.textContent =
				nodeId + ' (' + ref.node.x + ', ' + ref.node.y + ') ' + ref.node.type;
		}
	} else {
		TRV.dom.statusSelected.textContent = sel.size + ' nodes';
	}
};

// -- Contour walk (PageUp / PageDown) -------------------------------
// Walk selection forward/backward along the contour. If nothing is
// selected, selects the first on-curve node of the first contour.
TRV.walkContour = function(direction) {
	const layer = TRV.getActiveLayer();
	if (!layer) return;

	const sel = TRV.state.selectedNodeIds;
	const allNodes = TRV.getAllNodes(layer);
	if (allNodes.length === 0) return;

	// Nothing selected — pick first on-curve of first contour
	if (sel.size === 0) {
		for (var i = 0; i < allNodes.length; i++) {
			if (allNodes[i].type === 'on') {
				TRV.selectNode(allNodes[i].id, false);
				return;
			}
		}
		TRV.selectNode(allNodes[0].id, false);
		return;
	}

	// Find the contour of the first selected node
	const firstId = sel.values().next().value;
	const m = firstId.match(/^c(\d+)_n(\d+)$/);
	if (!m) return;
	const ci = parseInt(m[1]);
	const ni = parseInt(m[2]);

	// Collect nodes belonging to this contour
	const contourNodes = allNodes.filter(function(n) { return n.contourIdx === ci; });
	if (contourNodes.length === 0) return;

	// Find current position in contour node list
	var curIdx = -1;
	for (var j = 0; j < contourNodes.length; j++) {
		if (contourNodes[j].nodeIdx === ni) { curIdx = j; break; }
	}
	if (curIdx < 0) curIdx = 0;

	// Step forward or backward, wrapping around
	var newIdx = (curIdx + direction + contourNodes.length) % contourNodes.length;
	TRV.selectNode(contourNodes[newIdx].id, false);
};

// -- Constrained smooth movement -------------------------------------
// Compute unit tangent vectors for smooth on-curve nodes at drag start.
// Tangent = direction through the two adjacent handles (from their
// start positions). Returns Map<nodeId, {tx, ty}>.
TRV.computeDragTangents = function(dragStartPositions) {
	var tangents = new Map();
	var layer = TRV.getActiveLayer();
	if (!layer) return tangents;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!dragStartPositions.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;
				if (!nodes[ni].smooth) continue;

				var prevIdx = (ni - 1 + n) % n;
				var nextIdx = (ni + 1) % n;

				// Need two handles flanking this on-curve
				if (nodes[prevIdx].type === 'on' || nodes[nextIdx].type === 'on') continue;

				// Use start positions if available, else current
				var prevId = 'c' + ci + '_n' + prevIdx;
				var nextId = 'c' + ci + '_n' + nextIdx;
				var onStart = dragStartPositions.get(id);
				var prevPos = dragStartPositions.has(prevId) ? dragStartPositions.get(prevId) : nodes[prevIdx];
				var nextPos = dragStartPositions.has(nextId) ? dragStartPositions.get(nextId) : nodes[nextIdx];

				// Tangent: vector from prev handle to next handle
				var dx = nextPos.x - prevPos.x;
				var dy = nextPos.y - prevPos.y;
				var len = Math.sqrt(dx * dx + dy * dy);
				if (len < 0.001) continue;

				tangents.set(id, { tx: dx / len, ty: dy / len });
			}
			ci++;
		}
	}
	return tangents;
};

// Project a delta (dx, dy) onto a unit tangent (tx, ty).
// Returns { dx, dy } along the tangent direction.
TRV.projectOntoTangent = function(dx, dy, tangent) {
	var dot = dx * tangent.tx + dy * tangent.ty;
	return { dx: dot * tangent.tx, dy: dot * tangent.ty };
};

// -- Toggle smooth / sharp on selected on-curve nodes ---------------
// When converting to smooth, enforces collinearity by adjusting the
// shorter handle to match the longer handle's direction.
TRV.toggleSmooth = function() {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var sel = TRV.state.selectedNodeIds;
	if (sel.size === 0) return;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!sel.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;

				nodes[ni].smooth = !nodes[ni].smooth;

				// When making smooth, enforce collinearity immediately
				if (nodes[ni].smooth) {
					TRV._makeSmoothAt(nodes, n, ni);
				}
			}
			ci++;
		}
	}

	TRV.draw();
	TRV.updateStatusSelected();
};

// Enforce collinearity at on-curve node onIdx by rotating the shorter
// handle to be collinear with the longer one (preserving both lengths).
TRV._makeSmoothAt = function(nodes, n, onIdx) {
	var prevIdx = (onIdx - 1 + n) % n;
	var nextIdx = (onIdx + 1) % n;

	// Need two handles flanking the on-curve
	var hasPrev = (nodes[prevIdx].type !== 'on');
	var hasNext = (nodes[nextIdx].type !== 'on');
	if (!hasPrev || !hasNext) return;

	var ox = nodes[onIdx].x, oy = nodes[onIdx].y;

	// Vectors from on-curve to each handle
	var pDx = nodes[prevIdx].x - ox, pDy = nodes[prevIdx].y - oy;
	var nDx = nodes[nextIdx].x - ox, nDy = nodes[nextIdx].y - oy;
	var pLen = Math.sqrt(pDx * pDx + pDy * pDy);
	var nLen = Math.sqrt(nDx * nDx + nDy * nDy);

	if (pLen < 0.001 || nLen < 0.001) return;

	// Keep the longer handle fixed, rotate the shorter one
	var fixDx, fixDy, fixLen, adjIdx, adjLen;
	if (pLen >= nLen) {
		fixDx = pDx; fixDy = pDy; fixLen = pLen;
		adjIdx = nextIdx; adjLen = nLen;
	} else {
		fixDx = nDx; fixDy = nDy; fixLen = nLen;
		adjIdx = prevIdx; adjLen = pLen;
	}

	// Place adjusted handle opposite to the fixed one, at its own length
	var scale = -adjLen / fixLen;
	nodes[adjIdx].x = Math.round((ox + fixDx * scale) * 10) / 10;
	nodes[adjIdx].y = Math.round((oy + fixDy * scale) * 10) / 10;
};

// -- Smooth node constraint ------------------------------------------
// Two mechanisms, used in different contexts:
//
// A) Mouse drag (absolute positioning):
//    1. startDrag saves follower handles in dragStartPositions
//    2. Drag handler positions ALL entries from their start + delta
//    3. enforceSmoothCollinearity adjusts opposite handles
//
// B) Arrow keys (incremental):
//    1. moveSelectedNodes adds step to selected nodes
//    2. enforceSmoothForKeys translates adjacent handles, then
//       enforces collinearity

// Get non-selected handles adjacent to selected on-curves.
// These should follow their parent during drag (rigid body).
// Returns Map<nodeId, {x, y}> of current positions.
TRV.getFollowerHandles = function(selectedIds) {
	var followers = new Map();
	var layer = TRV.getActiveLayer();
	if (!layer) return followers;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!selectedIds.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;

				// Check adjacent nodes
				var prevIdx = (ni - 1 + n) % n;
				var nextIdx = (ni + 1) % n;
				var prevId = 'c' + ci + '_n' + prevIdx;
				var nextId = 'c' + ci + '_n' + nextIdx;

				if (nodes[prevIdx].type !== 'on' && !selectedIds.has(prevId)) {
					followers.set(prevId, { x: nodes[prevIdx].x, y: nodes[prevIdx].y });
				}
				if (nodes[nextIdx].type !== 'on' && !selectedIds.has(nextId)) {
					followers.set(nextId, { x: nodes[nextIdx].x, y: nodes[nextIdx].y });
				}
			}
			ci++;
		}
	}
	return followers;
};

// Enforce collinearity on smooth nodes after positioning.
// Called after all nodes (selected + followers) have been placed.
// movedIds: Set of all node IDs that were repositioned this frame.
TRV.enforceSmoothCollinearity = function(movedIds) {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!movedIds.has(id)) continue;
				if (nodes[ni].type === 'on') continue; // only handles

				TRV._enforceOppositeSmooth(nodes, n, ni, ci, movedIds);
			}
			ci++;
		}
	}
};

// Arrow key variant: translate adjacent handles then enforce collinearity.
// dx, dy are the incremental step (called once per keypress, so no drift).
TRV.enforceSmoothForKeys = function(draggedIds, dx, dy) {
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	// First pass: translate non-selected handles adjacent to selected on-curves
	var ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!draggedIds.has(id)) continue;
				if (nodes[ni].type !== 'on') continue;

				var prevIdx = (ni - 1 + n) % n;
				var nextIdx = (ni + 1) % n;
				var prevId = 'c' + ci + '_n' + prevIdx;
				var nextId = 'c' + ci + '_n' + nextIdx;

				if (nodes[prevIdx].type !== 'on' && !draggedIds.has(prevId)) {
					nodes[prevIdx].x = Math.round((nodes[prevIdx].x + dx) * 10) / 10;
					nodes[prevIdx].y = Math.round((nodes[prevIdx].y + dy) * 10) / 10;
				}
				if (nodes[nextIdx].type !== 'on' && !draggedIds.has(nextId)) {
					nodes[nextIdx].x = Math.round((nodes[nextIdx].x + dx) * 10) / 10;
					nodes[nextIdx].y = Math.round((nodes[nextIdx].y + dy) * 10) / 10;
				}
			}
			ci++;
		}
	}

	// Second pass: enforce collinearity for moved handles
	ci = 0;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			var n = nodes.length;

			for (var ni = 0; ni < n; ni++) {
				var id = 'c' + ci + '_n' + ni;
				if (!draggedIds.has(id)) continue;
				if (nodes[ni].type === 'on') continue;

				TRV._enforceOppositeSmooth(nodes, n, ni, ci, draggedIds);
			}
			ci++;
		}
	}
};

// For handle at handleIdx, find parent on-curve. If smooth, adjust
// the opposite handle to maintain collinearity (same angle, opposite
// direction, preserving the opposite handle's original length).
TRV._enforceOppositeSmooth = function(nodes, n, handleIdx, ci, movedIds) {
	var prevIdx = (handleIdx - 1 + n) % n;
	var nextIdx = (handleIdx + 1) % n;

	// Find parent on-curve (adjacent to this handle)
	var parentIdx = -1;
	if (nodes[prevIdx].type === 'on') parentIdx = prevIdx;
	else if (nodes[nextIdx].type === 'on') parentIdx = nextIdx;
	else return; // no adjacent on-curve

	var parent = nodes[parentIdx];
	if (!parent.smooth) return; // corner node — nothing to enforce

	// Opposite handle is on the other side of parent
	var oppositeIdx;
	if (parentIdx === prevIdx) {
		// Handle is after parent → opposite is before parent
		oppositeIdx = (parentIdx - 1 + n) % n;
	} else {
		// Handle is before parent → opposite is after parent
		oppositeIdx = (parentIdx + 1) % n;
	}

	// Must be a handle; if on-curve, it's a line segment — no constraint
	if (nodes[oppositeIdx].type === 'on') return;

	// Skip if opposite is also being moved (user controls both)
	var oppositeId = 'c' + ci + '_n' + oppositeIdx;
	if (movedIds.has(oppositeId)) return;

	// Vector from parent to dragged handle
	var ox = parent.x, oy = parent.y;
	var hx = nodes[handleIdx].x, hy = nodes[handleIdx].y;
	var vx = hx - ox, vy = hy - oy;
	var dist = Math.sqrt(vx * vx + vy * vy);
	if (dist < 0.001) return; // degenerate

	// Preserve opposite handle's distance from parent
	var opDx = nodes[oppositeIdx].x - ox;
	var opDy = nodes[oppositeIdx].y - oy;
	var opLen = Math.sqrt(opDx * opDx + opDy * opDy);
	if (opLen < 0.001) return; // degenerate

	// Place opposite at reversed direction, scaled to its length
	var scale = -opLen / dist;
	nodes[oppositeIdx].x = Math.round((ox + vx * scale) * 10) / 10;
	nodes[oppositeIdx].y = Math.round((oy + vy * scale) * 10) / 10;
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
	var w, h;
	if (TRV.state.multiView) {
		const cell = TRV.getCellRect(TRV.state.activeCell.row, TRV.state.activeCell.col);
		w = cell.w;
		h = cell.h;
	} else {
		w = canvasW;
		h = canvasH;
	}

	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

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

// Zoom centred on the viewport middle (for keyboard zoom)
TRV.zoomAtCenter = function(factor) {
	const w = TRV.dom.canvasWrap.clientWidth;
	const h = TRV.dom.canvasWrap.clientHeight;
	const cx = w / 2;
	const cy = h / 2;
	const newZoom = TRV.state.zoom * factor;

	TRV.state.pan.x = cx - (cx - TRV.state.pan.x) * (newZoom / TRV.state.zoom);
	TRV.state.pan.y = cy - (cy - TRV.state.pan.y) * (newZoom / TRV.state.zoom);
	TRV.state.zoom = newZoom;

	TRV.updateZoomStatus();
	TRV.draw();
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
		var infoHtml = '<span>' + (g.name || '?') + '</span>';
		if (g.unicodes) infoHtml += ' U+' + g.unicodes;
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
	// Always serialize fresh from data for saving
	var xmlString = TRV.state.glyphData ? TRV.glyphToXml(TRV.state.glyphData) : TRV.state.rawXml;
	if (!xmlString) return;

	const blob = new Blob([xmlString], { type: 'application/xml' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	const name = TRV.state.glyphData ? TRV.state.glyphData.name : 'glyph';
	a.download = name + '.trglyph';
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

	// Enforce smooth tangent continuity on neighbors
	TRV.enforceSmoothForKeys(sel, dx, dy);

	// No XML sync here — user clicks Refresh when needed
	TRV.draw();
	TRV.updateStatusSelected();
};
