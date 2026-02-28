// ===================================================================
// TypeRig Glyph Viewer — Geometry & Node Helpers
// ===================================================================
'use strict';

// -- Layer helpers ---------------------------------------------------
TRV.getActiveLayer = function() {
	if (!TRV.state.glyphData) return null;
	const name = TRV.state.activeLayer;
	return TRV.state.glyphData.layers.find(l => l.name === name)
		|| TRV.state.glyphData.layers[0] || null;
};

TRV.getAllNodes = function(layer) {
	const nodes = [];
	if (!layer) return nodes;
	let ci = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			let ni = 0;
			for (const node of contour.nodes) {
				nodes.push({
					...node,
					id: `c${ci}_n${ni}`,
					contourIdx: ci,
					nodeIdx: ni,
					contour: contour,
				});
				ni++;
			}
			ci++;
		}
	}
	return nodes;
};

// -- Node manipulation ----------------------------------------------
TRV.findNodeById = function(nodeId) {
	const layer = TRV.getActiveLayer();
	if (!layer) return null;

	let ci = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			for (let ni = 0; ni < contour.nodes.length; ni++) {
				if (`c${ci}_n${ni}` === nodeId) {
					return { node: contour.nodes[ni], contour, shape, layer };
				}
			}
			ci++;
		}
	}
	return null;
};

TRV.updateNodePosition = function(nodeId, gx, gy) {
	const ref = TRV.findNodeById(nodeId);
	if (!ref) return;

	ref.node.x = Math.round(gx * 10) / 10;
	ref.node.y = Math.round(gy * 10) / 10;
};

// -- Coordinate transforms ------------------------------------------
TRV.glyphToScreen = function(gx, gy) {
	return {
		x: gx * TRV.state.zoom + TRV.state.pan.x,
		y: -gy * TRV.state.zoom + TRV.state.pan.y,
	};
};

TRV.screenToGlyph = function(sx, sy) {
	return {
		x: (sx - TRV.state.pan.x) / TRV.state.zoom,
		y: -(sy - TRV.state.pan.y) / TRV.state.zoom,
	};
};

// -- Hit test: single node ------------------------------------------
TRV.hitTestNode = function(sx, sy, radius) {
	const layer = TRV.getActiveLayer();
	if (!layer) return null;

	const r2 = (radius || 8) * (radius || 8);
	const allNodes = TRV.getAllNodes(layer);

	let closest = null;
	let closestDist = Infinity;

	for (const node of allNodes) {
		const sp = TRV.glyphToScreen(node.x, node.y);
		const dx = sp.x - sx;
		const dy = sp.y - sy;
		const d2 = dx * dx + dy * dy;
		if (d2 < r2 && d2 < closestDist) {
			closestDist = d2;
			closest = node;
		}
	}

	return closest;
};

// -- Hit test: rectangle (screen coords) ----------------------------
TRV.hitTestRect = function(x1, y1, x2, y2) {
	const layer = TRV.getActiveLayer();
	if (!layer) return [];

	const minX = Math.min(x1, x2);
	const maxX = Math.max(x1, x2);
	const minY = Math.min(y1, y2);
	const maxY = Math.max(y1, y2);

	const allNodes = TRV.getAllNodes(layer);
	const ids = [];

	for (const node of allNodes) {
		const sp = TRV.glyphToScreen(node.x, node.y);
		if (sp.x >= minX && sp.x <= maxX && sp.y >= minY && sp.y <= maxY) {
			ids.push(node.id);
		}
	}

	return ids;
};

// -- Hit test: lasso polygon (screen coords) ------------------------
TRV.hitTestLasso = function(points) {
	if (points.length < 3) return [];

	const layer = TRV.getActiveLayer();
	if (!layer) return [];

	const allNodes = TRV.getAllNodes(layer);
	const ids = [];

	for (const node of allNodes) {
		const sp = TRV.glyphToScreen(node.x, node.y);
		if (TRV.pointInPolygon(sp.x, sp.y, points)) {
			ids.push(node.id);
		}
	}

	return ids;
};

// -- Point-in-polygon (ray casting) ---------------------------------
TRV.pointInPolygon = function(px, py, polygon) {
	let inside = false;
	const n = polygon.length;

	for (let i = 0, j = n - 1; i < n; j = i++) {
		const xi = polygon[i].x, yi = polygon[i].y;
		const xj = polygon[j].x, yj = polygon[j].y;

		if ((yi > py) !== (yj > py) &&
			px < (xj - xi) * (py - yi) / (yj - yi) + xi) {
			inside = !inside;
		}
	}

	return inside;
};

// -- Mask layer helpers ---------------------------------------------
TRV.isMaskLayer = function(layerName) {
	return layerName && layerName.toLowerCase().startsWith('mask.');
};

// Get the mask layer object for a given layer name, or null
TRV.getMaskFor = function(layerName) {
	if (!TRV.state.glyphData) return null;
	const maskName = 'mask.' + layerName;
	return TRV.state.glyphData.layers.find(
		l => l.name.toLowerCase() === maskName.toLowerCase()
	) || null;
};

// Get indices of non-mask layers (for grid population)
TRV.getNonMaskLayerIndices = function() {
	if (!TRV.state.glyphData) return [];
	const indices = [];
	TRV.state.glyphData.layers.forEach(function(layer, i) {
		if (!TRV.isMaskLayer(layer.name)) indices.push(i);
	});
	return indices;
};

// -- Hit test: contour stroke (screen coords) -----------------------
// Returns contour index (ci) if point is on/near a contour outline,
// or -1 if nothing hit. Uses canvas isPointInStroke for accuracy.
TRV.hitTestContour = function(sx, sy, tolerance) {
	const layer = TRV.getActiveLayer();
	if (!layer) return -1;

	const ctx = TRV.dom.ctx;
	tolerance = tolerance || 6;

	let ci = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			if (contour.nodes.length < 2) { ci++; continue; }

			ctx.beginPath();
			TRV.buildContourPath(contour);

			// Widen stroke detection area
			ctx.lineWidth = tolerance;
			if (ctx.isPointInStroke(sx, sy)) return ci;

			// Also check filled area
			if (ctx.isPointInPath(sx, sy, 'evenodd')) return ci;

			ci++;
		}
	}

	return -1;
};

// Return all node IDs belonging to contour index ci
TRV.getContourNodeIds = function(ci) {
	const layer = TRV.getActiveLayer();
	if (!layer) return [];

	let idx = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			if (idx === ci) {
				const ids = [];
				for (let ni = 0; ni < contour.nodes.length; ni++) {
					ids.push('c' + idx + '_n' + ni);
				}
				return ids;
			}
			idx++;
		}
	}
	return [];
};
