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
        col.operator("base_node.text_to_tree", icon="NODETREE")
        col.operator("base_node.format", text="Format", icon="ALIGN_LEFT")
        layout.prop(context.window_manager, "base_node_sync")
        options = prefs.get()
        if isinstance(options, bpy.types.AddonPreferences):
            row = layout.row(align=True)
            row.prop(options, "highlight", toggle=True)
            row.prop(options, "auto_complete", text="Auto Suggestions", toggle=True)

        trees = actions.linked_trees(text)
        if trees:
            box = layout.box()
            box.label(text="Linked Trees")
            for tree in trees:
                row = box.row(align=True)
                row.label(text=tree.name, icon="GEOMETRY_NODES")
                if tree.is_modifier:
                    row.operator("base_node.add_modifier", text="", icon="MODIFIER").tree = tree.name
                row.operator("base_node.tree_to_text", text="", icon="TEXT").tree = tree.name

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
        tree = edit_tree(context)
        layout.operator("base_node.tree_to_text", text="Open as Text", icon="TEXT")
        if tree.base_node_text:
            layout.label(text=f"Text: {tree.base_node_text.name}", icon="LINKED")
        layout.prop(context.window_manager, "base_node_sync")


classes = (TEXT_PT_base_node, NODE_PT_base_node)
