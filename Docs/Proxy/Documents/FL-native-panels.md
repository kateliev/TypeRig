# FontLab native panels from Python — what we learned

Distilled from building `typerig-toolbar-dock.py` (commits `13d9ea0`, `3baba32`, `3da456b`,
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
fallback is in `typerig-toolbar-dock.py`, it was never required).

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

1. **Windows**: not tested. `registerCustomPanel` is a C++ symbol; on macOS it resolves with
   `ctypes.CDLL(None)` by its Itanium-mangled name. On Windows the name is MSVC-mangled and the
   symbol may not be exported at all (exports are explicit on PE). Needs a probe on a Windows FontLab
   (see handout T1, stage 1). On Windows a regular `QToolBar` in `app.main` already docks.
2. Persistence: does FontLab restore a custom panel's dock position after a restart? (**UNVERIFIED**;
   the panel has to be recreated by running the script after each start.)
3. The `ResizePolicy` enum meaning and whether it makes a panel stretch in FL8.
4. Why the top edge once refused a drop (a drop target was shown but nothing docked); it worked
   later after the panel height was corrected, cause not proven.
5. Startup: how to run the script automatically (FL startup script / Scripts autorun).
