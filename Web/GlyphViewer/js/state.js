// ===================================================================
// TypeRig Glyph Viewer — State & DOM refs
// ===================================================================
'use strict';

const TRV = {
	// -- Application state ----------------------------------------------
	state: {
		glyphData: null,       // parsed glyph object
		rawXml: '',            // raw XML string
		activeLayer: null,     // current layer name

		// View
		pan: { x: 0, y: 0 },
		zoom: 1,
		filled: true,
		showNodes: true,
		showMetrics: true,
		showAnchors: true,
		showMask: true,
		showXml: false,

		// Selection — set of node IDs ('c{ci}_n{ni}')
		selectedNodeIds: new Set(),

		// Node dragging
		isPanning: false,
		isDragging: false,
		dragStartPositions: null, // Map: nodeId → { x, y } at drag start
		dragOriginGlyph: null,    // glyph coords where drag started
		lastMouse: { x: 0, y: 0 },
		spaceDown: false,

		// Multi-layer grid view
		multiView: false,
		joinedView: false,        // true = shared canvas, false = split cells
		gridCols: 2,
		gridRows: 1,
		gridLayers: null,
		activeCell: { row: 0, col: 0 },

		// Rect / lasso selection
		isSelecting: false,
		selectMode: null,          // 'rect' | 'lasso'
		selectStartScreen: null,   // { x, y } screen coords
		selectCurrentScreen: null, // { x, y } screen coords (rect end)
		selectLassoPoints: [],     // [{ x, y }, ...] screen coords
	},

	// -- DOM references (populated on init) -----------------------------
	dom: {},

	// -- XML panel line maps --------------------------------------------
	xmlLineNodeMap: {},
	xmlNodeLineMap: {},
	xmlEditTimer: null,
	xmlSyncTimer: null,   // debounce for real-time XML sync during drag
};

// Populate DOM refs after DOM is ready
TRV.dom = {
	canvas:         document.getElementById('glyph-canvas'),
	ctx:            document.getElementById('glyph-canvas').getContext('2d'),
	canvasWrap:     document.getElementById('canvas-wrap'),
	xmlContent:     document.getElementById('xml-content'),
	xmlNodeCount:   document.getElementById('xml-node-count'),
	parseStatus:    document.getElementById('parse-status'),
	splitHandle:    document.getElementById('split-handle'),
	main:           document.getElementById('main'),
	emptyState:     document.getElementById('empty-state'),
	fileInput:      document.getElementById('file-input'),
	dropOverlay:    document.getElementById('drop-overlay'),
	layerSelect:    document.getElementById('layer-select'),
	glyphInfo:      document.getElementById('glyph-info'),
	statusZoom:     document.getElementById('status-zoom'),
	statusCursor:   document.getElementById('status-cursor'),
	statusSelected: document.getElementById('status-selected'),
};
