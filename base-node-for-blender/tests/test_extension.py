"""Tests for Blender base_node extension.

Run in Blender via:
    blender --background --factory-startup --python-exit-code 1 --python base-node-for-blender/tests/test_extension.py
"""

from __future__ import annotations

import difflib
import importlib.util
import os
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


def test_named_constants():
    """A literal bound to a name is a node of its own: the tree keeps `size = 10`."""
    print("-> Test: named constants survive Text -> Tree -> Text...")
    from base_node.host import build_source, export_tree

    src = """
geometry graph box() -> Geometry {
  size = 10
  scale = 2.5
  offset = (1.0, 2.0, 3.0)
  on = true
  tint = (1.0, 0.5, 0.0, 1.0)
  flat = (0.5, 0.25)
  g = MeshCube(CombineXYZ(size, scale, -size), size)
  return SetPosition(g.mesh, on, offset: offset + flat)
}
"""
    tree = build_source(src, filename="box.bn")[0]
    kinds = {n.name: n.bl_idname for n in tree.nodes}
    assert kinds["size"] == "FunctionNodeInputInt" and tree.nodes["size"].integer == 10, kinds
    assert kinds["scale"] == "ShaderNodeValue" and tree.nodes["scale"].outputs[0].default_value == 2.5, kinds
    assert kinds["offset"] == "FunctionNodeInputVector", kinds
    assert kinds["on"] == "FunctionNodeInputBool", kinds
    assert kinds["tint"] == "FunctionNodeInputColor", kinds
    # Two numbers: a Vector node in 2D, whose link gives z = 0 to a 3D input
    assert kinds["flat"] == "FunctionNodeInputVector" and tree.nodes["flat"].vector_dimensions == 2, kinds

    exported, warnings = export_tree(tree)
    assert not warnings, warnings
    for line in ("size = 10", "scale = 2.5", "offset = (1.0, 2.0, 3.0)", "on = true",
                 "tint = (1.0, 0.5, 0.0, 1.0)", "flat = (0.5, 0.25)", "-size", "offset + flat"):
        assert line in exported, f"'{line}' lost:\n{exported}"
    again, _ = export_tree(build_source(exported, filename="box2.bn")[0])
    assert again == exported, f"not stable:\n{again}"

    # A Value node made in Blender reads back with its value, not as Value()
    tree = bpy.data.node_groups.new("made_by_hand", "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    out = tree.nodes.new("NodeGroupOutput")
    value = tree.nodes.new("ShaderNodeValue")
    value.outputs[0].default_value = 10.0
    cube = tree.nodes.new("GeometryNodeMeshCube")
    tree.links.new(value.outputs[0], cube.inputs["Vertices X"])
    tree.links.new(cube.outputs[0], out.inputs[0])
    exported, _ = export_tree(tree)
    assert "value = 10.0" in exported, exported
    print("   ✓ Named constants kept")


def test_comments():
    """Comments are kept in the tree, on the nodes they go with, and written back in their places."""
    print("-> Test: comments survive Text -> Tree -> Text...")
    from base_node.host import build_source, export_tree
    from base_node.host.comments import KEY
    from base_node.lang import format_source

    src = """// Above the profile line
// @profile "vector2d"

// Before the uses
use math (bump)

geometry graph lift(geometry: Geometry) -> Geometry {
  // a callee
  return SetPosition(geometry, offset: CombineXYZ(z: 1.0))
}

// The terrain
geometry graph relief(geometry: Geometry, height: Float = 0.4) -> Geometry {  // its header
  "Displaces vertices"
  // the height
  // on two lines
  h = bump(length(Position()) / 3.0, 0.5, 0.2) * height  // after the code
  // goes on to the next statement: a name is no node
  hh = h
  "Block" #teal {
    // in the frame
    k = hh * 2.0
    // end of the frame
  }  // after its brace
  "Note" {
    // a note
  }
  r = repeat(3, g: geometry) {
    // in the zone
    g2 = SetPosition(g, offset: CombineXYZ(z: h + k))
    // the zone's return
    return (g: g2)  // its end
  }
  // the return
  return lift(r.g)
  // end of the graph
}
// below the graph
"""
    tree = build_source(src, filename="terrain.bn")[-1]
    notes = {n.name: n[KEY].to_dict() for n in tree.nodes if KEY in n}
    assert tree[KEY].to_dict() == {
        "head": "// Above the profile line", "file": "// Before the uses", "before": "// The terrain",
        "after": "// its header", "end": "// end of the graph", "below": "// below the graph"}, tree[KEY].to_dict()
    assert notes["h"] == {"before": "// the height\n// on two lines", "after": "// after the code"}, notes
    # `hh = h` makes no node: its comment goes with the next statement, the frame
    assert notes["k"] == {"before": "// in the frame"}, notes
    assert notes["Block"] == {"before": "// goes on to the next statement: a name is no node",
                              "end": "// end of the frame", "end_after": "// after its brace"}, notes
    assert notes["Note"] == {"end": "// a note"}, notes
    assert notes["r"] == {"return_before": "// the zone's return", "return_after": "// its end"}, notes
    assert notes["Group Output"] == {"before": "// the return"}, notes
    # In the callee too: before its return, with its Group Output
    assert bpy.data.node_groups["lift"].nodes["Group Output"][KEY].to_dict() == {"before": "// a callee"}

    exported, warnings = export_tree(tree)
    assert not warnings, warnings
    lines = [line.strip() for line in exported.split("\n")]
    for comment in src.split("\n"):
        if "//" in comment and "@profile" not in comment:
            assert comment.strip()[comment.strip().index("//"):] in exported, f"'{comment}' lost:\n{exported}"
    assert lines[0] == "// Above the profile line" and lines[2].startswith("// @profile"), exported
    assert any(line.startswith("h = bump(") and line.endswith(" * height  // after the code") for line in lines), \
        exported
    assert "}  // after its brace" in lines and "return g2  // its end" in lines, exported
    assert format_source(exported) == exported, "not in the canonical layout"
    again, _ = export_tree(build_source(exported, filename="terrain2.bn")[-1])
    assert again == exported, f"not stable:\n{again}"

    # Written from the nodes: the text gives it back before the node's statement, a statement of its own
    from base_node.host.comments import set_comment, room
    from base_node.host.arrange import _box
    tree = build_source(src, filename="terrain.bn")[-1]
    length = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeVectorMath")
    set_comment(length, "before", ["written in the graph", "", "after a blank"])
    exported, _ = export_tree(tree)
    assert "  // written in the graph\n  //\n  // after a blank\n  vector_math = length(Position())" in exported, \
        exported
    set_comment(length, "before", [])
    assert KEY not in length, "an empty comment stays"
    set_comment(tree.nodes["h"], "before", [])
    assert tree.nodes["h"][KEY].to_dict() == {"after": "// after the code"}, "the other slots stay"

    # A new tree leaves room over its commented nodes: no other node in their comment's box
    tree = build_source(src.replace("relief", "relief_fresh"), filename="fresh.bn")[-1]
    boxes = {n.name: _box(n, 1.0) for n in tree.nodes if n.bl_idname != "NodeFrame"}
    for n in tree.nodes:
        above = room(n)[0]
        if not above or n.bl_idname == "NodeFrame":
            continue
        x, top = n.location_absolute
        for other, b in boxes.items():
            hit = b.x < x + n.width and x < b.x + b.width and b.y - b.height < top + above and top < b.y
            assert other == n.name or not hit, f"'{other}' lies in the comment of '{n.name}'"
    # A note grows to hold what it says
    note = tree.nodes["Note"]
    assert note.height >= room(note)[1], (note.height, room(note))

    # Built again without them, the tree drops them
    tree = build_source("""geometry graph relief(geometry: Geometry) -> Geometry {
  return geometry
}
""", filename="terrain.bn")[-1]
    assert KEY not in tree and not any(KEY in n for n in tree.nodes), "comments left behind"
    print("   ✓ Comments kept on their nodes")


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


def test_pipe_symbol():
    """The pipes drawn as ▷: real ones only, and not on the lines being edited."""
    print("-> Test: Pipe symbol...")
    from base_node.lang.lexer import tokenize
    from base_node.ui import pipes, prefs

    line = '  return g |> F(s: "a |> b") |> G()  // c |> d'
    assert pipes.columns(tokenize(line, strict=False)) == [11, 29], "only the pipes outside strings and comments"
    assert pipes.columns(tokenize("a |>", strict=False)) == [2]

    text = bpy.data.texts.new("pipes.bn")
    text.from_string("a\nb |> F()\nc |> G()\nd |> H()\n")
    text.cursor_set(1)
    assert list(pipes.raw_lines(text)) == [1], "the cursor's line keeps |>"
    text.cursor_set(3)
    text.select_set(3, 0, 1, 2)  # a selection made upward still covers its lines
    assert list(pipes.raw_lines(text)) == [1, 2, 3]
    bpy.data.texts.remove(text)

    assert prefs.DEFAULTS.pipe_symbol is True, "on by default"
    assert pipes.mono_font() >= 0
    print("   ✓ Pipe symbol verified")


def test_live_apply():
    """While typing, a valid text is built into its tree; an invalid one changes nothing and keeps the cursor."""
    print("-> Test: Live apply...")
    from base_node.host import build_source
    from base_node.ui import actions, live, prefs

    assert prefs.DEFAULTS.live_apply is True, "on by default"
    tree = build_source("geometry graph LiveDemo(geometry: Geometry) -> Geometry {\n  return geometry\n}\n")[0]
    text, _ = actions.open_view(tree)
    assert actions.is_applied(text)

    text.from_string(text.as_string().replace("return geometry", "return geometry |> SetShadeSmooth("))
    row = next(i for i, line in enumerate(text.lines) if "return" in line.body)
    text.cursor_set(row, character=2)
    try:
        actions.apply_view(text, live=True)
        raise AssertionError("an invalid text must not build")
    except Exception as e:
        assert type(e).__name__ == "BnError", e
    assert (text.current_line_index, text.current_character) == (row, 2), "a live build leaves the cursor"
    assert actions.DIAGNOSTICS.get(text.name), "the errors are listed"
    assert not any(n.bl_idname == "GeometryNodeSetShadeSmooth" for n in tree.nodes), "the tree keeps what it had"

    text.from_string(text.as_string().replace("SetShadeSmooth(", "SetShadeSmooth()"))
    actions.apply_view(text, live=True)
    assert any(n.bl_idname == "GeometryNodeSetShadeSmooth" for n in tree.nodes)
    assert actions.is_applied(text) and not actions.DIAGNOSTICS.get(text.name)

    # A text is built once it has rested, and only once per source
    live._seen.clear(), live._tried.clear()
    assert not live.due("t", "a", 0.0), "first seen"
    assert not live.due("t", "a", 0.2), "not rested yet"
    assert live.due("t", "a", 0.2 + live.REST)
    live._tried["t"] = "a"
    assert not live.due("t", "a", 5.0), "already built"
    assert not live.due("t", "ab", 5.0), "changed again: rests anew"
    live._seen.clear(), live._tried.clear()

    actions.close_view(text)
    bpy.data.node_groups.remove(tree)
    print("   ✓ Live apply verified")


def test_tree_without_output():
    """A tree with no Group Output node reads as a graph that returns nothing, and builds again."""
    print("-> Test: Tree without output...")
    from base_node.host import build_source, export_tree

    tree = bpy.data.node_groups.new("NoOutput", "GeometryNodeTree")
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    tree.nodes.new("NodeGroupInput")
    source, _ = export_tree(tree)
    assert "return ()" in source, source
    build_source(source, "no_output.bn")
    bpy.data.node_groups.remove(tree)
    print("   ✓ Tree without output verified")


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

    # A file elsewhere finds its modules in the module folders: by default, the stdlib bundled with the add-on
    import tempfile
    assert modules.FOLDERS == [modules.STDLIB], modules.FOLDERS
    assert os.path.isfile(os.path.join(modules.STDLIB, "math.bn")), "the stdlib is not bundled"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "lifted.bn")
        with open(path, "w", encoding="utf-8") as f:
            f.write("use math (sine01)\n\ngeometry graph lifted(geometry: Geometry) -> Geometry {\n"
                    "  return SetPosition(geometry, offset: CombineXYZ(z: sine01(1.0)))\n}\n")
        modules.FOLDERS[:] = []
        try:
            actions.import_file(path)
            raise AssertionError("math found with no module folder")
        except BnError:
            pass
        finally:
            modules.FOLDERS[:] = [modules.STDLIB]
        trees = actions.import_file(path)
    assert [t.name for t in trees] == ["lifted"], trees
    print("   ✓ Import verified")


def test_zones_read_back():
    """7. Trees as Blender lets one make them, around zones, read back into text that builds."""
    print("-> Test 7: Zones read back...")
    from base_node.host import build_source, export_tree

    def round_trip(tree):
        text, warnings = export_tree(tree)
        rebuilt = build_source(text, filename=f"{tree.name}.bn")[-1]
        again, _ = export_tree(rebuilt)
        assert again == text, f"not stable:\n{text}\n---\n{again}"
        return text, warnings

    # A frame around nodes inside a zone and outside it: one frame, continued in the zone
    framed, = build_source("""
geometry graph framed(geometry: Geometry) -> Geometry {
  "F" {
    up = CombineXYZ(z: 0.1) @ hide
  }
  s = simulate(mesh: geometry) {
    "F" .. {
      moved = SetPosition(mesh, offset: up) @ hide
    }
    return moved
  }
  return s
}
""", filename="framed.bn")
    text, warnings = round_trip(framed)
    assert not warnings, warnings
    assert len([n for n in framed.nodes if n.bl_idname == "NodeFrame"]) == 1
    assert '"F" .. {' in text, text

    # A state Blender calls "Delta Time", beside the zone's own elapsed time
    timed, = build_source("""
geometry graph timed(geometry: Geometry) -> (Geometry: Geometry, Time: Float) {
  s = simulate(mesh: geometry, "Delta Time" as delta_time_2: 0.0) {
    return (mesh: mesh, delta_time_2: delta_time_2 + delta_time)
  }
  return (Geometry: s.mesh, Time: s.delta_time_2)
}
""", filename="timed.bn")
    zout = next(n for n in timed.nodes if n.bl_idname == "GeometryNodeSimulationOutput")
    assert [i.name for i in zout.state_items] == ["mesh", "Delta Time"]
    text, warnings = round_trip(timed)
    assert not warnings, warnings
    assert '"Delta Time" as delta_time_2' in text, text

    # A generation item of a foreach named like its main geometry
    each, = build_source("""
geometry graph each(geometry: Geometry) -> (Geometry: Geometry, Points: Geometry) {
  e = foreach(geometry, domain: FACE) {
    return (points: Points(1))
  }
  return (Geometry: e, Points: e.points)
}
""", filename="each.bn")
    zout = next(n for n in each.nodes if n.bl_idname == "GeometryNodeForeachGeometryElementOutput")
    zout.generation_items[0].name = "Geometry"
    text, _warnings = round_trip(each)
    assert "e.Geometry" in text, text
    print("   ✓ Zones read back")


# Socket type -> Store Named Attribute data type, for the field outputs of a group
STORED = {"VALUE": "FLOAT", "VECTOR": "FLOAT_VECTOR", "INT": "INT", "BOOLEAN": "BOOLEAN",
          "RGBA": "FLOAT_COLOR", "ROTATION": "QUATERNION", "MATRIX": "FLOAT4X4"}


def caller(group, fed):
    """A modifier tree calling `group`: the object's geometry into its geometry inputs, Position
    into its float and vector inputs when `fed`, and each of its field outputs stored as an attribute."""
    t = bpy.data.node_groups.new(f".calls {group.name}", "GeometryNodeTree")
    t.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    t.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin, gout = t.nodes.new("NodeGroupInput"), t.nodes.new("NodeGroupOutput")
    call = t.nodes.new("GeometryNodeGroup")
    call.node_tree = group
    position = t.nodes.new("GeometryNodeInputPosition")
    xyz = t.nodes.new("ShaderNodeSeparateXYZ")
    t.links.new(position.outputs[0], xyz.inputs[0])
    for s in call.inputs:
        if s.type == "GEOMETRY":
            t.links.new(gin.outputs[0], s)
        elif fed and s.type == "VECTOR":
            t.links.new(position.outputs[0], s)
        elif fed and s.type in ("VALUE", "INT"):
            t.links.new(xyz.outputs[0], s)
    out = next((s for s in call.outputs if s.type == "GEOMETRY"), gin.outputs[0])
    for i, s in enumerate(call.outputs):
        if s.type in STORED:
            store = t.nodes.new("GeometryNodeStoreNamedAttribute")
            store.data_type = STORED[s.type]
            store.inputs["Name"].default_value = f"out_{i}"
            t.links.new(out, store.inputs["Geometry"])
            t.links.new(s, store.inputs["Value"])
            out = store.outputs[0]
    t.links.new(out, gout.inputs[0])
    return t


def fingerprint(obj):
    """Sizes and rounded values of every attribute of the evaluated geometry of `obj`."""
    geometry = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).evaluated_geometry()
    found = {}
    for component in ("mesh", "curves", "pointcloud"):
        data = getattr(geometry, component, None)
        if data is None:
            continue
        for a in data.attributes:
            if a.name.startswith("."):
                continue
            values = []
            for item in a.data:
                v = next((getattr(item, k) for k in ("vector", "value", "color") if hasattr(item, k)), None)
                if isinstance(v, float):
                    values.append(round(v, 4) + 0.0)
                elif hasattr(v, "__len__"):
                    # A matrix is rows of floats
                    flat = [y for x in v for y in x] if v and hasattr(v[0], "__len__") else v
                    values.extend(round(x, 4) + 0.0 for x in flat)
                elif v is not None:
                    values.append(v)
            found[f"{component}:{a.domain}:{a.name}:{a.data_type}"] = (len(a.data), hash(tuple(values)))
    instances = geometry.instances_pointcloud()
    found["instances"] = len(instances.points) if instances is not None else 0
    return found


def evaluate(group, kind):
    """Fingerprints of `group` as a modifier on a fresh mesh or curves object, over a few frames."""
    # The objects of the scene go; those a group uses, appended with it, out of any scene, stay
    for o in [o for o in bpy.data.objects if o.users_scene]:
        bpy.data.objects.remove(o)
    scene = bpy.context.scene
    scene.frame_set(1)
    if kind.startswith("mesh"):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3)
    else:
        bpy.ops.curve.primitive_bezier_circle_add()
        bpy.ops.object.convert(target="CURVES")
    obj = bpy.context.object
    modifier = obj.modifiers.new("GN", "NODES")
    modifier.node_group = caller(group, kind.endswith("fed")) if "caller" in kind else group
    # The simulations step from frame to frame
    prints = []
    for frame in (1, 2, 3, 10):
        scene.frame_set(frame)
        prints.append(fingerprint(obj))
    return prints


def credits(name):
    """The header of the .bn of an asset of the fixture: where it comes from, under which license."""
    return (f"// {name}, from Cartesian Caramel's Everyday Nodes\n"
            "// Author: Cartesian Caramel\n"
            "// Source: https://github.com/cartesiancaramel/blender-remote-asset-library-test-v1 (6c078f7)\n"
            "// License: CC0-1.0, https://creativecommons.org/publicdomain/zero/1.0/\n"
            "// Written by Base Node from tests/fixtures/everyday_geometry_nodes.blend;\n"
            "// to write it again: BASE_NODE_UPDATE_FIXTURES=1, see tests/fixtures/README.md\n"
            "\n")


def test_arrange():
    """10. Arrange a tree: links go left to right, no two nodes overlap, frames keep their nodes."""
    print("-> Test 10: Arranging nodes...")
    from base_node.host import build_source
    from base_node.host.arrange import _box, arrange_nodes

    src = """
geometry graph ripple(geometry: Geometry, frequency: Float = 2.0, amplitude: Float = 0.5) -> Geometry {
  p = Position()
  "Height" {
    r = length(p)
    h = sin(r * frequency) * amplitude
  }
  return SetPosition(geometry, offset: CombineXYZ(z: h))
}
"""
    tree = build_source(src, filename="ripple.bn")[0]
    nodes = [n for n in tree.nodes if n.bl_idname != "NodeFrame"]
    for i, n in enumerate(nodes):  # scrambled
        n.location_absolute = ((i * 377) % 900, (i * 613) % 700)
    assert arrange_nodes(tree) == len(nodes)

    for l in tree.links:
        assert l.from_node.location_absolute.x < l.to_node.location_absolute.x, \
            f"{l.from_node.name} -> {l.to_node.name} goes right to left"
    scale = bpy.context.preferences.system.ui_scale or 1.0
    rects = []
    for n in nodes:
        b = _box(n, scale)
        rects.append((n.name, b.x, b.y, b.x + b.width, b.y - b.height))
    for i, (a, ax0, ay0, ax1, ay1) in enumerate(rects):
        for b, bx0, by0, bx1, by1 in rects[i + 1:]:
            assert ax1 <= bx0 or bx1 <= ax0 or ay1 >= by0 or by1 >= ay0, f"{a} and {b} overlap"
    framed = {n.name for n in nodes if n.parent}
    assert framed, "the frame lost its nodes"
    inside = [r for r in rects if r[0] in framed]
    left, right = min(r[1] for r in inside), max(r[3] for r in inside)
    top, bottom = max(r[2] for r in inside), min(r[4] for r in inside)
    for name, x0, y0, x1, y1 in rects:
        if name not in framed:
            assert x1 <= left or x0 >= right or y1 >= top or y0 <= bottom, f"{name} is inside the frame"
    print(f"   ✓ {len(nodes)} nodes arranged")


def test_real_world_assets():
    """8. Third-party assets (tests/fixtures, CC0) read as text, built back, evaluate the same."""
    print("-> Test 8: Real-world assets...")
    from base_node.host import build_source, export_tree
    from base_node.lang.schema import key

    fixture = EXT_DIR / "tests" / "fixtures" / "everyday_geometry_nodes.blend"
    with bpy.data.libraries.load(str(fixture), link=False) as (src, dst):
        dst.node_groups = list(src.node_groups)
    loaded = list(dst.node_groups)
    assets = sorted((g for g in loaded if g.asset_data is not None), key=lambda g: g.name)
    assert len(assets) == 17, [g.name for g in assets]

    texts = {}
    for g in assets:
        text, warnings = export_tree(g)
        # Only frames interleaved with others are lost: they come back as two frames each
        lost = [w for w in warnings if "is split" not in w]
        assert not lost, f"{g.name}: {lost}"
        texts[g.name] = text
    # The texts are kept beside the fixture, to read and to see what a change of the reader changes
    expected_dir = fixture.with_suffix("")
    if os.environ.get("BASE_NODE_UPDATE_FIXTURES"):
        expected_dir.mkdir(exist_ok=True)
        for old in expected_dir.glob("*.bn"):
            old.unlink()
        for name, text in texts.items():
            (expected_dir / f"{key(name)}.bn").write_text(credits(name) + text, encoding="utf-8")
    changed, files = [], {}
    for name, text in texts.items():
        path = expected_dir / f"{key(name)}.bn"
        expected = files[name] = path.read_text(encoding="utf-8") if path.exists() else ""
        if credits(name) + text != expected:
            changed.append("".join(difflib.unified_diff(
                expected.splitlines(True), (credits(name) + text).splitlines(True),
                f"{path.name} (expected)", f"{path.name} (read)", n=1)))
    assert not changed, ("the assets read otherwise than tests/fixtures/everyday_geometry_nodes/*.bn; "
                         "if that is wanted, rerun with BASE_NODE_UPDATE_FIXTURES=1\n" + "\n".join(changed)[:4000])
    assert len(list(expected_dir.glob("*.bn"))) == len(texts), "a .bn of the fixtures has no asset"
    # The originals step aside: the texts build groups of the same names
    originals = {}
    for g in loaded:
        name = g.name
        g.name = f"original {name}"
        originals[name] = g

    # Built from the files themselves: the tree keeps their credits, and gives the file back
    for name, text in texts.items():
        tree = build_source(files[name], filename=f"{key(name)}.bn")[-1]
        assert tree.name == name, tree.name
        again, _ = export_tree(tree)
        assert again == files[name], f"{name}: Tree -> Text is not stable"
    for name in texts:
        for kind in ("mesh", "curves", "mesh caller", "mesh caller fed"):
            want = evaluate(originals[name], kind)
            got = evaluate(bpy.data.node_groups[name], kind)
            assert got == want, f"{name}: evaluates otherwise once rebuilt ({kind})"
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    print(f"   ✓ {len(texts)} real-world assets rebuilt from text, same results")


def main():
    print("=== Starting Base Node Blender extension tests ===")
    tests = [
        test_import_and_registration,
        test_check_profile_stdlib,
        test_build_and_round_trip,
        test_named_constants,
        test_comments,
        test_profile_ascent_and_linter,
        test_pipe_symbol,
        test_live_apply,
        test_tree_without_output,
        test_text_view,
        test_import_files,
        test_zones_read_back,
        test_arrange,
        test_real_world_assets,
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
