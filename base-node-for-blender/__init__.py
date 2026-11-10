"""Base Node for Blender (base_node / bnodes).

Nodes as Text (.bn) — Écrit et relit les arbres de nœuds comme des fonctions.
"""

from __future__ import annotations

import sys

# Modules cœurs embarqués
from . import host, lang

# Enregistrement des alias globaux dans sys.modules
this_module = sys.modules[__name__]
sys.modules["base_node"] = this_module
sys.modules["base_node.lang"] = lang
sys.modules["base_node.host"] = host

sys.modules["bnodes"] = this_module
sys.modules["bnodes.lang"] = lang
sys.modules["bnodes.host"] = host

try:
    from . import ui
    sys.modules["base_node.ui"] = ui
    sys.modules["bnodes.ui"] = ui
except Exception:
    ui = None


def register():
    if ui is not None:
        ui.register()


def unregister():
    if ui is not None:
        ui.unregister()


__all__ = ["host", "lang", "ui", "register", "unregister"]
