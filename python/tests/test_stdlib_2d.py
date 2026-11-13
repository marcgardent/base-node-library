"""Tests for the 2D standard library modules: planar2d, fillet2d, hachures2d, deform2d."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from base_node import (
    analyze_profile_ascent,
    check_profile,
    format_source,
    parse,
    solve_minimal_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STDLIB_DIR = REPO_ROOT / "stdlib"
MANIFEST_PATH = STDLIB_DIR / "manifest.json"


def test_2d_modules_manifest_registration():
    """Verify planar2d, fillet2d, hachures2d, deform2d are declared in manifest.json."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    modules = manifest["modules"]

    expected_2d = ["planar2d", "fillet2d", "hachures2d", "deform2d"]
    for mod_name in expected_2d:
        assert mod_name in modules, f"Module {mod_name} must be in stdlib manifest"
        entry = modules[mod_name]
        assert entry["name"] == mod_name
        assert entry["profile"] == "vector2d"
        assert entry["version"] == "0.8.2"
        assert entry["edition"] == "2026"
        assert (STDLIB_DIR / entry["file"]).exists()


@pytest.mark.parametrize("mod_name", ["planar2d", "fillet2d", "hachures2d", "deform2d"])
def test_2d_modules_parse_and_profile_ascent(mod_name):
    """Verify each 2D module parses, validates under vector2d, and solves to minimal profile vector2d."""
    file_path = STDLIB_DIR / f"{mod_name}.bn"
    text = file_path.read_text(encoding="utf-8")

    ast = parse(text, file_path.name)
    assert len(ast.graphs) == 4, f"{mod_name} must contain exactly 4 canonical graphs"

    # Profile check under vector2d
    errors = check_profile(ast, "vector2d")
    assert errors == [], f"Module {mod_name} profile check failed: {errors}"

    # Minimal profile solver
    min_profile = solve_minimal_profile(ast)
    assert min_profile == "vector2d", f"{mod_name} minimal profile should be vector2d, got {min_profile}"

    # Ascent analysis check
    ascent = analyze_profile_ascent(ast)
    assert ascent["minimal_profile"] == "vector2d"
    assert "core" in ascent["barriers"]
    assert "sdf2d" in ascent["barriers"]


def test_planar2d_graphs_signatures():
    """Verify graph signatures in planar2d.bn."""
    ast = parse((STDLIB_DIR / "planar2d.bn").read_text(encoding="utf-8"), "planar2d.bn")
    names = [g.name for g in ast.graphs]
    assert names == [
        "planar faces",
        "planar split intersections",
        "shape builder pick",
        "contour outer boundary",
    ]

    # Verify planar faces takes curves: Geometry and returns Geometry
    g_faces = ast.graphs[0]
    assert [p.name for p in g_faces.params] == ["curves", "tolerance"]
    assert len(g_faces.outputs) == 1
    assert g_faces.outputs[0].type == "Geometry"


def test_fillet2d_graphs_signatures():
    """Verify graph signatures in fillet2d.bn."""
    ast = parse((STDLIB_DIR / "fillet2d.bn").read_text(encoding="utf-8"), "fillet2d.bn")
    names = [g.name for g in ast.graphs]
    assert names == [
        "fillet corner",
        "fillet polygon",
        "chamfer polygon",
        "fillet bezier handles",
    ]

    # Verify fillet corner returns (p1: Vector, p2: Vector, center: Vector)
    g_corner = ast.graphs[0]
    ret_types = [(p.name, p.type) for p in g_corner.outputs]
    assert ret_types == [("p1", "Vector"), ("p2", "Vector"), ("center", "Vector")]


def test_hachures2d_graphs_signatures():
    """Verify graph signatures in hachures2d.bn."""
    ast = parse((STDLIB_DIR / "hachures2d.bn").read_text(encoding="utf-8"), "hachures2d.bn")
    names = [g.name for g in ast.graphs]
    assert names == [
        "hatch cross",
        "guilloche",
        "halftone dots",
        "lehmann hachures",
    ]

    # Verify guilloche returns Vector
    g_guilloche = ast.graphs[1]
    assert len(g_guilloche.outputs) == 1
    assert g_guilloche.outputs[0].type == "Vector"

    # Verify lehmann hachures returns Geometry
    g_lehmann = ast.graphs[3]
    assert len(g_lehmann.outputs) == 1
    assert g_lehmann.outputs[0].type == "Geometry"


def test_deform2d_graphs_signatures():
    """Verify graph signatures in deform2d.bn."""
    ast = parse((STDLIB_DIR / "deform2d.bn").read_text(encoding="utf-8"), "deform2d.bn")
    names = [g.name for g in ast.graphs]
    assert names == [
        "frenet frame 2d",
        "flow along curve",
        "ribbon outline",
        "arrow head",
    ]

    # Verify frenet frame 2d returns (pos, tangent, normal)
    g_frenet = ast.graphs[0]
    ret_types = [(p.name, p.type) for p in g_frenet.outputs]
    assert ret_types == [("pos", "Vector"), ("tangent", "Vector"), ("normal", "Vector")]


def test_cross_module_2d_pipeline():
    """Verify an end-to-end composite pipeline importing and calling all 4 2D modules."""
    src = """// @module pipeline2d
// @version 0.8.2
// @profile vector2d
// @edition 2026

use planar2d as p2d
use fillet2d as f2d
use hachures2d as h2d
use deform2d as d2d

geometry graph "artistic 2d pipeline"(
    spine: Geometry,
    pattern: Geometry,
    fillet_r: Float = 0.15 in 0.0..1.0
) -> (Output: Geometry, FramePos: Vector) {
  "Composite 2D procedural design using planar, fillet, hachures, and curve deformations"
  // 1. Deform pattern along spine
  flowed = d2d::"flow along curve"(pattern, spine, width_scale: 1.2)
  
  // 2. Round sharp corners with fillet
  filleted = f2d::"fillet polygon"(flowed, radius: fillet_r, segments: 4)
  
  // 3. Planar partitioning
  faces = p2d::"planar faces"(filleted, tolerance: 0.001)
  
  // 4. Sample moving frame along spine
  frame = d2d::"frenet frame 2d"(spine, factor: 0.5)
  
  // 5. Lehmann hachure annotation at midpoint
  hachure = h2d::"lehmann hachures"(frame.tangent, slope: 0.6, length: 0.3)
  
  combined = faces + hachure
  return (Output: combined, FramePos: frame.pos)
}
"""
    ast = parse(src, "pipeline2d.bn")
    assert len(ast.graphs) == 1
    assert check_profile(ast, "vector2d") == []
    assert solve_minimal_profile(ast) == "vector2d"
