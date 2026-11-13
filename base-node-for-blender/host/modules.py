"""Where a `use` finds its module: a text datablock of the .blend, or a .bn file.

`use math` reads the text datablock math.bn, else math.bn in a module folder;
`use math from "//lib/math.bn"` a file relative to the .blend, as elsewhere in
Blender. Libraries, URLs and {project_root} come later.
"""

import os

import bpy

# Custom properties of a group built by a `use`, for Tree → Text to write the use back
MODULE = "base_node_module"
SOURCE = "base_node_source"


# Folders where `use name` looks for name.bn after the texts of the .blend: the preferences set it
FOLDERS = []


def find(name, folders):
    """Path of name.bn in the first folder that has it, or None."""
    for folder in folders:
        path = os.path.join(bpy.path.abspath(folder), name + ".bn")
        if folder and os.path.isfile(path):
            return os.path.normpath(path)
    return None


def load(name, source, folders=None):
    """(text, filename) of a module. Raises LookupError with the reason.

    A `use` with no source looks in `folders` after the texts, the module folders when not given.
    """
    if source is None:
        text = bpy.data.texts.get(name + ".bn")
        if text is not None:
            return text.as_string(), text.name
        path = find(name, FOLDERS if folders is None else folders)
        if path is None:
            raise LookupError(f"no text '{name}.bn' in this file, nor {name}.bn in a module folder; "
                              f"for an external file: use {name} from \"//path/{name}.bn\"")
        with open(path, encoding="utf-8") as f:
            return f.read(), path
    if source.startswith(("http://", "https://")):
        raise LookupError("online modules are not yet supported")
    if "{project_root}" in source:
        raise LookupError("{project_root} requires Blender 5.3")
    if source.startswith(("./", "../")):
        raise LookupError(f"a path relative to the .blend starts with '//', as elsewhere in Blender: "
                          f"'//{source.removeprefix('./')}'")
    if source.startswith("//"):
        if not bpy.data.filepath:
            raise LookupError("'//' resolves from the .blend folder: save the file first")
        path = os.path.normpath(bpy.path.abspath(source))
    elif os.path.isabs(source):
        path = source
    else:
        raise LookupError(f"'{source}': expected a '//…' path relative to the .blend, or an absolute path; "
                          "asset libraries are not yet supported")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), source
    except OSError as e:
        raise LookupError(f"cannot read '{source}': {e.strerror}") from None


def module_of(tree):
    """(name, source) of the module a group was built from by a `use`, or None."""
    name = tree.get(MODULE)
    return (name, tree.get(SOURCE) or None) if name else None
