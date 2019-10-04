#FLM: TypeRig Playground
# - Dependancies
import fontlab as fl6
import fontgate as fgt
import FL as legacy
import PythonQt as pqt

import typerig.proxy as proxy
import typerig.glyph as gl
import typerig.node as tn
import typerig.brain as fb
import typerig.curve as tc

# - Tools ---------- -----------
def up(): Update(CurrentGlyph())

# - Init -----------------------------
font = proxy.pFont()
g = proxy.pGlyph()
g = gl.eGlyph()
ws = proxy.pWorkspace()

# - Finish ---------------------------
print 'INIT:\tPlayground >> %s !' %g.name