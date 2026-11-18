# FontLab native panels from Python — what we learned

Distilled from building the first dock-toolbar script (since replaced by `typerig.proxy.fl.gui.native_panel`; commits `13d9ea0`, `3baba32`, `3da456b`,
`1f82921`, Nov 2026). Everything here was verified live in **FontLab 9** (through the FL MCP
`run_python`) and **FontLab 8.4.2** (through log files, see §9). Both ship Python 3.11 and
Qt 5.15 (FL9: 5.15.19, FL8: 5.15.15) with PythonQt 3.2, so the Python side is identical; only
FontLab's own dock engine differs (§7).

Anything marked **UNVERIFIED** was not tested. Windows was never tested.

---

## 1. Why a plain Qt toolbar cannot dock on macOS

* On Windows `app.main` (the `MainWindow`) is the visible frame, so `QToolBar`s added with
  `addToolBar()` dock in it.
* On macOS `MainWindow` is a **hidden** `QMainWindow` (no central widget, `isVisible() == False`).
  The visible UI is a set of separate top-level windows: `YFrameWindow` (glyph / font windows),
  `YDock` (panel docks), `ToolbarPanel` (the left tool strip, a `YToolbar`).
* Calling `app.main.show()` just pops up a second floating "FontLab 9" window with a title bar and an
  empty central area. That is not docking.
* `YToolbar` is FontLab's own toolbar class (it docks on any edge and re-orients) but it is
  **not creatable from Python**, and the only instance is FontLab's own `ToolbarPanel`.

## 2. FontLab's docking object model

```
YFrameWindow (glyph/font window)  ── a docked YDock becomes its child
YDock                 top-level window (floating / desktop-docked) or child of a YFrameWindow
 └─ YPanel            one per stacked panel; has a 19 px header (YTabWidget starts at y=19)
     └─ YTabWidget    FontLab's own tab widget (NOT a QTabWidget subclass, but has addTab)
         └─ QStackedWidget
             └─ YPanelWidget   <- the page: this is what Python creates
```

Other classes seen in crash reports / symbols: `YTab` (one per page, created by FontLab),
`YDockHost` / `YDesktopDockHost` (edge hosts; `getDock(edge, create)`, `updateDockDropTargets`,
`canDrop`, `dockPanel`), `YPanelManager` (singleton), `YDropTargetPM`.

Edge bit values used by the host: **Top = 1, Left = 2, Right = 4, Bottom = 8** (`Qt::Edge`).
`canDrop` compares the dragged item's size with `getTop/Left/Right/BottomDockMaxWidth/Height`.

## 3. The working recipe (Python)

```python
panel = fontlab.CreatePanel(PANEL_ID, 'Title')       # YPanelWidget. Args: (int id, str title='', ResizePolicy, QWidget parent)
panel.setWindowTitle('Title')                        # BEFORE registering. CreatePanel's title arg does not set it.
panel.setObjectName('MY_PANEL')
# ... build the content: a layout on `panel` (see §6)

register = getattr(ctypes.CDLL(None), '_ZN10MainWindow19registerCustomPanelEP12YPanelWidget')
register.argtypes = [ctypes.c_void_p, ctypes.c_void_p]; register.restype = None
ptr = lambda o: int(re.search(r'\(0x([0-9a-f]+)', repr(o)).group(1), 16)   # PythonQt repr: Class(0x7f..., name=..)
register(ptr(fontlab.MainWindow()), ptr(panel))      # adds Window > Panels > Custom Panels entry + registers with the manager

action = find_action()                               # see below
action.setObjectName('QAction')                      # FontLab's slot ignores any other sender name
action.trigger()                                     # FontLab opens the panel in a NEW FLOATING YDock, at MINIMUM size
QApplication.processEvents()
# then size the YPanel (not the YDock): yp_panel.resize(w, h); yp_dock.setGeometry(x, y, w, h)
```

Finding the action (it is created by `registerCustomPanel`, text is empty):

| FontLab | how to match |
|---|---|
| 9 | `action.property('fontlab.commandId') == 'Window.Panels.Custom.' + title` |
| 8 and 9 | `action.data() == PANEL_ID` (both versions `setData(panel id)`). **Use this as the common key.** |

`mainWindow.findChildren(QAction)` finds it immediately; no menu popup is needed (a menu-refresh
fallback is in `native_panel.TRNativePanel.find_action`, it was never required).

Triggering the action a second time while the panel is open is a harmless no-op.

Panel ids: any int, must be unique among FontLab panels. `7210` was used. FontLab's own ids are
unknown (**UNVERIFIED** whether ids are persisted in saved workspaces).

## 4. Why putting a plain widget into an existing dock crashes FontLab

The first attempt did `YTabWidget.addTab(QWidget, 'Title')` on an existing dock (Output). It
renders and even drags, but FontLab crashes on: dropping a dock, right-clicking a panel header, and
opening/validating the Window menu. The crash reports (`SIGSEGV`, address `0x20`):

* `YPanelManager::findTab(YPanelWidget const*)` → loop over every `YPanel::tabs()` →
  `ldr x8, [tab, #0x20]` with `tab == NULL`.
* `YPanel::tabs()` builds its list with `YTabWidget::tab(int)`, which returns the **`YTab`**
  FontLab creates for each page. A page added with plain `QTabWidget::addTab` has no `YTab`, so the
  list contains a null.
* `YPanel::updateMinimumSize` (called on drop through `YDock::doInsertPanel → YPanel::setDock`)
  derefs the same null.

Putting a `YPanelWidget` from `CreatePanel` into the tab widget by hand does **not** help: it still
crashes in `findTab`. The panel must be **registered** (`registerCustomPanel`) and opened by
FontLab's own action so that FontLab builds the `YPanel` + `YTab` itself.

Never mix: do not add pages to FontLab's `YTabWidget`s yourself.

## 5. What Python can and cannot reach

* `fontlab.PanelManager()` returns a **PythonQt wrapper** exposing only QObject signals/slots
  (`panelClosed`, `toolbarOpened`, `toolbarClosed`, `showContextMenu`...). The binary contains a
  richer pygate class with `registerPanel`, `openPanel`, `openTabbedPanel`, `openFloatingPanel`,
  `registeredPanels`, `panels`, `mainWindow`, `instance()`, **but it is not reachable** from
  Python (`hasattr` is False everywhere we looked, including `sys.modules` scans and `gc`).
* `MainWindow.showPanel(int id, bool)` exists but only opens FontLab-registered ids; a
  `CreatePanel` widget is not registered, so it does nothing.
* `YPanelWidget::ResizePolicy` values are unknown (1, 2, 3 made no visible difference on floating
  docks; policy while docked was **UNVERIFIED**). Default was used.
* `QAction`s and `QMenu`s of the main window are fully reachable (`findChildren`, `menuBar()`).
* `MainWindow.metaObject()` slot lists work for `MainWindow`; for most FL classes `metaObject()`
  introspection returns the string `'QMetaObject'` (PythonQt oddity) — read symbols from the
  binary instead (§9).

## 6. Sizing rules (learned the hard way)

1. A custom panel opens **at minimum size** (about 50x69). Size it yourself right after `trigger()`.
2. Resize the **`YPanel`** (the `YDock` ancestor's child), and also set the `YDock` geometry.
   `YDock.setGeometry` alone leaves the `YPanel` at its old size in a floating dock.
3. FontLab does **not** read your `YPanelWidget.minimumSize()` to size the panel; `YPanel`'s minimum
   is a fixed ~50x69 (69x50 with the header on the side). Do not set a minimum size on the panel
   widget: it just overflows the stack widget.
4. Make the content widget's size hint irrelevant: `setSizePolicy(Ignored, Ignored)` on the scroll
   area. Otherwise a freshly created scroll area (huge hint) made the dock balloon to 1700x2235.
5. Dock behaviour differs between versions (§7).

## 7. FontLab 8 vs FontLab 9

| | FL 9 | FL 8.4.2 |
|---|---|---|
| `fontlab.commandId` property on the registered action | yes | **no** → match by `action.data()` |
| docked panel fills the dock height | **yes** | **no**: keeps its old height (e.g. 83 px) inside a full-height `YDock` (e.g. 135x1081) |
| MCP (`run_python` from outside) | yes | **no** (debug through log files, §9) |
| `registerCustomPanel` symbol | exported | exported (same mangled name) |

Consequence: do not decide orientation or layout from the *panel's* size alone. Use
`max(panel size, dock size)`, and if the panel is the **only** `YPanel` in a tall dock and is much
shorter than the dock, grow the `YPanel` to the dock height once per dock-shape change
(`TRToolbarScroll.fill_dock`).

## 8. PythonQt and layout lessons (all found by measuring)

* **No `super()` for virtuals.** In a Python subclass of a Qt widget you cannot call
  `super().resizeEvent(e)` / `super().event(e)` (AttributeError). Do not override virtuals on
  widgets that need their base behaviour. Poll with a `QTimer` instead.
* **Never destroy a PythonQt widget whose child `QTimer` is connected to a bound method of that same
  widget** (`deleteLater()` / parent deletion): the slot's bound method holds the Python wrapper,
  PythonQt deletes the widget a second time → FontLab crashes in `QWidget::~QWidget`
  (report: `QScrollArea` → `QTimer` → `PythonQtSignalReceiver` → `PythonQtInstanceWrapper_deleteObject`).
  Stop the timer and **park the widget hidden** in a module-level graveyard list instead.
* **Scrollbar feedback loop = flicker.** If you lay out from `viewport().size`, a scrollbar
  appearing shrinks the viewport, which re-triggers layout, which hides the scrollbar... Measured on a
  resize sweep: 122 viewport changes and 18 scrollbar toggles for 81 resize steps. Fix: size from
  `maximumViewportSize()` (ignores scrollbars) and reserve scrollbar room explicitly.
* **Hysteresis** on orientation (wide→tall when `w < 0.8 h`, tall→wide when `w > 1.25 h`) so a
  near-square panel does not flip.
* **Debounce**: apply a new size only after it stayed the same for 2 ticks (40 ms tick). Dragging and
  docking pass through many transient sizes.
* **Flow individual buttons, not whole `QToolBar`s.** A 30-button toolbar cannot wrap, so vertical
  mode failed whenever the dock was shorter than the toolbar. The `QToolBar`s are kept hidden only as
  owners of the `QAction`s; each action is shown as a `QToolButton` with `setDefaultAction`,
  `setAutoRaise(True)`, `setToolButtonStyle(TextOnly)`, `setFont(action.font)`,
  `setFocusPolicy(NoFocus)`. This reproduces the look (icon font, checked highlight, tooltips).
* `TRFlowLayout.widthForHeight` returns the wrong value in vertical mode: compute extents yourself.
* Python state that must survive between runs lives on the long-lived `Toolbar` module
  (`Toolbar._dock_state`) because FontLab resets the script namespace between runs. **FL8 may reset
  modules too** (**UNVERIFIED**; the diagnostic once reported no state before the toolbar script
  had been run).
* FontLab can **not unregister** a panel. Re-running a script must reuse the registered panel and
  swap its content; otherwise the same id is registered twice and the menu gets duplicate entries.
* `QToolBar.setOrientation` works for standalone bars but they cannot wrap; not needed once buttons
  flow individually.

## 9. Debugging toolbox

**Crash reports**: `~/Library/Logs/DiagnosticReports/FontLab 9-*.ips` (FL8 presumably `FontLab 8-*.ips`, not seen yet).
First line is a JSON header, the rest is JSON. The faulting thread's stack, quickly:

```python
import json, sys
raw = open(sys.argv[1]).read(); d = json.loads(raw.partition('\n')[2])
imgs = d['usedImages']; th = d['threads'][d['faultingThread']]
print(d['exception'])
for i, fr in enumerate(th['frames'][:28]):
    print(i, (imgs[fr['imageIndex']].get('name') or '?')[:28], fr.get('symbol', '?'), fr.get('symbolLocation', ''))
```

**Symbols and disassembly** (the binary is not stripped; arm64):

```bash
cd "/Applications/FontLab 9.app/Contents/MacOS"
nm -C "FontLab 9" | grep "YPanelManager::"                       # list methods + addresses
strings -a "FontLab 9" | grep -n "registerPanel"                 # pygate docstrings / property names
lldb -b -o 'disassemble -n "YPanelManager::findTab(YPanelWidget const*)"' "FontLab 9"
```

Reading `bl`/`blr` targets, `cmp`/`cbz` and string loads from `lldb` disassembly was enough to find
every behaviour above (e.g. the `sender().objectName() == "QAction"` check in
`MainWindow::doCustomPanelActionTriggered`).

**Live inspection (FL9 only)**: the MCP tool `mcp__fontlab__run_python` runs Python in FontLab's
main interpreter. Useful: `QApplication.allWidgets()`, `topLevelWidgets()`, walking `.parent()`
chains, `widget.grab().save(png)`, calling `action.trigger()`, `QTimer` samplers that log state.

**Synthetic mouse drag works**: building a `QMouseEvent(type, localPos, windowPos, screenPos, button,
buttons, modifiers)` and `QApplication.sendEvent(QApplication.widgetAt(globalPos), ev)` drives FontLab's
drag/dock machinery (it really docked a panel). Useful for tests, but it changes the user's layout.

**No-MCP debugging (FL8, Windows)**: write a *temporary* script that (run 1) prints a snapshot and starts
a `QTimer` recorder, and (run 2) dumps the recording to a log file in a known absolute path that the
agent can read. Ask the user: "run the toolbar script, run the diagnostic, dock and resize, run
the diagnostic again". The recorder should log: platform / Python / Qt versions, the widget chain
with geometry, min/max sizes and visibility, the scroll/page/viewport sizes, orientation state and
any exceptions from calling the layout code by hand. **Delete the diagnostic afterwards.** This
found the FL8 dock-height behaviour in two rounds.

## 10. Safety rules for working inside a live FontLab

* **Never call native C++ through `ctypes` with a guessed `this`**. A probe of
  `YDockHost::getTopDockMaxWidth` with the pointer returned by `findDesktopDockHost` crashed
  FontLab (`SIGBUS`). The only native call proven safe is
  `MainWindow::registerCustomPanel(MainWindow*, YPanelWidget*)`.
* A crash loses the user's unsaved work. Before any experiment that may crash, prefer read-only
  probes and static analysis (`nm`, `lldb disassemble`), and say what you are about to do.
* Never grab the **desktop** for screenshots (`QPixmap.grabWindow(desktop.winId(), ...)`): it captures
  other apps (it once captured a video call). Use `widget.grab()`.
* Programmatic window/menu probes leave residue in the user's session (extra registered panels, moved
  docks). A registered panel cannot be removed: use distinct throw-away ids/titles and tell the user to
  restart FontLab afterwards.

## 11. Open questions

1. **Windows**: ~~open~~ **ANSWERED, see section 13.** A native custom panel is impossible: FontLab.exe
   exports no symbols at all. The same content goes into a `QDockWidget` instead.
2. Persistence: does FontLab restore a custom panel's dock position after a restart? (**UNVERIFIED**;
   the panel has to be recreated by running the script after each start.)
3. The `ResizePolicy` enum meaning and whether it makes a panel stretch in FL8.
4. Why the top edge once refused a drop (a drop target was shown but nothing docked); it worked
   later after the panel height was corrected, cause not proven.
5. Startup: how to run the script automatically (FL startup script / Scripts autorun).

---

## 12. The public API (`typerig.proxy.fl.gui.native_panel`, v1.0)

```python
from typerig.proxy.fl.gui.native_panel import TRNativePanel

def build(panel):                       # content_builder
	page = QtGui.QWidget()              # owns the widgets
	buttons = [...]                     # widgets to flow, in order, one after the other (no separators)
	return page, buttons, refs          # refs: QActions, dialogs, button groups... kept alive

panel = TRNativePanel(7210, 'TypeRig Toolbar', build)    # object_name / legacy_names optional
panel.open()      # create / reuse / adopt, (re)build the content, let FontLab open it. True when showing
panel.rebuild()   # swap the content only (new scroll area, old one parked)
panel.scroll, panel.panel, panel.state, panel.mode      # 'native' (macOS) | 'dock' (Windows)
```

* `TRToolbarScroll` is the flow engine (hysteresis 0.8 / 1.25, 2 x 40 ms debounce, `maximumViewportSize()`,
  dock-shape orientation, `fill_dock` for FontLab 8). `fit_count` counts layout passes (diagnostics).
* State lives in the module (`_STATE`, `_GRAVEYARD`). When it is gone (module purged) `open()` **adopts** the
  already registered panel: it looks for a `YPanelWidget` with the object name (or a legacy name), parks every
  stale scroll area in it, and reuses it. Verified live: reload of the module, one panel, one menu entry.
* Windows: `resolve_register()` only returns a callable when the MSVC symbol resolves in the main module;
  it never does (section 13), so `open()` builds a `QDockWidget` on `app.main` instead.

### New pitfalls found while building the unified toolbar

* A freshly created `QScrollArea` reports a default viewport (about 640x480) until FontLab lays it out: the first
  `fit()` of a reused panel wraps at that stale size. The poll timer re-fits as soon as the real size is known
  (about 2 ticks); do not treat the first layout as final.
* `maximumViewportSize()`, `sizeHint` of a `QToolButton` and similar are *methods or properties inconsistently* in
  PythonQt: `scroll.maximumViewportSize()` needs the call, `button.sizeHint` and `edit.text` do not.
* `run_python` over the MCP gives every call a fresh namespace: keep a test harness in a file and `exec()` it.
* Test through `fl6.CurrentGlyph` monkeypatching only if you restore it afterwards (it is a global of the
  running FontLab); the same for `pWorkspace.getCanvas` (returns `None` without a glyph window).
* The layer-selection dialog (`TRLayerSelectNEW`) calls `parent.layers_refresh()` on every edit: whatever is
  passed as its parent needs that method. `getTable()` returns a *list of layer names*, a valid `pLayers`.

---

## 13. Windows: measured, and what we do instead (FontLab 9 / Windows 10, Nov 2026)

Measured in the running application through the FontLab MCP bridge, not guessed:

1. `GetProcAddress(GetModuleHandle(NULL), "?registerCustomPanel@MainWindow@@QEAAXPEAVYPanelWidget@@@Z")`
   returns `NULL`.
2. Parsing the PE export directory of the main module: **FontLab.exe exports 0 symbols.** No mangling
   variant can help - there is no export table to look in.
3. All 152 loaded modules were scanned for an export containing `CustomPanel` or `MainWindow@@`: the only
   hits are in `Qt5Widgets.dll` (`QMainWindow::addDockWidget` and friends). FontLab's own classes live in
   the executable and are not exported.
4. The Python side offers no replacement: `fl6.CreatePanel(id, title)` builds a `YPanelWidget` but nothing
   registers it; `MainWindow.showPanel(id, True)` on an unregistered id does nothing; `menuCustomPanels`
   stays empty; `YPanelManager` has no registration slot (PythonQt lists every slot, and there is none).
   `YPanel` (the dock host) is not constructible from Python.

**Conclusion**: a native FontLab panel can not be created on Windows. Do not spend more time on it; re-run
the three probes above when a new FontLab build ships.

**What the TypeRig Toolbar does instead**: on Windows the script does not build a panel at all. It renders
the *same button table* (`toolbar_buttons.toolbar_sections()`) as plain `QToolBars` with `QActions` -
`typerig.proxy.fl.gui.toolbar_bars.TRToolbarBars`, the way TypeRig toolbars worked before 3.0, which
Windows handles natively and which users liked:

* One bar per section plus the scope masthead, created in table order, so the icon order matches macOS.
* Qt does the hard parts for free: dock in all four toolbar areas, turn vertical when docked left / right,
  float, and move what does not fit into the `>>` overflow menu.
* `pack_rows()` inserts toolbar breaks so the top-area bars fill as many rows as they need instead of
  being squeezed into one (Qt never wraps a toolbar area by itself). Bars the user moved to another edge
  are left where they are.
* Re-running the script keeps the bars and swaps only their actions, so the arrangement survives and the
  callbacks are always the freshly imported code. Old actions are parked, never deleted.
* The platform gate is in the script (`Scripts/TypeRig GUI/typerig-toolbar.py`), one `system() == 'Windows'`.

**`TRNativePanel` still has a Windows fallback** - mode `'dock'`, the content in a real `QDockWidget` on
`fl6.MainWindow()` (which *is* a `QMainWindow`; its central widget is FontLab's `YFrameWindow`, so the dock
surrounds FontLab's own dock system). The toolbar no longer uses it, but it is there for any other panel
that wants one, and it gives everything the native panel gives except tabbing with FontLab's own Y panels:

* `addDockWidget(Qt.TopDockWidgetArea, dock)` on creation; the user can drag it to all four edges or float it.
* Resizing works through the normal dock separator, and the content reflows (the poll timer sees the new
  viewport). The scroll area keeps `QSizePolicy.Ignored` so the content never dictates the dock size, plus a
  48x40 minimum so Qt can not collapse the dock to nothing.
* Orientation no longer has to be guessed: `MainWindow.dockWidgetArea(dock)` gives the area, and
  `TRNativePanel.orientation_hint()` turns left/right into columns and top/bottom into rows. Floating falls
  back to the shape heuristic with hysteresis.
* `after_fit()` sizes the dock to the content **once per dock area** with `MainWindow.resizeDocks()`
  (height when docked top/bottom, width when left/right), so the panel opens showing every button and a size
  the user drags afterwards is left alone. Floating resets the mark, so re-docking fits again.
* `adopt_dock()` reuses the dock of an earlier run (by object name, and only when it still belongs to this
  main window - an orphan from a previous experiment is left to rot). A dock the user closed with the X is
  shown again by the next run.
* `retire_toolbar()` removes the `QToolBar` that TypeRig <= 3.0 docked on Windows, so an updated script does
  not come up underneath it.

Pitfalls measured here:

* `resizeDocks()` only takes effect after the event loop runs: read the geometry back on a later tick, not
  in the same statement.
* `QDockWidget.setWidget()` keeps the old widget as a child: park it *and* `setParent(None)`, or the stale
  content stays alive behind the new one.
* Deleting a dock widget destroys its children, and an in-flight `QApplication.allWidgets()` iteration then
  raises on the destroyed objects. Park, never delete (same rule as section 8).
* A `QDockWidget` created from Python keeps `MainWindow` as its parent even while floating, so the parent
  check in `adopt_dock()` is safe for floating panels.
