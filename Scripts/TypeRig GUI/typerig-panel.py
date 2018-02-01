#FLM: Typerig Panel
# ----------------------------------------
# (C) Vassil Kateliev, 2018 (http://www.kateliev.com)
# (C) Karandash Type Foundry (http://www.karandash.eu)
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
#import fontlab as fl6
#import fontgate as fgt
from PythonQt import QtCore, QtGui

# -- Internals - Load toolpanels 
import Panel 

# - Init --------------------------
app_version = '0.20'
app_name = 'Typerig Panel'

# - Style -------------------------
ss_Toolbox_dflt = """
                QDialog { background-color: Gainsboro; }

                QCheckBox::indicator:unchecked {
                  border: 1px Solid Gray;
                 }
                
                QCheckBox::indicator:checked {
                  background-color: dodgerblue;
                  border: 1px Solid dodgerblue;
                 }

                QTabWidget::pane { background-color: Gainsboro;}
                QTabWidget::tab-bar { background-color: Gainsboro; }
                QTabBar::tab { background-color: LightGray; }
                QTabBar::tab:hover { background-color: SkyBlue; }
                QTabBar::tab:selected { background-color:#eeeeee; }
                QTabWidget>QWidget>QWidget{ background: #eeeeee;  }

                """
ss_Toolbox_fl6 = """
                QDialog { background-color: Gainsboro; }

                QPushButton {
                  background-color: White;
                  border-radius: 6px;
                  padding: 6px;
                }
                
                QPushButton::pressed {
                  background-color: dimgrey;
                  color: white;
                  border-radius: 6px;
                  padding: 6px;
                }
                               
                QTabWidget::pane { background-color: Gainsboro;}
                QTabWidget::tab-bar { background-color: Gainsboro; }
                QTabBar::tab { background-color: LightGray; }
                QTabBar::tab:hover { background-color: SkyBlue; }
                QTabBar::tab:selected { background-color:#eeeeee; }
                QTabWidget>QWidget>QWidget{ background: #eeeeee;  }
                
                QLineEdit { 
                  background-color: White;
                  border: 1px Solid White;
                  padding: 4px;
                }
                
                QListWidget { 
                  background-color: White;
                  border: 0px;
                  alternate-background-color: WhiteSmoke;
                  padding: 4px;
                }
                
                QLabel { 
                  padding-top: 4px;
                  padding-bottom: 4px;
                }
               
                QListWidget::Item::Hover { 
                  border: 0px;
                }
                
                QListWidget::Item::Selected { 
                  background-color: #d3f8d3;
                  border: 0px; 
                  color:black;
                }
               
                QComboBox { 
                  /*background-color: White;*/
                  /*border: 1px Solid White;*/
                  padding: 4px;
                }
                /*
                QComboBox::drop-down {
                  background-color: white;
                  border: 1px Solid lightgray;
                  border-radius: 4px;
                }
                
                QComboBox::down-arrow {
                  image: url(:/Res/down-arrow.png);
                }
                */
                
                QCheckBox::indicator:unchecked {
                  background-color: White;
                  border: 1px Solid White;
                  border-radius: 2px;
                 }
                
                QCheckBox::indicator:checked {
                  background-color: dodgerblue;
                  border: 1px Solid dodgerblue;
                  border-radius: 6px;
                 }
                 
                """

# - Interface -----------------------------
# -- Main Widget --------------------------
class typerig_Panel(QtGui.QDialog):
  def __init__(self):
    super(typerig_Panel, self).__init__()
  
    self.setStyleSheet(ss_Toolbox_dflt)
    
    # - Layers --------------------------
    self.chk_ActiveLayer = QtGui.QCheckBox('Active Layer')
    self.chk_Masters = QtGui.QCheckBox('Master Layers')
    self.chk_Masks = QtGui.QCheckBox('Mask Layers')
    self.chk_Service = QtGui.QCheckBox('Service Layers')

    self.chk_ActiveLayer.setCheckState(QtCore.Qt.Checked)
    self.chk_ActiveLayer.setStyleSheet('QCheckBox::indicator:checked {background-color: limegreen; border: 1px Solid limegreen;}')
      
    self.chk_ActiveLayer.stateChanged.connect(self.refreshLayers)
    self.chk_Masters.stateChanged.connect(self.refreshLayers)
    self.chk_Masks.stateChanged.connect(self.refreshLayers)
    self.chk_Service.stateChanged.connect(self.refreshLayers)

    self.refreshLayers()
        
    # - Tabs --------------------------
    # -- Dynamically load all tabs

    self.tabs = QtGui.QTabWidget()
    self.tabs.setTabPosition(QtGui.QTabWidget.East)

    # --- Load all tabs from this directory as modules. Check __init__.py 
    # --- <dirName>.modules tabs/modules manifest in list format
    for toolName in Panel.modules:
      self.tabs.addTab(eval('Panel.%s.tool_tab()' %toolName), toolName)
    
    # - Layouts -------------------------------
    layoutV = QtGui.QVBoxLayout() 
    layoutV.setContentsMargins(0,0,0,0)
    
    subH01 = QtGui.QGridLayout()
    subH01.setContentsMargins(15,10,30,5)
        
    # -- Build layouts -------------------------------
    subH01.addWidget(self.chk_ActiveLayer, 0, 0)
    subH01.addWidget(self.chk_Masters, 0 ,1)
    subH01.addWidget(self.chk_Masks, 1, 0)
    subH01.addWidget(self.chk_Service, 1,1 )
       
    layoutV.addLayout(subH01)
    layoutV.addWidget(self.tabs)

    # - Set Widget -------------------------------
    self.setLayout(layoutV)
    self.setWindowTitle('%s %s' %(app_name, app_version))
    self.setGeometry(300, 300, 220, 440)
    self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # Always on top!!
    
    self.show()

  def refreshLayers(self):
    global pLayers
    pLayers = (self.chk_ActiveLayer.isChecked(), self.chk_Masters.isChecked(), self.chk_Masks.isChecked(), self.chk_Service.isChecked())
    
    for toolName in Panel.modules:
      exec('Panel.%s.pLayers = %s' %(toolName, pLayers))
  
# - RUN ------------------------------
dialog = typerig_Panel()

