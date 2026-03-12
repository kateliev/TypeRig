// ===================================================================
// TypeRig Glyph Viewer — Drawing Theme / Color Palette
// ===================================================================
// All canvas drawing colors in one place.
// CSS colors live in style.css; this file covers canvas rendering only.
// ===================================================================
'use strict';

TRV.theme = {
	appTitle: 		'TR:EDIT', 
};

TRV.themeDark = {
	// -- Canvas background ------------------------------------------
	bgFilled:       '#18181b',
	bgOutline:      '#1a1a1e',
	bgPreview: 		'#ffffff',
	// Same as RGB tuple for gradient fading (dividers)
	bgFadeRgb:      '24,24,27',

	// -- Contour outlines -------------------------------------------
	contour: {
		fill:         'rgba(200,200,210,0.12)',
		stroke:       'rgba(200,200,210,0.6)',
		strokePlain:  '#c8c8d2',           // outline mode (no fill)
		lineWidth:    1,
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
		radius:       4,                   // node circle radius
		strokeWidth:  1.5,                 // node stroke width
		handleWidth:  1,                   // handle line width
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
		strokeWidth:  1,
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
		dividerHairlineJ:  'rgba(255,255,255,0.05)', 	// joined mode
		dividerFadeAlpha:  	0.6,                       	// split mode fade
		dividerFadeAlphaJ: 	0.55,                      	// joined mode fade
		activeBorder:      'rgba(91,157,239,0.35)',
		strokeWidth:       1,                        	// divider line width
		fade: 				24,
		joinedGap: 			80,							// joined mode gap between cells
		stripGap: 			40,  						// glyph strip gap between glyphs
	},

	// -- Cell highlight in glyphs mode ------------------------------
	activeCellHightlight: {
		backgroundGradient: 
							[[0, 'rgba(91,157,239,0)'],
							[0.15, 'rgba(91,157,239,0.04)'],
							[0.85, 'rgba(91,157,239,0.04)'],
							[1, 'rgba(91,157,239,0)']],
		strokeStyle: 		'rgba(91,157,239,0.12)',
		strokeWidth:       1,
	},

	// -- On stem measurment ----------------------------------------
	onStemMeasurment: {
		line:      		'rgba(6,182,212,0.7)',   // cyan measurement line
		linePreview: 	'rgba(6,182,212,0.5)', // lighter for BW preview
		mark:      		'#06b6d4',               // endpoint marks
		label:     		'#06b6d4',               // distance label
		labelFont: 		'11px "JetBrains Mono", monospace',
		lineWidth:      	1,
	},

	// -- Keyaboard movement ----------------------------------------
	keyboard: {
			arrowStep : 		1,
			arrowStep_SHIFT : 	10,
			arrowStep_CTRL : 	100,
	},
};

TRV.themeLight = {
	// -- Canvas background ------------------------------------------
	bgFilled:       '#ffffff',
	bgOutline:      '#f5f5f5',
	bgPreview: 		'#ffffff',
	bgFadeRgb:      '245,245,245',

	// -- Contour outlines -------------------------------------------
	contour: {
		fill:         'rgba(30,30,30,0.08)',
		stroke:       'rgba(30,30,30,0.5)',
		strokePlain:  '#404048',           // outline mode (no fill)
		lineWidth:    1.5,                 // slightly thicker for light bg
	},

	// -- Mask layer outlines ----------------------------------------
	mask: {
		stroke:       'rgba(234,88,12,0.4)',
		lineWidth:    2,
	},

	// -- Metrics (baseline, advance, sidebearings) ------------------
	metrics: {
		baseline:     'rgba(234,88,12,0.3)',
		sidebearing:  'rgba(234,88,12,0.4)',
		advance:      'rgba(37,99,235,0.5)',
		labelBase:    'rgba(234,88,12,0.6)',
		labelBaseFg:  'rgba(234,88,12,0.7)',
		labelAdvance: 'rgba(37,99,235,0.8)',
	},

	// -- Nodes & handles --------------------------------------------
	node: {
		onCorner:     '#1a1a1e',           // on-curve corner
		onSmooth:     '#16a34a',           // on-curve smooth
		offCurve:     '#2563eb',           // cubic/quadratic off-curve
		selected:     '#dc2626',           // any selected node
		outline:      'rgba(255,255,255,0.9)',   // node stroke (white for contrast)
		handleLine:   'rgba(37,99,235,0.5)',
		startPoint:   '#dc2626',           // contour start triangle
		radius:       5,                   // slightly larger for light bg
		strokeWidth:  2,                   // thicker stroke for light bg
		handleWidth:  1.5,                // thicker handle lines
	},

	// -- Anchors ----------------------------------------------------
	anchor: {
		fill:         '#dc2626',
		outline:      'rgba(255,255,255,0.9)',
		crosshair:    'rgba(220,38,38,0.5)',
		label:        'rgba(220,38,38,0.9)',
	},

	// -- Selection overlay (rect / lasso) ---------------------------
	selection: {
		fill:         'rgba(37,99,235,0.1)',
		stroke:       'rgba(37,99,235,0.7)',
		strokeWidth:  1.5,
	},

	// -- Layer label badge -------------------------------------------
	label: {
		textColor:    '#ffffff',
		font:         '10px "JetBrains Mono", monospace',
	},

	// -- Per-layer color palette (cycled by index) ------------------
	layerColors: [
		'#2563eb',  // blue
		'#dc2626',  // red
		'#16a34a',  // green
		'#7c3aed',  // purple
		'#d97706',  // amber
		'#0891b2',  // cyan
		'#db2777',  // pink
		'#65a30d',  // lime
	],

	// -- Grid / multi-view ------------------------------------------
	grid: {
		dividerHairline:   'rgba(0,0,0,0.1)',
		dividerHairlineJ:  'rgba(0,0,0,0.08)', 	// joined mode
		dividerFadeAlpha:  	0.5,                       	// split mode fade
		dividerFadeAlphaJ: 	0.45,                      	// joined mode fade
		activeBorder:      'rgba(37,99,235,0.5)',
		strokeWidth:       1.5,                      // thicker dividers
		fade: 				24,
		joinedGap: 			80,							// joined mode gap between cells
		stripGap: 			40,  						// glyph strip gap between glyphs
	},

	// -- Cell highlight in glyphs mode ------------------------------
	activeCellHightlight: {
		backgroundGradient: 
							[[0, 'rgba(37,99,235,0)'],
							[0.15, 'rgba(37,99,235,0.06)'],
							[0.85, 'rgba(37,99,235,0.06)'],
							[1, 'rgba(37,99,235,0)']],
		strokeStyle: 		'rgba(37,99,235,0.2)',
		strokeWidth:       1.5,
	},

	// -- On stem measurment ----------------------------------------
	onStemMeasurment: {
		line:      		'rgba(8,145,178,0.8)',   // cyan measurement line
		linePreview: 	'rgba(8,145,178,0.6)', // lighter for BW preview
		mark:      		'#0891b2',               // endpoint marks
		label:     		'#0891b2',               // distance label
		labelFont: 		'11px "JetBrains Mono", monospace',
		lineWidth:      	1.5,
	},

	// -- Keyaboard movement ----------------------------------------
	keyboard: {
			arrowStep : 		1,
			arrowStep_SHIFT : 	10,
			arrowStep_CTRL : 	100,
	},
};

// -- Get current theme based on body attribute ----------------------
TRV.getCurrentTheme = function() {
	var body = document.body;
	if (body.getAttribute('data-theme') === 'light') {
		return TRV.themeLight;
	}
	return TRV.themeDark;
};

// -- Helpers --------------------------------------------------------
TRV.getLayerColor = function(layerIdx) {
	const colors = TRV.getCurrentTheme().layerColors;
	return colors[layerIdx % colors.length];
};

TRV.getBgColor = function() {
	const theme = TRV.getCurrentTheme();
	return TRV.state.filled ? theme.bgFilled : theme.bgOutline;
};
