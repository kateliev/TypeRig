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
	// Returns { node, contour, shape, layer } reference into glyphData
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

	ref.node.x = Math.round(gx * 10) / 10; // round to 0.1
	ref.node.y = Math.round(gy * 10) / 10;
};

// -- Coordinate transforms ------------------------------------------
TRV.glyphToScreen = function(gx, gy) {
	// Glyph Y is up, screen Y is down → flip
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

// -- Hit test -------------------------------------------------------
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
