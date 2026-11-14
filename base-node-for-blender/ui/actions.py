"""What the operators do, kept apart from them so tests can call it without a UI."""

import hashlib
import os

import bpy

from ..host import build_source, export_tree, modules
from ..lang import BnError
from ..lang.format import format_source

EXT = ".bn"

# Per text name, for the panel: errors of the last build, warnings of the last export.
# Runtime only: they are not saved with the file.
DIAGNOSTICS = {}
WARNINGS = {}


def is_bn(text):
    return text is not None and text.name.endswith(EXT)


def build_text(text, live=False):
    """Build every graph of the text into its tree of the same name. Raises BnError.

    On an error nothing is built, and the cursor goes to it, unless the build is live:
    then it stays where the user types.
    """
    DIAGNOSTICS.pop(text.name, None)
    try:
        return build_source(text.as_string(), text.name)
    except BnError as e:
        DIAGNOSTICS[text.name] = e.diagnostics
        if not live:
            first = e.diagnostics[0]
            text.cursor_set(first.line - 1, character=max(0, first.col - 1))
        raise


# Text view of a tree: the tree is the only data, the text lives while an area shows it.
VIEW_TREE = "base_node_view"       # ID property of the text: name of the tree it shows
VIEW_HASH = "base_node_view_hash"  # ID property of the text: hash of the source the tree holds


def _digest(source):
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def is_view(text):
    return text is not None and VIEW_TREE in text


def view_tree(text):
    """The tree a view text shows, or None when the text is not a view (or its tree is gone)."""
    name = text.get(VIEW_TREE) if text is not None else None
    return bpy.data.node_groups.get(name) if name else None


def open_view(tree):
    """Write the tree into a hidden text that only stands for it. Returns (text, warnings)."""
    source, warnings = export_tree(tree)
    name = f".{tree.name}{EXT}"  # leading dot: hidden from the text browser
    text = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    text.from_string(source)
    text.cursor_set(0)
    text.use_fake_user = False
    text[VIEW_TREE] = tree.name
    text[VIEW_HASH] = _digest(text.as_string())
    WARNINGS[text.name] = warnings
    DIAGNOSTICS.pop(text.name, None)
    return text, warnings


def is_applied(text):
    """True when the tree already holds what the view text says."""
    return text.get(VIEW_HASH) == _digest(text.as_string())


def apply_view(text, live=False):
    """Write a view text into its tree, keeping the text. Returns the tree; raises BnError.

    An unchanged text leaves the tree as it is, so its layout survives a look at the code.
    """
    tree = view_tree(text)
    source = text.as_string()
    if tree is not None and text.get(VIEW_HASH) == _digest(source):
        return tree
    trees = build_text(text, live)
    # Callees are written first: when the main graph was renamed in the text, it is the last one
    if trees and tree not in trees:
        tree = trees[-1]
    if tree is not None:
        text[VIEW_TREE] = tree.name
    text[VIEW_HASH] = _digest(source)
    return tree


def close_view(text):
    """Write a view text into its tree, then remove the text. Returns the tree; raises BnError.

    On an error the text stays, with its diagnostics, so that it can be fixed.
    """
    tree = apply_view(text)
    WARNINGS.pop(text.name, None)
    DIAGNOSTICS.pop(text.name, None)
    bpy.data.texts.remove(text)
    return tree


def format_text(text):
    """Rewrite the text in the canonical layout. True when it changed; raises BnError."""
    source = text.as_string()
    DIAGNOSTICS.pop(text.name, None)
    try:
        formatted = format_source(source, text.name)
    except BnError as e:
        DIAGNOSTICS[text.name] = e.diagnostics
        first = e.diagnostics[0]
        text.cursor_set(first.line - 1, character=max(0, first.col - 1))
        raise
    if formatted == source:
        return False
    line, char = text.current_line_index, text.current_character
    text.from_string(formatted)
    line = min(line, len(text.lines) - 1)
    text.cursor_set(line, character=min(char, len(text.lines[line].body)))
    return True


def import_file(path):
    """Build every graph of a .bn file into the trees of the same names. Returns them; raises BnError, OSError.

    Its `use` lines find their modules in the .blend's texts, next to the file, then in the module folders.
    """
    with open(path, encoding="utf-8") as f:
        source = f.read()
    here = os.path.dirname(os.path.abspath(path))
    beside = {}

    def load(name, src):
        if src is None and bpy.data.texts.get(name + EXT) is None:
            found = modules.find(name, [here])
            if found is not None:
                beside[name] = found
        return modules.load(name, src, [here, *modules.FOLDERS])

    trees = build_source(source, os.path.basename(path), load)
    # A module found next to the file keeps its path, so that the text view of a tree finds it again
    for g in bpy.data.node_groups:
        name = g.get(modules.MODULE)
        if name in beside and not g.get(modules.SOURCE):
            g[modules.SOURCE] = beside[name]
    return trees
