// ===================================================================
// TypeRig Glyph Viewer — Glyph Widget
// ===================================================================
// HTML overlay widgets for glyph strip view.
// Shows editable widget for active glyph, read-only for others.
// ===================================================================
'use strict';

// -- Compute widget position and size anchored to glyph advance ------
TRV._getWidgetRect = function(advW, verticalOffset) {
	var lsbScreen = TRV.glyphToScreen(0, 0);
	var rsbScreen = TRV.glyphToScreen(advW, 0);
	var wrapRect = TRV.dom.canvasWrap.getBoundingClientRect();

	var glyphScreenW = (rsbScreen.x - lsbScreen.x)*0.6;
	var minW = 120;
	var widgetW = Math.max(minW, glyphScreenW);

	var screenX = lsbScreen.x + widgetW/2;
	var screenY = lsbScreen.y + (verticalOffset || 12);

	return {
		left: screenX,
		top: screenY,
		width: widgetW
	};
};

// -- Glyph Widget HTML Overlay ---------------------------------------
TRV._widgetSlot = null;

TRV.showGlyphWidget = function(slot, layer) {
	var widget = TRV.dom.glyphWidget;
	if (!widget || !slot || !layer) return;

	var state = TRV.state;
	var bounds = TRV._getLayerBounds(layer);
	var advW = layer.width || 0;

	var lsbVal = bounds ? Math.round(bounds.minX) : 0;
	var rsbVal = bounds ? Math.round(advW - bounds.maxX) : 0;

	var name = slot.name;
	var unicode = '';
	if (TRV.font && TRV.font.encoding) {
		var code = TRV.font.encoding[name];
		if (code) unicode = 'U+' + code.toString(16).toUpperCase().padStart(4, '0');
	}

	var rect = TRV._getWidgetRect(advW, 12);

	widget.style.left = rect.left + 'px';
	widget.style.top = rect.top + 'px';
	widget.style.width = rect.width + 'px';

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

	var widget = document.createElement('div');
	widget.className = 'glyph-widget glyph-widget--readonly visible';
	widget.style.left = rect.left + 'px';
	widget.style.top = rect.top + 'px';
	widget.style.width = rect.width + 'px';
	widget.innerHTML =
		'<div class="gw-row">' +
			'<div class="gw-field"><span class="tri">label</span><span class="gw-value">' + name + '</span></div>' +
			'<div class="gw-field"><span class="tri">select_glyph</span><span class="gw-value">' + unicode + '</span></div>' +
		'</div>' +
		'<div class="gw-row">' +
			'<div class="gw-field"><span class="tri">metrics_lsb</span><span class="gw-value">' + lsbVal + '</span></div>' +
			'<div class="gw-field"><span class="tri">metrics_advance</span><span class="gw-value">' + advW + '</span></div>' +
			'<div class="gw-field"><span class="tri">metrics_rsb</span><span class="gw-value">' + rsbVal + '</span></div>' +
		'</div>';
	container.appendChild(widget);
};

TRV.updateGlyphWidget = function() {
	var state = TRV.state;
	if (!state.glyphData || !state.glyphViewMode) {
		TRV.hideGlyphWidget();
		return;
	}

	var ws = TRV.workspace;
	if (ws.activeIdx < 0 || ws.activeIdx >= ws.glyphs.length) {
		TRV.hideGlyphWidget();
		return;
	}

	if (TRV.dom.glyphWidgets) {
		TRV.dom.glyphWidgets.innerHTML = '';
	}

	var layout = TRV.getGlyphStripLayout();

	var activeSlot = null;
	for (var i = 0; i < layout.slots.length; i++) {
		if (layout.slots[i].active) { activeSlot = layout.slots[i]; break; }
	}

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

	TRV.showGlyphWidget(activeSlot, layer);
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

		var cacheEntry = TRV.glyphCache.get(glyphName);
		if (!cacheEntry) return;

		var state = TRV.state;
		var layer = TRV.getLayerByName(cacheEntry.glyphData, state.activeLayer);
		if (!layer) layer = cacheEntry.glyphData.layers[0];
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
