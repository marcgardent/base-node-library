import bpy

from . import completion, highlight, keys, operators, panels, pipes, prefs

classes = prefs.classes + operators.classes + completion.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Only for a group a `use` built from a text module: the text goes along when the group is appended
    bpy.types.NodeTree.base_node_text = bpy.props.PointerProperty(
        type=bpy.types.Text, name="Module Text", description="The .bn module text this group was built from")
    keys.bind()
    prefs.apply_folders()
    bpy.types.TOPBAR_MT_file_import.append(operators.menu_import)
    highlight.register()  # first, so that the popup draws over it
    pipes.register()
    completion.register()


def unregister():
    completion.unregister()
    pipes.unregister()
    highlight.unregister()
    keys.unbind()
    bpy.types.TOPBAR_MT_file_import.remove(operators.menu_import)
    if hasattr(bpy.types.NodeTree, "base_node_text"):
        del bpy.types.NodeTree.base_node_text
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
