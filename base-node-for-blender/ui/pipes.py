"""The pipe `|>` shown as one symbol, ▷, over its two cells.

The Text Editor draws one character per cell and knows no ligatures, so a
font can't do it: this paints the theme's background over `|` and `>`, then
draws the symbol across both. The text itself keeps `|>`. Lines the cursor
or the selection is on show the real characters, to edit them.
"""

import os

import blf
import bpy

from ..lang.lexer import tokenize
from . import actions, draw, prefs

SYMBOL = "▷"

_fonts = {}  # font path -> blf id


def columns(tokens):
    """0-based columns of the pipes among one line's tokens."""
    return [t.col - 1 for t in tokens if t.kind == "|>"]


def raw_lines(text):
    """0-based lines that keep `|>`: from the cursor to the end of the selection."""
    a, b = text.current_line_index, text.select_end_line_index
    return range(min(a, b), max(a, b) + 1)


def mono_font():
    """The Text Editor's font: the user's monospaced one, else the one Blender ships."""
    path = bpy.context.preferences.view.font_path_ui_mono
    if not path:
        path = os.path.join(bpy.utils.system_resource("DATAFILES", path="fonts"), "DejaVuSansMono.woff2")
    path = bpy.path.abspath(path)
    if path not in _fonts:
        fid = blf.load(path) if os.path.isfile(path) else -1
        _fonts[path] = fid if fid >= 0 else 0
    return _fonts[path]


def draw_pipes():
    space = bpy.context.space_data
    text = space.text
    if not actions.is_bn(text) or not prefs.get().pipe_symbol:
        return
    region = bpy.context.region
    lh = draw.line_height(space)
    theme = bpy.context.preferences.themes[0].text_editor
    keep = raw_lines(text)

    cells = []  # (x0, y0, x1) of each pipe's two cells
    first = 0 if space.show_word_wrap else max(0, space.top - 1)
    for row in range(first, len(text.lines)):
        _, y = draw.char_box(space, row, 0)
        if y > region.height + lh:
            continue
        if y < -lh:
            break
        if row in keep or "|>" not in text.lines[row].body:
            continue
        for col in columns(tokenize(text.lines[row].body, strict=False)):
            x0, y0 = draw.char_box(space, row, col)
            x1, y1 = draw.char_box(space, row, col + 2)
            if y1 != y0 or x0 < body_left(space, (x1 - x0) / 2):
                continue  # wrapped between `|` and `>`, or scrolled under the line numbers
            cells.append((x0, y0, x1))
    if not cells:
        return

    draw.rects([(x0, y0, x1, y0 + lh) for x0, y0, x1 in cells], (*theme.space.back, 1.0))

    fid = mono_font()
    size = round(space.font_size * bpy.context.preferences.system.ui_scale)
    blf.size(fid, size)
    blf.color(fid, *theme.space.text, 1.0)
    w = blf.dimensions(fid, SYMBOL)[0]
    # Centered between the two cells, and on the middle of `>` from the Text Editor's baseline
    _, gh = blf.dimensions(fid, ">")
    _, sh = blf.dimensions(fid, SYMBOL)
    for x0, y0, x1 in cells:
        blf.position(fid, round((x0 + x1 - w) / 2), y0 + baseline(lh, size) + round((gh - sh) / 2), 0)
        blf.draw(fid, SYMBOL)


def body_left(space, cell):
    """Left edge of the text, as the Text Editor puts it: past the line numbers and one cell."""
    if not space.show_line_numbers:
        return cell
    return cell * (len(str(len(space.text.lines))) + 3)


def baseline(lh, size):
    """Height of the text's baseline above the bottom of its line."""
    return (lh - size) // 2 + round(size * 0.2)


_handler = None


def register():
    global _handler
    _handler = bpy.types.SpaceTextEditor.draw_handler_add(draw_pipes, (), "WINDOW", "POST_PIXEL")


def unregister():
    global _handler
    if _handler is not None:
        bpy.types.SpaceTextEditor.draw_handler_remove(_handler, "WINDOW")
        _handler = None
