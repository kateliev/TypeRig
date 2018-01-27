# TypeRig
TypeRig (root\Lib\) is a Python library aimed at simplifying (to some extent) the current FontLab VI API while offering some additional functionality that is heavily biased towards a simultaneous multi-layered workflow.

TypeRig GUI (root\GUI\) is a collecton of GUI centered tools representing functionality found in the library. Currently there reside:
- TypeRig Panel - a floating side panel with various tools. New tools will be added as plugin-basis by just dropping the updated or new tabs as .py files in (root\GUI\Panel\Panel)

### Installation
Unpack files anywhere you want. Then:
- TypeRig Module - Run the provided install.py, it will create link/path to Python Site packages. Please note that if you change the location of the installation you should run the script again.

- TypeRig GUI - Please refer to Fontlab VI manual about "Scripting Panel" section "Open the List of scripts" 
(http://help.fontlab.com/fontlab-vi/Scripting-panel/)

### Known Issues/Problems
TypeRig GUI
- NO UNDO! Save your work! Anything you do will be reverted to the last manipulation done by the editor. Currently the Fontlab VI undo/history system is beyond my understanding, will be implemented/fixed in the coming months.
- NO Errors and output! Regretfully there is a bug in the current build of Fontlab (and API) that prevents nested widgets from sending infromation to the standart os.stderr os.stdout.
- NO Integration! The current floating panel is floating above all applications, not just FL. It is part of it but is not integrated within the workspace. It has also fake/mokup FL styling. If you are not very found of the FL interface as well as the Panel looks and feel, you could always revert it by changing the style sheet of the widget in root\GUI\Panel\typerig-panel.py at line #122 'self.setStyleSheet(ss_Toolbox_fl6)' to 'self.setStyleSheet(ss_Toolbox_dflt)'

### Documenation
A fresh copy of the current master API could be obtained here (as a pydoc dump) as well as using python's help(...) function.

### Developer
TypeRig FDK is developed by Vassil Kateliev (2017).

For contact and inquiries: vassil(at)kateliev(dot)com
---
www.typerig.com (TBI/TBA)
