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
    # Ctrl+Tab flips an area between a tree and its text, on every keyboard layout (Ctrl+` was ² on AZERTY)
    _items.append((km, km.keymap_items.new("base_node.toggle_view", "TAB", "PRESS", ctrl=True)))
    # Ctrl+Shift+A formats the text (Cmd+Shift+A on macOS); free in the Text Editor
    mac = sys.platform == "darwin"
    _items.append((km, km.keymap_items.new("base_node.format", "A", "PRESS", shift=True, ctrl=not mac, oskey=mac)))
    km = kc.keymaps.new("Node Editor", space_type="NODE_EDITOR")
    # In place of Blender's Ctrl+Tab that leaves a group: Tab still does
    _items.append((km, km.keymap_items.new("base_node.toggle_view", "TAB", "PRESS", ctrl=True)))
    # Ctrl+Shift+A arranges the nodes, as Node Arrange did; the same keys format a text
    _items.append((km, km.keymap_items.new("base_node.arrange", "A", "PRESS", shift=True, ctrl=not mac, oskey=mac)))


def shortcut(keymap, idname):
    """The keys of an operator as the user has them, short: "Ctrl ⏎", or "" when it has none."""
    wm = bpy.context.window_manager
    for kc in (wm.keyconfigs.user, wm.keyconfigs.addon):
        km = kc.keymaps.get(keymap) if kc else None
        for kmi in km.keymap_items if km else ():
            if kmi.idname == idname and kmi.active:
                return kmi.to_string(compact=True)
    return ""


def unbind():
    for km, kmi in _items:
        km.keymap_items.remove(kmi)
    _items.clear()
