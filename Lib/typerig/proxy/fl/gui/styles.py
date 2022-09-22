# MODULE: Typerig / GUI / styles
# NOTE: Fontlab specific user interface styling elements
# ----------------------------------------
# (C) Vassil Kateliev, 2021-2022
#-----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

__version__ = '0.0.1'

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

'''