"""Highlighting of .bn texts: translucent boxes over keywords, calls, types and values.

The Text Editor colors only the languages it knows, in C; this draws over
the text instead of recoloring it. Types take the color of their socket.
"""

import bpy

from ..lang.colors import rgb
from ..lang.lexer import tokenize
from ..lang.schema import TREE_KINDS, TYPES
from ..lang.sugar import FUNCS
from . import actions, draw, prefs

ALPHA = 0.22
SWATCH = 0.6  # a frame color shows itself, more opaque

COLORS = {
    "keyword": (0.65, 0.40, 0.95),
    "node": (0.30, 0.55, 1.00),
    "function": (0.20, 0.80, 0.80),
    "literal": (1.00, 0.60, 0.20),
    "comment": (0.50, 0.50, 0.50),
    "namespace": (0.00, 0.78, 0.65),
    "stdlib_func": (0.00, 0.78, 0.65),
    "local_func": (0.95, 0.75, 0.20),
    "warning": (0.95, 0.30, 0.25),
}

# Blender's default socket colors
SOCKETS = {
    "Float": (0.63, 0.63, 0.63), "Int": (0.35, 0.55, 0.36), "Bool": (0.80, 0.65, 0.84),
    "Vector": (0.39, 0.39, 0.78), "Color": (0.78, 0.78, 0.16), "Rotation": (0.65, 0.39, 0.78),
    "Matrix": (0.72, 0.20, 0.52), "String": (0.44, 0.70, 1.00), "Menu": (0.40, 0.40, 0.40),
    "Geometry": (0.00, 0.84, 0.64), "Shader": (0.39, 0.78, 0.39), "Object": (0.93, 0.62, 0.36),
    "Collection": (0.96, 0.96, 0.96), "Material": (0.92, 0.46, 0.51), "Image": (0.39, 0.22, 0.39),
    "Texture": (0.62, 0.31, 0.64), "Bundle": (0.50, 0.50, 0.50), "Closure": (0.50, 0.50, 0.50),
}


def classify(tokens, context=None):
    """(token, color key) for the tokens worth a box, from one line's tokens."""
    ctx = context or {}
    declared = ctx.get("declared", set())
    mode = ctx.get("mode", "standard")
    allowed_nodes = ctx.get("allowed_nodes")
    allowed_types = ctx.get("allowed_types")

    out = []
    for i, t in enumerate(tokens):
        prev = tokens[i - 1].kind if i else None
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if t.kind == "KEYWORD":
            out.append((t, "literal" if t.text in ("true", "false") else "keyword"))
        elif t.kind in ("NUMBER", "STRING", "OPEN_STRING"):
            out.append((t, "literal"))
        elif t.kind == "COMMENT":
            out.append((t, "comment"))
        elif t.kind == "COLOR" and rgb(t.text[1:]):
            out.append((t, rgb(t.text[1:])))
        elif t.kind == "::":
            out.append((t, "namespace"))
        elif t.kind == "IDENT":
            # `use`, `as`, and `from` are keywords on a use line: `use ink2d as gp from "…"`
            is_use_line = tokens[0].text == "use"
            if is_use_line:
                if t.text in ("use", "as", "from"):
                    out.append((t, "keyword"))
                else:
                    out.append((t, "namespace"))
            elif nxt is not None and nxt.kind == "::":
                out.append((t, "namespace"))
            elif prev == "::":
                out.append((t, "stdlib_func"))
            elif t.text in TREE_KINDS and nxt is not None and nxt.text == "graph":
                out.append((t, "keyword"))
            elif t.text in TYPES and prev in (":", "->"):
                if allowed_types is not None and t.text not in allowed_types:
                    out.append((t, "warning"))
                else:
                    out.append((t, t.text))
            elif nxt is not None and nxt.kind == "(":
                if t.text in declared:
                    out.append((t, "local_func" if mode in ("origin", "portability") else "function"))
                elif t.text in FUNCS:
                    out.append((t, "function"))
                else:
                    if allowed_nodes is not None and t.text not in allowed_nodes:
                        out.append((t, "warning"))
                    else:
                        out.append((t, "node"))
            elif prev == "KEYWORD" and tokens[i - 1].text == "graph":
                out.append((t, "local_func" if mode in ("origin", "portability") else "node"))
    return out


def boxes(space, row, tokens, context=None):
    """{color key: [(x0, y0, x1, y1)]} for one 0-based text line."""
    lh = draw.line_height(space)
    out = {}
    for t, color in classify(tokens, context):
        start = t.col - 1
        length = len(t.text) + (2 if t.kind == "STRING" else 1 if t.kind == "OPEN_STRING" else 0)
        x0, y0 = draw.char_box(space, row, start)
        x1, y1 = draw.char_box(space, row, start + length)
        if y1 != y0:
            # Wrapped: one box per character keeps each on its row
            for c in range(start, start + length):
                cx, cy = draw.char_box(space, row, c)
                nx, ny = draw.char_box(space, row, c + 1)
                if ny == cy:
                    out.setdefault(color, []).append((cx, cy, nx, cy + lh))
            continue
        out.setdefault(color, []).append((x0, y0, x1, y0 + lh))
    return out


def draw_highlight():
    space = bpy.context.space_data
    text = space.text
    if not actions.is_bn(text) or not prefs.get().highlight:
        return
    region = bpy.context.region
    lh = draw.line_height(space)
    found = {}

    p = prefs.get()
    mode = getattr(p, "highlight_mode", "standard")
    target_prof = getattr(p, "target_profile", "auto")

    # Fast scan of text for declared local graphs
    declared = set()
    for line in text.lines:
        b = line.body.strip()
        if " graph " in b:
            after = b.split(" graph ", 1)[1]
            gname = after.split("(")[0].strip().strip('"')
            declared.add(gname)

    allowed_nodes = None
    allowed_types = None
    if mode == "portability" or target_prof != "auto":
        from ..lang.profiles import load_profile
        prof_name = target_prof
        if prof_name == "auto":
            for line in text.lines[:5]:
                b = line.body.strip()
                if "@profile" in b:
                    prof_name = b.split("@profile", 1)[1].strip().strip('"').strip("'")
                    break
            if prof_name == "auto":
                prof_name = "vector2d"
        try:
            prof = load_profile(prof_name)
            allowed_nodes = prof.get("_allowed_bl_idnames", set()) | set(prof.get("nodes", []))
            for a, target in prof.get("aliases", {}).items():
                if target in allowed_nodes:
                    allowed_nodes.add(a)
            allowed_types = set(prof.get("types", []))
        except Exception:
            pass

    context = {
        "mode": mode,
        "declared": declared,
        "allowed_nodes": allowed_nodes,
        "allowed_types": allowed_types,
    }

    # With word wrap, `top` counts screen rows, which are at least as many as lines
    first = 0 if space.show_word_wrap else max(0, space.top - 1)
    for row in range(first, len(text.lines)):
        _, y = draw.char_box(space, row, 0)
        if y > region.height + lh:
            continue
        if y < -lh:
            break
        tokens = tokenize(text.lines[row].body, strict=False)[:-1]
        for color, rects in boxes(space, row, tokens, context).items():
            found.setdefault(color, []).extend(rects)

    active_colors = dict(COLORS)
    if hasattr(p, "color_stdlib"):
        active_colors["namespace"] = tuple(p.color_stdlib)
        active_colors["stdlib_func"] = tuple(p.color_stdlib)
    if hasattr(p, "color_local"):
        active_colors["local_func"] = tuple(p.color_local)
    if hasattr(p, "color_warning"):
        active_colors["warning"] = tuple(p.color_warning)

    for color, rects in found.items():
        if isinstance(color, tuple):
            draw.rects(rects, (*color, SWATCH))
        else:
            draw.rects(rects, (*(active_colors.get(color) or SOCKETS.get(color, active_colors["comment"])), ALPHA))


_handler = None


def register():
    global _handler
    _handler = bpy.types.SpaceTextEditor.draw_handler_add(draw_highlight, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handler
    if _handler is not None:
        bpy.types.SpaceTextEditor.draw_handler_remove(_handler, "WINDOW")
        _handler = None
