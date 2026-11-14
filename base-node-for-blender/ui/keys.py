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
    mac = sys.platform == "darwin"
    # Alt+P applies a .bn text to its tree, as it runs a Python script; other texts still run
    _items.append((km, km.keymap_items.new("base_node.apply_view", "P", "PRESS", alt=True)))
    mod = prefs.get().complete_key
    _items.append((km, km.keymap_items.new("base_node.complete", "SPACE", "PRESS",
                                           alt=mod == "ALT", shift=mod == "SHIFT", ctrl=mod == "CTRL")))
    # Ctrl+Tab flips an area between a tree and its text, on every keyboard layout (Ctrl+` was ² on AZERTY)
    _items.append((km, km.keymap_items.new("base_node.toggle_view", "TAB", "PRESS", ctrl=True)))
    # Ctrl+Shift+A formats the text (Cmd+Shift+A on macOS); free in the Text Editor
    _items.append((km, km.keymap_items.new("base_node.format", "A", "PRESS", shift=True, ctrl=not mac, oskey=mac)))
    km = kc.keymaps.new("Node Editor", space_type="NODE_EDITOR")
    # Inside a group, Ctrl+Tab still leaves it; from the top tree, it goes on to the text
    kmi = km.keymap_items.new("base_node.toggle_view", "TAB", "PRESS", ctrl=True)
    kmi.properties.leave_groups = True
    _items.append((km, kmi))
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
