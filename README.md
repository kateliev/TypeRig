# TypeRig
**TypeRig** (`.\Lib\`) is a Python library aimed at simplifying the current FontLab 6 & 7 API while offering some additional functionality that is heavily biased towards a simultaneous multi-layered workflow.

**TypeRig GUI** (`.\Scripts\TypeRig GUI`) is a collection of GUI centered tools representing functionality found in the library. Currently there reside:
- **TypeRig Panel** (`typerig-panel.py`) - a floating side panel aimed at  glyph and outlines manipulation;
- **Typerig Manager** (`typerig-manager.py`) - a set of tools for editing various font related parameters;
- **Typerig Filter** (`typerig-filter.py`) - assorted outline modifiers.

**Delta Machine** (`.\Scripts\Delta Machine`) - an advanced tool for adaptive outline scaling based on the exceptional work *A Multiple Master based method for scaling glyphs without changing the stroke characteristics* by Tim Ahrens.

### Known issues
Please refer to https://github.com/kateliev/TypeRig/issues

### Installation
Unpack files anywhere you want. Then:
- **TypeRig Module** - Run the provided install in shell using `python install.py`. It will create link/path to Python Site packages. Please note that if you change the location of the installation you should run the script again.

- **TypeRig GUI** - Please refer to Fontlab VI manual about ["Scripting Panel" section "Open the List of scripts"](http://help.fontlab.com/fontlab-vi/Scripting-panel/#open-the-list-of-scripts)

*Note: It is possible that you could have two or more Python installations on one machine. Please note which one is set to work with your current Fontlab instalaltion. If it happens that your main Python installation differes from the one supplied with Fontlab, then you should manually copy the library provided as `/typerig/` folder residing in `./Lib/` to your `/FontLab VER/Resources/python/2.7/site-packages/` folder. To test it out, if the library is poperly installed please open your FL6 scripting panel, navigate to and open the console and type `import typerig`. If no error is returned, then the manual isntallation went just fine.*

### Developer
TypeRig FDK is developed by: **Vassil Kateliev** (2017-2020) and **Adam Twardoch** (2019-2020)

For contact and inquiries: vassil(at)kateliev(dot)com

www.typerig.com
