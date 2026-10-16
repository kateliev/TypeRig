# encoding: utf-8
# -------------------------------------------------------------------------
# TypeRig Panel — TypeRig core bootstrap
#
# Action modules use underscored naming (node_actions.py, etc.) and are
# imported directly. This module provides thin backward-compatible wrappers.
# -------------------------------------------------------------------------

from __future__ import division, print_function

import typerig  # required: assumes user has installed typerig (.pth or copy)

from typerig.core.actions import node_actions
from typerig.core.actions import node_panel_actions
from typerig.core.actions import curve_actions
from typerig.core.actions import contour_actions
from typerig.core.actions import draw_actions
from typerig.core.actions import cut_panel_actions


def bootstrap():
    '''Kept for backwards compatibility — imports above already load everything.'''
    pass


def get_node_actions():
    return node_actions.NodeActions, node_panel_actions


def get_curve_actions():
    return curve_actions.CurveActions


def get_contour_actions():
    return contour_actions.ContourActions


def get_draw_actions():
    return draw_actions.DrawActions


def get_cut_actions():
    return cut_panel_actions
