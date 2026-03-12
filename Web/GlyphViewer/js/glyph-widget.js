// ===================================================================
// TypeRig Glyph Viewer — Glyph Widget
// ===================================================================
// HTML overlay widgets for glyph strip view.
// Shows editable widget for active glyph, read-only for others.
// ===================================================================
'use strict';

// -- Compute widget position and size (centered on glyph middle) ------
TRV._getWidgetRect = function(advW, verticalOffset) {
	var lsbScreen = TRV.glyphToScreen(0, 0);
	var rsbScreen = TRV.glyphToScreen(advW, 0);
	var wrapRect = TRV.dom.canvasWrap.getBoundingClientRect();
	var state = TRV.state;

	// Fixed size: half of advance width
	var widgetW = advW * 0.5 * state.zoom;
	var minW = 100;
	widgetW = Math.max(minW, widgetW);

	// Center on middle of glyph (advance / 2)
	var midScreenX = (lsbScreen.x + rsbScreen.x) / 2;
	var screenX = midScreenX - widgetW / 2;
	var screenY = lsbScreen.y + (verticalOffset || 12);

	return {
		left: screenX,
		top: screenY,
		width: widgetW
	};
};

// -- Glyph Widget HTML Overlay ---------------------------------------
TRV._widgetSlot = null;

TRV.showGlyphWidget = function(name, layer) {
	var widget = TRV.dom.glyphWidget;
	if (!widget || !name || !layer) return;

	var state = TRV.state;
	var bounds = TRV._getLayerBounds(layer);
	var advW = layer.width || 0;

	var lsbVal = bounds ? Math.round(bounds.minX) : 0;
	var rsbVal = bounds ? Math.round(advW - bounds.maxX) : 0;

	var unicode = '';
	if (TRV.font && TRV.font.encoding) {
		var code = TRV.font.encoding[name];
		if (code) unicode = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
	}

	var rect = TRV._getWidgetRect(advW, 12);

	widget.style.left = rect.left + 'px';
	widget.style.top = rect.top + 'px';
	widget.style.width = rect.width + 'px';

	// Determine if we should stack vertically (when widget is narrow)
	var stackFields = rect.width < 140;

	if (stackFields) {
		widget.classList.add('gw-stacked');
	} else {
		widget.classList.remove('gw-stacked');
	}

	TRV.dom.gwName.value = name;
	TRV.dom.gwUnicode.value = unicode;
	TRV.dom.gwLsb.value = lsbVal;
	TRV.dom.gwAdvance.value = advW;
	TRV.dom.gwRsb.value = rsbVal;

	TRV._widgetSlot = name;

	widget.classList.add('visible');
};

TRV.hideGlyphWidget = function() {
	if (TRV.dom.glyphWidget) {
		TRV.dom.glyphWidget.classList.remove('visible');
	}
	TRV._widgetSlot = null;
	if (TRV.dom.glyphWidgets) {
		TRV.dom.glyphWidgets.innerHTML = '';
	}
};

TRV._createReadonlyWidget = function(name, layer) {
	var container = TRV.dom.glyphWidgets;
	if (!container) return;

	var state = TRV.state;
	var bounds = TRV._getLayerBounds(layer);
	var advW = layer.width || 0;

	var unicode = '';
	if (TRV.font && TRV.font.encoding) {
		var code = TRV.font.encoding[name];
		if (code) unicode = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
	}

	var rect = TRV._getWidgetRect(advW, 12);

	var widget = document.createElement('div');
	widget.className = 'glyph-widget glyph-widget--readonly visible';
	widget.style.left = rect.left + 'px';
	widget.style.top = rect.top + 'px';
	widget.style.width = rect.width + 'px';
	widget.dataset.glyphName = name;

	// Stacked layout: name, unicode, close button
	widget.innerHTML =
		'<div class="gw-field"><span class="tri">label</span><span class="gw-value">' + name + '</span></div>' +
		'<div class="gw-field"><span class="tri">select_glyph</span><span class="gw-value">' + unicode + '</span></div>' +
		'<div class="gw-field gw-field--action" data-field="close"><span class="tri">close</span></div>';

	container.appendChild(widget);

	// Stop propagation on the widget to prevent canvas click handling
	widget.addEventListener('click', function(e) {
		e.stopPropagation();
	});

	widget.addEventListener('mousedown', function(e) {
		e.stopPropagation();
	});

	// Wire close button
	var closeBtn = widget.querySelector('[data-field="close"]');
	if (closeBtn) {
		closeBtn.addEventListener('click', function(e) {
			e.stopPropagation();
			e.preventDefault();
			TRV.removeGlyphFromStrip(name);
		});
	}
};

TRV.updateGlyphWidget = function() {
	var state = TRV.state;

	// No glyph loaded - hide widget
	if (!state.glyphData) {
		TRV.hideGlyphWidget();
		return;
	}

	// Clear non-active widgets container
	if (TRV.dom.glyphWidgets) {
		TRV.dom.glyphWidgets.innerHTML = '';
	}

	// --- GLYPH STRIP MODE ---
	if (state.glyphViewMode && TRV.font) {
		var ws = TRV.workspace;
		if (ws.activeIdx < 0 || ws.activeIdx >= ws.glyphs.length) {
			TRV.hideGlyphWidget();
			return;
		}

		var layout = TRV.getGlyphStripLayout();

		var activeSlot = null;
		for (var i = 0; i < layout.slots.length; i++) {
			if (layout.slots[i].active) { activeSlot = layout.slots[i]; break; }
		}

		// Create read-only widgets for non-active glyphs
		var basePanX = state.pan.x - (activeSlot ? activeSlot.x * state.zoom : 0);
		var basePanY = state.pan.y;
		var savedPanX = state.pan.x;
		var savedPanY = state.pan.y;

		for (var i = 0; i < layout.slots.length; i++) {
			var slot = layout.slots[i];
			if (slot.active) continue;

			var cacheEntry = TRV.glyphCache.get(slot.name);
			if (!cacheEntry) continue;

			var layer = TRV.getLayerByName(cacheEntry.glyphData, state.activeLayer);
			if (!layer) layer = cacheEntry.glyphData.layers[0];
			if (!layer) continue;

			state.pan.x = basePanX + slot.x * state.zoom;
			state.pan.y = basePanY;

			TRV._createReadonlyWidget(slot.name, layer);
		}

		state.pan.x = savedPanX;
		state.pan.y = savedPanY;

		if (!activeSlot) {
			TRV.hideGlyphWidget();
			return;
		}

		// Show editable widget for active glyph
		var name = ws.glyphs[ws.activeIdx];
		var cacheEntry = TRV.glyphCache.get(name);
		if (!cacheEntry) {
			TRV.hideGlyphWidget();
			return;
		}

		var layer = TRV.getLayerByName(cacheEntry.glyphData, state.activeLayer);
		if (!layer) layer = cacheEntry.glyphData.layers[0];
		if (!layer) {
			TRV.hideGlyphWidget();
			return;
		}

		TRV.showGlyphWidget(name, layer);
		return;
	}

	// --- SINGLE GLYPH MODE (not glyphViewMode) ---
	// Show editable widget for the current glyph
	var layer = TRV.getActiveLayer();
	if (!layer) {
		TRV.hideGlyphWidget();
		return;
	}

	var glyphName = state.glyphData.name || TRV.activeGlyph;
	if (!glyphName) {
		TRV.hideGlyphWidget();
		return;
	}

	TRV.showGlyphWidget(glyphName, layer);
};

TRV.initGlyphWidget = function() {
	var nameInput = TRV.dom.gwName;
	var unicodeInput = TRV.dom.gwUnicode;
	var lsbInput = TRV.dom.gwLsb;
	var advInput = TRV.dom.gwAdvance;
	var rsbInput = TRV.dom.gwRsb;

	nameInput.addEventListener('change', function() {
		var oldName = TRV._widgetSlot;
		var newName = this.value.trim();
		if (!oldName || !newName || oldName === newName) return;

		var ws = TRV.workspace;
		var idx = ws.glyphs.indexOf(oldName);
		if (idx >= 0) {
			ws.glyphs[idx] = newName;
			TRV.activeGlyph = newName;
			TRV.dirtyGlyphs.add(newName);
			TRV.dirtyGlyphs.delete(oldName);
			TRV._widgetSlot = newName;
			TRV.updateGlyphPanelActive();
		}
	});

	unicodeInput.addEventListener('change', function() {
		var glyphName = TRV._widgetSlot;
		var val = this.value.trim();
		if (!glyphName) return;

		var code = null;
		if (val.startsWith('U+') || val.startsWith('u+')) {
			code = parseInt(val.slice(2), 16);
		} else if (/^[0-9a-fA-F]+$/.test(val)) {
			code = parseInt(val, 16);
		}

		if (code !== null && code >= 0 && code <= 0x10FFFF) {
			if (TRV.font && TRV.font.encoding) {
				TRV.font.encoding[glyphName] = code;
				TRV.dirtyGlyphs.add(glyphName);
				this.value = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
			}
		} else {
			if (TRV.font && TRV.font.encoding) {
				var current = TRV.font.encoding[glyphName];
				if (current) {
					this.value = 'U+' + current.toString(16).toUpperCase().padStart(4, '0');
				}
			}
		}
	});

	function updateWidths() {
		var glyphName = TRV._widgetSlot;
		if (!glyphName) return;

		var lsb = parseInt(lsbInput.value) || 0;
		var adv = parseInt(advInput.value) || 0;
		var rsb = parseInt(rsbInput.value) || 0;

		if (lsb + rsb > adv) {
			rsb = adv - lsb;
			rsbInput.value = rsb;
		}

		var state = TRV.state;
		var glyphData = null;

		// Try cache first (glyph strip mode), then state.glyphData (single mode)
		var cacheEntry = TRV.glyphCache.get(glyphName);
		if (cacheEntry) {
			glyphData = cacheEntry.glyphData;
		} else if (state.glyphData && state.glyphData.name === glyphName) {
			glyphData = state.glyphData;
		}

		if (!glyphData) return;

		var layer = TRV.getLayerByName(glyphData, state.activeLayer);
		if (!layer) layer = glyphData.layers[0];
		if (!layer) return;

		layer.width = adv;

		var bounds = TRV._getLayerBounds(layer);
		if (bounds) {
			var currentLsb = Math.round(bounds.minX);
			var delta = lsb - currentLsb;
			if (delta !== 0) {
				for (var si = 0; si < layer.shapes.length; si++) {
					var shape = layer.shapes[si];
					for (var ki = 0; ki < shape.contours.length; ki++) {
						var nodes = shape.contours[ki].nodes;
						for (var ni = 0; ni < nodes.length; ni++) {
							nodes[ni].x += delta;
						}
					}
				}
			}
		}

		TRV.dirtyGlyphs.add(glyphName);
		TRV.draw();
		TRV.updateGlyphWidget();
	}

	lsbInput.addEventListener('change', updateWidths);
	advInput.addEventListener('change', updateWidths);
	rsbInput.addEventListener('change', updateWidths);

	var closeBtn = TRV.dom.glyphWidget.querySelector('[data-field="close"]');
	if (closeBtn) {
		closeBtn.addEventListener('click', function() {
			var name = TRV._widgetSlot;
			if (name) {
				TRV.removeGlyphFromStrip(name);
			}
		});
	}
};

TRV._getLayerBounds = function(layer) {
	var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	var found = false;
	for (var si = 0; si < layer.shapes.length; si++) {
		var shape = layer.shapes[si];
		for (var ki = 0; ki < shape.contours.length; ki++) {
			var nodes = shape.contours[ki].nodes;
			for (var ni = 0; ni < nodes.length; ni++) {
				found = true;
				if (nodes[ni].x < minX) minX = nodes[ni].x;
				if (nodes[ni].y < minY) minY = nodes[ni].y;
				if (nodes[ni].x > maxX) maxX = nodes[ni].x;
				if (nodes[ni].y > maxY) maxY = nodes[ni].y;
			}
		}
	}
	return found ? { minX: minX, minY: minY, maxX: maxX, maxY: maxY } : null;
};
