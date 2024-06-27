## Documentation
### TypeRig API
_Planned_

### TypeRig GUI
- [Basics](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Panel-Basics)

#### Panel
- [Anchors](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Anchor-Panel)
- [Contour](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Contour-Panel)
- [Curve](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Curve-Panel)
- [Guidelines](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Guide-Panel)
- [Layers](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Layer-Panel)
- [Metrics](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Metrics-Panel)
- [Nodes](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Node-Panel)
- [Outline](http://kateliev.github.io/TypeRig/Docs/GUI/TR-Outline-Panel)
- [Statistics](https://kateliev.github.io/TypeRig/Docs/GUI/TR-Stats-Panel)

#### Kern
_Planned_

#### Manager
_Planned_

#### Metrics
_Planned_

#### Filter
_Planned_

### DeltaMachine
- [Delta Machine Quick Start](https://kateliev.github.io/TypeRig/Docs/DeltaMachine/DeltaMachine)

## Installation
### FontLab 7 - Manual installation from GitHub
Download the archived (.zip) package provided from this repository or clone it. Run FontLab 7 and drag the installation file provided in the root folder called `install.vfpy` to the application _(as if it was a font)_. The _Output window_ should report if the installation was successful. The **TypeRig library** should now be installed.

If you want to install the **GUI based part of Typerig** _(only after successfully installing the core library)_ please open FonLab, _Scripting panel_. At the bottom of the panel you will see a small black _Plus sign (+)_. Click on it and FontLab will ask you to _Select directory_ where your scripts reside. Point the app towards `./Scripts/Delta Machine` and `./Scripts/GUI`.

### FontLab 7 - Automatic installation within the application
Run FontLab 7, choose _Scripts > Update / Install Scripts_. Click _OK_ in the dialog, wait until the installation completes. When you see the _TypeRig is up-to-date_ dialog, click _OK_ and restart FontLab 7.

The _Scripts_ menu should now show the _Delta Machine_ and _TypeRig GUI_ submenus.

### FontLab VI
Unpack files anywhere you want. Then:
- **TypeRig Module** - Run the provided install in shell using `python install.py`. It will create link/path to Python Site packages. Please note that if you change the location of the installation you should run the script again.

- **TypeRig GUI** - Please refer to Fontlab VI manual about ["Scripting Panel" section "Open the List of scripts"](http://help.fontlab.com/fontlab-vi/Scripting-panel/#open-the-list-of-scripts)

*Note: It is possible that you could have two or more Python installations on one machine. Please note which one is set to work with your current Fontlab instalaltion. If it happens that your main Python installation differes from the one supplied with Fontlab, then you should manually copy the library provided as `/typerig/` folder residing in `./Lib/` to your `/FontLab VER/Resources/python/2.7/site-packages/` folder. To test it out, if the library is poperly installed please open your FL6 scripting panel, navigate to and open the console and type `import typerig`. If no error is returned, then the manual isntallation went just fine.*
