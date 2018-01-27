#FLM: TAB Node Tools 1.0
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TAB Nodes', '0.10'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph

#from typerig.utils import outputHere # Remove later!

# - Sub widgets ------------------------
class basicOps(QtGui.QGridLayout):
  # - Basic Node operations
  def __init__(self):
    super(basicOps, self).__init__()
    
    # - Basic operations
    self.btn_insert = QtGui.QPushButton('&Insert')
    self.btn_remove = QtGui.QPushButton('&Remove')
    
    self.btn_insert.setMinimumWidth(80)
    self.btn_remove.setMinimumWidth(80)

    self.btn_insert.setToolTip('Insert Node after Selection\nat given time T')
    self.btn_remove.setToolTip('Remove Selected Nodes!\nFor proper curve node deletion\nalso select the associated handles!')
    
    self.btn_insert.clicked.connect(self.insertNode)
    self.btn_remove.clicked.connect(self.removeNode)

    # - Inserion time
    self.edt_time = QtGui.QLineEdit('0.5')
    self.edt_time.setMinimumWidth(30)
    self.edt_time.setToolTip('Insertion Time')

    # -- Build: Basic Ops
    self.addWidget(self.btn_insert, 1, 0)
    self.addWidget(QtGui.QLabel('T:'), 1, 1)
    self.addWidget(self.edt_time, 1, 2)
    self.addWidget(self.btn_remove, 1, 3)

  def insertNode(self):
    '''
    import sys        
    sys.stdout = open(r'd:\\stdout.log', 'w')
    sys.stderr = open(r'd:\\stderr.log', 'w')
    '''

    glyph = eGlyph()
    selection = glyph.selectedAtContours(True)
    wLayers = glyph._prepareLayers(pLayers)

    for layer in wLayers:
      nodeMap = glyph._mapOn(layer)
      
      for cID, nID in reversed(selection):
        glyph.insertNodeAt(cID, nodeMap[cID][nID] + float(self.edt_time.text), layer)

    glyph.update()

  def removeNode(self):
    glyph = eGlyph()
    selection = glyph.selectedAtContours()
    wLayers = glyph._prepareLayers(pLayers)

    for layer in wLayers:
      for cID, nID in reversed(selection):
        glyph.removeNodeAt(cID, nID, layer)
        #glyph.contours()[cID].clearNodes()

    glyph.update()


class breakContour(QtGui.QGridLayout):
  # - Split/Break contour 
  def __init__(self):
    super(breakContour, self).__init__()
       
    # -- Split button
    self.btn_splitContour = QtGui.QPushButton('&Break')
    self.btn_splitContourClose = QtGui.QPushButton('Break && &Close')
    
    self.btn_splitContour.clicked.connect(self.splitContour)
    self.btn_splitContourClose.clicked.connect(self.splitContourClose)
    
    self.btn_splitContour.setMinimumWidth(80)
    self.btn_splitContourClose.setMinimumWidth(80)

    self.btn_splitContour.setToolTip('Break contour at selected Node(s).')
    self.btn_splitContourClose.setToolTip('Break contour and close open contours!\nUseful for cutting stems and etc.')

    # -- Extrapolate value
    self.edt_expand = QtGui.QLineEdit('0.0')
    self.edt_expand.setMinimumWidth(30)

    self.edt_expand.setToolTip('Extrapolate endings.')
                
    # -- Build: Split/Break contour
    self.addWidget(self.btn_splitContour, 1, 0)
    self.addWidget(QtGui.QLabel('E:'), 1, 1)
    self.addWidget(self.edt_expand, 1, 2)
    self.addWidget(self.btn_splitContourClose, 1, 3)
        
  def splitContour(self):
    glyph = eGlyph()
    glyph.splitContour(layers=pLayers, expand=float(self.edt_expand.text), close=False)
    glyph.update()

  def splitContourClose(self):
    glyph = eGlyph()
    glyph.splitContour(layers=pLayers, expand=float(self.edt_expand.text), close=True)
    glyph.update()        

class convertHobby(QtGui.QHBoxLayout):
  # - Split/Break contour 
  def __init__(self):
    super(convertHobby, self).__init__()

    # -- Convert button
    self.btn_convertNode = QtGui.QPushButton('C&onvert')
    self.btn_convertNode.setToolTip('Convert/Unconvert selected curve node to Hobby Knot')
    self.btn_convertNode.clicked.connect(self.convertHobby)

    #self.btn_convertNode.setFixedWidth(80)

    # -- Close contour checkbox
    #self.chk_Safe = QtGui.QCheckBox('Safe')

    # -- Tension value (not implemented yet)
    #self.edt_tension = QtGui.QLineEdit('0.0')
    #self.edt_tension.setDisabled(True)    
        
    # -- Build
    self.addWidget(self.btn_convertNode)
    #self.addWidget(QtGui.QLabel('T:'), 1, 1)
    #self.addWidget(self.edt_tension, 1, 2)
    #self.addWidget(self.chk_Safe, 1, 3)

  def convertHobby(self):
    glyph = eGlyph()
    wLayers = glyph._prepareLayers(pLayers)
    selection = glyph.selected()

    for layerName in wLayers:
      pNodes = [glyph.nodes(layerName)[nID] for nID in selection]
      print pNodes

      for node in pNodes:
        if not node.hobby:
          node.hobby = True
        else:
          node.hobby = False
        node.update()

    glyph.update()
    
    #fl6.Update(fl6.CurrentGlyph())

# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
  def __init__(self):
    super(tool_tab, self).__init__()

    # - Init
    layoutV = QtGui.QVBoxLayout()
    
    layoutV.addWidget(QtGui.QLabel('Basic Operations'))
    layoutV.addLayout(basicOps())

    layoutV.addWidget(QtGui.QLabel('Break/Knot Contour'))
    layoutV.addLayout(breakContour())

    layoutV.addWidget(QtGui.QLabel('Convert to Hobby'))
    layoutV.addLayout(convertHobby())    

    # - Build ---------------------------
    layoutV.addStretch()
    self.setLayout(layoutV)
  

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 200, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()