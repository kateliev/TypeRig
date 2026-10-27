# encoding: utf-8
# -------------------------------------------------------------------------
# typerig.proxy.gs3.gui — reusable Glyphs 3/4 panel framework
#
# What lives here (one source of truth across every TR-style Glyphs plugin):
#
#   config.py       UI namespace + GS3/GS4 host detection and presets
#   panel_base.py   TRPanelBase + @register_panel for tool sub-panels
#   widgets.py      IconButton (square, icon-font ligature-rendered)
#   icon_font.py    register_icon_font() + tr_attr() for OpenType rlig icons
#   scope.py        polymorphic pLayers resolver (tuple or [(name, type), …])
#   dialogs.py      inline layer-picker + master-values dialog
#   tint_list.py    TRTintList: List2 colour coded by kind (dots + row tint)
#   thumbnail.py    contours drawn as images + TRThumbGrid picker
#   observer.py     TRObserver: base for the Toolbar observer row
#   layer_toast.py  observer: layer name toast at the pointer on layer change
#   stem_probe.py   observer: live stem width under the pointer
#   node_slider.py  observer: Option-drag a node along its segment
#   node_ghost.py   observer: ghost node on the path, Ctrl+Option+right click adds it
#   assets/         shared icon font (typerig-icons.ttf)
#
# A new TR Glyphs plugin typically only ships:
#   - plugin.py            Glyphs plugin entry stub
#   - main_panel.py        TRMainPanel with its masthead and tabs
#   - configurator.py      tool-list persistence
#   - Panel/*.py           the tool sub-panels (subclassing TRPanelBase)
# ... and imports everything else from typerig.proxy.gs3.gui.
#
# See `Lib/porting_guide.md` in the TypeRig-Glyphs repo for the full guide.
# -------------------------------------------------------------------------
