"""Tests for declarative compatibility profiles (base_node/profiles.py)."""

import pytest

from base_node import compile_source, parse
from base_node.ir import Graph, Node
from base_node.profiles import (
    analyze_profile_ascent,
    check_profile,
    load_profile,
    solve_minimal_profile,
)


def test_load_all_profiles_and_hierarchy():
    """Verify loading and hierarchical resolution of all 5 profiles."""
    core = load_profile("core")
    assert core["name"] == "core"
    assert core["extends"] is None
    assert "Float" in core["types"]
    assert "Geometry" not in core["types"]
    assert "Math" in core["nodes"]
    assert "repeat" in core["zones"]
    assert not core["allow_all_blender_nodes"]

    sdf2d = load_profile("sdf2d")
    assert sdf2d["name"] == "sdf2d"
    assert sdf2d["extends"] == "core"
    assert "Float" in sdf2d["types"]
    assert "Position" in sdf2d["nodes"]
    assert "Position" in sdf2d["implicit"]

    vector2d = load_profile("vector2d")
    assert vector2d["name"] == "vector2d"
    assert vector2d["extends"] == "sdf2d"
    assert "Geometry" in vector2d["types"]
    assert "Material" in vector2d["types"]
    assert "CurveCircle" in vector2d["nodes"]
    assert "foreach" in vector2d["zones"]
    assert "repeat" in vector2d["zones"]

    ink2d = load_profile("ink2d")
    assert ink2d["name"] == "ink2d"
    assert ink2d["extends"] == "vector2d"
    assert "Geometry" in ink2d["types"]
    assert "GreasePencilDrawTime" in ink2d["nodes"]
    assert "CurveTilt" in ink2d["nodes"]
    assert "foreach" in ink2d["zones"]
    assert "repeat" in ink2d["zones"]

    raster2d = load_profile("raster2d")
    assert raster2d["name"] == "raster2d"
    assert raster2d["extends"] == "sdf2d"
    assert "Image" in raster2d["types"]
    assert "Blur" in raster2d["nodes"]

    blender = load_profile("blender-geometry")
    assert blender["name"] == "blender-geometry"
    assert blender["extends"] == "ink2d"
    assert blender["allow_all_blender_nodes"] is True
    assert "closure" in blender["zones"]
    assert "Bundle" in blender["types"]


def test_check_profile_valid_core(schema):
    """A pure math graph is valid under the core profile."""
    src = """
geometry graph calcul(x: Float, y: Float) -> Float {
  return sin(x) * 2.0 + cos(y)
}
"""
    graphs = compile_source(src, schema, "test.bn")
    errors = check_profile(graphs, profile="core")
    assert errors == []


def test_check_profile_rejects_geometry_in_core(schema):
    """The core profile rejects the Geometry type."""
    src = """
geometry graph pass_geom(g: Geometry) -> Geometry {
  return g
}
"""
    graphs = compile_source(src, schema, "test.bn")
    errors = check_profile(graphs, profile="core")
    assert len(errors) > 0
    assert any("Geometry" in e for e in errors)


def test_check_profile_valid_vector2d(schema):
    """A curve / mesh graph is valid under vector2d."""
    src = """
geometry graph grille(taille: Float = 1.0) -> Geometry {
  g = MeshGrid(size_x: taille, size_y: taille)
  return SetPosition(g.mesh, position: Position())
}
"""
    graphs = compile_source(src, schema, "test.bn")
    errors = check_profile(graphs, profile="vector2d")
    assert errors == []


def test_check_profile_rejects_simulation_in_vector2d():
    """The vector2d profile rejects simulation zones."""
    g = Graph(
        kind="geometry",
        name="non_portable_sim",
        inputs=[],
        outputs=[],
        nodes=[Node(id="n1", bl_idname="GeometryNodeSimulationInput")],
    )
    errors = check_profile([g], profile="vector2d")
    assert len(errors) > 0
    assert any("GeometryNodeSimulationInput" in e for e in errors)


def test_check_profile_blender_geometry_allows_all():
    """The blender-geometry profile accepts all Blender nodes."""
    g = Graph(
        kind="geometry",
        name="custom_node",
        inputs=[("b", "Bundle")],
        outputs=[],
        nodes=[Node(id="n1", bl_idname="GeometryNodeExtrudeMesh")],
    )
    errors = check_profile([g], profile="blender-geometry")
    assert errors == []


def test_solve_minimal_profile_ascent_hierarchy(schema):
    """Verify automatic profile ascent solving across all tiers."""
    # Tier 1: core
    src_core = """
geometry graph f_core(x: Float, y: Float) -> Float {
  return sin(x) * 2.0 + cos(y)
}
"""
    graphs_core = compile_source(src_core, schema, "test_core.bn")
    assert solve_minimal_profile(graphs_core) == "core"
    ast_core = parse(src_core, "test_core.bn")
    assert solve_minimal_profile(ast_core) == "core"

    # Tier 2: sdf2d (needs Position / spatial inputs)
    src_sdf = """
geometry graph f_sdf(center: Vector, radius: Float) -> Float {
  p = Position()
  return length(p - center) - radius
}
"""
    graphs_sdf = compile_source(src_sdf, schema, "test_sdf.bn")
    assert solve_minimal_profile(graphs_sdf) == "sdf2d"
    ast_sdf = parse(src_sdf, "test_sdf.bn")
    assert solve_minimal_profile(ast_sdf) == "sdf2d"

    # Tier 3: vector2d (needs Geometry / MeshGrid / Curves)
    src_vec = """
geometry graph f_vec(size: Float = 1.0) -> Geometry {
  g = MeshGrid(size_x: size, size_y: size)
  return SetPosition(g.mesh, position: Position())
}
"""
    graphs_vec = compile_source(src_vec, schema, "test_vec.bn")
    assert solve_minimal_profile(graphs_vec) == "vector2d"
    ast_vec = parse(src_vec, "test_vec.bn")
    assert solve_minimal_profile(ast_vec) == "vector2d"

    # Tier 4: ink2d (needs Grease Pencil dynamics)
    src_ink = """
use ink2d as gp

geometry graph f_ink(strokes: Geometry, progress: Float) -> Geometry {
  return gp::living_ink(strokes, speed: 1.0)
}
"""
    ast_ink = parse(src_ink, "test_ink.bn")
    assert solve_minimal_profile(ast_ink) == "ink2d"

    # Tier 5: blender-geometry (needs host-specific nodes / Bundle)
    g_host = Graph(
        kind="geometry",
        name="f_host",
        inputs=[("b", "Bundle")],
        outputs=[],
        nodes=[Node(id="n1", bl_idname="GeometryNodeExtrudeMesh")],
    )
    assert solve_minimal_profile([g_host]) == "blender-geometry"


def test_analyze_profile_ascent_barriers(schema):
    """Verify detailed profile ascent analysis with barrier identification."""
    src = """
geometry graph wavy_mesh(size: Float = 2.0) -> Geometry {
  m = MeshGrid(size_x: size, size_y: size)
  return SetPosition(m.mesh, position: Position())
}
"""
    ast = parse(src, "wavy_mesh.bn")
    analysis = analyze_profile_ascent(ast)

    assert analysis["minimal_profile"] == "vector2d"
    assert "core" in analysis["barriers"]
    assert "sdf2d" in analysis["barriers"]
    assert "vector2d" not in analysis["barriers"]

    # Barrier reasons for core contain Geometry and MeshGrid
    core_barriers = " ".join(analysis["barriers"]["core"])
    assert "Geometry" in core_barriers or "MeshGrid" in core_barriers

    # Tested contains entries for all 5 profiles in chain
    assert set(analysis["tested"].keys()) == {"core", "sdf2d", "vector2d", "ink2d", "blender-geometry"}
    assert analysis["tested"]["vector2d"] == []
    assert analysis["tested"]["ink2d"] == []
    assert analysis["tested"]["blender-geometry"] == []

