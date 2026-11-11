from types import SimpleNamespace

import bpy

# The add-on's own package: "base_node" from the sources, "bl_ext.<repo>.base_node" once installed
ROOT = __package__.rpartition(".")[0]

KEYS = (
    ("ALT", "Alt+Space", "Free in Blender; KDE sometimes uses it for KRunner"),
    ("SHIFT", "Shift+Space", "Always free, less convenient"),
    ("CTRL", "Ctrl+Space", "Used by Blender to toggle area: only replaces it in .bn text editors"),
)

# When the add-on runs from the sources (tests), it has no preferences entry
DEFAULTS = SimpleNamespace(complete_key="ALT", auto_complete=True, highlight=True)


def get():
    addon = bpy.context.preferences.addons.get(ROOT)
    return addon.preferences if addon else DEFAULTS


def update_keys(self, context):
    from . import keys
    keys.bind()


class BaseNodePreferences(bpy.types.AddonPreferences):
    bl_idname = ROOT

    complete_key: bpy.props.EnumProperty(
        name="Suggestions", items=KEYS, default="ALT", update=update_keys,
        description="Shortcut that opens suggestions in a .bn text editor")
    auto_complete: bpy.props.BoolProperty(
        name="Open after ( . :", default=True,
        description="Suggestions open automatically after a parenthesis, period, or colon")
    highlight: bpy.props.BoolProperty(
        name="Highlight", default=True,
        description="Highlight keywords, nodes, types, and values in .bn text files")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "complete_key")
        layout.prop(self, "auto_complete")
        layout.prop(self, "highlight")
        layout.label(text="Ctrl+Enter builds the tree from text.", icon="INFO")


classes = (BaseNodePreferences,)
