// ===================================================================
// TypeRig Glyph Viewer — Canvas Drawing
// ===================================================================
// All color values come from TRV.theme (theme.js).
// ===================================================================
'use strict';

TRV.draw = function() {
	const { canvas, ctx, canvasWrap } = TRV.dom;
	const state = TRV.state;
	const dpr = window.devicePixelRatio || 1;
	const w = canvasWrap.clientWidth;
	const h = canvasWrap.clientHeight;

	canvas.width = w * dpr;
	canvas.height = h * dpr;
	canvas.style.width = w + 'px';
	canvas.style.height = h + 'px';
	ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

	// Clear
	ctx.fillStyle = TRV.getBgColor();
	ctx.fillRect(0, 0, w, h);

	if (!state.glyphData) return;

	// Multi-view: delegate to split or joined renderer
	if (state.multiView) {
		if (state.joinedView) {
			TRV.drawJoinedView(w, h);
		} else {
			TRV.drawSplitView(w, h);
		}
		return;
	}

	const layer = TRV.getActiveLayer();
	if (!layer) return;

	// Draw mask layer underneath (if visible)
	if (state.showMask) {
		const mask = TRV.getMaskFor(layer.name);
		if (mask) TRV.drawMaskContours(mask);
	}

	if (state.showMetrics) TRV.drawMetrics(layer, w, h);
	TRV.drawContours(layer);
	if (state.showAnchors) TRV.drawAnchors(layer);
	if (state.showNodes) TRV.drawNodes(layer);
	TRV.drawLayerLabel(layer);

	// Draw selection overlay (rect or lasso)
	if (state.isSelecting) TRV.drawSelectionOverlay();
};

// -- Metrics --------------------------------------------------------
TRV.drawMetrics = function(layer, w, h) {
	const ctx = TRV.dom.ctx;
	const t = TRV.theme.metrics;
	const advW = layer.width;
	const advH = layer.height;

	// Baseline (y=0)
	const baseY = TRV.glyphToScreen(0, 0).y;
	ctx.strokeStyle = t.baseline;
	ctx.lineWidth = 1;
	ctx.setLineDash([6, 4]);
	ctx.beginPath();
	ctx.moveTo(0, baseY);
	ctx.lineTo(w, baseY);
	ctx.stroke();
	ctx.setLineDash([]);

	// Advance height line (y=advH)
	const topY = TRV.glyphToScreen(0, advH).y;
	ctx.strokeStyle = t.baseline;
	ctx.setLineDash([6, 4]);
	ctx.beginPath();
	ctx.moveTo(0, topY);
	ctx.lineTo(w, topY);
	ctx.stroke();
	ctx.setLineDash([]);

	// LSB line (x=0)
	const lsbX = TRV.glyphToScreen(0, 0).x;
	ctx.strokeStyle = t.sidebearing;
	ctx.lineWidth = 1;
	ctx.setLineDash([]);
	ctx.beginPath();
	ctx.moveTo(lsbX, 0);
	ctx.lineTo(lsbX, h);
	ctx.stroke();

	// RSB / Advance width line
	const rsbX = TRV.glyphToScreen(advW, 0).x;
	ctx.strokeStyle = t.advance;
	ctx.beginPath();
	ctx.moveTo(rsbX, 0);
	ctx.lineTo(rsbX, h);
	ctx.stroke();

	// Labels
	ctx.font = '10px "JetBrains Mono", monospace';

	ctx.fillStyle = t.labelBaseFg;
	ctx.textAlign = 'left';
	ctx.fillText('LSB (x=0)', lsbX + 4, baseY - 6);

	ctx.fillStyle = t.labelAdvance;
	ctx.textAlign = 'right';
	ctx.fillText(`ADV (${advW})`, rsbX - 4, baseY - 6);

	ctx.fillStyle = t.labelBase;
	ctx.textAlign = 'left';
	ctx.fillText('Baseline', lsbX + 4, baseY + 14);

	ctx.fillStyle = t.labelBase;
	ctx.fillText(`Height (${advH})`, lsbX + 4, topY + 14);
};

// -- Contours -------------------------------------------------------
TRV.drawContours = function(layer) {
	const ctx = TRV.dom.ctx;
	const t = TRV.theme.contour;

	if (TRV.state.filled) {
		// Filled mode: all contours in ONE path so even-odd punches counters
		ctx.beginPath();
		for (const shape of layer.shapes) {
			for (const contour of shape.contours) {
				if (contour.nodes.length === 0) continue;
				TRV.buildContourPath(contour);
			}
		}
		ctx.fillStyle = t.fill;
		ctx.fill('evenodd');
		ctx.strokeStyle = t.stroke;
		ctx.lineWidth = 1;
		ctx.stroke();
	} else {
		// Outline mode: stroke each contour independently
		for (const shape of layer.shapes) {
			for (const contour of shape.contours) {
				if (contour.nodes.length === 0) continue;
				ctx.beginPath();
				TRV.buildContourPath(contour);
				ctx.strokeStyle = t.strokePlain;
				ctx.lineWidth = 1.5;
				ctx.stroke();
			}
		}
	}
};

TRV.buildContourPath = function(contour) {
	const ctx = TRV.dom.ctx;
	const nodes = contour.nodes;
	if (nodes.length === 0) return;

	// Types: 'on' = on-curve, 'curve' = cubic BCP, 'off' = quadratic off-curve
	const n = nodes.length;

	// Find first on-curve
	let firstOn = 0;
	for (let j = 0; j < n; j++) {
		if (nodes[j].type === 'on') { firstOn = j; break; }
	}

	const sp = TRV.glyphToScreen(nodes[firstOn].x, nodes[firstOn].y);
	ctx.moveTo(sp.x, sp.y);

	let i = (firstOn + 1) % n;
	let count = 0;

	while (count < n - 1) {
		const node = nodes[i];

		if (node.type === 'on') {
			const p = TRV.glyphToScreen(node.x, node.y);
			ctx.lineTo(p.x, p.y);

		} else if (node.type === 'curve') {
			// Cubic: two BCPs then on-curve
			const bcp1 = node;
			const bcp2 = nodes[(i + 1) % n];
			const onCurve = nodes[(i + 2) % n];
			const p1 = TRV.glyphToScreen(bcp1.x, bcp1.y);
			const p2 = TRV.glyphToScreen(bcp2.x, bcp2.y);
			const p3 = TRV.glyphToScreen(onCurve.x, onCurve.y);
			ctx.bezierCurveTo(p1.x, p1.y, p2.x, p2.y, p3.x, p3.y);
			i = (i + 2) % n;
			count += 2;

		} else if (node.type === 'off') {
			// Quadratic: single off-curve then on-curve
			const offNode = node;
			const onCurve = nodes[(i + 1) % n];
			const p1 = TRV.glyphToScreen(offNode.x, offNode.y);
			const p2 = TRV.glyphToScreen(onCurve.x, onCurve.y);
			ctx.quadraticCurveTo(p1.x, p1.y, p2.x, p2.y);
			i = (i + 1) % n;
			count += 1;
		}

		i = (i + 1) % n;
		count++;
	}

	if (contour.closed) ctx.closePath();
};

// -- Nodes & handles ------------------------------------------------
TRV.drawNodes = function(layer) {
	const ctx = TRV.dom.ctx;
	const sel = TRV.state.selectedNodeIds;
	const tn = TRV.theme.node;

	// First pass: draw handle lines
	// Cubic BCPs connect to their parent on-curve only, NOT to each other
	// Quadratic off-curves connect to both adjacent on-curve nodes
	let ci = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			const nodes = contour.nodes;
			const n = nodes.length;

			for (let ni = 0; ni < n; ni++) {
				const node = nodes[ni];

				if (node.type === 'curve') {
					const sp = TRV.glyphToScreen(node.x, node.y);
					const prevIdx = (ni - 1 + n) % n;
					const nextIdx = (ni + 1) % n;
					const prev = nodes[prevIdx];
					const next = nodes[nextIdx];

					if (prev.type === 'on') {
						const pp = TRV.glyphToScreen(prev.x, prev.y);
						ctx.strokeStyle = tn.handleLine;
						ctx.lineWidth = 1;
						ctx.beginPath();
						ctx.moveTo(pp.x, pp.y);
						ctx.lineTo(sp.x, sp.y);
						ctx.stroke();
					}

					if (next.type === 'on') {
						const np = TRV.glyphToScreen(next.x, next.y);
						ctx.strokeStyle = tn.handleLine;
						ctx.lineWidth = 1;
						ctx.beginPath();
						ctx.moveTo(sp.x, sp.y);
						ctx.lineTo(np.x, np.y);
						ctx.stroke();
					}

				} else if (node.type === 'off') {
					const sp = TRV.glyphToScreen(node.x, node.y);
					const prevIdx = (ni - 1 + n) % n;
					const nextIdx = (ni + 1) % n;

					if (nodes[prevIdx].type === 'on') {
						const pp = TRV.glyphToScreen(nodes[prevIdx].x, nodes[prevIdx].y);
						ctx.strokeStyle = tn.handleLine;
						ctx.lineWidth = 1;
						ctx.beginPath();
						ctx.moveTo(pp.x, pp.y);
						ctx.lineTo(sp.x, sp.y);
						ctx.stroke();
					}

					if (nodes[nextIdx].type === 'on') {
						const np = TRV.glyphToScreen(nodes[nextIdx].x, nodes[nextIdx].y);
						ctx.strokeStyle = tn.handleLine;
						ctx.lineWidth = 1;
						ctx.beginPath();
						ctx.moveTo(sp.x, sp.y);
						ctx.lineTo(np.x, np.y);
						ctx.stroke();
					}
				}
			}
			ci++;
		}
	}

	// Second pass: draw node markers
	ci = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			const nodes = contour.nodes;
			const n = nodes.length;

			// Find first on-curve (start point — drawn as triangle in pass 3)
			let firstOn = 0;
			for (let j = 0; j < n; j++) {
				if (nodes[j].type === 'on') { firstOn = j; break; }
			}
			const startNode = nodes[firstOn];

			for (let ni = 0; ni < n; ni++) {
				const node = nodes[ni];

				// Skip the start node — triangle replaces it
				if (ni === firstOn) { continue; }

				// Skip end node if it overlaps the start node
				if (ni === n - 1 && node.x === startNode.x && node.y === startNode.y) {
					continue;
				}

				const id = `c${ci}_n${ni}`;
				const sp = TRV.glyphToScreen(node.x, node.y);
				const isSelected = sel.has(id);
				const r = isSelected ? 5 : (node.type === 'on' ? 4 : 3);

				if (node.type === 'on') {
					ctx.fillStyle = isSelected ? tn.selected : (node.smooth ? tn.onSmooth : tn.onCorner);
					ctx.strokeStyle = isSelected ? tn.selected : tn.outline;
					ctx.lineWidth = 1;

					if (node.smooth) {
						ctx.beginPath();
						ctx.arc(sp.x, sp.y, r, 0, Math.PI * 2);
						ctx.fill();
						ctx.stroke();
					} else {
						ctx.fillRect(sp.x - r, sp.y - r, r * 2, r * 2);
						ctx.strokeRect(sp.x - r, sp.y - r, r * 2, r * 2);
					}
				} else {
					ctx.fillStyle = isSelected ? tn.selected : tn.offCurve;
					ctx.strokeStyle = isSelected ? tn.selected : tn.outline;
					ctx.lineWidth = 1;
					ctx.beginPath();
					ctx.arc(sp.x, sp.y, r, 0, Math.PI * 2);
					ctx.fill();
					ctx.stroke();
				}
			}
			ci++;
		}
	}

	// Third pass: contour start point triangles
	ci = 0;
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			const nodes = contour.nodes;
			const n = nodes.length;
			if (n < 2) { ci++; continue; }

			// Find first on-curve (same logic as buildContourPath)
			let firstOn = 0;
			for (let j = 0; j < n; j++) {
				if (nodes[j].type === 'on') { firstOn = j; break; }
			}

			const startNode = nodes[firstOn];
			const nextNode = nodes[(firstOn + 1) % n];
			const sp = TRV.glyphToScreen(startNode.x, startNode.y);
			const np = TRV.glyphToScreen(nextNode.x, nextNode.y);

			// Direction angle from start towards next node
			const dx = np.x - sp.x;
			const dy = np.y - sp.y;
			const angle = Math.atan2(dy, dx);

			const isStartSelected = sel.has('c' + ci + '_n' + firstOn);
			const size = 6;

			ctx.save();
			ctx.translate(sp.x, sp.y);
			ctx.rotate(angle);

			// Triangle pointing in contour direction
			ctx.beginPath();
			ctx.moveTo(size + 4, 0);               // tip (ahead)
			ctx.lineTo(-size + 2, -size + 1);      // base left
			ctx.lineTo(-size + 2, size - 1);       // base right
			ctx.closePath();

			ctx.fillStyle = isStartSelected ? tn.selected : tn.startPoint;
			ctx.fill();
			ctx.strokeStyle = tn.outline;
			ctx.lineWidth = 1;
			ctx.stroke();

			ctx.restore();
			ci++;
		}
	}
};

// -- Anchors --------------------------------------------------------
TRV.drawAnchors = function(layer) {
	if (!layer.anchors || layer.anchors.length === 0) return;
	const ctx = TRV.dom.ctx;
	const ta = TRV.theme.anchor;

	for (const anchor of layer.anchors) {
		const sp = TRV.glyphToScreen(anchor.x, anchor.y);
		const size = 6;

		ctx.fillStyle = ta.fill;
		ctx.strokeStyle = ta.outline;
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(sp.x, sp.y - size);
		ctx.lineTo(sp.x + size, sp.y);
		ctx.lineTo(sp.x, sp.y + size);
		ctx.lineTo(sp.x - size, sp.y);
		ctx.closePath();
		ctx.fill();
		ctx.stroke();

		ctx.strokeStyle = ta.crosshair;
		ctx.setLineDash([3, 3]);
		ctx.beginPath();
		ctx.moveTo(sp.x - 12, sp.y);
		ctx.lineTo(sp.x + 12, sp.y);
		ctx.moveTo(sp.x, sp.y - 12);
		ctx.lineTo(sp.x, sp.y + 12);
		ctx.stroke();
		ctx.setLineDash([]);

		ctx.font = '10px "JetBrains Mono", monospace';
		ctx.fillStyle = ta.label;
		ctx.textAlign = 'left';
		ctx.fillText(anchor.name, sp.x + size + 4, sp.y + 3);
	}
};

// -- Selection overlay (rect or lasso) ------------------------------
TRV.drawSelectionOverlay = function() {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;
	const ts = TRV.theme.selection;

	ctx.save();

	if (state.selectMode === 'rect' && state.selectStartScreen && state.selectCurrentScreen) {
		const x1 = state.selectStartScreen.x;
		const y1 = state.selectStartScreen.y;
		const x2 = state.selectCurrentScreen.x;
		const y2 = state.selectCurrentScreen.y;

		// Semi-transparent fill
		ctx.fillStyle = ts.fill;
		ctx.fillRect(
			Math.min(x1, x2), Math.min(y1, y2),
			Math.abs(x2 - x1), Math.abs(y2 - y1)
		);

		// Dashed border
		ctx.strokeStyle = ts.stroke;
		ctx.lineWidth = 1;
		ctx.setLineDash([4, 3]);
		ctx.strokeRect(
			Math.min(x1, x2), Math.min(y1, y2),
			Math.abs(x2 - x1), Math.abs(y2 - y1)
		);
		ctx.setLineDash([]);

	} else if (state.selectMode === 'lasso' && state.selectLassoPoints.length > 1) {
		const pts = state.selectLassoPoints;

		// Semi-transparent fill
		ctx.fillStyle = ts.fill;
		ctx.beginPath();
		ctx.moveTo(pts[0].x, pts[0].y);
		for (let i = 1; i < pts.length; i++) {
			ctx.lineTo(pts[i].x, pts[i].y);
		}
		ctx.closePath();
		ctx.fill();

		// Dashed border
		ctx.strokeStyle = ts.stroke;
		ctx.lineWidth = 1;
		ctx.setLineDash([4, 3]);
		ctx.beginPath();
		ctx.moveTo(pts[0].x, pts[0].y);
		for (let i = 1; i < pts.length; i++) {
			ctx.lineTo(pts[i].x, pts[i].y);
		}
		ctx.closePath();
		ctx.stroke();
		ctx.setLineDash([]);
	}

	ctx.restore();
};

// -- Mask contours (underneath main layer) --------------------------
TRV.drawMaskContours = function(maskLayer) {
	if (!maskLayer) return;
	const ctx = TRV.dom.ctx;
	const tm = TRV.theme.mask;

	for (const shape of maskLayer.shapes) {
		for (const contour of shape.contours) {
			if (contour.nodes.length === 0) continue;

			ctx.beginPath();
			TRV.buildContourPath(contour);

			ctx.strokeStyle = tm.stroke;
			ctx.lineWidth = tm.lineWidth;
			ctx.stroke();
		}
	}
};

// -- Layer name label (filled badge, centered below baseline) -------
TRV.drawLayerLabel = function(layer) {
	const ctx = TRV.dom.ctx;
	const tl = TRV.theme.label;
	if (!TRV.state.glyphData) return;

	const layers = TRV.state.glyphData.layers;
	const idx = layers.indexOf(layer);
	const color = TRV.getLayerColor(idx >= 0 ? idx : 0);
	const name = layer.name || '(unnamed)';

	// Position: centered on advance width, below baseline
	const cx = layer.width / 2;
	const labelGy = -30; // 30 units below baseline
	const pos = TRV.glyphToScreen(cx, labelGy);

	ctx.font = tl.font;
	const textW = ctx.measureText(name).width;
	const padX = 6;
	const padY = 3;
	const boxW = textW + padX * 2;
	const boxH = 14 + padY * 2;
	const boxX = pos.x - boxW / 2;
	const boxY = pos.y - boxH / 2;
	const radius = 3;

	// Filled rounded rect background
	ctx.fillStyle = color;
	ctx.beginPath();
	ctx.moveTo(boxX + radius, boxY);
	ctx.lineTo(boxX + boxW - radius, boxY);
	ctx.quadraticCurveTo(boxX + boxW, boxY, boxX + boxW, boxY + radius);
	ctx.lineTo(boxX + boxW, boxY + boxH - radius);
	ctx.quadraticCurveTo(boxX + boxW, boxY + boxH, boxX + boxW - radius, boxY + boxH);
	ctx.lineTo(boxX + radius, boxY + boxH);
	ctx.quadraticCurveTo(boxX, boxY + boxH, boxX, boxY + boxH - radius);
	ctx.lineTo(boxX, boxY + radius);
	ctx.quadraticCurveTo(boxX, boxY, boxX + radius, boxY);
	ctx.closePath();
	ctx.fill();

	// Label text
	ctx.fillStyle = tl.textColor;
	ctx.textAlign = 'center';
	ctx.textBaseline = 'middle';
	ctx.fillText(name, pos.x, pos.y);
	ctx.textBaseline = 'alphabetic'; // reset
};
