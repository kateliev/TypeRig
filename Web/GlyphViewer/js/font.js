// ===================================================================
// TypeRig Glyph Viewer — Font-level operations (.trfont)
// ===================================================================
// Handles .trfont folder open/save via File System Access API.
// Lazy glyph loading with LRU cache and per-glyph undo stacks.
'use strict';

// -- Font state -----------------------------------------------------
TRV.font = null;            // null = loose .trglyph mode
TRV.glyphCache = new Map(); // name → { glyphData, undoStack, redoStack, selection, pan, zoom }
TRV.dirtyGlyphs = new Set();
TRV.activeGlyph = null;     // current glyph name
TRV.CACHE_MAX = 32;         // LRU eviction threshold

// -- Workspace (glyph strip) ----------------------------------------
TRV.workspace = {
	glyphs: [],       // ordered glyph names in strip (user-controlled)
	activeIdx: 0,     // index of active glyph in strip
};
TRV.STRIP_GAP = 40;  // glyph units between strip glyphs

// -- Resolve default layer name for thumbnails & strip ---------------
// Priority: font master default → 'Regular' → first non-mask layer
TRV.getDefaultLayerName = function(glyphData) {
	if (!glyphData || !glyphData.layers || glyphData.layers.length === 0) return null;

	// 1. If font has masters defined, use the default master's layer name
	if (TRV.font && TRV.font.masters && TRV.font.masters.length > 0) {
		for (var i = 0; i < TRV.font.masters.length; i++) {
			if (TRV.font.masters[i].isDefault) {
				var lname = TRV.font.masters[i].layerName;
				for (var j = 0; j < glyphData.layers.length; j++) {
					if (glyphData.layers[j].name === lname) return lname;
				}
			}
		}
		// Fallback: first master's layer name
		var firstMasterLayer = TRV.font.masters[0].layerName;
		for (var j = 0; j < glyphData.layers.length; j++) {
			if (glyphData.layers[j].name === firstMasterLayer) return firstMasterLayer;
		}
	}

	// 2. Try 'Regular'
	for (var j = 0; j < glyphData.layers.length; j++) {
		if (glyphData.layers[j].name === 'Regular') return 'Regular';
	}

	// 3. First non-mask layer
	for (var j = 0; j < glyphData.layers.length; j++) {
		if (!TRV.isMaskLayer(glyphData.layers[j].name)) return glyphData.layers[j].name;
	}

	// 4. Whatever's there
	return glyphData.layers[0].name;
};

// Helper: get layer object by name from glyphData
TRV.getLayerByName = function(glyphData, name) {
	if (!glyphData) return null;
	for (var i = 0; i < glyphData.layers.length; i++) {
		if (glyphData.layers[i].name === name) return glyphData.layers[i];
	}
	return null;
};

// -- Parse font.xml -------------------------------------------------
TRV.parseFontXml = function(xmlString) {
	var parser = new DOMParser();
	var doc = parser.parseFromString(xmlString, 'text/xml');
	var root = doc.documentElement;

	// Info: <info> → <meta key="..." value="..."/>
	var info = { family: 'Untitled', style: 'Regular' };
	var infoEl = root.querySelector('info');
	if (infoEl) {
		var metas = infoEl.querySelectorAll('meta');
		for (var i = 0; i < metas.length; i++) {
			var k = metas[i].getAttribute('key');
			var v = metas[i].getAttribute('value') || '';
			if (k === 'family-name') info.family = v;
			else if (k === 'style-name') info.style = v;
		}
	}

	// Metrics: <metrics upm="..." ascender="..." .../>
	var metrics = { upm: 1000, ascender: 800, descender: -200, xHeight: 500, capHeight: 700 };
	var metricsEl = root.querySelector('metrics');
	if (metricsEl) {
		var _int = function(attr, def) {
			var v = metricsEl.getAttribute(attr);
			return v !== null ? parseInt(v) : def;
		};
		metrics.upm       = _int('upm', 1000);
		metrics.ascender  = _int('ascender', 800);
		metrics.descender = _int('descender', -200);
		metrics.xHeight   = _int('x-height', 500);
		metrics.capHeight = _int('cap-height', 700);
	}

	// Masters: <masters> → <master name="..." layer="..." default="true"/>
	var masters = [];
	var masterEls = root.querySelectorAll('masters > master');
	for (var i = 0; i < masterEls.length; i++) {
		masters.push({
			name: masterEls[i].getAttribute('name') || '',
			layerName: masterEls[i].getAttribute('layer') || masterEls[i].getAttribute('name') || '',
			isDefault: masterEls[i].getAttribute('default') === 'true'
		});
	}

	// Encoding: <encoding> → <entry name="..." unicodes="0041 0042"/>
	var encoding = {};
	var encEls = root.querySelectorAll('encoding > entry');
	for (var i = 0; i < encEls.length; i++) {
		var name = encEls[i].getAttribute('name');
		var val = encEls[i].getAttribute('unicodes');
		if (name && val) encoding[name] = val;
	}

	return { info: info, metrics: metrics, masters: masters, encoding: encoding };
};

// -- Parse glyphs.xml -----------------------------------------------
TRV.parseGlyphsManifest = function(xmlString) {
	var parser = new DOMParser();
	var doc = parser.parseFromString(xmlString, 'text/xml');
	var root = doc.documentElement;

	var entries = [];
	var index = {};
	var glyphEls = root.querySelectorAll('glyph');

	for (var i = 0; i < glyphEls.length; i++) {
		var el = glyphEls[i];
		var entry = {
			name: el.getAttribute('name') || '',
			path: el.getAttribute('src') || '',
			alias: el.getAttribute('alias') || ''
		};
		entries.push(entry);
		var key = entry.alias || entry.name;
		index[key] = entry;
	}

	return { entries: entries, index: index };
};

// -- Read file from directory handle --------------------------------
TRV._readFile = async function(dirHandle, relativePath) {
	var parts = relativePath.replace(/\\/g, '/').split('/');
	var current = dirHandle;

	// Navigate subdirectories
	for (var i = 0; i < parts.length - 1; i++) {
		current = await current.getDirectoryHandle(parts[i]);
	}

	var fileHandle = await current.getFileHandle(parts[parts.length - 1]);
	var file = await fileHandle.getFile();
	return await file.text();
};

// -- Write file to directory handle ---------------------------------
TRV._writeFile = async function(dirHandle, relativePath, content) {
	var parts = relativePath.replace(/\\/g, '/').split('/');
	var current = dirHandle;

	// Navigate/create subdirectories
	for (var i = 0; i < parts.length - 1; i++) {
		current = await current.getDirectoryHandle(parts[i], { create: true });
	}

	var fileHandle = await current.getFileHandle(parts[parts.length - 1], { create: true });
	var writable = await fileHandle.createWritable();
	await writable.write(content);
	await writable.close();
};

// -- Open .trfont folder --------------------------------------------
TRV.openFont = async function() {
	try {
		var dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });

		// Read font.xml
		var fontXml;
		try {
			fontXml = await TRV._readFile(dirHandle, 'font.xml');
		} catch (e) {
			alert('Not a valid .trfont folder: font.xml not found.');
			return;
		}

		// Read glyphs.xml
		var glyphsXml;
		try {
			glyphsXml = await TRV._readFile(dirHandle, 'glyphs.xml');
		} catch (e) {
			alert('Not a valid .trfont folder: glyphs.xml not found.');
			return;
		}

		var fontData = TRV.parseFontXml(fontXml);
		var manifest = TRV.parseGlyphsManifest(glyphsXml);

		// Attach encoding unicodes to manifest entries
		for (var i = 0; i < manifest.entries.length; i++) {
			var entry = manifest.entries[i];
			var key = entry.alias || entry.name;
			if (fontData.encoding[key]) {
				entry.unicodes = fontData.encoding[key];
			}
		}

		// Store font state
		TRV.font = {
			dirHandle: dirHandle,
			info: fontData.info,
			metrics: fontData.metrics,
			masters: fontData.masters,
			encoding: fontData.encoding,
			manifest: manifest.entries,
			manifestIndex: manifest.index
		};

		// Clear previous state
		TRV.glyphCache.clear();
		TRV.dirtyGlyphs.clear();
		TRV.activeGlyph = null;

		// Update UI
		TRV.buildGlyphPanel();
		TRV.updateFontInfo();

		// Load first glyph
		if (manifest.entries.length > 0) {
			await TRV.switchGlyph(manifest.entries[0].alias || manifest.entries[0].name);
		}

	} catch (e) {
		if (e.name !== 'AbortError') {
			console.error('openFont error:', e);
			alert('Error opening font: ' + e.message);
		}
	}
};

// -- Load a single glyph from disk ----------------------------------
TRV.loadGlyphFile = async function(name) {
	if (!TRV.font) return null;

	var entry = TRV.font.manifestIndex[name];
	if (!entry) return null;

	try {
		var xmlString = await TRV._readFile(TRV.font.dirHandle, entry.path);
		var glyphData = TRV.parseGlyphXML(xmlString);
		return glyphData;
	} catch (e) {
		console.error('Error loading glyph "' + name + '":', e);
		return null;
	}
};

// -- Switch active glyph -------------------------------------------
TRV.switchGlyph = async function(name) {
	if (!TRV.font) return;
	if (name === TRV.activeGlyph) return;

	// Stash current glyph state into cache
	if (TRV.activeGlyph && TRV.glyphCache.has(TRV.activeGlyph)) {
		var current = TRV.glyphCache.get(TRV.activeGlyph);
		current.selection = new Set(TRV.state.selectedNodeIds);
		current.pan = { x: TRV.state.pan.x, y: TRV.state.pan.y };
		current.zoom = TRV.state.zoom;
	}

	// Load glyph if not cached
	if (!TRV.glyphCache.has(name)) {
		var glyphData = await TRV.loadGlyphFile(name);
		if (!glyphData) return;

		TRV.glyphCache.set(name, {
			glyphData: glyphData,
			undoStack: [],
			redoStack: [],
			selection: new Set(),
			pan: null,
			zoom: null
		});

		// LRU eviction
		TRV._evictCache();
	}

	// Activate
	var entry = TRV.glyphCache.get(name);
	TRV.activeGlyph = name;
	TRV.state.glyphData = entry.glyphData;
	TRV.state.rawXml = '';

	// Restore per-glyph state
	TRV.state.selectedNodeIds = entry.selection;

	// Populate layer dropdown
	TRV.dom.layerSelect.innerHTML = '';
	for (var i = 0; i < entry.glyphData.layers.length; i++) {
		var layer = entry.glyphData.layers[i];
		var opt = document.createElement('option');
		opt.value = layer.name;
		opt.textContent = layer.name || '(unnamed)';
		TRV.dom.layerSelect.appendChild(opt);
	}

	if (entry.glyphData.layers.length > 0) {
		TRV.state.activeLayer = entry.glyphData.layers[0].name;
		TRV.dom.layerSelect.value = TRV.state.activeLayer;
	}

	// Glyph info in toolbar
	var g = entry.glyphData;
	var enc = TRV.font.encoding[name] || g.unicodes || '';
	var infoHtml = '<span>' + (g.name || name) + '</span>';
	if (enc) infoHtml += ' U+' + enc;
	TRV.dom.glyphInfo.innerHTML = infoHtml;

	TRV.dom.emptyState.classList.add('hidden');

	// Restore or fit viewport (skip in strip mode — zoom persists)
	if (TRV.state.glyphViewMode && TRV.font) {
		// Strip mode: zoom stays, just update strip membership
	} else if (entry.pan !== null) {
		TRV.state.pan = entry.pan;
		TRV.state.zoom = entry.zoom;
	} else {
		TRV.fitToView();
	}

	// Re-init multi-view if active
	if (TRV.state.glyphViewMode) {
		TRV.updateWorkspaceStrip();
		TRV.state.activeCell = { row: 0, col: 0 };
		TRV.syncActiveCellToLayer();
	} else if (TRV.state.multiView) {
		TRV.initMultiGrid();
	}

	TRV.buildXmlPanel();
	TRV.draw();
	TRV.updateStatusSelected();
	TRV.updateGlyphPanelActive();
};

// -- LRU eviction ---------------------------------------------------
TRV._evictCache = function() {
	if (TRV.glyphCache.size <= TRV.CACHE_MAX) return;

	// Evict oldest entries that aren't dirty or active
	var keys = Array.from(TRV.glyphCache.keys());
	for (var i = 0; i < keys.length; i++) {
		if (TRV.glyphCache.size <= TRV.CACHE_MAX) break;
		var k = keys[i];
		if (k === TRV.activeGlyph) continue;
		if (TRV.dirtyGlyphs.has(k)) continue;
		TRV.glyphCache.delete(k);
	}
};

// -- Per-glyph undo integration -------------------------------------
// These replace the global stacks when a font is open.
TRV._getUndoEntry = function() {
	if (!TRV.font || !TRV.activeGlyph) return null;
	return TRV.glyphCache.get(TRV.activeGlyph) || null;
};

// -- Save dirty glyphs to disk --------------------------------------
TRV.saveDirtyGlyphs = async function() {
	if (!TRV.font || TRV.dirtyGlyphs.size === 0) return;

	var saved = 0;
	var errors = [];

	for (var name of TRV.dirtyGlyphs) {
		var entry = TRV.glyphCache.get(name);
		if (!entry) continue;

		var manifestEntry = TRV.font.manifestIndex[name];
		if (!manifestEntry) continue;

		try {
			var xmlString = TRV.glyphToXml(entry.glyphData);
			await TRV._writeFile(TRV.font.dirHandle, manifestEntry.path, xmlString);
			saved++;
		} catch (e) {
			errors.push(name + ': ' + e.message);
		}
	}

	TRV.dirtyGlyphs.clear();
	TRV.updateGlyphPanelDirty();

	if (errors.length > 0) {
		alert('Saved ' + saved + ' glyphs. Errors:\n' + errors.join('\n'));
	}
};

// -- Build glyph list panel -----------------------------------------
TRV.buildGlyphPanel = function() {
	var panel = document.getElementById('glyph-panel');
	var list = document.getElementById('glyph-list');
	var search = document.getElementById('glyph-search');
	var countEl = document.getElementById('glyph-count');
	if (!panel || !list) return;

	panel.classList.add('visible');
	list.innerHTML = '';

	// Disconnect previous observer
	if (TRV._thumbObserver) TRV._thumbObserver.disconnect();

	if (!TRV.font) return;

	for (var i = 0; i < TRV.font.manifest.length; i++) {
		var entry = TRV.font.manifest[i];
		var name = entry.alias || entry.name;
		var div = document.createElement('div');
		div.className = 'glyph-entry';
		div.dataset.name = name;

		// Thumbnail canvas
		var cvs = document.createElement('canvas');
		cvs.className = 'glyph-thumb';
		cvs.width = 28;
		cvs.height = 36;
		div.appendChild(cvs);

		var nameSpan = document.createElement('span');
		nameSpan.className = 'glyph-entry-name';
		nameSpan.textContent = name;
		div.appendChild(nameSpan);

		if (entry.unicodes) {
			var uniSpan = document.createElement('span');
			uniSpan.className = 'glyph-entry-uni';
			uniSpan.textContent = 'U+' + entry.unicodes;
			div.appendChild(uniSpan);
		}

		var dot = document.createElement('span');
		dot.className = 'glyph-entry-dirty';
		div.appendChild(dot);

		list.appendChild(div);
	}

	// Clear search
	if (search) search.value = '';

	// Show count
	if (countEl) countEl.textContent = TRV.font.manifest.length;

	// Setup IntersectionObserver for lazy thumbnail loading
	TRV._thumbObserver = new IntersectionObserver(function(entries) {
		for (var i = 0; i < entries.length; i++) {
			if (!entries[i].isIntersecting) continue;
			var el = entries[i].target;
			var name = el.dataset.name;
			if (!name || el.dataset.thumbLoaded) continue;
			TRV._queueThumbnail(name, el);
		}
	}, { root: list, rootMargin: '100px 0px' });

	var allEntries = list.querySelectorAll('.glyph-entry');
	for (var i = 0; i < allEntries.length; i++) {
		TRV._thumbObserver.observe(allEntries[i]);
	}
};

// -- Thumbnail rendering queue --------------------------------------
TRV._thumbQueue = [];
TRV._thumbRunning = false;

TRV._queueThumbnail = function(name, el) {
	// Skip if already queued or rendered
	if (el.dataset.thumbLoaded) return;
	TRV._thumbQueue.push({ name: name, el: el });
	TRV._processThumbQueue();
};

TRV._processThumbQueue = async function() {
	if (TRV._thumbRunning) return;
	TRV._thumbRunning = true;

	while (TRV._thumbQueue.length > 0) {
		var item = TRV._thumbQueue.shift();
		var name = item.name;
		var el = item.el;

		if (el.dataset.thumbLoaded) continue;

		// Load glyph if not cached
		var cacheEntry = TRV.glyphCache.get(name);
		var glyphData = cacheEntry ? cacheEntry.glyphData : null;

		if (!glyphData) {
			glyphData = await TRV.loadGlyphFile(name);
			if (!glyphData) {
				el.dataset.thumbLoaded = 'empty';
				continue;
			}
			// Don't pollute the editing cache with thumbnail loads
			// Just use the data temporarily
		}

		TRV._renderThumbnail(el, glyphData);
		el.dataset.thumbLoaded = 'true';

		// Yield every 8 thumbnails to keep UI responsive
		if (TRV._thumbQueue.length > 0 && TRV._thumbQueue.length % 8 === 0) {
			await new Promise(function(r) { requestAnimationFrame(r); });
		}
	}

	TRV._thumbRunning = false;
};

// -- Render a single glyph thumbnail --------------------------------
TRV._renderThumbnail = function(entryEl, glyphData) {
	var cvs = entryEl.querySelector('.glyph-thumb');
	if (!cvs) return;

	var ctx = cvs.getContext('2d');
	var w = cvs.width;
	var h = cvs.height;

	// Find default layer (consistent across all glyphs)
	var layerName = TRV.getDefaultLayerName(glyphData);
	var layer = TRV.getLayerByName(glyphData, layerName);
	if (!layer || layer.shapes.length === 0) return;

	// Compute transform to fit glyph in thumbnail
	var upm = TRV.font ? TRV.font.metrics.upm : 1000;
	var desc = TRV.font ? Math.abs(TRV.font.metrics.descender) : 200;
	var advW = layer.width || upm;
	var totalH = upm + desc * 0.3;

	var scale = Math.min((w - 4) / advW, (h - 4) / totalH);
	var ox = (w - advW * scale) / 2;
	var oy = h - 3 - desc * 0.3 * scale;

	ctx.clearRect(0, 0, w, h);

	// Draw filled contours
	ctx.beginPath();
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var contour = shape.contours[ki];
			if (!contour.closed || contour.nodes.length === 0) continue;
			TRV._buildThumbPath(ctx, contour.nodes, scale, ox, oy);
		}
	}

	ctx.fillStyle = 'rgba(200,200,210,0.55)';
	ctx.fill('nonzero');
};

// -- Build a contour path for thumbnail (mini version of buildContourPath)
TRV._buildThumbPath = function(ctx, nodes, scale, ox, oy) {
	var n = nodes.length;
	if (n === 0) return;

	// Find first on-curve
	var firstOn = 0;
	for (var j = 0; j < n; j++) {
		if (nodes[j].type === 'on') { firstOn = j; break; }
	}

	var tx = function(x) { return x * scale + ox; };
	var ty = function(y) { return -y * scale + oy; };

	ctx.moveTo(tx(nodes[firstOn].x), ty(nodes[firstOn].y));

	var i = (firstOn + 1) % n;
	var count = 0;

	while (count < n - 1) {
		var node = nodes[i];

		if (node.type === 'on') {
			ctx.lineTo(tx(node.x), ty(node.y));
		} else if (node.type === 'curve') {
			var b1 = node;
			var b2 = nodes[(i + 1) % n];
			var on = nodes[(i + 2) % n];
			ctx.bezierCurveTo(tx(b1.x), ty(b1.y), tx(b2.x), ty(b2.y), tx(on.x), ty(on.y));
			i = (i + 2) % n;
			count += 2;
		} else if (node.type === 'off') {
			var off = node;
			var on = nodes[(i + 1) % n];
			ctx.quadraticCurveTo(tx(off.x), ty(off.y), tx(on.x), ty(on.y));
			i = (i + 1) % n;
			count += 1;
		}

		i = (i + 1) % n;
		count++;
	}

	ctx.closePath();
};

// -- Refresh a single thumbnail after editing -----------------------
TRV.refreshThumbnail = function(name) {
	var list = document.getElementById('glyph-list');
	if (!list) return;
	var entry = list.querySelector('.glyph-entry[data-name="' + name + '"]');
	if (!entry) return;

	var cacheEntry = TRV.glyphCache.get(name);
	if (cacheEntry) {
		entry.dataset.thumbLoaded = '';
		TRV._renderThumbnail(entry, cacheEntry.glyphData);
		entry.dataset.thumbLoaded = 'true';
	}
};

// -- Update active highlight in glyph panel -------------------------
TRV.updateGlyphPanelActive = function() {
	var list = document.getElementById('glyph-list');
	if (!list) return;

	var stripSet = new Set(TRV.workspace.glyphs);

	var entries = list.querySelectorAll('.glyph-entry');
	for (var i = 0; i < entries.length; i++) {
		var name = entries[i].dataset.name;
		entries[i].classList.toggle('active', name === TRV.activeGlyph);
		entries[i].classList.toggle('in-strip', TRV.state.glyphViewMode && stripSet.has(name));
	}

	// Scroll active entry into view
	var active = list.querySelector('.glyph-entry.active');
	if (active) active.scrollIntoView({ block: 'nearest' });
};

// -- Update dirty dots in glyph panel -------------------------------
TRV.updateGlyphPanelDirty = function() {
	var list = document.getElementById('glyph-list');
	if (!list) return;

	var entries = list.querySelectorAll('.glyph-entry');
	for (var i = 0; i < entries.length; i++) {
		entries[i].classList.toggle('dirty', TRV.dirtyGlyphs.has(entries[i].dataset.name));
	}
};

// -- Filter glyph list by search text -------------------------------
TRV.filterGlyphPanel = function(query) {
	var list = document.getElementById('glyph-list');
	if (!list) return;

	var q = query.toLowerCase();
	var entries = list.querySelectorAll('.glyph-entry');
	for (var i = 0; i < entries.length; i++) {
		var name = entries[i].dataset.name.toLowerCase();
		entries[i].style.display = (!q || name.indexOf(q) >= 0) ? '' : 'none';
	}
};

// -- Update font info in toolbar ------------------------------------
TRV.updateFontInfo = function() {
	if (!TRV.font) return;
	var info = TRV.font.info;
	document.title = 'TR:GLYPH — ' + info.family + ' ' + info.style;
};

// -- Fit active glyph to its cell in glyph view mode ----------------
TRV.fitGlyphToCell = function() {
	if (!TRV.font || !TRV.state.multiView) return;

	var cell = TRV.getCellRect(TRV.state.activeCell.row, TRV.state.activeCell.col);
	var layer = TRV.getActiveLayer();
	if (!layer) return;

	var upm = TRV.font.metrics.upm;
	var desc = Math.abs(TRV.font.metrics.descender);
	var advW = layer.width || upm;
	var totalH = upm + desc * 0.5;
	var fitZoom = (cell.h * 0.8) / totalH;

	TRV.state.zoom = fitZoom;
	TRV.state.pan = {
		x: (cell.w - advW * fitZoom) / 2,
		y: cell.h * 0.75
	};
	TRV.updateZoomStatus();
};

// -- Unsaved changes warning ----------------------------------------
window.addEventListener('beforeunload', function(e) {
	if (TRV.dirtyGlyphs.size > 0) {
		e.preventDefault();
		e.returnValue = '';
	}
});

// -- Cycle through layers -------------------------------------------
// Rotates the active cell's layer in gridLayers (multi-view/strip).
// Falls back to global activeLayer rotation in single view.
TRV.cycleLayer = function(direction) {
	var state = TRV.state;
	var glyphData = state.glyphData;
	if (!glyphData) return;

	// Build valid (non-mask) layer indices
	var valid = [];
	for (var i = 0; i < glyphData.layers.length; i++) {
		if (!TRV.isMaskLayer(glyphData.layers[i].name)) valid.push(i);
	}
	if (valid.length <= 1) return;

	// Per-cell rotation when gridLayers is active
	if (state.gridLayers && state.gridLayers[state.activeCell.row] &&
		state.gridLayers[state.activeCell.row][state.activeCell.col] !== undefined) {
		var r = state.activeCell.row;
		var c = state.activeCell.col;
		var current = state.gridLayers[r][c];
		var pos = valid.indexOf(current);
		if (pos < 0) pos = 0;
		pos = ((pos + direction) % valid.length + valid.length) % valid.length;
		state.gridLayers[r][c] = valid[pos];

		state.activeLayer = glyphData.layers[valid[pos]].name;
		TRV.dom.layerSelect.value = state.activeLayer;
	} else {
		// Single view: rotate global activeLayer
		var names = valid.map(function(i) { return glyphData.layers[i].name; });
		var idx = names.indexOf(state.activeLayer);
		if (idx < 0) idx = 0;
		idx = ((idx + direction) % names.length + names.length) % names.length;
		state.activeLayer = names[idx];
		TRV.dom.layerSelect.value = state.activeLayer;
	}

	state.selectedNodeIds.clear();
	TRV.draw();
	TRV.updateStatusSelected();
};

// -- Step to next/previous glyph in manifest ------------------------
TRV.stepGlyph = function(direction) {
	if (!TRV.font || !TRV.activeGlyph) return;

	var manifest = TRV.font.manifest;
	var idx = -1;
	for (var i = 0; i < manifest.length; i++) {
		var name = manifest[i].alias || manifest[i].name;
		if (name === TRV.activeGlyph) { idx = i; break; }
	}

	if (idx < 0) return;

	var newIdx = idx + direction;
	if (newIdx < 0) newIdx = manifest.length - 1;
	if (newIdx >= manifest.length) newIdx = 0;

	var newName = manifest[newIdx].alias || manifest[newIdx].name;
	TRV.switchGlyph(newName);
};
