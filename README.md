![TR Core](https://img.shields.io/badge/TR%20Core%20--%20Python-3%2B-green) ![TR GUI](https://img.shields.io/badge/TR%20GUI%20--%20Python-3.10-orange) ![GitHub last commit](https://img.shields.io/github/last-commit/kateliev/TypeRig)
# TypeRig
**TypeRig** is a Python library that streamlines the FontLab API and provides extra features focused on multiple master and variable fonts. It is undergoing rapid development, so it's recommended to keep it updated regularly.

### Important note
If you are experiencing any trouble running your scripts after February 2022 please refer to our [latest Py2.7 release](https://github.com/kateliev/TypeRig/releases/tag/v1.9.0-Py2.7). It is a snapshot of TR that is both Py2.7 and Py3.10 compatible. 

## Documentation
Please refer to the following [work in progress document](https://kateliev.github.io/TypeRig/Docs/).

## Known issues
Please refer to our [issues tracker](https://github.com/kateliev/TypeRig/issues).

## Releases
Please take a look at our latest [releases](https://github.com/kateliev/TypeRig/releases).

## Installation
### FontLab 7+
#### Manual installation from GitHub 
Download the archived (.zip) package provided from this repository or clone it. Run FontLab 7+ and drag the installation file provided in the root folder caleld `install.vfpy` to the application _(as if it was a font)_. Follow the steps as described by the installer.

If you want to install the **GUI based part of Typerig** _(only after successfully installing the core library)_ please open FonLab, _Scripting panel_. At the bottom of the panel you will see a small black _Plus sign (+)_. Click on it and FontLab will ask you to _Select directory_ where your scripts reside. Point the app towards `./Scripts/Delta Machine` and `./Scripts/GUI`.

#### Automatic installation within the application
Run FontLab 7+, choose _Scripts > Update / Install Scripts_. Click _OK_ in the dialog, wait until the installation completes. When you see the _TypeRig is up-to-date_ dialog, click _OK_ and restart FontLab 7.

The _Scripts_ menu should now show the _Delta Machine_ and _TypeRig GUI_ sub-menus.

## Developer
TypeRig FDK is developed by: **Vassil Kateliev** (2017-2023) and **Adam Twardoch** (2019-2022)

For contact and inquiries: vassil(at)kateliev(dot)com

www.typerig.com
