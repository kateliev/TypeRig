// ===================================================================
// TypeRig Glyph Viewer — Canvas Drawing
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
	ctx.fillStyle = state.filled ? '#18181b' : '#1a1a1e';
	ctx.fillRect(0, 0, w, h);

	const layer = TRV.getActiveLayer();
	if (!layer) return;

	if (state.showMetrics) TRV.drawMetrics(layer, w, h);
	TRV.drawContours(layer);
	if (state.showAnchors) TRV.drawAnchors(layer);
	if (state.showNodes) TRV.drawNodes(layer);

	// Draw selection overlay (rect or lasso)
	if (state.isSelecting) TRV.drawSelectionOverlay();
};

// -- Metrics --------------------------------------------------------
TRV.drawMetrics = function(layer, w, h) {
	const ctx = TRV.dom.ctx;
	const advW = layer.width;
	const advH = layer.height;
	const baselineColor = 'rgba(255,120,80,0.25)';

	// Baseline (y=0)
	const baseY = TRV.glyphToScreen(0, 0).y;
	ctx.strokeStyle = baselineColor;
	ctx.lineWidth = 1;
	ctx.setLineDash([6, 4]);
	ctx.beginPath();
	ctx.moveTo(0, baseY);
	ctx.lineTo(w, baseY);
	ctx.stroke();
	ctx.setLineDash([]);

	// Advance height line (y=advH)
	const topY = TRV.glyphToScreen(0, advH).y;
	ctx.strokeStyle = baselineColor;
	ctx.setLineDash([6, 4]);
	ctx.beginPath();
	ctx.moveTo(0, topY);
	ctx.lineTo(w, topY);
	ctx.stroke();
	ctx.setLineDash([]);

	// LSB line (x=0)
	const lsbX = TRV.glyphToScreen(0, 0).x;
	ctx.strokeStyle = 'rgba(255,120,80,0.35)';
	ctx.lineWidth = 1;
	ctx.setLineDash([]);
	ctx.beginPath();
	ctx.moveTo(lsbX, 0);
	ctx.lineTo(lsbX, h);
	ctx.stroke();

	// RSB / Advance width line
	const rsbX = TRV.glyphToScreen(advW, 0).x;
	ctx.strokeStyle = 'rgba(91,157,239,0.45)';
	ctx.beginPath();
	ctx.moveTo(rsbX, 0);
	ctx.lineTo(rsbX, h);
	ctx.stroke();

	// Labels
	ctx.font = '10px "JetBrains Mono", monospace';

	ctx.fillStyle = 'rgba(255,120,80,0.6)';
	ctx.textAlign = 'left';
	ctx.fillText('LSB (x=0)', lsbX + 4, baseY - 6);

	ctx.fillStyle = 'rgba(91,157,239,0.7)';
	ctx.textAlign = 'right';
	ctx.fillText(`ADV (${advW})`, rsbX - 4, baseY - 6);

	ctx.fillStyle = 'rgba(255,120,80,0.5)';
	ctx.textAlign = 'left';
	ctx.fillText('Baseline', lsbX + 4, baseY + 14);

	ctx.fillStyle = 'rgba(255,120,80,0.5)';
	ctx.fillText(`Height (${advH})`, lsbX + 4, topY + 14);
};

// -- Contours -------------------------------------------------------
TRV.drawContours = function(layer) {
	for (const shape of layer.shapes) {
		for (const contour of shape.contours) {
			TRV.drawContour(contour);
		}
	}
};

TRV.drawContour = function(contour) {
	if (contour.nodes.length === 0) return;
	const ctx = TRV.dom.ctx;

	ctx.beginPath();
	TRV.buildContourPath(contour);

	if (TRV.state.filled) {
		ctx.fillStyle = 'rgba(200,200,210,0.12)';
		ctx.fill('evenodd');
		ctx.strokeStyle = 'rgba(200,200,210,0.6)';
		ctx.lineWidth = 1;
		ctx.stroke();
	} else {
		ctx.strokeStyle = '#c8c8d2';
		ctx.lineWidth = 1.5;
		ctx.stroke();
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
						ctx.strokeStyle = 'rgba(91,157,239,0.35)';
						ctx.lineWidth = 1;
						ctx.beginPath();
						ctx.moveTo(pp.x, pp.y);
						ctx.lineTo(sp.x, sp.y);
						ctx.stroke();
					}

					if (next.type === 'on') {
						const np = TRV.glyphToScreen(next.x, next.y);
						ctx.strokeStyle = 'rgba(91,157,239,0.35)';
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
						ctx.strokeStyle = 'rgba(91,157,239,0.35)';
						ctx.lineWidth = 1;
						ctx.beginPath();
						ctx.moveTo(pp.x, pp.y);
						ctx.lineTo(sp.x, sp.y);
						ctx.stroke();
					}

					if (nodes[nextIdx].type === 'on') {
						const np = TRV.glyphToScreen(nodes[nextIdx].x, nodes[nextIdx].y);
						ctx.strokeStyle = 'rgba(91,157,239,0.35)';
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
			for (let ni = 0; ni < nodes.length; ni++) {
				const node = nodes[ni];
				const id = `c${ci}_n${ni}`;
				const sp = TRV.glyphToScreen(node.x, node.y);
				const isSelected = sel.has(id);
				const r = isSelected ? 5 : (node.type === 'on' ? 4 : 3);

				if (node.type === 'on') {
					ctx.fillStyle = isSelected ? '#ff6b6b' : (node.smooth ? '#50c878' : '#e8e8ec');
					ctx.strokeStyle = isSelected ? '#ff6b6b' : 'rgba(0,0,0,0.5)';
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
					ctx.fillStyle = isSelected ? '#ff6b6b' : '#5b9def';
					ctx.strokeStyle = isSelected ? '#ff6b6b' : 'rgba(0,0,0,0.5)';
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
};

// -- Anchors --------------------------------------------------------
TRV.drawAnchors = function(layer) {
	if (!layer.anchors || layer.anchors.length === 0) return;
	const ctx = TRV.dom.ctx;

	for (const anchor of layer.anchors) {
		const sp = TRV.glyphToScreen(anchor.x, anchor.y);
		const size = 6;

		ctx.fillStyle = '#ff6b6b';
		ctx.strokeStyle = 'rgba(0,0,0,0.5)';
		ctx.lineWidth = 1;
		ctx.beginPath();
		ctx.moveTo(sp.x, sp.y - size);
		ctx.lineTo(sp.x + size, sp.y);
		ctx.lineTo(sp.x, sp.y + size);
		ctx.lineTo(sp.x - size, sp.y);
		ctx.closePath();
		ctx.fill();
		ctx.stroke();

		ctx.strokeStyle = 'rgba(255,107,107,0.4)';
		ctx.setLineDash([3, 3]);
		ctx.beginPath();
		ctx.moveTo(sp.x - 12, sp.y);
		ctx.lineTo(sp.x + 12, sp.y);
		ctx.moveTo(sp.x, sp.y - 12);
		ctx.lineTo(sp.x, sp.y + 12);
		ctx.stroke();
		ctx.setLineDash([]);

		ctx.font = '10px "JetBrains Mono", monospace';
		ctx.fillStyle = 'rgba(255,107,107,0.8)';
		ctx.textAlign = 'left';
		ctx.fillText(anchor.name, sp.x + size + 4, sp.y + 3);
	}
};

// -- Selection overlay (rect or lasso) ------------------------------
TRV.drawSelectionOverlay = function() {
	const ctx = TRV.dom.ctx;
	const state = TRV.state;

	ctx.save();

	if (state.selectMode === 'rect' && state.selectStartScreen && state.selectCurrentScreen) {
		const x1 = state.selectStartScreen.x;
		const y1 = state.selectStartScreen.y;
		const x2 = state.selectCurrentScreen.x;
		const y2 = state.selectCurrentScreen.y;

		// Semi-transparent fill
		ctx.fillStyle = 'rgba(91,157,239,0.08)';
		ctx.fillRect(
			Math.min(x1, x2), Math.min(y1, y2),
			Math.abs(x2 - x1), Math.abs(y2 - y1)
		);

		// Dashed border
		ctx.strokeStyle = 'rgba(91,157,239,0.6)';
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
		ctx.fillStyle = 'rgba(91,157,239,0.08)';
		ctx.beginPath();
		ctx.moveTo(pts[0].x, pts[0].y);
		for (let i = 1; i < pts.length; i++) {
			ctx.lineTo(pts[i].x, pts[i].y);
		}
		ctx.closePath();
		ctx.fill();

		// Dashed border
		ctx.strokeStyle = 'rgba(91,157,239,0.6)';
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
