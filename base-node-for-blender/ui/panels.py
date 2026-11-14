import blf
import bpy

from . import actions, keys, prefs
from .operators import edit_tree


class Shortcuts:
    """The shortcut of each button of a panel, greyed: on its right when there is room,
    else listed under the buttons, the keys first, after the button's icon."""

    def __init__(self, context, keymap, buttons):
        self.buttons = buttons  # idname -> (text, icon) of its button
        self.keys = {i: keys.shortcut(keymap, i) for i in buttons}
        self.shown = []
        p = context.preferences
        scale = p.system.ui_scale
        blf.size(0, p.ui_styles[0].widget.points * scale)
        widths = {i: blf.dimensions(0, k)[0] + 16 * scale for i, k in self.keys.items()}
        keys_w = max(widths.values())
        text_w = max(blf.dimensions(0, t)[0] for t, _icon in buttons.values()) + 12 * scale
        room = max(1, context.region.width - 50 * scale)  # less the panel's margins
        self.beside = text_w + 40 * scale + keys_w <= room  # a button has an icon and padding
        self.factor = min(0.75, max(0.25, 1 - keys_w / room))
        # Listed: the icon and the keys, then the name only when it fits whole
        self.listed = {}
        for i, w in widths.items():
            name_w = blf.dimensions(0, buttons[i][0])[0] + 8 * scale
            self.listed[i] = (w + 24 * scale) / room if w + 24 * scale + name_w <= room else None

    def row(self, layout, idname):
        """A row for the button of `idname`, its keys on its right or kept for the list."""
        if not self.beside:
            self.shown.append(idname)
            return layout.row(align=True)
        row = layout.split(factor=self.factor, align=True)
        left = row.row(align=True)
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.active = False
        sub.label(text=self.keys[idname])
        return left

    def button(self, layout, idname):
        text, icon = self.buttons[idname]
        return self.row(layout, idname).operator(idname, text=text, icon=icon)

    def legend(self, layout):
        """The keys of the buttons that had no room for them."""
        if not self.shown:
            return
        col = layout.column(align=True)
        col.active = False
        for idname in self.shown:
            text, icon = self.buttons[idname]
            factor = self.listed[idname]
            if factor is None:
                col.label(text=self.keys[idname], icon=icon)
                continue
            row = col.split(factor=factor)
            row.label(text=self.keys[idname], icon=icon)
            row.label(text=text)


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
        rows = Shortcuts(context, "Text", {
            "base_node.apply_view": ("Apply to Tree", "FILE_REFRESH"),
            "base_node.toggle_view": ("Back to Nodes", "NODETREE"),
            "base_node.format": ("Format", "ALIGN_LEFT"),
            "base_node.complete": ("Suggestions", "VIEWZOOM")})
        if actions.is_view(text):
            row = rows.row(col, "base_node.apply_view")
            row.operator("base_node.apply_view", icon="FILE_REFRESH")
            if tree is not None and tree.is_modifier:
                row.operator("base_node.add_modifier", text="", icon="MODIFIER").tree = tree.name
            rows.button(col, "base_node.toggle_view")
        rows.button(col, "base_node.format")
        # Suggestions have no button, only keys
        if rows.beside:
            rows.row(col, "base_node.complete").label(text="Suggestions", icon="VIEWZOOM")
        else:
            rows.shown.append("base_node.complete")
        rows.legend(layout)
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
        col = layout.column(align=True)
        rows = Shortcuts(context, "Node Editor", {
            "base_node.toggle_view": ("Edit as Text", "TEXT"),
            "base_node.arrange": ("Arrange Nodes", "SNAP_GRID")})
        rows.button(col, "base_node.toggle_view")
        rows.button(col, "base_node.arrange")
        rows.legend(layout)


classes = (TEXT_PT_base_node, NODE_PT_base_node)
