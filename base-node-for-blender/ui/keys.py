"""Shortcuts of the Text and Node Editors; the operators' polls let other texts and trees through."""

import sys

import bpy

from . import prefs

_items = []


def bind():
    unbind()
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return  # no add-on keyconfig in background mode
    km = kc.keymaps.new("Text", space_type="TEXT_EDITOR")
    # Ctrl+Enter applies the text to its tree; Alt+P stays Python's
    _items.append((km, km.keymap_items.new("base_node.apply_view", "RET", "PRESS", ctrl=True)))
    mod = prefs.get().complete_key
    _items.append((km, km.keymap_items.new("base_node.complete", "SPACE", "PRESS",
                                           alt=mod == "ALT", shift=mod == "SHIFT", ctrl=mod == "CTRL")))
    # Ctrl+` flips an area between a tree and its text; free in both editors
    _items.append((km, km.keymap_items.new("base_node.toggle_view", "ACCENT_GRAVE", "PRESS", ctrl=True)))
    # Ctrl+Shift+A formats the text (Cmd+Shift+A on macOS); free in the Text Editor
    mac = sys.platform == "darwin"
    _items.append((km, km.keymap_items.new("base_node.format", "A", "PRESS", shift=True, ctrl=not mac, oskey=mac)))
    km = kc.keymaps.new("Node Editor", space_type="NODE_EDITOR")
    _items.append((km, km.keymap_items.new("base_node.toggle_view", "ACCENT_GRAVE", "PRESS", ctrl=True)))
    # Ctrl+Shift+A arranges the nodes, as Node Arrange did; the same keys format a text
    _items.append((km, km.keymap_items.new("base_node.arrange", "A", "PRESS", shift=True, ctrl=not mac, oskey=mac)))


def unbind():
    for km, kmi in _items:
        km.keymap_items.remove(kmi)
    _items.clear()
