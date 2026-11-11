"""Base Node for Blender (base_node).

Nodes as Text (.bn) — Write and read node trees as functions.
"""

from __future__ import annotations

import sys

# Embedded core modules
from . import host, lang

# Register global aliases in sys.modules
this_module = sys.modules[__name__]
sys.modules["base_node"] = this_module
sys.modules["base_node.lang"] = lang
sys.modules["base_node.host"] = host

try:
    from . import ui
    sys.modules["base_node.ui"] = ui
except Exception:
    ui = None


def register():
    if ui is not None:
        ui.register()


def unregister():
    if ui is not None:
        ui.unregister()


__all__ = ["host", "lang", "ui", "register", "unregister"]
