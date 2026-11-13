"""Tests for Blender base_node extension.

Run in Blender via:
    blender --background --factory-startup --python-exit-code 1 --python base-node-for-blender/tests/test_extension.py
"""

from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

EXT_DIR = Path(__file__).resolve().parents[1]
LIB_ROOT = EXT_DIR.parent
STDLIB_DIR = LIB_ROOT / "stdlib"

_spec = importlib.util.spec_from_file_location(
    "base_node", EXT_DIR / "__init__.py", submodule_search_locations=[str(EXT_DIR)]
)
base_node = importlib.util.module_from_spec(_spec)
sys.modules["base_node"] = base_node
_spec.loader.exec_module(base_node)

import bpy


def test_import_and_registration():
    """1. Verify import and registration of base_node."""
    print("-> Test 1: Verifying imports and registration...")
    assert base_node is not None, "base_node not found"
    assert base_node.lang is not None, "base_node.lang missing"
    assert base_node.host is not None, "base_node.host missing"

    # Register and unregister addon
    base_node.register()
    assert hasattr(bpy.types.NodeTree, "base_node_text"), "NodeTree.base_node_text missing"
    assert not hasattr(bpy.types.WindowManager, "base_node_sync"), "the text/tree selection sync is gone"
    print("   ✓ Imports and registration verified")


def test_check_profile_stdlib():
    """2. Verify stdlib modules conformance against target profiles."""
    print("-> Test 2: Verifying stdlib profiles...")
    from base_node.host.schema import BlenderSchema
    from base_node.lang import compile_source
    from base_node.lang.profiles import check_profile

    name_fallbacks = {
        "math": ["math.bn"],
        "sdf2d": ["sdf2d.bn"],
        "curves2d": ["curves2d.bn"],
        "patterns2d": ["patterns2d.bn"],
        "planar2d": ["planar2d.bn"],
        "fillet2d": ["fillet2d.bn"],
        "hachures2d": ["hachures2d.bn"],
        "deform2d": ["deform2d.bn"],
        "ink2d": ["ink2d.bn"],
    }

    target_specs = [
        (["math.bn"], "core"),
        (["sdf2d.bn"], "sdf2d"),
        (["curves2d.bn"], "vector2d"),
        (["patterns2d.bn"], "vector2d"),
        (["planar2d.bn"], "vector2d"),
        (["fillet2d.bn"], "vector2d"),
        (["hachures2d.bn"], "vector2d"),
        (["deform2d.bn"], "vector2d"),
        (["ink2d.bn"], "ink2d"),
    ]

    def loader(name: str, _caller: str):
        candidates = name_fallbacks.get(name, [f"{name}.bn"])
        for fname in candidates:
            p = STDLIB_DIR / fname
            if p.exists():
                return p.read_text(encoding="utf-8"), str(p)
        raise LookupError(f"Module stdlib not found: {name}")

    with BlenderSchema() as schema:
        for candidates, expected_profile in target_specs:
            filepath = None
            for cand in candidates:
                p = STDLIB_DIR / cand
                if p.exists():
                    filepath = p
                    break
            assert filepath is not None and filepath.exists(), f"Missing file from candidates {candidates}"
            source = filepath.read_text(encoding="utf-8")

            graphs = compile_source(source, schema, str(filepath), load=loader)
            assert len(graphs) > 0, f"No graph compiled for {filepath.name}"

            errors = check_profile(graphs, profile=expected_profile)
            assert errors == [], f"Errors in {filepath.name} for profile '{expected_profile}':\n" + "\n".join(errors)
            print(f"   ✓ {filepath.name} ({len(graphs)} graphs) validated under profile '{expected_profile}'")


def test_build_and_round_trip():
    """3. Build and round-trip Tree -> Text -> Tree in Blender."""
    print("-> Test 3: Build and round-trip Tree -> Text -> Tree...")
    from base_node.host import build_source, export_tree

    src = """
geometry graph wave(geometry: Geometry, frequency: Float = 2.0, amplitude: Float = 0.5) -> Geometry {
  "Surface wave along Z"
  p = Position()
  h = sin(p.x * frequency) * amplitude
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
"""

    # 1. Text -> Tree
    trees = build_source(src, filename="wave.bn")
    assert len(trees) == 1, f"Expected 1 built tree, got {len(trees)}"
    tree = trees[0]
    assert tree.name == "wave", f"Unexpected tree name: {tree.name}"
    assert len(tree.nodes) > 0, "Built tree contains no nodes"

    # Verify attached properties
    assert hasattr(tree, "base_node_text"), "Property base_node_text missing on node group"

    # 2. Tree -> Text
    exported, warnings = export_tree(tree)
    assert "geometry graph wave" in exported, f"Header missing in export:\n{exported}"
    assert "SetPosition" in exported, f"SetPosition missing in export:\n{exported}"

    # 3. Text -> Tree (second pass)
    rebuilt_trees = build_source(exported, filename="wave_rebuilt.bn")
    assert len(rebuilt_trees) == 1
    rebuilt_tree = rebuilt_trees[0]
    assert rebuilt_tree.name == "wave"

    re_exported, _ = export_tree(rebuilt_tree)
    assert re_exported == exported, "Tree -> Text round trip is not stable"
    print("   ✓ Tree -> Text -> Tree round-trip verified")


def test_profile_ascent_and_linter():
    """4. Verify profile ascent detection on exported tree and highlighter linter."""
    print("-> Test 4: Verifying profile ascent solver & highlighter linter...")
    from base_node.host import build_source, export_tree
    from base_node.lang.lexer import tokenize
    from base_node.ui.highlight import classify

    # Test decompiled tree has // @profile "vector2d"
    src = """
geometry graph spiral(r: Float = 1.0) -> Geometry {
  c = CurvePrimitiveCircle(radius: r)
  return c.curve
}
"""
    trees = build_source(src, filename="spiral.bn")
    exported, _ = export_tree(trees[0])
    assert exported.startswith('// @profile "vector2d"'), f"Expected vector2d profile header, got:\n{exported}"

    # Test highlighter classify in origin & portability mode
    toks = tokenize("use ink2d as gp\n", strict=False)
    classes = dict((t.text, c) for t, c in classify(toks))
    assert classes.get("ink2d") == "namespace"

    toks_call = tokenize("gp::living_ink(strokes)\n", strict=False)
    classes_call = dict((t.text, c) for t, c in classify(toks_call))
    assert classes_call.get("living_ink") == "stdlib_func"

    # In portability mode with core profile, CurvePrimitiveCircle is flagged as warning
    toks_node = tokenize("c = CurvePrimitiveCircle(radius: 1.0)\n", strict=False)
    ctx_core = {"mode": "portability", "allowed_nodes": {"Math", "VectorMath"}, "declared": set()}
    classes_node = dict((t.text, c) for t, c in classify(toks_node, ctx_core))
    assert classes_node.get("CurvePrimitiveCircle") == "warning"

    print("   ✓ Profile ascent and highlighter linter verified")


def test_text_view():
    """5. A tree shown as text is written back into it, and the text goes away."""
    print("-> Test 5: Text view of a tree...")
    from base_node.host import build_source
    from base_node.lang import BnError
    from base_node.ui import actions

    tree = build_source("""
geometry graph view_me(geometry: Geometry) -> Geometry {
  return SetPosition(geometry, offset: CombineXYZ(z: 1.0))
}
""", filename="view_me.bn")[0]
    texts_before = set(bpy.data.texts)

    # A tree linked to a text by an older version is unlinked when it is built again
    legacy = bpy.data.texts.new("legacy_view_me.bn")
    tree.base_node_text = legacy
    build_source(actions.export_tree(tree)[0], "view_me.bn")
    assert tree.base_node_text is None, "a rebuilt tree still points at a text"
    bpy.data.texts.remove(legacy)

    # Unchanged: the tree is left as it is, the text is removed
    text, _ = actions.open_view(tree)
    assert text.name.startswith(".") and actions.is_view(text) and actions.view_tree(text) == tree
    node = tree.nodes[0]
    node.location = (123.0, 45.0)
    assert actions.close_view(text) == tree
    assert tree.nodes[0].location[0] == 123.0, "an unchanged text rebuilt the tree"
    assert set(bpy.data.texts) == texts_before, "the view text was not removed"
    assert tree.base_node_text is None, "the view linked the tree to a text"

    # Applied: the tree is rebuilt and the text stays open; closing then rebuilds nothing more
    text, _ = actions.open_view(tree)
    text.from_string(text.as_string().replace("z: 1.0", "z: 2.0"))
    assert actions.apply_view(text) == tree and text.name in bpy.data.texts
    combine = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeCombineXYZ")
    assert combine.inputs["Z"].default_value == 2.0, "the applied text did not reach the tree"
    combine.location = (7.0, 7.0)
    assert actions.close_view(text) == tree
    combine = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeCombineXYZ")
    assert combine.location[0] == 7.0, "closing an applied text rebuilt the tree"

    # Changed: closing rebuilds the tree from the text
    text, _ = actions.open_view(tree)
    text.from_string(text.as_string().replace("z: 2.0", "z: 4.0"))
    assert actions.close_view(text) == tree
    combine = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeCombineXYZ")
    assert combine.inputs["Z"].default_value == 4.0, "the edited text did not reach the tree"
    assert set(bpy.data.texts) == texts_before

    # Broken: the text stays, with its errors, until it builds
    text, _ = actions.open_view(tree)
    text.from_string(text.as_string().replace("SetPosition(", "SetPosition(("))
    try:
        actions.close_view(text)
        raise AssertionError("a broken text closed")
    except BnError:
        pass
    assert text.name in bpy.data.texts and text.name in actions.DIAGNOSTICS
    text.from_string(text.as_string().replace("SetPosition((", "SetPosition("))
    assert actions.close_view(text) == tree

    # Renamed in the text: the area follows the new tree
    text, _ = actions.open_view(tree)
    text.from_string(text.as_string().replace("graph view_me", "graph view_me_2"))
    renamed = actions.close_view(text)
    assert renamed is not None and renamed.name == "view_me_2", renamed
    print("   ✓ Text view verified")


def test_import_files():
    """6. File > Import builds the graphs of .bn files, finding the modules next to them."""
    print("-> Test 6: Import .bn files...")
    import os
    from base_node.host import modules
    from base_node.lang import BnError
    from base_node.ui import actions

    # ink2d uses math: found next to it, and kept with its path for a later build
    trees = actions.import_file(str(STDLIB_DIR / "ink2d.bn"))
    assert trees and all(t.get(modules.MODULE) is None for t in trees), "ink2d's own graphs became module groups"
    math_groups = [g for g in bpy.data.node_groups if g.get(modules.MODULE) == "math"]
    assert math_groups, "ink2d's use of math built nothing"
    assert all(os.path.samefile(g[modules.SOURCE], STDLIB_DIR / "math.bn") for g in math_groups)

    # A text view of a tree that calls math builds again without any math.bn text
    caller = next(t for t in trees if any(n.bl_idname == "GeometryNodeGroup" and n.node_tree in math_groups
                                          for n in t.nodes))
    text, _ = actions.open_view(caller)
    assert "use math" in text.as_string()
    text.from_string(text.as_string() + "\n")
    assert actions.close_view(text) == caller

    # A file elsewhere finds its modules through the module folder
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "lifted.bn")
        with open(path, "w", encoding="utf-8") as f:
            f.write("use math (sine01)\n\ngeometry graph lifted(geometry: Geometry) -> Geometry {\n"
                    "  return SetPosition(geometry, offset: CombineXYZ(z: sine01(1.0)))\n}\n")
        try:
            actions.import_file(path)
            raise AssertionError("math found with no module folder")
        except BnError:
            pass
        modules.FOLDERS[:] = [str(STDLIB_DIR)]
        try:
            trees = actions.import_file(path)
        finally:
            modules.FOLDERS[:] = []
    assert [t.name for t in trees] == ["lifted"], trees
    print("   ✓ Import verified")


def main():
    print("=== Starting Base Node Blender extension tests ===")
    tests = [
        test_import_and_registration,
        test_check_profile_stdlib,
        test_build_and_round_trip,
        test_profile_ascent_and_linter,
        test_text_view,
        test_import_files,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception:
            failed += 1
            traceback.print_exc()

    if failed:
        print(f"\n❌ FAILED: {failed} test(s) failed")
        sys.exit(1)
    else:
        print(f"\n✅ SUCCESS: 100% of tests ({len(tests)}/{len(tests)}) passed successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
