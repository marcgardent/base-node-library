"""Tests for Blender base_node extension and bnodes alias.

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
import bnodes


def test_import_and_aliases():
    """1. Verify import of base_node and bnodes alias."""
    print("-> Test 1: Verifying imports and aliases...")
    assert base_node is not None, "base_node not found"
    assert bnodes is not None, "bnodes not found"
    assert base_node is bnodes, "bnodes is not an alias of base_node"
    assert base_node.lang is bnodes.lang, "base_node.lang and bnodes.lang differ"
    assert base_node.host is bnodes.host, "base_node.host and bnodes.host differ"

    # Register and unregister addon
    base_node.register()
    assert hasattr(bpy.types.NodeTree, "base_node_text"), "NodeTree.base_node_text missing"
    assert hasattr(bpy.types.NodeTree, "bnodes_text"), "NodeTree.bnodes_text missing"
    assert hasattr(bpy.types.WindowManager, "base_node_sync"), "WindowManager.base_node_sync missing"
    assert hasattr(bpy.types.WindowManager, "bnodes_sync"), "WindowManager.bnodes_sync missing"
    print("   ✓ Imports and aliases verified")


def test_check_profile_stdlib():
    """2. Verify stdlib modules conformance against target profiles."""
    print("-> Test 2: Verifying stdlib profiles...")
    from base_node.host.schema import BlenderSchema
    from base_node.lang import compile_source
    from base_node.lang.profiles import check_profile

    name_fallbacks = {
        "math": ["math.bn", "maths.bn"],
        "maths": ["math.bn", "maths.bn"],
        "sdf2d": ["sdf2d.bn"],
        "curves2d": ["curves2d.bn", "courbes2d.bn"],
        "courbes2d": ["curves2d.bn", "courbes2d.bn"],
        "patterns2d": ["patterns2d.bn", "motifs2d.bn"],
        "motifs2d": ["patterns2d.bn", "motifs2d.bn"],
        "gp_tools2d": ["gp_tools2d.bn", "gp_outils2d.bn"],
        "gp_outils2d": ["gp_tools2d.bn", "gp_outils2d.bn"],
    }

    target_specs = [
        (["math.bn", "maths.bn"], "core"),
        (["sdf2d.bn"], "sdf2d"),
        (["curves2d.bn", "courbes2d.bn"], "vector2d"),
        (["patterns2d.bn", "motifs2d.bn"], "vector2d"),
        (["gp_tools2d.bn", "gp_outils2d.bn"], "vector2d"),
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
    assert hasattr(tree, "bnodes_text"), "Property bnodes_text missing on node group"
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


def main():
    print("=== Starting Base Node Blender extension tests ===")
    tests = [
        test_import_and_aliases,
        test_check_profile_stdlib,
        test_build_and_round_trip,
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
