#FLM: TAB Guidelines 1.1
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TAB Guidelines', '0.22'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
  def __init__(self):
    super(tool_tab, self).__init__()

    # - Init
    layout = QtGui.QFormLayout()
    
    # -- Guide Name
    self.edt_guideName = QtGui.QLineEdit()
    self.edt_guideName.setText('DropGuideline')

    # -- Guide Color Selector
    self.cmb_colorSelector = QtGui.QComboBox()
    colorNames = QtGui.QColor.colorNames()
    
    for i in range(len(colorNames)):
      self.cmb_colorSelector.addItem(colorNames[i])
      self.cmb_colorSelector.setItemData(i, QtGui.QColor(colorNames[i]), QtCore.Qt.DecorationRole)

    self.cmb_colorSelector.setCurrentIndex(colorNames.index('red'))

    # -- Guide button
    self.btn_dropGuide = QtGui.QPushButton('&Drop Guideline')
    self.btn_dropGuide.setToolTip('Drop guideline between any two selected nodes.\nIf single node is selected a vertical guide is\ndropped (using the italic angle if present).')
    self.btn_dropGuide.clicked.connect(self.dropGuideline)
    
    # - Build
    layout.addRow('N:', self.edt_guideName)
    layout.addRow('C:',self.cmb_colorSelector)
    layout.addWidget(self.btn_dropGuide)

    self.setLayout(layout)

  # - Procedures
  def dropGuideline(self):
      glyph = eGlyph()
      glyph.dropGuide(layers=pLayers, name=self.edt_guideName.text, color=self.cmb_colorSelector.currentText)
      glyph.update()
      
      #fl6.Update(fl6.CurrentGlyph())

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 200, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()