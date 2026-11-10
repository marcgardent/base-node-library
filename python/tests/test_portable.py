"""Tests for the portable .bn subset (base_node.portable)."""

import pytest

from base_node import compile_source
from base_node.ir import Graph, Node
from base_node.portable import (
    CANONICAL_PORTABLE_NODES,
    PORTABLE_ALIASES,
    PORTABLE_BL_IDNAMES,
    PORTABLE_IMPLICIT,
    PORTABLE_TYPES,
    check_portable,
    dump_portable_schema,
)


def test_portable_types_and_implicits():
    """Vérifie l'ensemble canonique des types et entrées implicites portables."""
    assert PORTABLE_TYPES == (
        "Float",
        "Int",
        "Bool",
        "Vector",
        "Color",
        "Rotation",
        "Matrix",
        "String",
        "Menu",
        "Geometry",
        "Image",
        "Material",
    )
    assert PORTABLE_IMPLICIT == ("Position", "Normal", "Index", "ID")
    assert PORTABLE_ALIASES["WhiteNoise"] == "TexWhiteNoise"
    assert PORTABLE_ALIASES["TransformGeometry"] == "Transform"
    assert PORTABLE_ALIASES["CurveCircle"] == "CurvePrimitiveCircle"
    assert PORTABLE_ALIASES["CurveQuadrilateral"] == "CurvePrimitiveQuadrilateral"
    assert PORTABLE_ALIASES["CurveLine"] == "CurvePrimitiveLine"
    assert PORTABLE_ALIASES["BoundingBox"] == "BoundBox"


def test_dump_portable_schema_with_fake_schema(schema):
    """Vérifie l'extraction du schéma portable avec le schéma factice de test."""
    doc = dump_portable_schema(schema)
    assert doc["version"] == 1
    assert doc["types"] == list(PORTABLE_TYPES)
    assert doc["implicit"] == list(PORTABLE_IMPLICIT)
    assert doc["aliases"] == dict(PORTABLE_ALIASES)
    assert "nodes" in doc

    # Accès direct via PortableSchema et accès imbriqué via .nodes
    assert "Math" in doc
    assert "Math" in doc.nodes
    math_node = doc["Math"]
    assert math_node["bl_idname"] == "ShaderNodeMath"
    assert "operation" in math_node["props"]
    assert [s["name"] for s in math_node["inputs"]] == ["Value", "Value"]
    assert [s["name"] for s in math_node["outputs"]] == ["Value"]

    # Compare
    assert "Compare" in doc
    compare_node = doc["Compare"]
    assert compare_node["bl_idname"] == "FunctionNodeCompare"
    assert [s["name"] for s in compare_node["outputs"]] == ["Result"]


def test_check_portable_valid_compiled_graph(schema):
    """Un graphe valide compilé depuis .bn doit passer check_portable sans erreur."""
    src = """
geometry graph f(g: Geometry, t: Float = 0.5 in 0.0..1.0, p: Vector = Position()) -> Geometry {
  h = t * 2.0
  q = p + CombineXYZ(0.0, h, 0.0)
  return SetPosition(g, position: q)
}
"""
    graphs = compile_source(src, schema, "test.bn")
    errors = check_portable(graphs)
    assert errors == []


def test_check_portable_repeat_zone(schema):
    """Les zones repeat sont supportées dans le socle portable."""
    src = """
geometry graph boucle(x: Float) -> Float {
  r = repeat(10, val: x) {
    return (val: val * 1.5)
  }
  return r.val
}
"""
    graphs = compile_source(src, schema, "test.bn")
    errors = check_portable(graphs)
    assert errors == []


def test_check_portable_rejects_non_portable_type():
    """Un type d'interface non portable (ex. Shader ou Object) est rejeté."""
    g = Graph(
        kind="geometry",
        name="test_obj",
        inputs=[("obj", "Object")],
        outputs=[("geo", "Geometry")],
        nodes=[],
    )
    errors = check_portable([g])
    assert any("entrée 'obj' de type non portable 'Object'" in e for e in errors)

    g2 = Graph(
        kind="geometry",
        name="test_shader",
        inputs=[("geo", "Geometry")],
        outputs=[("sh", "Shader")],
        nodes=[],
    )
    errors2 = check_portable([g2])
    assert any("sortie 'sh' de type non portable 'Shader'" in e for e in errors2)


def test_check_portable_rejects_non_portable_kind():
    """Un genre d'arbre non portable (ex. shader ou compositor) est rejeté."""
    g = Graph(
        kind="shader",
        name="mon_shader",
        inputs=[],
        outputs=[],
        nodes=[],
    )
    errors = check_portable([g])
    assert any("type d'arbre 'shader' non portable" in e for e in errors)


def test_check_portable_rejects_non_portable_implicit():
    """Une entrée implicite non portable (ex. SelfObject) est rejetée."""
    g = Graph(
        kind="geometry",
        name="test_self",
        inputs=[("s", "Object")],
        outputs=[],
        nodes=[],
        defaults={"s": {"implicit": "SELF_OBJECT"}},
    )
    errors = check_portable([g])
    assert any("entrée implicite 'SELF_OBJECT'" in e for e in errors)


def test_check_portable_rejects_non_portable_node():
    """Un nœud 3D ou shader hors du socle portable est rejeté."""
    # SubdivideMesh n'est pas dans le socle commun 2D
    g = Graph(
        kind="geometry",
        name="test_node",
        inputs=[],
        outputs=[],
        nodes=[
            Node(id="n1", bl_idname="GeometryNodeSubdivideMesh"),
        ],
    )
    errors = check_portable([g])
    assert any("GeometryNodeSubdivideMesh" in e for e in errors)


def test_check_portable_rejects_simulation_zone():
    """Simulation zones are not part of the portable 2D subset."""
    g = Graph(
        kind="geometry",
        name="test_sim",
        inputs=[],
        outputs=[],
        nodes=[
            Node(id="n1", bl_idname="GeometryNodeSimulationInput"),
            Node(id="n2", bl_idname="GeometryNodeSimulationOutput"),
        ],
    )
    errors = check_portable([g])
    assert any("GeometryNodeSimulationInput" in e for e in errors)
    assert any("GeometryNodeSimulationOutput" in e for e in errors)


def test_check_portable_rejects_non_portable_item_type():
    """Un item de nœud portant un type non portable est rejeté."""
    g = Graph(
        kind="geometry",
        name="test_items",
        inputs=[],
        outputs=[],
        nodes=[
            Node(
                id="n1",
                bl_idname="GeometryNodeCaptureAttribute",
                items=[("col", "Object")],
            ),
        ],
    )
    errors = check_portable([g])
    assert any("type non portable 'Object'" in e for e in errors)
