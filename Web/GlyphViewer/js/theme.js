// ===================================================================
// TypeRig Glyph Viewer — Drawing Theme / Color Palette
// ===================================================================
// All canvas drawing colors in one place.
// CSS colors live in style.css; this file covers canvas rendering only.
// ===================================================================
'use strict';

TRV.theme = {
	// -- Canvas background ------------------------------------------
	bgFilled:       '#18181b',
	bgOutline:      '#1a1a1e',
	// Same as RGB tuple for gradient fading (dividers)
	bgFadeRgb:      '24,24,27',

	// -- Contour outlines -------------------------------------------
	contour: {
		fill:         'rgba(200,200,210,0.12)',
		stroke:       'rgba(200,200,210,0.6)',
		strokePlain:  '#c8c8d2',           // outline mode (no fill)
	},

	// -- Mask layer outlines ----------------------------------------
	mask: {
		stroke:       'rgba(255,160,60,0.3)',
		lineWidth:    1.5,
	},

	// -- Metrics (baseline, advance, sidebearings) ------------------
	metrics: {
		baseline:     'rgba(255,120,80,0.25)',
		sidebearing:  'rgba(255,120,80,0.35)',
		advance:      'rgba(91,157,239,0.45)',
		labelBase:    'rgba(255,120,80,0.5)',
		labelBaseFg:  'rgba(255,120,80,0.6)',
		labelAdvance: 'rgba(91,157,239,0.7)',
	},

	// -- Nodes & handles --------------------------------------------
	node: {
		onCorner:     '#e8e8ec',           // on-curve corner
		onSmooth:     '#50c878',           // on-curve smooth
		offCurve:     '#5b9def',           // cubic/quadratic off-curve
		selected:     '#ff6b6b',           // any selected node
		outline:      'rgba(0,0,0,0.5)',   // node stroke
		handleLine:   'rgba(91,157,239,0.35)',
		startPoint:   '#ff6b6b',           // contour start triangle
	},

	// -- Anchors ----------------------------------------------------
	anchor: {
		fill:         '#ff6b6b',
		outline:      'rgba(0,0,0,0.5)',
		crosshair:    'rgba(255,107,107,0.4)',
		label:        'rgba(255,107,107,0.8)',
	},

	// -- Selection overlay (rect / lasso) ---------------------------
	selection: {
		fill:         'rgba(91,157,239,0.08)',
		stroke:       'rgba(91,157,239,0.6)',
	},

	// -- Layer label badge -------------------------------------------
	label: {
		textColor:    '#000000',
		font:         '10px "JetBrains Mono", monospace',
	},

	// -- Per-layer color palette (cycled by index) ------------------
	layerColors: [
		'#5b9def',  // blue
		'#ef6b5b',  // red
		'#50c878',  // green
		'#c084fc',  // purple
		'#f59e0b',  // amber
		'#06b6d4',  // cyan
		'#f472b6',  // pink
		'#a3e635',  // lime
	],

	// -- Grid / multi-view ------------------------------------------
	grid: {
		dividerHairline:   'rgba(255,255,255,0.06)',
		dividerHairlineJ:  'rgba(255,255,255,0.05)', // joined mode
		dividerFadeAlpha:  0.6,                       // split mode fade
		dividerFadeAlphaJ: 0.55,                      // joined mode fade
		activeBorder:      'rgba(91,157,239,0.35)',
	},
};

// -- Helpers --------------------------------------------------------
TRV.getLayerColor = function(layerIdx) {
	const colors = TRV.theme.layerColors;
	return colors[layerIdx % colors.length];
};

TRV.getBgColor = function() {
	return TRV.state.filled ? TRV.theme.bgFilled : TRV.theme.bgOutline;
};
