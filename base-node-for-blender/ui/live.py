"""The tree follows its text while it is typed: as soon as the text is valid, it is applied.

A timer looks at the texts of trees shown in a Text Editor. Once a changed text has
rested for a moment, it is built; a build either succeeds whole or changes nothing,
so an invalid text leaves the tree as it was and lists its errors in the sidebar.
"""

import time

import bpy

from ..lang import BnError
from . import actions, prefs

TICK = 0.25  # seconds between two looks
REST = 0.5   # a text unchanged for this long is built

_seen = {}  # text name -> (source, when it was first seen so)
_tried = {}  # text name -> the source last built, valid or not


def shown_views():
    """The view texts open in a Text Editor, with the areas that show them."""
    found = {}
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "TEXT_EDITOR":
                text = area.spaces.active.text
                if actions.is_view(text):
                    found.setdefault(text, []).append(area)
    return found


def due(name, source, now):
    """True when this source has rested long enough and was not built yet."""
    seen = _seen.get(name)
    if seen is None or seen[0] != source:
        _seen[name] = (source, now)
        return False
    return now - seen[1] >= REST and _tried.get(name) != source


def tick():
    if not prefs.get().live_apply:
        _seen.clear()
        return TICK
    now = time.monotonic()
    views = shown_views()
    for name in list(_seen):
        if name not in {t.name for t in views}:
            _seen.pop(name, None)
            _tried.pop(name, None)
    for text, areas in views.items():
        source = text.as_string()
        if actions.is_applied(text):
            _seen.pop(text.name, None)
            _tried[text.name] = source
            continue
        if not due(text.name, source, now):
            continue
        _tried[text.name] = source
        try:
            actions.apply_view(text, live=True)
        except BnError:
            pass  # the tree keeps what it had; the sidebar lists the errors
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type in {"NODE_EDITOR", "VIEW_3D"} or area in areas:
                    area.tag_redraw()
    return TICK


def register():
    bpy.app.timers.register(tick, first_interval=TICK, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    _seen.clear()
    _tried.clear()
