"""Drawing the comments of the text in the Node Editor, on the nodes that keep them.

A node's comments are shown above it, in a box of the theme's tooltip colors: those written
before its statement, after it on its line, and, for a zone's output, around its return. A
frame shows above it the comments of its block's head, under it those of its end; a note, which
has nothing else, shows them inside. The tree's own comments are in a corner of the editor.
The boxes follow the view: they zoom with the nodes, and vanish when the text gets too small.
"""

import blf
import bpy

from ..host.comments import KEY, notes_of
from . import draw, prefs

SIZE = 11        # font size at zoom 1, as Blender's node text
PAD = 4          # around the text, at zoom 1
GAP = 6          # between a box and its node, at zoom 1
MIN_SIZE = 6     # under this font size in pixels, nothing is drawn
MIN_WIDTH = 180  # a box is as wide as its node, and at least this, at zoom 1

ABOVE = ("before", "after", "return_before", "return_after")
BELOW = ("end", "end_after")
TREE = ("head", "file", "before", "after", "end", "below")


def plain(comment):
    """`// text` -> `text`: the comment as it reads."""
    body = comment.lstrip()
    body = body[2:] if body.startswith("//") else body
    return body[1:] if body.startswith(" ") else body


def lines_of(notes, slots):
    return [plain(c) for slot in slots for c in notes.get(slot, [])]


def wrap(fid, lines, width):
    """Lines cut at spaces to fit `width` pixels; a word longer than that stays whole."""
    out = []
    for line in lines:
        words, current = line.split(" "), ""
        for word in words:
            tried = f"{current} {word}" if current else word
            if current and blf.dimensions(fid, tried)[0] > width:
                out.append(current)
                current = word
            else:
                current = tried
        out.append(current)
    return out


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
        """`scale`: pixels per unit of SIZE, PAD and the widths."""
        self.view = view
        self.fid = 0
        self.size = round(SIZE * scale)
        self.pad = PAD * scale
        self.line = round(self.size * 1.3)
        tip = theme.user_interface.wcol_tooltip
        # The tooltip's colors, its back a little toward its text to stand out of the editor's
        self.back = (*(b + (t - b) * 0.12 for b, t in zip(tip.inner[:3], tip.text[:3])), 0.92)
        self.text = (*tip.text[:3], 1.0)
        self.edge = (*tip.text[:3], 0.45)
        self.bar = max(2, round(2 * scale))
        blf.size(self.fid, self.size)

    def box(self, lines, x, y, width, upward):
        """Draw the lines in a box `width` wide, from (x, y) up or down. Returns the box."""
        lines = wrap(self.fid, lines, width - self.bar - 2 * self.pad)
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
    for node in tree.nodes:
        if KEY not in node:
            continue
        notes = notes_of(node)
        left, bottom, right, top = node_box(node, view)
        width = max(right - left, MIN_WIDTH * view.scale)
        above = lines_of(notes, ABOVE)
        below = lines_of(notes, BELOW)
        if node.bl_idname == "NodeFrame" and not any(c.parent == node for c in tree.nodes):
            # A note: its comments are what it says, inside it under its label
            label = round(node.label_size * view.scale * 1.5) if node.label else 0
            if above:
                painter.box(above, left, top + gap, width, upward=True)
            if below:
                painter.box(below, left + gap, top - label - gap, max(right - left - 2 * gap, width / 2),
                            upward=False)
            continue
        if above:
            painter.box(above, left, top + gap, width, upward=True)
        if below:
            painter.box(below, left, bottom - gap, width, upward=False)

    # The tree's own: a fixed box in the lower left corner, not zoomed
    lines = lines_of(notes_of(tree), TREE)
    if lines:
        fixed = Painter(view, theme, view.ui)
        margin = 12 * view.ui
        fixed.box(lines, margin, margin, min(360 * view.ui, view.region.width - 2 * margin), upward=True)


_handler = None


def register():
    global _handler
    _handler = bpy.types.SpaceNodeEditor.draw_handler_add(draw_notes, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handler
    if _handler is not None:
        bpy.types.SpaceNodeEditor.draw_handler_remove(_handler, "WINDOW")
        _handler = None
