"""Drawing the comments of the text in the Node Editor, on the nodes that keep them.

A node's comments are shown above it, as wide as it, in a box of the theme's tooltip colors:
those written before its statement, after it on its line, and, for a zone's output, around its
return; those of a zone's end under it. A frame shows above it the comments of its block's head,
under it those of its end; a note, which has nothing else, shows them inside. The tree's own
comments are in a corner of the editor. The boxes follow the view: they zoom with the nodes, and
vanish when the text gets too small. Their sizes are the ones Arrange Nodes leaves room for:
see host.comments.
"""

import blf
import bpy

from ..host.comments import ABOVE, BAR, BELOW, GAP, KEY, LINE, PAD, SIZE, lines_of, notes_of, wrap
from . import draw, prefs

MIN_SIZE = 6  # under this font size in pixels, nothing is drawn
TREE = ("head", "file", "before", "after", "end", "below")
CORNER = 360  # width of the box of the tree's comments, at UI scale 1


class View:
    """The editor's view: where a point of the tree is in the region, and how big things are."""

    def __init__(self, context):
        self.region = context.region
        self.v2d = context.region.view2d
        self.ui = context.preferences.system.ui_scale
        x0, _ = self.v2d.view_to_region(0, 0, clip=False)
        x1, _ = self.v2d.view_to_region(1000, 0, clip=False)
        self.zoom = (x1 - x0) / 1000  # region pixels per view unit
        self.scale = self.zoom * self.ui  # region pixels per node unit (node.location, node.width)

    def point(self, x, y):
        return self.v2d.view_to_region(x * self.ui, y * self.ui, clip=False)

    def visible(self, x0, y0, x1, y1):
        return x1 >= 0 and y1 >= 0 and x0 <= self.region.width and y0 <= self.region.height


class Painter:
    def __init__(self, view, theme, scale):
        """`scale`: region pixels per node unit."""
        self.view = view
        self.fid = 0
        self.scale = scale
        self.size = round(SIZE * scale)
        self.pad = PAD * scale
        self.bar = max(1, round(BAR * scale))
        self.line = round(SIZE * LINE) * scale
        tip = theme.user_interface.wcol_tooltip
        # The tooltip's colors, its back a little toward its text to stand out of the editor's
        self.back = (*(b + (t - b) * 0.12 for b, t in zip(tip.inner[:3], tip.text[:3])), 0.92)
        self.text = (*tip.text[:3], 1.0)
        self.edge = (*tip.text[:3], 0.45)

    def box(self, lines, x, y, width, upward):
        """Draw the lines in a box `width` wide, from (x, y) up or down. Returns the box."""
        # Cut where the layout cuts them: at the font size of node units, then scaled
        blf.size(self.fid, SIZE)
        lines = wrap(lines, width / self.scale - BAR - 2 * PAD, self.fid)
        blf.size(self.fid, self.size)
        height = len(lines) * self.line + 2 * self.pad
        y0, y1 = (y, y + height) if upward else (y - height, y)
        box = (x, y0, x + width, y1)
        if not self.view.visible(*box):
            return box
        draw.rects([box], self.back)
        draw.rects([(x, y0, x + self.bar, y1)], self.edge)
        blf.color(self.fid, *self.text)
        for i, text in enumerate(lines):
            baseline = y1 - self.pad - (i + 1) * self.line + round(self.line * 0.3)
            blf.position(self.fid, x + self.bar + self.pad, baseline, 0)
            blf.draw(self.fid, text)
        return box


def node_box(node, view):
    """(left, bottom, right, top) of a node in region pixels."""
    x, y = node.location_absolute
    left, top = view.point(x, y)
    width = node.width * view.scale
    # dimensions are in view units, once the node has been drawn; a hidden node is its header
    height = node.dimensions.y * view.zoom if node.dimensions.y else 20 * view.scale
    return left, top - height, left + width, top


def draw_notes():
    context = bpy.context
    space = context.space_data
    tree = getattr(space, "edit_tree", None)
    if tree is None or not prefs.get().show_comments:
        return
    view = View(context)
    theme = context.preferences.themes[0]
    painter = Painter(view, theme, view.scale)
    if painter.size < MIN_SIZE:
        return
    gap = GAP * view.scale
    framing = {n.parent.name for n in tree.nodes if n.parent is not None}
    for node in tree.nodes:
        if KEY not in node:
            continue
        notes = notes_of(node)
        left, bottom, right, top = node_box(node, view)
        width = right - left
        above, below = lines_of(notes, ABOVE), lines_of(notes, BELOW)
        if above:
            painter.box(above, left, top + gap, width, upward=True)
        if not below:
            continue
        if node.bl_idname == "NodeFrame" and node.name not in framing:
            # A note: its comments are what it says, inside it under its label
            label = node.label_size * 1.5 * view.scale if node.label else 0
            painter.box(below, left + gap, top - label - gap, width - 2 * gap, upward=False)
        else:
            painter.box(below, left, bottom - gap, width, upward=False)

    # The tree's own: a fixed box in the lower left corner, not zoomed
    lines = lines_of(notes_of(tree), TREE)
    if lines:
        margin = 12 * view.ui
        width = min(CORNER * view.ui, view.region.width - 2 * margin)
        Painter(view, theme, view.ui).box(lines, margin, margin, width, upward=True)


_handler = None


def register():
    global _handler
    _handler = bpy.types.SpaceNodeEditor.draw_handler_add(draw_notes, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handler
    if _handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_handler, "WINDOW")
        _handler = None
