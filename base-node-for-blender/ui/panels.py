import bpy

from . import actions, prefs
from .operators import edit_tree


class TEXT_PT_base_node(bpy.types.Panel):
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "Nodes"
    bl_label = "Nodes as Text"

    @classmethod
    def poll(cls, context):
        return actions.is_bn(context.space_data.text)

    def draw(self, context):
        layout = self.layout
        text = context.space_data.text
        col = layout.column(align=True)
        tree = actions.view_tree(text)
        if actions.is_view(text):
            row = col.row(align=True)
            row.operator("base_node.apply_view", icon="FILE_REFRESH")
            if tree is not None and tree.is_modifier:
                row.operator("base_node.add_modifier", text="", icon="MODIFIER").tree = tree.name
            col.operator("base_node.toggle_view", text="Back to Nodes", icon="NODETREE")
        col.operator("base_node.format", text="Format", icon="ALIGN_LEFT")
        options = prefs.get()
        if isinstance(options, bpy.types.AddonPreferences):
            row = layout.row(align=True)
            row.prop(options, "highlight", toggle=True)
            row.prop(options, "auto_complete", text="Auto Suggestions", toggle=True)

            box_prof = layout.box()
            box_prof.label(text="Target Profile & Linter", icon="PREFERENCES")
            box_prof.prop(options, "target_profile", text="Profile")
            box_prof.prop(options, "highlight_mode", text="Highlight")

            from ..lang.parser import parse
            from ..lang.profiles import check_profile, solve_minimal_profile
            try:
                ast_file = parse(text.as_string(), text.name)
                min_prof = solve_minimal_profile(ast_file)
                box_prof.label(text=f"Detected: {min_prof}", icon="INFO")
                if options.target_profile != "auto":
                    errs = check_profile(ast_file, profile=options.target_profile)
                    if not errs:
                        box_prof.label(text=f"✓ Compatible with '{options.target_profile}'", icon="CHECKMARK")
                    else:
                        box_prof.label(text=f"⚠ {len(errs)} barrier(s) for '{options.target_profile}':", icon="ERROR")
                        col_e = box_prof.column(align=True)
                        for e in errs[:3]:
                            col_e.label(text=f"• {e}")
            except Exception:
                pass

        diags = actions.DIAGNOSTICS.get(text.name)
        if diags:
            box = layout.box()
            box.label(text=f"{len(diags)} error(s)", icon="ERROR")
            for d in diags:
                op = box.operator("base_node.goto", text=f"{d.line}:{d.col}  {d.message}", emboss=False)
                op.line, op.col = d.line, d.col

        warnings = actions.WARNINGS.get(text.name)
        if warnings:
            box = layout.box()
            box.label(text=f"{len(warnings)} export warning(s)", icon="INFO")
            for w in warnings:
                box.label(text=w)


class NODE_PT_base_node(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Text"
    bl_label = "Nodes as Text"

    @classmethod
    def poll(cls, context):
        return edit_tree(context) is not None

    def draw(self, context):
        layout = self.layout
        layout.operator("base_node.toggle_view", text="Edit as Text", icon="TEXT")


classes = (TEXT_PT_base_node, NODE_PT_base_node)
