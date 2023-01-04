# MODULE: Typerig / GUI / styles
# NOTE: Fontlab specific user interface styling elements
# ----------------------------------------
# (C) Vassil Kateliev, 2021-2022
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.0.3'

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

QDoubleSpinBox#spn_panel {
    max-height: 20px;
    max-width: 60px;
    min-height: 20px;
    min-width: 60px;
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

'''