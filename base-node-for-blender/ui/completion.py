"""Suggestions under the cursor of a .bn text.

The operator is modal: it keeps the popup open while the word is typed,
refreshes it on a timer, and takes ↑ ↓ Tab Enter Esc. Every other key goes
through to the Text Editor. A watcher opens it after `(` `,` `.` `:` or `#`,
even with spaces typed after it.

Inside a call, the prototype of the call shows under the line: its inputs,
those already given dimmed and the one being written lit, then its outputs.
"""

import blf
import bpy

from ..host import BlenderSchema, modules
from ..lang.complete import OPENERS, complete, product_sign, signature
from . import actions, draw, prefs
from .highlight import COLORS, SOCKETS, rgb

ROWS = 10
WATCH = 0.1
TYPED = 4  # keys typed between two ticks that still count as typing


class Popup:
    """What the draw callback shows; the operator itself may be gone when it runs."""
    text = None  # Text being completed, or None when closed
    line = 0     # 1-based
    start = 0    # 1-based column of the word being replaced
    items = ()
    selected = 0
    seen = None  # (line, column, body) at the last refresh


def cursor_state(text):
    return text.current_line_index, text.current_character, text.current_line.body


def refresh(text, asked=False):
    """Suggestions at the cursor of the text; False, and closed, when there are none."""
    line, col = text.current_line_index + 1, text.current_character + 1
    with BlenderSchema() as schema:
        Popup.start, items = complete(text.as_string(), line, col, schema, modules.load, asked)
    Popup.line, Popup.items = line, items
    Popup.selected = min(Popup.selected, len(items) - 1) if items else 0
    Popup.text = text if items else None
    Popup.seen = cursor_state(text)
    return bool(items)


def accept(context):
    """Write the selected item in place of the word; True when suggestions follow it."""
    item = Popup.items[Popup.selected]
    text = Popup.text
    row = Popup.line - 1
    text.select_set(row, Popup.start - 1, row, text.current_character)
    bpy.ops.text.insert(text=item.insert)
    # A call or a prop has more to say right after: its inputs, its values
    if item.insert.endswith("(") or item.kind == "prop":
        Popup.selected = 0
        return refresh(text)
    close()
    return False


def close():
    Popup.text, Popup.items, Popup.selected, Popup.seen = None, (), 0, None


class BASE_NODE_OT_complete(bpy.types.Operator):
    """Suggest nodes, inputs, outputs and values at the cursor"""
    bl_idname = "base_node.complete"
    bl_label = "Suggestions"

    auto: bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space and space.type == "TEXT_EDITOR" and actions.is_bn(space.text)

    def invoke(self, context, event):
        text = context.space_data.text
        if Popup.text is not None or text.current_line_index != text.select_end_line_index \
                or text.current_character != text.select_end_character:
            return {"CANCELLED"}
        if not refresh(text, asked=not self.auto):
            return {"CANCELLED"}
        if not self.auto and len(Popup.items) == 1 and text.current_character + 1 > Popup.start:
            if not accept(context):
                return self.finish(context, {"FINISHED"})
        self.timer = context.window_manager.event_timer_add(WATCH, window=context.window)
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def finish(self, context, result):
        close()
        if getattr(self, "timer", None):
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        if context.area:
            context.area.tag_redraw()
        return result

    def modal(self, context, event):
        space = context.space_data
        text = Popup.text
        if text is None or space is None or getattr(space, "text", None) != text:
            return self.finish(context, {"CANCELLED", "PASS_THROUGH"})
        context.area.tag_redraw()
        t, press = event.type, event.value == "PRESS"
        plain = not (event.ctrl or event.alt or event.oskey)

        if press and plain and t in {"UP_ARROW", "DOWN_ARROW", "PAGE_UP", "PAGE_DOWN"}:
            step = {"UP_ARROW": -1, "DOWN_ARROW": 1, "PAGE_UP": -ROWS, "PAGE_DOWN": ROWS}[t]
            Popup.selected = max(0, min(len(Popup.items) - 1, Popup.selected + step))
            return {"RUNNING_MODAL"}
        if press and plain and t in {"TAB", "RET", "NUMPAD_ENTER"}:
            return {"RUNNING_MODAL"} if accept(context) else self.finish(context, {"FINISHED"})
        if press and t == "ESC":
            return self.finish(context, {"CANCELLED"})
        if press and t in {"LEFTMOUSE", "RIGHTMOUSE", "MIDDLEMOUSE"} or t == "WINDOW_DEACTIVATE":
            return self.finish(context, {"CANCELLED", "PASS_THROUGH"})
        if press and event.unicode == " " and text.current_character + 1 == Popup.start:
            # `, ` or `: ` before the word: the same suggestions follow the space
            return {"PASS_THROUGH"}
        if press and event.unicode and not (event.unicode.isalnum() or event.unicode == "_"):
            # The word is over; the watcher reopens after ( . :
            return self.finish(context, {"CANCELLED", "PASS_THROUGH"})
        if t == "TIMER":
            state = cursor_state(text)
            if state != Popup.seen:
                if state[0] != Popup.line - 1 or state[1] + 1 < Popup.start or not refresh(text):
                    return self.finish(context, {"CANCELLED", "PASS_THROUGH"})
        return {"PASS_THROUGH"}


def draw_overlay():
    space = bpy.context.space_data
    try:
        text = space.text
        if not actions.is_bn(text):
            return
    except ReferenceError:
        return  # the text was freed with its file
    # The prototype sticks to the line; the suggestions go past it
    below, above = draw_hint(space)
    if Popup.text == text:
        draw_popup(space, below, above)


# The inputs of the call stand apart from every other suggestion
ARGUMENT = (1.00, 0.50, 0.72)
KIND_COLORS = {
    "input": ARGUMENT, "prop": ARGUMENT, "enum": COLORS["literal"], "keyword": COLORS["keyword"],
    "node": COLORS["node"], "function": COLORS["function"], "graph": COLORS["local_func"],
}


class Look:
    """Sizes and colors of the Text Editor, for one draw."""

    def __init__(self, space):
        self.lh = draw.line_height(space)
        self.scale = bpy.context.preferences.system.ui_scale
        self.size = round(space.font_size * self.scale)
        self.pad = round(4 * self.scale)
        self.region = bpy.context.region
        self.theme = bpy.context.preferences.themes[0].text_editor
        self.fg = tuple(self.theme.space.text)

    def baseline(self, top, n):
        """Of the text on row n of a box whose top is at `top`."""
        return top - self.pad - self.lh * (n + 1) + (self.lh - self.size) // 2 + round(2 * self.scale)

    def box(self, x, top, width, height, shade, border):
        back = self.theme.space.back
        draw.rects([(x - 1, top - height - 1, x + width + 1, top + 1)], (*self.fg, border))
        draw.rects([(x, top - height, x + width, top)], (*(c * shade for c in back), 0.97))

    def kind(self, item):
        """Color of an item's label: by kind, a type by its socket, a color by itself."""
        if item.kind == "type":
            return SOCKETS.get(item.label, self.fg)
        if item.kind == "color":
            return rgb(item.detail[1:]) or self.fg
        return KIND_COLORS.get(item.kind, self.fg)

    def type(self, name):
        return SOCKETS.get(name, self.fg)


def draw_popup(space, gap_below=0, gap_above=0):
    """The suggestions, past the room the prototype took on either side of the line."""
    k = Look(space)
    lh, pad, region = k.lh, k.pad, k.region
    x, y = draw.char_box(space, Popup.line - 1, Popup.start - 1)

    items = Popup.items
    # Under the line when it fits, else on the side with more room, fewer rows if need be
    below, above = y - pad - gap_below, region.height - (y + lh) - gap_above
    wanted = lh * (min(ROWS, len(items)) + (len(items) > ROWS)) + pad * 2
    under = wanted <= below or below >= above
    room = max(1, int(((below if under else above) - pad * 2) // lh))
    rows = min(ROWS, room, len(items))
    if len(items) > rows:
        rows = max(1, min(rows, room - 1))  # a last row says where the selection is
    more = len(items) > rows
    first = max(0, min(Popup.selected - rows // 2, len(items) - rows))
    shown = items[first:first + rows]
    blf.size(0, k.size)
    mark = round(3 * k.scale)  # the bar of color left of each label
    label_w = max(blf.dimensions(0, i.label)[0] for i in shown)
    detail_w = max((blf.dimensions(0, i.detail)[0] for i in shown if i.detail), default=0)
    width = mark + label_w + detail_w + pad * (7 if detail_w else 3)
    height = lh * (len(shown) + more) + pad * 2

    top = y - pad - gap_below if under else y + lh + gap_above + height
    top = max(height, min(top, region.height))  # never out of the editor, even scrolled away
    x = max(0, min(x - pad, region.width - width))
    k.box(x, top, width, height, 0.8, 0.35)
    row = Popup.selected - first
    draw.rects([(x, top - pad - lh * (row + 1), x + width, top - pad - lh * row)], (*k.theme.selected_text, 1.0))

    for n, item in enumerate(shown):
        color = k.kind(item)
        row_top = top - pad - lh * n
        draw.rects([(x + pad, row_top - lh + pad, x + pad + mark, row_top - pad)], (*color, 1.0))
        is_arg = item.kind in ("input", "prop")
        if n and not is_arg and shown[n - 1].kind in ("input", "prop"):
            # Where the inputs of the call end and the rest begins
            draw.rects([(x + pad, row_top, x + width - pad, row_top + 1)], (*k.fg, 0.3))
        blf.color(0, *(color if is_arg or item.kind in ("enum", "keyword") else k.fg), 1.0)
        blf.position(0, x + pad * 2 + mark, k.baseline(top, n), 0)
        blf.draw(0, item.label)
        if item.detail:
            blf.color(0, *(k.type(item.detail) if item.detail in SOCKETS else k.fg), 0.7)
            blf.position(0, x + width - pad - blf.dimensions(0, item.detail)[0], k.baseline(top, n), 0)
            blf.draw(0, item.detail)
    if more:
        blf.color(0, *k.fg, 0.55)
        note = f"{Popup.selected + 1}/{len(items)}"
        blf.position(0, x + width - pad - blf.dimensions(0, note)[0], k.baseline(top, len(shown)), 0)
        blf.draw(0, note)


def draw_hint(space):
    """The prototype of the call the cursor is in, just under the line (over it without room).

    (room taken under the line, room taken over it)."""
    text = space.text
    hint = _hints.get(text.name)
    if not hint or hint[1] is None or hint[0][0] != text.current_line_index:
        return 0, 0
    sig = hint[1]
    k = Look(space)
    lh, pad, region, fg = k.lh, k.pad, k.region, k.fg
    punct = (*fg, 0.6)

    # (text, color, lit): lit is the input being written, on the selection color
    parts = [(sig.name + "(", punct, False)]
    for n, (name, ty, state) in enumerate(sig.inputs):
        alpha = 0.35 if state == "given" else 1.0
        parts.append((name, (*ARGUMENT, alpha), state == "current"))
        parts.append((": ", (*fg, alpha * 0.6), False))
        parts.append((ty, (*k.type(ty), alpha * 0.85), False))
        if n + 1 < len(sig.inputs):
            parts.append((", ", punct, False))
    parts.append((")", punct, False))
    if sig.outputs:
        parts.append((" -> " + ("(" if len(sig.outputs) > 1 else ""), punct, False))
        for n, (name, ty) in enumerate(sig.outputs):
            if len(sig.outputs) > 1:
                parts.append((name + ": ", (*fg, 0.8), False))
            parts.append((ty + (", " if n + 1 < len(sig.outputs) else ""), (*k.type(ty), 0.85), False))
        if len(sig.outputs) > 1:
            parts.append((")", punct, False))

    # On as many rows as the editor's width asks, cutting after a comma or before the arrow
    blf.size(0, k.size)
    widest = max(lh, region.width - pad * 4)
    rows, w, chunk = [[]], 0, []
    for part in parts + [None]:
        if part is not None and not (part[0].endswith(", ") or part[0].startswith(" -> ")):
            chunk.append(part)
            continue
        if part is not None and part[0].endswith(", "):
            chunk.append(part)
        cw = sum(blf.dimensions(0, c[0])[0] for c in chunk)
        if w and w + cw > widest:
            rows.append([])
            w = 0
        for c in chunk:
            rows[-1].append((w, *c))
            w += blf.dimensions(0, c[0])[0]
        chunk = [part] if part is not None and part[0].startswith(" -> ") else []
    width = max(dx + blf.dimensions(0, p)[0] for row in rows for dx, p, _c, _l in row[-1:]) + pad * 2
    height = lh * len(rows) + pad * 2

    x, _ = draw.char_box(space, text.current_line_index, max(0, sig.col - 1))
    _, y = draw.char_box(space, text.current_line_index, 0)
    under = height <= y - pad or y - pad >= region.height - (y + lh)
    top = y - pad if under else y + lh + height
    top = max(height, min(top, region.height))
    x = max(0, min(x - pad, region.width - width))
    k.box(x, top, width, height, 0.9, 0.2)
    for n, row in enumerate(rows):
        for dx, part, color, lit in row:
            if lit:
                x0 = x + pad + dx
                draw.rects([(x0 - 2, top - pad - lh * (n + 1), x0 + blf.dimensions(0, part)[0] + 2,
                             top - pad - lh * n)], (*k.theme.selected_text, 1.0))
            blf.color(0, *color)
            blf.position(0, x + pad + dx, k.baseline(top, n), 0)
            blf.draw(0, part)
    return (height + 1, 0) if under else (0, height + 1)


# The watcher: one (line, column, body length) per text name, from the last tick
_typed = {}
# The prototype under the line: per text name, the cursor state it was read at and its Signature
_hints = {}


def read_hint(text, area):
    """The Signature at the cursor of the text, read again when the cursor or its line changed."""
    state = cursor_state(text)
    old = _hints.get(text.name)
    if old and old[0] == state:
        return
    sig = None
    selecting = text.current_line_index != text.select_end_line_index \
        or text.current_character != text.select_end_character
    if prefs.get().signature and not selecting:
        try:
            with BlenderSchema() as schema:
                sig = signature(text.as_string(), state[0] + 1, state[1] + 1, schema, modules.load)
        except Exception:  # a timer that raises is unregistered: no prototype is better than no watcher
            sig = None
    _hints[text.name] = (state, sig)
    if sig != (old[1] if old else None):
        area.tag_redraw()


def watch():
    wm = bpy.context.window_manager
    if wm is None:
        return WATCH
    if Popup.text is not None:
        # A popup left over by an operator that did not end itself (file loaded, area closed)
        if not any(op.bl_idname == "BASE_NODE_OT_complete" for w in wm.windows for op in w.modal_operators):
            close()
    seen = set()
    for window in wm.windows:
        for area in window.screen.areas if window.screen else ():
            if area.type != "TEXT_EDITOR":
                continue
            text = area.spaces.active.text
            if not actions.is_bn(text) or text.name in seen:
                continue
            seen.add(text.name)
            read_hint(text, area)
            body = text.current_line.body
            now = (text.current_line_index, text.current_character, len(body))
            # Kept while a popup is open too: the key that closes it may be an opener
            last = _typed.get(text.name)
            _typed[text.name] = now
            if Popup.text is not None or not last or now[0] != last[0]:
                continue
            n = now[1] - last[1]
            if not 1 <= n <= TYPED or now[2] - last[2] != n:
                continue  # not a few keys typed on the line: a move, a paste, a deletion
            region = next(r for r in area.regions if r.type == "WINDOW")
            swap = product_sign(body[:now[1]]) if n == 1 else None
            if swap:
                swap_sign(text, window, area, region, *swap)
                return WATCH
            # `,` `:` … just typed, maybe followed by spaces typed in the same tick
            before = body[:now[1]].rstrip(" ")
            if prefs.get().auto_complete and len(before) > last[1] and before[-1:] in OPENERS:
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.base_node.complete("INVOKE_DEFAULT", auto=True)
                return WATCH
    return WATCH


def swap_sign(text, window, area, region, start, end, sign):
    """`n dot ` becomes `n ⋅ ` as it is typed; one undo step brings the word back."""
    row = text.current_line_index
    with bpy.context.temp_override(window=window, area=area, region=region):
        text.select_set(row, start, row, end)
        bpy.ops.text.insert("EXEC_DEFAULT", True, text=sign)
        text.cursor_set(row, character=start + len(sign) + 1)
    _typed[text.name] = (row, text.current_character, len(text.current_line.body))


classes = (BASE_NODE_OT_complete,)
_handler = None


def register():
    global _handler
    _handler = bpy.types.SpaceTextEditor.draw_handler_add(draw_overlay, (), "WINDOW", "POST_PIXEL")
    bpy.app.timers.register(watch, first_interval=WATCH, persistent=True)


def unregister():
    global _handler
    if bpy.app.timers.is_registered(watch):
        bpy.app.timers.unregister(watch)
    if _handler is not None:
        bpy.types.SpaceTextEditor.draw_handler_remove(_handler, "WINDOW")
        _handler = None
    close()
    _typed.clear()
    _hints.clear()
