# MODULE: Typerig / GUI / styles
# NOTE: Fontlab specific user interface styling elements
# ----------------------------------------
# (C) Vassil Kateliev, 2021-2022
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.0.7'

# -- CSS Styling ------------------------
css_fl_button = '''
QPushButton {
    background: none;
    border-radius: 5px;
}

QPushButton :checked {
    background-color: #e1e2e3;
    border: 1px solid #dadbdc;
    border-top-color: #d1d2d3;
}

QPushButton :hover {
    background-color: #eaebec;
}

QPushButton :pressed {
    background-color: #a0a0a0;
}

QPushButton :disabled {
    background-color: transparent;
    border: none;
}
'''

css_tr_button = '''
QLabel#lbl_icon {
    color: #212121;
    font-family: "TypeRig Icons";
    font-size: 20px;
    background: none;
    margin: 2 0 2 0;
    padding: 2 0 2 0;
    min-height: 22px;
    min-width: 22px;
}

QPushButton#btn_mast {
    color: #212121;
    font-family: "TypeRig Icons";
    font-size: 20px;
    background: none;
    border-radius: 5px;
    margin: 2 0 2 0;
    padding: 2 0 2 0;
    min-height: 22px;
}

QPushButton#btn_mast:checked {
    background-color: #9c9e9f;
    border: 1px solid #dadbdc;
    border-top-color: #d1d2d3;
    color: #ffffff;
}

QPushButton#btn_mast:hover {
    /*background-color: #ffffff;*/
    /*color: #212121;*/
    border: 1px solid #dadbdc;
    border-bottom-color: #d1d2d3;
}

QPushButton#btn_mast:pressed {
    background-color: #9c9e9f;
    color: #ffffff;
}

QPushButton#btn_mast:disabled {
    background-color: transparent;
    border: none;
}

QGroupBox#box_group {
    background: #edeeef;
    border-radius: 5px;
    padding-top: 5px;
    padding-bottom: 5px;
    padding-right: 5px;
    padding-left: 5px;
    margin-top: 0px;
    margin-bottom: 0px;
    margin-right: 0px;
    margin-left: 0px;
    border: none;
}

QSpinBox#spn_panel,
QSpinBox#spn_panel_inf,
QDoubleSpinBox#spn_panel,
QDoubleSpinBox#spn_panel_inf {
    max-height: 20px;
    max-width: 60px;
    min-height: 20px;
    min-width: 60px;
}

QSpinBox#spn_panel_inf,
QDoubleSpinBox#spn_panel_inf {
    max-width: 70px;
}

QPushButton#btn_panel_opt,
QPushButton#btn_panel, 
QLabel#lbl_panel {
    /*margin: 2 0 2 0;*/
    /*padding: 2 0 2 0;*/
    background: none;
    border-radius: 5px;
    border: 1px solid transparent;
    color: #212121;
    font-family: "TypeRig Icons";
    font-size: 20px;
    max-height: 26px;
    max-width: 26px;
    min-height: 26px;
    min-width: 26px;
    text-align: center;
}

QLabel#lbl_panel {
    border: none;
}

QPushButton#btn_panel_opt{
    border: 1px solid #d1d2d3;
}

QPushButton#btn_panel_opt:checked,
QPushButton#btn_panel:checked {
    background-color: #9c9e9f;
    border: 1px solid #dadbdc;
    border-top-color: #d1d2d3;
    color: #ffffff;
}

QPushButton#btn_panel_opt:checked:hover,
QPushButton#btn_panel:checked:hover {
    background-color: #9c9e9f;
    border: 1px solid #dadbdc;
    border-top-color: #d1d2d3;
    color: #ffffff;
   
}

QPushButton#btn_panel_opt:hover,
QPushButton#btn_panel:hover {
    background-color: #ffffff;
    color: #212121;
}

QPushButton#btn_panel_opt:pressed,
QPushButton#btn_panel:pressed {
    background-color: #9c9e9f;
    color: #ffffff;
}

QPushButton#btn_panel_opt:disabled,
QPushButton#btn_panel:disabled {
    background-color: transparent;
    color: #9c9e9f;
    border: none;
}

QSlider#sld_panel:groove:horizontal {
    border: 0px;
    height: 2px;
    background: #9c9e9f;
    margin: 2px 0;
}

QSlider#sld_panel:handle:horizontal {
    background: #9c9e9f;
    border: 1px solid #9c9e9f;
    width: 8px;
    margin: -4px 0;
    border-radius: 4px;
}

QSlider#sld_panel:add-page:horizontal {
    border: 0px;
    height: 2px;
    background: #d1d2d3;
    margin: 2px 0;
}

QSlider#sld_panel:sub-page:horizontal {
   border: 0px;
    height: 2px;
    background: #9c9e9f;
    margin: 2px 0;
}
'''

css_tr_button_dark = '''
QLabel#lbl_icon {
    color: #dcdcdc;
    font-family: "TypeRig Icons";
    font-size: 20px;
    background: none;
    margin: 2 0 2 0;
    padding: 2 0 2 0;
    min-height: 22px;
    min-width: 22px;
}

QPushButton#btn_mast {
    color: #dcdcdc;
    font-family: "TypeRig Icons";
    font-size: 20px;
    background: none;
    border-radius: 5px;
    margin: 2 0 2 0;
    padding: 2 0 2 0;
    min-height: 22px;
}

QPushButton#btn_mast:checked {
    background-color: #1d1e1f;
    border: 1px solid #2d2e34;
    border-top-color: #000000;
    color: #dcdcdc;
}

QPushButton#btn_mast:hover {
    background-color: #404142;
    border: 1px solid #2d2e34;
    border-bottom-color: #000000;
}

QPushButton#btn_mast:pressed {
    background-color: #1d1e1f;
    color: #dcdcdc;
}

QPushButton#btn_mast:disabled {
    background-color: transparent;
    border: none;
}

QGroupBox#box_group {
    background: #2d2e34;
    border-radius: 5px;
    padding-top: 5px;
    padding-bottom: 5px;
    padding-right: 5px;
    padding-left: 5px;
    margin-top: 0px;
    margin-bottom: 0px;
    margin-right: 0px;
    margin-left: 0px;
    border: none;
}

QSpinBox#spn_panel,
QSpinBox#spn_panel_inf,
QDoubleSpinBox#spn_panel,
QDoubleSpinBox#spn_panel_inf {
    max-height: 20px;
    max-width: 60px;
    min-height: 20px;
    min-width: 60px;
}

QSpinBox#spn_panel_inf,
QDoubleSpinBox#spn_panel_inf {
    max-width: 70px;
}

QPushButton#btn_panel_opt,
QPushButton#btn_panel, 
QLabel#lbl_panel {
    background: none;
    border-radius: 5px;
    border: 1px solid transparent;
    color: #dcdcdc;
    font-family: "TypeRig Icons";
    font-size: 20px;
    max-height: 26px;
    max-width: 26px;
    min-height: 26px;
    min-width: 26px;
    text-align: center;
}

QLabel#lbl_panel {
    border: none;
}

QPushButton#btn_panel_opt{
    border: 1px solid #17191e;
}

QPushButton#btn_panel_opt:checked,
QPushButton#btn_panel:checked {
    background-color: #1d1e1f;
    border: 1px solid #17191e;
    border-top-color: #000000;
    color: #dcdcdc;
}

QPushButton#btn_panel_opt:checked:hover,
QPushButton#btn_panel:checked:hover {
    background-color: #404142;
    border: 1px solid #17191e;
    border-top-color: #000000;
    color: #dcdcdc;
   
}

QPushButton#btn_panel_opt:hover,
QPushButton#btn_panel:hover {
    background-color: #404142;
    color: #dcdcdc;
}

QPushButton#btn_panel_opt:pressed,
QPushButton#btn_panel:pressed {
    background-color: #1d1e1f;
    color: #dcdcdc;
}

QPushButton#btn_panel_opt:disabled,
QPushButton#btn_panel:disabled {
    background-color: transparent;
    color: #404142;
    border: none;
}

QSlider#sld_panel:groove:horizontal {
    border: 0px;
    height: 2px;
    background: #404142;
    margin: 2px 0;
}

QSlider#sld_panel:handle:horizontal {
    background: #404142;
    border: 1px solid #404142;
    width: 8px;
    margin: -4px 0;
    border-radius: 4px;
}

QSlider#sld_panel:add-page:horizontal {
    border: 0px;
    height: 2px;
    background: #4d4e4f;
    margin: 2px 0;
}

QSlider#sld_panel:sub-page:horizontal {
   border: 0px;
    height: 2px;
    background: #404142;
    margin: 2px 0;
}
'''