# MODULE: Actions | Typerig
# ----------------------------------------
# (C) Adam Twardoch, 2019
# -----------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# Running UI FontLab actions

from typerig.proxy import pWorkspace
from typerig.QtGui import QAction
from collections import OrderedDict


class TRActions(object):
    def __init__(self):
        self.ws = pWorkspace()
        self.main = self.ws.main
        self.actions = {}
        self._buildActions()

    def _buildActions(self):
        for ind, obj in enumerate(self.main.children()):
            if type(obj) == QAction:
                if obj.statusTip:
                    if obj.statusTip[0] == '@':
                        self.actions[
                            obj.statusTip.replace('@mainwindow.action', '')
                        ] = ind

    def getQAction(self, code):
        if code in self.actions:
            return self.main.children()[self.actions[unicode(code)]]

    def run(self, code):
        self.getQAction(code).trigger()

    def help(self, code):
        a = self.getQAction(code)
        return u'%s: %s. %s' % (code, a.text if a.text else '', a.toolTip if a.toolTip else '')

    def helpAll(self):
        help = []
        for code in sorted(self.actions):
            help.append("- %s" % self.help(code))
        return "\n".join(help)


if __name__ == '__main__':
    actions = TRActions()
    print actions.helpAll()
    actions.run('About')
