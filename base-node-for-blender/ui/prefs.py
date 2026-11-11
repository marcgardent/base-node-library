from types import SimpleNamespace

import bpy

# The add-on's own package: "base_node" from the sources, "bl_ext.<repo>.base_node" once installed
ROOT = __package__.rpartition(".")[0]

KEYS = (
    ("ALT", "Alt+Space", "Free in Blender; KDE sometimes uses it for KRunner"),
    ("SHIFT", "Shift+Space", "Always free, less convenient"),
    ("CTRL", "Ctrl+Space", "Used by Blender to toggle area: only replaces it in .bn text editors"),
)

PROFILES = (
    ("auto", "Auto-Detect", "Automatically detect and validate minimal profile"),
    ("core", "core", "Pure scalar and vector math (universal)"),
    ("sdf2d", "sdf2d", "2D spatial distance fields"),
    ("vector2d", "vector2d", "2D vector curves, shapes, and meshes (SVG-like)"),
    ("ink2d", "ink2d", "2D living ink, Grease Pencil 3 strokes and dynamics"),
    ("blender-geometry", "blender-geometry", "Full Blender Geometry Nodes host profile"),
)

HIGHLIGHT_MODES = (
    ("standard", "Standard Syntax", "Classic syntax highlighting"),
    ("origin", "Origin (Stdlib vs Local)", "Differentiate standard library modules and namespaces from local graphs"),
    ("portability", "Portability Linter", "Highlight host-specific or non-portable nodes"),
)

# When the add-on runs from the sources (tests), it has no preferences entry
DEFAULTS = SimpleNamespace(
    complete_key="ALT", auto_complete=True, highlight=True,
    target_profile="auto", highlight_mode="standard",
    color_stdlib=(0.0, 0.78, 0.65), color_local=(0.95, 0.75, 0.20), color_warning=(0.95, 0.30, 0.25)
)


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

    # Syntax Highlighting & Portability Profiles
    target_profile: bpy.props.EnumProperty(
        name="Target Profile", items=PROFILES, default="auto",
        description="Target profile for portability and live checking")
    highlight_mode: bpy.props.EnumProperty(
        name="Highlight Mode", items=HIGHLIGHT_MODES, default="standard",
        description="Syntax coloring scheme and namespace visualization")
    color_stdlib: bpy.props.FloatVectorProperty(
        name="Stdlib / Namespace", subtype="COLOR", size=3, default=(0.0, 0.78, 0.65), min=0.0, max=1.0,
        description="Highlight color for standard library modules and namespaces (ink2d::, math::)")
    color_local: bpy.props.FloatVectorProperty(
        name="Local Graphs", subtype="COLOR", size=3, default=(0.95, 0.75, 0.20), min=0.0, max=1.0,
        description="Highlight color for user-defined local graphs")
    color_warning: bpy.props.FloatVectorProperty(
        name="Non-Portable / Warning", subtype="COLOR", size=3, default=(0.95, 0.30, 0.25), min=0.0, max=1.0,
        description="Highlight color for nodes outside the selected target profile")

    def draw(self, context):
        layout = self.layout

        box_edit = layout.box()
        box_edit.label(text="Editor & Suggestions", icon="TEXT")
        box_edit.prop(self, "complete_key")
        box_edit.prop(self, "auto_complete")
        box_edit.prop(self, "highlight")

        box_color = layout.box()
        box_color.label(text="Syntax Coloring & Portability Profiles", icon="COLOR")
        box_color.prop(self, "target_profile")
        box_color.prop(self, "highlight_mode")
        if self.highlight:
            col = box_color.column(align=True)
            col.prop(self, "color_stdlib")
            col.prop(self, "color_local")
            col.prop(self, "color_warning")

        layout.label(text="Ctrl+Enter builds the tree from text.", icon="INFO")


classes = (BaseNodePreferences,)
