#FLM: TAB Curve Tools 1.0
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------

# No warranties. By using this you agree
# that you use it at your own risk!

# - Init
global pLayers
pLayers = None
app_name, app_version = 'TypeRig | Curves', '0.10'

# - Dependencies -----------------
import fontlab as fl6
import fontgate as fgt
from PythonQt import QtCore, QtGui
from typerig.glyph import eGlyph
from typerig.node import eNode
from typerig.curve import eCurveEx

# - Sub widgets ------------------------
class curveEq(QtGui.QGridLayout):
  # - Curve optimization
  def __init__(self):
    super(curveEq, self).__init__()
    
    # - Basic operations
    self.btn_tunni = QtGui.QPushButton('&Tunni (Auto)')
    self.btn_hobby = QtGui.QPushButton('&Hobby (Curvature)')
    self.btn_prop = QtGui.QPushButton('&Proportional (Handles)')
    
    self.btn_tunni.setMinimumWidth(85)
    self.btn_hobby.setMinimumWidth(85)
    self.btn_prop.setMinimumWidth(85)

    self.btn_tunni.setToolTip('Apply Tunni curve optimization')
    self.btn_hobby.setToolTip('Set Hobby spline curvature')
    self.btn_prop.setToolTip('Set handle length in proportion to bezier node distance')
    
    self.edt_hobby = QtGui.QLineEdit('0.95')
    self.edt_prop = QtGui.QLineEdit('0.30')
    

    self.btn_tunni.clicked.connect(lambda: self.eqContour('tunni'))
    self.btn_hobby.clicked.connect(lambda: self.eqContour('hobby'))
    self.btn_prop.clicked.connect(lambda: self.eqContour('prop'))

    # -- Build: Curve optimization
    self.addWidget(self.btn_tunni, 0, 0, 1, 5)
    
    self.addWidget(self.btn_hobby, 1, 0, 1, 5 )
    self.addWidget(QtGui.QLabel('C:'), 1, 5, 1, 1)
    self.addWidget(self.edt_hobby, 1, 6, 1, 1)
    
    self.addWidget(self.btn_prop, 2, 0, 1, 5)
    self.addWidget(QtGui.QLabel('P:'), 2, 5, 1, 1)
    self.addWidget(self.edt_prop, 2, 6, 1, 1)

    self.setColumnStretch(0,1)
    self.setColumnStretch(6,0)
    self.setColumnStretch(7,0)

    self.setColumnMinimumWidth(0, 180)

  def eqContour(self, method):
    '''
    import sys        
    sys.stdout = open(r'd:\\stdout.log', 'w')
    sys.stderr = open(r'd:\\stderr.log', 'w')
    '''

    glyph = eGlyph()
    selection = glyph.selected(True)
    wLayers = glyph._prepareLayers(pLayers)

    for layer in wLayers:
      nodes = [eNode(glyph.nodes(layer)[nid]) for nid in selection]
      conNodes =  [nodes[nid] for nid in range(len(nodes)-1) if nodes[nid].getNextOn() == nodes[nid+1].fl]
      segmentNodes = [node.getSegmentNodes() for node in conNodes]

      for segment in reversed(segmentNodes):
        if len(segment) == 4:
          wSegment = eCurveEx(segment)
          
          if method is 'tunni':
            wSegment.eqTunni()

          elif method is 'hobby':
            curvature = (float(self.edt_hobby.text), float(self.edt_hobby.text))
            wSegment.eqHobbySpline(curvature)

          elif method is 'prop':
            proportion = float(self.edt_prop.text)
            wSegment.eqProportionalHandles(proportion)

          glyph.updateObject(glyph.fl, 'Curve Eq. %s @ %s' %(method, '; '.join(wLayers)))
          glyph.update()


# - Tabs -------------------------------
class tool_tab(QtGui.QWidget):
  def __init__(self):
    super(tool_tab, self).__init__()

    # - Init
    layoutV = QtGui.QVBoxLayout()
        
    # - Build   
    layoutV.addWidget(QtGui.QLabel('Curve optimization'))
    layoutV.addLayout(curveEq())

     # - Build ---------------------------
    layoutV.addStretch()
    self.setLayout(layoutV)

# - Test ----------------------
if __name__ == '__main__':
  test = tool_tab()
  test.setWindowTitle('%s %s' %(app_name, app_version))
  test.setGeometry(300, 300, 280, 400)
  test.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
  
  test.show()