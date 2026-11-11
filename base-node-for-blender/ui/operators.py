import bpy

from ..lang import BnError
from . import actions


def edit_tree(context):
    space = context.space_data
    tree = getattr(space, "edit_tree", None) if space and space.type == "NODE_EDITOR" else None
    return tree if tree is not None and tree.bl_idname == "GeometryNodeTree" else None


def show_text(context, text):
    """Open the text in a Text Editor of the screen, if there is one."""
    for area in context.screen.areas if context.screen else ():
        if area.type == "TEXT_EDITOR":
            area.spaces.active.text = text
            area.tag_redraw()
            return True
    return False


class BASE_NODE_OT_text_to_tree(bpy.types.Operator):
    """Build the node trees written in this text"""
    bl_idname = "base_node.text_to_tree"
    bl_label = "Text → Tree"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == "TEXT_EDITOR" \
            and actions.is_bn(context.space_data.text)

    def execute(self, context):
        text = context.space_data.text
        try:
            trees = actions.text_to_tree(text)
        except BnError as e:
            n = len(e.diagnostics)
            self.report({"ERROR"}, f"{e.diagnostics[0]}" + (f" (+{n - 1} error(s))" if n > 1 else ""))
            return {"CANCELLED"}
        for area in context.screen.areas:
            if area.type == "NODE_EDITOR":
                area.tag_redraw()
        self.report({"INFO"}, f"{len(trees)} tree(s) built: {', '.join(t.name for t in trees)}")
        return {"FINISHED"}


class BASE_NODE_OT_format(bpy.types.Operator):
    """Rewrite this text in the canonical layout, keeping its comments"""
    bl_idname = "base_node.format"
    bl_label = "Format"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == "TEXT_EDITOR" \
            and actions.is_bn(context.space_data.text)

    def execute(self, context):
        try:
            changed = actions.format_text(context.space_data.text)
        except BnError as e:
            self.report({"ERROR"}, f"nothing formatted: {e.diagnostics[0]}")
            return {"CANCELLED"}
        self.report({"INFO"}, "text formatted" if changed else "text already formatted")
        return {"FINISHED"}


class BASE_NODE_OT_tree_to_text(bpy.types.Operator):
    """Write this node tree, and the groups it calls, as text"""
    bl_idname = "base_node.tree_to_text"
    bl_label = "Tree → Text"
    bl_options = {"REGISTER", "UNDO"}

    tree: bpy.props.StringProperty(description="Node group to write; the edited one when empty")

    @classmethod
    def poll(cls, context):
        return edit_tree(context) is not None or (context.space_data and context.space_data.type == "TEXT_EDITOR")

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree) if self.tree else edit_tree(context)
        if tree is None:
            self.report({"ERROR"}, "no Geometry Nodes tree to write")
            return {"CANCELLED"}
        text, warnings = actions.tree_to_text(tree)
        shown = show_text(context, text)
        message = f"'{tree.name}' written to {text.name}"
        if not shown:
            message += "; open it in a Text Editor"
        if warnings:
            message += f" ({len(warnings)} warning(s), see Nodes panel)"
        self.report({"WARNING"} if warnings else {"INFO"}, message)
        return {"FINISHED"}


class BASE_NODE_OT_goto(bpy.types.Operator):
    """Put the cursor on this line"""
    bl_idname = "base_node.goto"
    bl_label = "Go to Line"
    bl_options = {"INTERNAL"}

    line: bpy.props.IntProperty()
    col: bpy.props.IntProperty(default=1)

    @classmethod
    def poll(cls, context):
        return context.space_data and context.space_data.type == "TEXT_EDITOR" and context.space_data.text

    def execute(self, context):
        space = context.space_data
        space.text.cursor_set(self.line - 1, character=max(0, self.col - 1))
        space.top = max(0, self.line - 1 - space.visible_lines // 2)
        return {"FINISHED"}


class BASE_NODE_OT_add_modifier(bpy.types.Operator):
    """Add this node tree as a Geometry Nodes modifier of the active object"""
    bl_idname = "base_node.add_modifier"
    bl_label = "Add as Modifier"
    bl_options = {"REGISTER", "UNDO"}

    tree: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type in {"MESH", "CURVES", "POINTCLOUD", "VOLUME", "GREASEPENCIL"}

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree)
        if tree is None:
            return {"CANCELLED"}
        obj = context.active_object
        mod = obj.modifiers.new(tree.name, "NODES")
        mod.node_group = tree
        self.report({"INFO"}, f"modifier '{mod.name}' added to {obj.name}")
        return {"FINISHED"}


classes = (BASE_NODE_OT_text_to_tree, BASE_NODE_OT_format, BASE_NODE_OT_tree_to_text, BASE_NODE_OT_goto,
           BASE_NODE_OT_add_modifier)
