// ===================================================================
// TypeRig Glyph Viewer — On-stem measurement
// ===================================================================
// Approach B: perpendicular to nearest contour wall, with H/V fallback.
// Reuses TRV._evalCubic, _evalLine, _nearestOnSegment, getContourSegments.
'use strict';

TRV.stem = {};

// -- Cubic derivative at t ------------------------------------------
TRV.stem.cubicDeriv = function(pts, t) {
	var u = 1 - t;
	var p0 = pts[0], p1 = pts[1], p2 = pts[2], p3 = pts[3];
	return {
		x: 3*u*u*(p1.x - p0.x) + 6*u*t*(p2.x - p1.x) + 3*t*t*(p3.x - p2.x),
		y: 3*u*u*(p1.y - p0.y) + 6*u*t*(p2.y - p1.y) + 3*t*t*(p3.y - p2.y)
	};
};

// -- Ray-segment crossings ------------------------------------------
// Find all t in [0,1] where the segment crosses the infinite line
// through (ox,oy) with direction (dx,dy).
// Uses cross-product: (B(t) - O) x D = 0 -> scalar cubic in t.
// Returns array of { t, x, y, s } where s = signed distance along ray.
TRV.stem.raySegmentCrossings = function(ox, oy, dx, dy, seg) {
	var results = [];
	var pts = seg.pts;

	if (seg.type === 'line') {
		// Line: P(t) = A + t*(B-A), t in [0,1]
		var ax = pts[0].x, ay = pts[0].y;
		var bx = pts[1].x - ax, by = pts[1].y - ay;

		// (A + t*B' - O) x D = 0
		// ((ax-ox) + t*bx)*dy - ((ay-oy) + t*by)*dx = 0
		var c0 = (ax - ox) * dy - (ay - oy) * dx;
		var c1 = bx * dy - by * dx;

		if (Math.abs(c1) < 1e-10) return results; // parallel
		var t = -c0 / c1;
		if (t >= -1e-6 && t <= 1 + 1e-6) {
			t = Math.max(0, Math.min(1, t));
			var px = ax + t * (pts[1].x - ax);
			var py = ay + t * (pts[1].y - ay);
			var len2 = dx * dx + dy * dy;
			var s = ((px - ox) * dx + (py - oy) * dy) / len2;
			var windSign = (by > 0) ? 1 : -1;
			results.push({ t: t, x: px, y: py, s: s, windSign: windSign });
		}
		return results;
	}

	// Quadratic or cubic: build f(t) = (B(t)-O) x D as polynomial
	var p0 = pts[0], p1 = pts[1], p2 = pts[2], p3 = pts[3];
	var A, B, C, D, N;

	if (seg.type === 'quadratic') {
		// Power-form for quadratic: B(t) = (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2
		// = P0 + 2t*(P1-P0) + t^2*(P0 - 2*P1 + P2)
		var ax2 = p0.x - 2*p1.x + p2.x;
		var bx1 = 2*(p1.x - p0.x);
		var cx0 = p0.x;
		var ay2 = p0.y - 2*p1.y + p2.y;
		var by1 = 2*(p1.y - p0.y);
		var cy0 = p0.y;

		A = 0; // quadratic has no t^3 term
		B = ax2 * dy - ay2 * dx;
		C = bx1 * dy - by1 * dx;
		D = (cx0 - ox) * dy - (cy0 - oy) * dx;
		N = 8;
	} else {
		// Cubic power-form
		var ax3 = -p0.x + 3*p1.x - 3*p2.x + p3.x;
		var bx2 =  3*p0.x - 6*p1.x + 3*p2.x;
		var cx1 = -3*p0.x + 3*p1.x;
		var dx0 =  p0.x;
		var ay3 = -p0.y + 3*p1.y - 3*p2.y + p3.y;
		var by2 =  3*p0.y - 6*p1.y + 3*p2.y;
		var cy1 = -3*p0.y + 3*p1.y;
		var dy0 =  p0.y;

		A = ax3 * dy - ay3 * dx;
		B = bx2 * dy - by2 * dx;
		C = cx1 * dy - cy1 * dx;
		D = (dx0 - ox) * dy - (dy0 - oy) * dx;
		N = 12;
	}

	var evalFn = seg.type === 'quadratic' ? TRV._evalQuadratic : TRV._evalCubic;

	// Find roots via sampling + bisection (robust for any polynomial)
	var vals = new Array(N + 1);
	for (var i = 0; i <= N; i++) {
		var tt = i / N;
		vals[i] = ((A * tt + B) * tt + C) * tt + D;
	}

	var len2 = dx * dx + dy * dy;

	for (var i = 0; i < N; i++) {
		if (vals[i] * vals[i + 1] > 0) continue; // no sign change

		// Bisect to find root
		var lo = i / N, hi = (i + 1) / N;
		var flo = vals[i], fhi = vals[i + 1];
		for (var iter = 0; iter < 24; iter++) {
			var mid = (lo + hi) * 0.5;
			var fmid = ((A * mid + B) * mid + C) * mid + D;
			if (flo * fmid <= 0) { hi = mid; fhi = fmid; }
			else { lo = mid; flo = fmid; }
		}

		var t = (lo + hi) * 0.5;
		if (t < -1e-6 || t > 1 + 1e-6) continue;
		t = Math.max(0, Math.min(1, t));

		var pt = evalFn(pts, t);
		var s = ((pt.x - ox) * dx + (pt.y - oy) * dy) / len2;

		// Winding sign: tangent y-component relative to ray direction
		// For nonzero fill rule inside test
		var tangY = 0;
		if (seg.type === 'line') {
			tangY = pts[1].y - pts[0].y;
		} else if (seg.type === 'quadratic') {
			var u2 = 1 - t;
			tangY = 2 * u2 * (pts[1].y - pts[0].y) + 2 * t * (pts[2].y - pts[1].y);
		} else {
			var u3 = 1 - t;
			tangY = 3*u3*u3*(pts[1].y-pts[0].y) + 6*u3*t*(pts[2].y-pts[1].y) + 3*t*t*(pts[3].y-pts[2].y);
		}

		results.push({ t: t, x: pt.x, y: pt.y, s: s, windSign: tangY > 0 ? 1 : -1 });
	}

	return results;
};

// -- Ray vs all contours in layer -----------------------------------
TRV.stem.rayLayerCrossings = function(ox, oy, dx, dy, layer) {
	var all = [];
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var segs = TRV.getContourSegments(shape.contours[ki]);
			for (var gi = 0; gi < segs.length; gi++) {
				var hits = TRV.stem.raySegmentCrossings(ox, oy, dx, dy, segs[gi]);
				for (var hi = 0; hi < hits.length; hi++) all.push(hits[hi]);
			}
		}
	}
	return all;
};

// -- Point-in-glyph (nonzero winding via horizontal ray) ------------
TRV.stem.isInside = function(gx, gy, layer) {
	var crossings = TRV.stem.rayLayerCrossings(gx, gy, 1, 0, layer);
	// Nonzero winding: sum signed crossings to the right
	var winding = 0;
	for (var i = 0; i < crossings.length; i++) {
		if (crossings[i].s > 1e-6) winding += crossings[i].windSign;
	}
	return winding !== 0;
};

// -- Find nearest contour point (glyph coords) ---------------------
TRV.stem.nearestOnLayer = function(gx, gy, layer) {
	var best = null;

	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var segs = TRV.getContourSegments(shape.contours[ki]);
			for (var gi = 0; gi < segs.length; gi++) {
				var hit = TRV._nearestOnSegment(segs[gi], gx, gy);
				if (!best || hit.dist < best.dist) {
					best = { seg: segs[gi], t: hit.t, x: hit.x, y: hit.y, dist: hit.dist };
				}
			}
		}
	}
	return best;
};

// -- Perpendicular measurement from cursor --------------------------
// Returns { from: {x,y}, to: {x,y}, dist } or null
TRV.stem.measurePerp = function(gx, gy, layer) {
	var nearest = TRV.stem.nearestOnLayer(gx, gy, layer);
	if (!nearest) return null;

	// Get tangent at nearest point
	var tang;
	if (nearest.seg.type === 'cubic') {
		tang = TRV.stem.cubicDeriv(nearest.seg.pts, nearest.t);
	} else if (nearest.seg.type === 'quadratic') {
		// Quadratic derivative: B'(t) = 2(1-t)(P1-P0) + 2t(P2-P1)
		var qp = nearest.seg.pts;
		var u = 1 - nearest.t;
		tang = {
			x: 2 * u * (qp[1].x - qp[0].x) + 2 * nearest.t * (qp[2].x - qp[1].x),
			y: 2 * u * (qp[1].y - qp[0].y) + 2 * nearest.t * (qp[2].y - qp[1].y)
		};
	} else {
		var pts = nearest.seg.pts;
		tang = { x: pts[1].x - pts[0].x, y: pts[1].y - pts[0].y };
	}

	// Perpendicular direction (rotate tangent 90 degrees)
	var px = -tang.y, py = tang.x;
	var plen = Math.sqrt(px * px + py * py);
	if (plen < 1e-10) return null;
	px /= plen; py /= plen;

	// Cast perpendicular ray from cursor
	var crossings = TRV.stem.rayLayerCrossings(gx, gy, px, py, layer);
	if (crossings.length < 2) return null;

	// Find nearest crossing on each side of cursor (s < 0 and s > 0)
	var negBest = null, posBest = null;
	for (var i = 0; i < crossings.length; i++) {
		var c = crossings[i];
		if (c.s < -1e-6 && (!negBest || c.s > negBest.s)) negBest = c;
		if (c.s >  1e-6 && (!posBest || c.s < posBest.s)) posBest = c;
	}

	if (!negBest || !posBest) return null;

	var dx = posBest.x - negBest.x;
	var dy = posBest.y - negBest.y;
	return {
		from: { x: negBest.x, y: negBest.y },
		to:   { x: posBest.x, y: posBest.y },
		dist: Math.sqrt(dx * dx + dy * dy),
		mode: 'perp'
	};
};

// -- Axis-aligned measurement (fallback) ----------------------------
// dir: 'h' for horizontal, 'v' for vertical
TRV.stem.measureAxis = function(gx, gy, layer, dir) {
	var dx = dir === 'h' ? 1 : 0;
	var dy = dir === 'h' ? 0 : 1;
	var crossings = TRV.stem.rayLayerCrossings(gx, gy, dx, dy, layer);

	var negBest = null, posBest = null;
	for (var i = 0; i < crossings.length; i++) {
		var c = crossings[i];
		if (c.s < -1e-6 && (!negBest || c.s > negBest.s)) negBest = c;
		if (c.s >  1e-6 && (!posBest || c.s < posBest.s)) posBest = c;
	}

	if (!negBest || !posBest) return null;

	var ddx = posBest.x - negBest.x;
	var ddy = posBest.y - negBest.y;
	return {
		from: { x: negBest.x, y: negBest.y },
		to:   { x: posBest.x, y: posBest.y },
		dist: Math.sqrt(ddx * ddx + ddy * ddy),
		mode: dir === 'h' ? 'horiz' : 'vert'
	};
};

// -- Main measurement (perpendicular with H/V fallback) -------------
TRV.stem.measure = function(gx, gy, layer) {
	// Try perpendicular measurement first
	var m = TRV.stem.measurePerp(gx, gy, layer);
	if (m) return m;

	// Fallback: try both axes, return the smaller (likely stem width)
	var mh = TRV.stem.measureAxis(gx, gy, layer, 'h');
	var mv = TRV.stem.measureAxis(gx, gy, layer, 'v');

	if (mh && mv) return mh.dist <= mv.dist ? mh : mv;
	return mh || mv;
};

// -- Draw stem measurement on canvas --------------------------------
TRV.drawStemMeasurement = function(layer) {
	if (!TRV.state.showStem) return;

	var mouse = TRV.state.previewMouse;
	if (!mouse) return;

	// Convert screen mouse to glyph coords
	var gp = TRV.screenToGlyph(mouse.x, mouse.y);

	// Only measure inside glyph body
	if (!TRV.stem.isInside(gp.x, gp.y, layer)) return;

	var m = TRV.stem.measure(gp.x, gp.y, layer);
	if (!m) return;

	var ctx = TRV.dom.ctx;
	var th = TRV.getCurrentTheme().onStemMeasurment;
	var preview = TRV.state.previewMode;

	// Convert endpoints to screen coords
	var sp1 = TRV.glyphToScreen(m.from.x, m.from.y);
	var sp2 = TRV.glyphToScreen(m.to.x, m.to.y);

	// Measurement line
	ctx.save();
	ctx.strokeStyle = preview ? th.linePreview : th.line;
	ctx.lineWidth = 1;
	ctx.setLineDash([4, 3]);
	ctx.beginPath();
	ctx.moveTo(sp1.x, sp1.y);
	ctx.lineTo(sp2.x, sp2.y);
	ctx.stroke();
	ctx.setLineDash([]);

	// Endpoint marks (small crosses)
	var mk = 4;
	ctx.strokeStyle = th.mark;
	ctx.lineWidth = 1.5;
	ctx.beginPath();
	ctx.moveTo(sp1.x - mk, sp1.y); ctx.lineTo(sp1.x + mk, sp1.y);
	ctx.moveTo(sp1.x, sp1.y - mk); ctx.lineTo(sp1.x, sp1.y + mk);
	ctx.moveTo(sp2.x - mk, sp2.y); ctx.lineTo(sp2.x + mk, sp2.y);
	ctx.moveTo(sp2.x, sp2.y - mk); ctx.lineTo(sp2.x, sp2.y + mk);
	ctx.stroke();

	// Distance label at midpoint
	var mx = (sp1.x + sp2.x) / 2;
	var my = (sp1.y + sp2.y) / 2;
	var label = Math.round(m.dist) + '';

	ctx.font = th.labelFont;
	ctx.textAlign = 'center';
	ctx.textBaseline = 'bottom';

	// Small background pill for readability
	var tw = ctx.measureText(label).width;
	var pad = 3;
	ctx.fillStyle = preview ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.6)';
	ctx.fillRect(mx - tw / 2 - pad, my - 14 - pad, tw + pad * 2, 14 + pad);

	ctx.fillStyle = th.label;
	ctx.fillText(label, mx, my - pad);

	ctx.restore();
};
