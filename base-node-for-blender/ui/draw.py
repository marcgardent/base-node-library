"""Drawing over the Text Editor: where a character is, and flat rectangles."""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader


def line_height(space):
    # As the Text Editor computes it: the font size plus 30 % spacing
    return round(space.font_size * bpy.context.preferences.system.ui_scale * 1.3)


def visible_rows(space, region):
    """The 0-based lines of the text shown in the region, top to bottom."""
    lh = line_height(space)
    # With word wrap, `top` counts screen rows, which are at least as many as lines
    first = 0 if space.show_word_wrap else max(0, space.top - 1)
    for row in range(first, len(space.text.lines)):
        _, y = char_box(space, row, 0)
        if y > region.height + lh:
            continue
        if y < -lh:
            break
        yield row


def char_box(space, line, col):
    """(x, bottom y) in region pixels of the character at a 0-based line and column."""
    return space.region_location_from_cursor(line, col)


def rects(boxes, color):
    """Fill (x0, y0, x1, y1) boxes with one RGBA color."""
    if not boxes:
        return
    verts, indices = [], []
    for x0, y0, x1, y1 in boxes:
        n = len(verts)
        verts += [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        indices += [(n, n + 1, n + 2), (n, n + 2, n + 3)]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRIS", {"pos": verts}, indices=indices)
    gpu.state.blend_set("ALPHA")
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")
