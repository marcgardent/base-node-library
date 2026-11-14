"""Arrange the nodes of a tree: their boxes laid out by `sugiyama`, then moved there.

Sizes and sockets are where the editor last drew them. A node never drawn (in background
mode, or just built) gets an estimate instead: its sockets counted in rows, outputs from the
top and inputs from the bottom, so that its links can bend a little.
"""

from statistics import fmean

import bpy

from .sockets import drawn_y
from .sugiyama import Box, Frame, arrange

ROW = 22         # one socket row
FIRST = 35       # from the top of a node to its first output
LAST = 16        # from the last input to the bottom of a node
REROUTE = 8
HIDDEN_TOP = 10  # a collapsed node is drawn a little above its location
TALL = {"VECTOR", "ROTATION"}  # an unlinked value of these shows a row per component


def _shown(sockets):
    return [s for s in sockets if s.enabled and (s.is_linked or not s.hide)]


def _rows(s):
    return 4 if s.type in TALL and not s.is_linked and not s.hide_value else 1


def _box(node, scale):
    ins, outs = list(node.inputs), list(node.outputs)
    if node.bl_idname == "NodeReroute":
        w = h = REROUTE
        drawn = False
        offs_in, offs_out = [h / 2] * len(ins), [h / 2] * len(outs)
    else:
        shown_in, shown_out = _shown(ins), _shown(outs)
        w, h = node.dimensions.x / scale, node.dimensions.y / scale
        drawn = bool(w and h)
        if not drawn:
            w = node.width
            h = FIRST - ROW / 2 + ROW * (len(shown_out) + sum(map(_rows, shown_in))) + LAST
        if node.hide:
            offs_in, offs_out = [h / 2] * len(ins), [h / 2] * len(outs)
        else:
            out_at = {s.as_pointer(): FIRST + ROW * i for i, s in enumerate(shown_out)}
            in_at, below = {}, 0
            for s in reversed(shown_in):
                below += _rows(s)
                in_at[s.as_pointer()] = h - LAST - ROW * (below - 1)
            offs_in = [in_at.get(s.as_pointer(), h / 2) for s in ins]
            offs_out = [out_at.get(s.as_pointer(), h / 2) for s in outs]
    x, y = node.location_absolute
    top = _top(node, y, h)
    if drawn:
        for socks, offs in ((ins, offs_in), (outs, offs_out)):
            for i, s in enumerate(socks):
                if s.enabled and (s.is_linked or not s.hide):
                    real = drawn_y(s, scale, x, top, w, h)
                    if real is not None:
                        offs[i] = top - real
    return Box(node.name, w, h, offs_in, offs_out,
               frame=node.parent.name if node.parent else None, x=x, y=top)


def _top(node, y, h):
    """The y of a node's top, from the y of its location."""
    if node.bl_idname == "NodeReroute":
        return y + REROUTE / 2
    return y + h / 2 - HIDDEN_TOP if node.hide else y


def arrange_nodes(tree, nodes=None, spacing=(50, 50), iterations=24):
    """Lay out `nodes` of `tree` (all of them by default) where they were; the number moved."""
    nodes = [n for n in (tree.nodes if nodes is None else nodes) if n.bl_idname != "NodeFrame"]
    if not nodes:
        return 0
    system = bpy.context.preferences.system
    scale = system.ui_scale or 1.0  # 0 in background mode
    boxes = [_box(n, scale) for n in nodes]
    names = {n.name for n in nodes}

    frames, seen = [], set()
    padding = 1.5 * (int(20 * scale) + 2 * (system.pixel_size or 1.0)) / scale
    for n in nodes:
        f = n.parent
        while f is not None and f.name not in seen:
            seen.add(f.name)
            label = f.label_size * 1.25 - padding / 2 if f.label else 0.0
            frames.append(Frame(f.name, f.parent.name if f.parent else None, label))
            f = f.parent

    index = {}
    for n in nodes:
        for i, s in enumerate(n.inputs):
            index[s.as_pointer()] = i
        for i, s in enumerate(n.outputs):
            index[s.as_pointer()] = i
    links = [(l.from_node.name, index[l.from_socket.as_pointer()], l.to_node.name, index[l.to_socket.as_pointer()])
             for l in tree.links
             if l.is_valid and not l.is_hidden and l.from_node.name in names and l.to_node.name in names]

    pos = arrange(boxes, links, frames, spacing=tuple(spacing), padding=padding, iterations=iterations)

    # The layout keeps the place the nodes had: the mean of their corners stays
    dx = fmean(b.x for b in boxes) - fmean(pos[b.id][0] for b in boxes)
    dy = fmean(b.y for b in boxes) - fmean(pos[b.id][1] for b in boxes)
    for n, b in zip(nodes, boxes):
        x, top = pos[b.id]
        x, top = x + dx, top + dy
        if n.bl_idname == "NodeReroute":
            n.location_absolute = (x + REROUTE / 2, top - REROUTE / 2)
        elif n.hide:
            n.location_absolute = (x, top - b.height / 2 + HIDDEN_TOP)
        else:
            n.location_absolute = (x, top)
    return len(nodes)
