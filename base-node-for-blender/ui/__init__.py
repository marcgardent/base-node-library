import bpy

from . import completion, highlight, keys, operators, panels, prefs, sync

classes = prefs.classes + operators.classes + completion.classes + panels.classes


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NodeTree.bnodes_text = bpy.props.PointerProperty(
        type=bpy.types.Text, name="Text", description="The .bn text this tree is built from")
    bpy.types.NodeTree.base_node_text = bpy.props.PointerProperty(
        type=bpy.types.Text, name="Text", description="The .bn text this tree is built from")
    bpy.types.WindowManager.bnodes_sync = bpy.props.BoolProperty(
        name="Sync Selection", default=True,
        description="A node and its line follow each other between the text and node editors")
    bpy.types.WindowManager.base_node_sync = bpy.props.BoolProperty(
        name="Sync Selection", default=True,
        description="A node and its line follow each other between the text and node editors")
    keys.bind()
    sync.register()
    highlight.register()  # first, so that the popup draws over it
    completion.register()


def unregister():
    completion.unregister()
    highlight.unregister()
    sync.unregister()
    keys.unbind()
    if hasattr(bpy.types.WindowManager, "base_node_sync"):
        del bpy.types.WindowManager.base_node_sync
    if hasattr(bpy.types.WindowManager, "bnodes_sync"):
        del bpy.types.WindowManager.bnodes_sync
    if hasattr(bpy.types.NodeTree, "base_node_text"):
        del bpy.types.NodeTree.base_node_text
    if hasattr(bpy.types.NodeTree, "bnodes_text"):
        del bpy.types.NodeTree.bnodes_text
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
