import os

import bpy
from bpy_extras.io_utils import ImportHelper

from ..host import comments
from ..host.arrange import arrange_nodes
from ..lang import BnError
from . import actions, prefs


def edit_tree(context):
    space = context.space_data
    tree = getattr(space, "edit_tree", None) if space and space.type == "NODE_EDITOR" else None
    return tree if tree is not None and tree.bl_idname == "GeometryNodeTree" else None


def report_error(op, e):
    n = len(e.diagnostics)
    op.report({"ERROR"}, f"{e.diagnostics[0]}" + (f" (+{n - 1} error(s))" if n > 1 else ""))


class BASE_NODE_OT_apply_view(bpy.types.Operator):
    """Write this text into its node tree, and keep editing it"""
    bl_idname = "base_node.apply_view"
    bl_label = "Apply to Tree"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Every .bn text: Alt+P must not run one as Python
        space = context.space_data
        return space and space.type == "TEXT_EDITOR" and actions.is_bn(space.text)

    def execute(self, context):
        text = context.space_data.text
        if not actions.is_view(text):
            self.report({"WARNING"}, "Not the text of a tree: Alt+Z in a Node Editor shows one")
            return {"CANCELLED"}
        try:
            tree = actions.apply_view(text)
        except BnError as e:
            report_error(self, e)
            return {"CANCELLED"}
        for area in context.screen.areas:
            if area.type in {"NODE_EDITOR", "VIEW_3D"}:
                area.tag_redraw()
        self.report({"INFO"}, f"'{tree.name}' built" if tree else "nothing built")
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


class BASE_NODE_OT_toggle_view(bpy.types.Operator):
    """Show this area's node tree as text, or the text back as its node tree.
    The tree stays the only data: the text is written back into it, then removed"""
    bl_idname = "base_node.toggle_view"
    bl_label = "Nodes ↔ Text"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space and space.type == "TEXT_EDITOR":
            return actions.is_view(space.text)
        return edit_tree(context) is not None

    def execute(self, context):
        area = context.area
        if area.type == "TEXT_EDITOR":
            return self.to_nodes(area)
        return self.to_text(context, area)

    def to_text(self, context, area):
        tree = edit_tree(context)
        text, warnings = actions.open_view(tree)
        area.type = "TEXT_EDITOR"
        space = area.spaces.active
        space.text = text
        space.top = 0
        if warnings:
            self.report({"WARNING"}, f"{len(warnings)} export warning(s), see Nodes panel")
        return {"FINISHED"}

    def to_nodes(self, area):
        text = area.spaces.active.text
        try:
            tree = actions.close_view(text)
        except BnError as e:
            report_error(self, e)
            return {"CANCELLED"}
        area.type = "NODE_EDITOR"
        space = area.spaces.active
        if tree is not None and space.edit_tree != tree:
            space.tree_type = tree.bl_idname
            space.node_tree = tree
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


class BASE_NODE_OT_import(bpy.types.Operator, ImportHelper):
    """Build the node trees of .bn files; their `use` lines also find modules next to them"""
    bl_idname = "base_node.import_bn"
    bl_label = "Import Base Node (.bn)"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    filename_ext = ".bn"
    filter_glob: bpy.props.StringProperty(default="*.bn", options={"HIDDEN"})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        names = [f.name for f in self.files if f.name] or [os.path.basename(self.filepath)]
        folder = self.directory or os.path.dirname(self.filepath)
        built, failed = [], []
        for name in names:
            path = os.path.join(folder, name)
            try:
                built += actions.import_file(path)
            except BnError as e:
                failed.append(name)
                n = len(e.diagnostics)
                self.report({"ERROR"}, f"{e.diagnostics[0]}" + (f" (+{n - 1} error(s))" if n > 1 else ""))
            except OSError as e:
                failed.append(name)
                self.report({"ERROR"}, f"{name}: {e.strerror}")
        if not built:
            return {"CANCELLED"}
        message = f"{len(built)} tree(s) imported from {len(names) - len(failed)} file(s)"
        if failed:
            message += f"; failed: {', '.join(failed)}"
        self.report({"WARNING"} if failed else {"INFO"}, message)
        return {"FINISHED"}


class BASE_NODE_OT_arrange(bpy.types.Operator):
    """Lay out the selected nodes, or all of them when none is: links go left to right,
    in line with their sockets, and each frame keeps its nodes together"""
    bl_idname = "base_node.arrange"
    bl_label = "Arrange Nodes"
    bl_options = {"REGISTER", "UNDO"}

    spacing: bpy.props.IntVectorProperty(name="Spacing", size=2, default=(50, 50), min=0, subtype="XYZ",
                                         description="Room between two columns, then between two nodes of a column")

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space is not None and space.type == "NODE_EDITOR" and space.edit_tree is not None

    def execute(self, context):
        tree = context.space_data.edit_tree
        nodes = [n for n in tree.nodes if n.select] or list(tree.nodes)
        # A node never drawn has no size yet: draw once, so that the layout uses the real ones
        if context.window and any(not n.dimensions.y for n in nodes if n.bl_idname not in {"NodeFrame", "NodeReroute"}):
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=0)
        # Room for the comments drawn over the nodes, when they are
        room = comments.room if prefs.get().show_comments else None
        count = arrange_nodes(tree, nodes, spacing=self.spacing, room=room)
        if not count:
            self.report({"WARNING"}, "no node to arrange")
            return {"CANCELLED"}
        return {"FINISHED"}


# A comment the dialog shows: its lines so far, then an empty one to write the next
MAX_LINES = 24


class BaseNodeCommentLine(bpy.types.PropertyGroup):
    body: bpy.props.StringProperty(name="Line", description="One line of the comment")


class BASE_NODE_OT_edit_comment(bpy.types.Operator):
    """Write the comment shown over the active node. The text gives it back as `//` lines before
    the node's statement"""
    bl_idname = "base_node.edit_comment"
    bl_label = "Edit Comment"
    bl_options = {"REGISTER", "UNDO"}

    lines: bpy.props.CollectionProperty(type=BaseNodeCommentLine)

    @classmethod
    def poll(cls, context):
        tree = edit_tree(context)
        node = tree.nodes.active if tree is not None else None
        if node is None or node.bl_idname in comments.UNWRITTEN:
            cls.poll_message_set("Select a node that has a statement in the text: "
                                 "not a Group Input, a reroute or a zone's input")
            return False
        return True

    def invoke(self, context, event):
        node = edit_tree(context).nodes.active
        written = comments.lines_of(comments.notes_of(node), ("before",))
        self.lines.clear()
        for i in range(MAX_LINES):
            self.lines.add().body = written[i] if i < len(written) else ""
        return context.window_manager.invoke_props_dialog(self, width=420, title=f"Comment on {node.name}")

    def draw(self, context):
        col = self.layout.column(align=True)
        last = max((i for i, line in enumerate(self.lines) if line.body), default=-1)
        for line in list(self.lines)[:min(last + 2, MAX_LINES)]:
            col.prop(line, "body", text="")
        after = comments.lines_of(comments.notes_of(edit_tree(context).nodes.active), ("after",))
        if after:
            self.layout.label(text=f"On its line: {' '.join(after)}", icon="INFO")

    def execute(self, context):
        node = edit_tree(context).nodes.active
        lines = [line.body for line in self.lines]
        while lines and not lines[-1].strip():
            lines.pop()
        comments.set_comment(node, "before", lines)
        context.area.tag_redraw()
        return {"FINISHED"}


def menu_arrange(self, context):
    self.layout.separator()
    self.layout.operator(BASE_NODE_OT_arrange.bl_idname, icon="SNAP_GRID")
    self.layout.operator(BASE_NODE_OT_edit_comment.bl_idname, icon="TEXT")


def menu_comment(self, context):
    self.layout.separator()
    self.layout.operator(BASE_NODE_OT_edit_comment.bl_idname, icon="TEXT")


def menu_import(self, context):
    self.layout.operator(BASE_NODE_OT_import.bl_idname, text="Base Node (.bn)")


classes = (BASE_NODE_OT_import, BASE_NODE_OT_apply_view, BASE_NODE_OT_format, BASE_NODE_OT_toggle_view, BASE_NODE_OT_goto,
           BASE_NODE_OT_add_modifier, BASE_NODE_OT_arrange, BaseNodeCommentLine, BASE_NODE_OT_edit_comment)
