# MODULE: TypeRig Kern / Sub Panels
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2018-2020 	(http://www.kateliev.com)
# (C) Karandash Type Foundry 		(http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies -----------------
import os

# - Init
global modules
modules = [moduleName[:-3] for moduleName in os.listdir(os.path.dirname(__file__)) if '__' not in moduleName and '.py' == moduleName[-3:]]

for module in modules:
    __import__(module, locals(), globals())
