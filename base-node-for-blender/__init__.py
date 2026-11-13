"""Base Node for Blender (base_node).

Nodes as Text (.bn) — Write and read node trees as functions.

The add-on lives under its extension package (bl_ext.<repo>.base_node) and adds
no top-level module: Blender reports those as a policy violation, and a global
`base_node` would shadow the Python package of the same name.
"""

from __future__ import annotations

# Embedded core modules
from . import host, lang

try:
    from . import ui
except Exception:
    ui = None


def register():
    if ui is not None:
        ui.register()


def unregister():
    if ui is not None:
        ui.unregister()


__all__ = ["host", "lang", "ui", "register", "unregister"]
