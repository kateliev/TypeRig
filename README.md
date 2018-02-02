# TypeRig
**TypeRig** (`.\Lib\`) is a Python library aimed at simplifying (to some extent) the current FontLab VI API while offering some additional functionality that is heavily biased towards a simultaneous multi-layered workflow.

**TypeRig GUI** (`.\Scripts\TypeRig GUI`) is a collecton of GUI centered tools representing functionality found in the library. Currently there reside:
- TypeRig Panel (typerig-panel.py) - a floating side panel with various tools. New tools will be added as plugin-basis by just dropping the updated or new tabs as .py files in (`.\Scripts\TypeRig GUI`)

### Installation
Unpack files anywhere you want. Then:
- **TypeRig Module** - Run the provided install in shell using `python install.py`. It will create link/path to Python Site packages. Please note that if you change the location of the installation you should run the script again.

- **TypeRig GUI** - Please refer to Fontlab VI manual about "Scripting Panel" section "Open the List of scripts" 
(http://help.fontlab.com/fontlab-vi/Scripting-panel/)

### Current features
As implemented in the GUI. All of the listed work on on several layers simultaneously unless noted so.
(Note: Module offers more that the included in the GUI)

#### Node Panel
- Add/remove nodes 
- Break and knot contours. Also serif and stem and etc. disconnection.
- Hobby knots (experimental TBI) (Active Layer only)
- Interpolated move aka Interpolated nudge (Active Layer only)
- Slanted Grid move: Move nodes with the italic angle applied in the Y direction (Active Layer only)

#### Guide panel
- Drop guideline: Drop guideline between any two selected nodes (on all layers) or a vertical guideline at a single node (with italic angle if present) 

#### Layer panel
- Copy/Paste/Swap layer outline, metrics, anchors and guides (also usable as FontLab V swap with mask feature)
- Interpolate current layer to any selected layer (more TBI)
- Interpolate any two selected layers into the current active layer (more TBI)

*Metrics panel (TBI)*
*Anchors panel (TBI)*
*Kern pair generator panel (TBI)*

### Known Issues/Problems
TypeRig GUI
- **NO UNDO! Save your work!** Anything you do will be reverted to the last manipulation done by the editor. Currently the Fontlab VI undo/history system is beyond my understanding, will be implemented/fixed in the coming months.
- NO Errors and output! Regretfully there is a bug in the current build of Fontlab (and API) that prevents nested widgets from sending infromation to the standart os.stderr os.stdout.
- NO Integration! The current floating panel is floating above all applications, not just FL. It is part of it but is not integrated within the workspace. It has also fake/mokup FL styling. If you are not very found of the FL interface as well as the Panel looks and feel, you could always revert it by changing the style sheet of the widget in `root\GUI\Panel\typerig-panel.py` at line #122 `self.setStyleSheet(ss_Toolbox_fl6)` to `self.setStyleSheet(ss_Toolbox_dflt)`

### Documenation
A fresh copy of the current master API could be obtained here (as a pydoc dump) as well as using python's help(...) function. (TBI)

### Developer
TypeRig FDK is developed by Vassil Kateliev (2017).

For contact and inquiries: vassil(at)kateliev(dot)com

www.typerig.com (TBI/TBA)
