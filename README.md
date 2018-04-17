# TypeRig
**TypeRig** (`.\Lib\`) is a Python library aimed at simplifying (to some extent) the current FontLab VI API while offering some additional functionality that is heavily biased towards a simultaneous multi-layered workflow.

**TypeRig GUI** (`.\Scripts\TypeRig GUI`) is a collecton of GUI centered tools representing functionality found in the library. Currently there reside:
- **TypeRig Panel** (`typerig-panel.py`) - a floating side panel combining the following tools listed below. 
*New tools will be added on plugin-basis by just dropping the updated or new tabs as .py files in `.\Scripts\TypeRig GUI\Panel` sub-folder.*

#### Current features
Below listed featueres are implemented as TypeRig GUI. They affect **all compatible layers** simultaneously unless noted so.

##### Node Panel
- Add/remove nodes 
- Align Nodes, chanel processing and more... 
- Break, cut and knot contours.
- Close open contours.
- Interpolated move aka Interpolated nudge (Active Layer only).
- Slanted Grid move with the italic angle applied in the Y direction (Active Layer only).

##### Contour Panel
- Contour optimization: Tunni (Auto balance handles), Hobby (Adjust Curvature), Proportional (Handle length)

##### Guide panel
- Drop guideline: Drop guideline between any two selected nodes (on all layers) or a vertical guideline at a single node (with italic angle if present) 

##### Layer panel
- Set layer types'
- Add, remove and duplicate layers.
- Copy/Paste/Swap active layer outline, metrics, anchors and guides to any selected layer (also usable as FontLab V's swap with mask feature).
- Interpolate current layer to any selected layer... (more TBI)
- Interpolate any two selected layers into the current active layer... (more TBI)

*'affects multiple selected layers*

##### Anchors panel
- Visually check if an anchor is present in all selected layers
- Clear all or selected anchors on all of the chosen layers
- Add or move an anchor to given coordinates or using various positioning algorithms (including feature detection)

##### Metrics panel
- Copy metrics from glyph (with adjustments)
- Set metric equations

##### Mixer panel (closed beta')
- Set custom axis and interpolate between any two compatible layers
- Change width and weight while keeping stem/stroke widths (works with italics also)
...more TBI

*'In order to operate, Mixer panel requires percompiled binary library MathRig that is currently available to limited number of users on Windows platform only. MAC version is also on its way...*

###### *Kern pair generator panel (TBI)*
###### *Hints panel (TBI)*

#### Known issues
Please refer to https://github.com/kateliev/TypeRig/issues

### Installation
Unpack files anywhere you want. Then:
- **TypeRig Module** - Run the provided install in shell using `python install.py`. It will create link/path to Python Site packages. Please note that if you change the location of the installation you should run the script again.

- **TypeRig GUI** - Please refer to Fontlab VI manual about ["Scripting Panel" section "Open the List of scripts"](http://help.fontlab.com/fontlab-vi/Scripting-panel/#open-the-list-of-scripts)

*Note: It is possible that you could have two or more Python installations on one machine. Please note which one is set to work with your current Fontlab IV instalaltion. If it happens that your main Python installation differes from the one supplied with Fontlab, then you should manually copy the library provided as `/typerig/` folder residing in `./Lib/` to your `/FontLab IV/Resources/python/2.7/site-packages/` folder. To test it out, if the library is poperly installed please open your FL6 scripting panel, navigate to and open the console and type `import typerig`. If no error is returned, then the manual isntallation went just fine.*

### Documenation
A non-fresh copy of the current master API could be obtained here (as a pydoc dump) as well as using python's help(...) function. (TBI)

### Developer
TypeRig FDK is developed by Vassil Kateliev (2017).

For contact and inquiries: vassil(at)kateliev(dot)com

www.typerig.com (TBI/TBA)
