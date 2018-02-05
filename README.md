# TypeRig
**TypeRig** (`.\Lib\`) is a Python library aimed at simplifying (to some extent) the current FontLab VI API while offering some additional functionality that is heavily biased towards a simultaneous multi-layered workflow.

**TypeRig GUI** (`.\Scripts\TypeRig GUI`) is a collecton of GUI centered tools representing functionality found in the library. Currently there reside:
- **TypeRig Panel** (`typerig-panel.py`) - a floating side panel combining the following tools listed below. 
*New tools will be added on plugin-basis by just dropping the updated or new tabs as .py files in `.\Scripts\TypeRig GUI\Panel` sub-folder.*

#### Current features
Below listed featueres are implemented as TypeRig GUI. They affect **all compatible layers** simultaneously unless noted so.

##### Node Panel
- Add/remove nodes 
- Break, cut and knot contours.
- Interpolated move aka Interpolated nudge (Active Layer only)
- Slanted Grid move with the italic angle applied in the Y direction (Active Layer only)

##### Contour Panel
- Contour optimization: Tunni (Auto balance handles), Hobby (Adjust Curvature), Proportional (Handle length)

##### Guide panel
- Drop guideline: Drop guideline between any two selected nodes (on all layers) or a vertical guideline at a single node (with italic angle if present) 

##### Layer panel
- Copy/Paste/Swap active layer outline, metrics, anchors and guides to any selected layer (also usable as FontLab V's swap with mask feature)
- Interpolate current layer to any selected layer... (more TBI)
- Interpolate any two selected layers into the current active layer... (more TBI)

###### *Metrics panel (TBI)*
###### *Anchors panel (TBI)*
###### *Kern pair generator panel (TBI)*

### Installation
Unpack files anywhere you want. Then:
- **TypeRig Module** - Run the provided install in shell using `python install.py`. It will create link/path to Python Site packages. Please note that if you change the location of the installation you should run the script again.

- **TypeRig GUI** - Please refer to Fontlab VI manual about ["Scripting Panel" section "Open the List of scripts"](http://help.fontlab.com/fontlab-vi/Scripting-panel/#open-the-list-of-scripts)

### Known Issues/Problems
TypeRig GUI
- **NO UNDO! Save your work!** Anything you do will be reverted to the last manipulation done by the editor. Currently the Fontlab VI undo/history system is beyond my understanding, will be implemented/fixed in the coming months.
- NO Errors and output! Regretfully there is a bug in the current build of Fontlab (and API) that prevents nested widgets from sending infromation to the standart os.stderr os.stdout.
- NO Integration! The current floating panel is floating above all applications, not just FL. It is part of it but is not integrated within the workspace. *This would happen when the FL6 team announces official plugin API.*

### Documenation
A fresh copy of the current master API could be obtained here (as a pydoc dump) as well as using python's help(...) function. (TBI)

### Developer
TypeRig FDK is developed by Vassil Kateliev (2017).

For contact and inquiries: vassil(at)kateliev(dot)com

www.typerig.com (TBI/TBA)
