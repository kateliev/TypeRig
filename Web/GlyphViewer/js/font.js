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

	// Restore or fit viewport
	if (entry.pan !== null) {
		TRV.state.pan = entry.pan;
		TRV.state.zoom = entry.zoom;
	} else {
		TRV.fitToView();
	}

	// Re-init multi-view if active
	if (TRV.state.multiView) TRV.initMultiGrid();

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

	if (!TRV.font) return;

	for (var i = 0; i < TRV.font.manifest.length; i++) {
		var entry = TRV.font.manifest[i];
		var name = entry.alias || entry.name;
		var div = document.createElement('div');
		div.className = 'glyph-entry';
		div.dataset.name = name;

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
};

// -- Update active highlight in glyph panel -------------------------
TRV.updateGlyphPanelActive = function() {
	var list = document.getElementById('glyph-list');
	if (!list) return;

	var entries = list.querySelectorAll('.glyph-entry');
	for (var i = 0; i < entries.length; i++) {
		entries[i].classList.toggle('active', entries[i].dataset.name === TRV.activeGlyph);
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

// -- Unsaved changes warning ----------------------------------------
window.addEventListener('beforeunload', function(e) {
	if (TRV.dirtyGlyphs.size > 0) {
		e.preventDefault();
		e.returnValue = '';
	}
});

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
