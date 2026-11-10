"""Profils de compatibilité déclaratifs pour Base Node (.bn).

Gère le chargement hiérarchique (extends) des profils dans profiles/<name>.json
et la validation syntaxique et sémantique de graphes compilés ou AST
(check_profile).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Identifiants internes d'entrées implicites dans Blender Geometry Nodes
IMPLICIT_MAP = {
    "Position": {"Position", "POSITION"},
    "Normal": {"Normal", "NORMAL"},
    "Index": {"Index", "INDEX"},
    "ID": {"ID", "ID_OR_INDEX"},
}

CANONICAL_TO_BL_IDNAME: dict[str, str] = {
    "BooleanMath": "FunctionNodeBooleanMath",
    "BoundBox": "GeometryNodeBoundBox",
    "BoundingBox": "GeometryNodeBoundBox",
    "CaptureAttribute": "GeometryNodeCaptureAttribute",
    "Clamp": "ShaderNodeClamp",
    "CombineXYZ": "ShaderNodeCombineXYZ",
    "Compare": "FunctionNodeCompare",
    "CurveCircle": "GeometryNodeCurvePrimitiveCircle",
    "CurveLine": "GeometryNodeCurvePrimitiveLine",
    "CurvePrimitiveCircle": "GeometryNodeCurvePrimitiveCircle",
    "CurvePrimitiveLine": "GeometryNodeCurvePrimitiveLine",
    "CurvePrimitiveQuadrilateral": "GeometryNodeCurvePrimitiveQuadrilateral",
    "CurveQuadrilateral": "GeometryNodeCurvePrimitiveQuadrilateral",
    "CurveSpiral": "GeometryNodeCurveSpiral",
    "CurveStar": "GeometryNodeCurveStar",
    "CurveToMesh": "GeometryNodeCurveToMesh",
    "FillCurve": "GeometryNodeFillCurve",
    "FilletCurve": "GeometryNodeFilletCurve",
    "ID": "GeometryNodeInputID",
    "Index": "GeometryNodeInputIndex",
    "IndexSwitch": "GeometryNodeIndexSwitch",
    "InstanceOnPoints": "GeometryNodeInstanceOnPoints",
    "JoinGeometry": "GeometryNodeJoinGeometry",
    "MapRange": "ShaderNodeMapRange",
    "Math": "ShaderNodeMath",
    "MenuSwitch": "GeometryNodeMenuSwitch",
    "MergeByDistance": "GeometryNodeMergeByDistance",
    "MeshCircle": "GeometryNodeMeshCircle",
    "MeshGrid": "GeometryNodeMeshGrid",
    "MeshLine": "GeometryNodeMeshLine",
    "Mix": "ShaderNodeMix",
    "NamedAttribute": "GeometryNodeInputNamedAttribute",
    "Normal": "GeometryNodeInputNormal",
    "Points": "GeometryNodePoints",
    "Position": "GeometryNodeInputPosition",
    "Radius": "GeometryNodeInputRadius",
    "RandomValue": "FunctionNodeRandomValue",
    "RealizeInstances": "GeometryNodeRealizeInstances",
    "ResampleCurve": "GeometryNodeResampleCurve",
    "ReverseCurve": "GeometryNodeReverseCurve",
    "SampleIndex": "GeometryNodeSampleIndex",
    "SeparateXYZ": "ShaderNodeSeparateXYZ",
    "SetCurveRadius": "GeometryNodeSetCurveRadius",
    "SetMaterial": "GeometryNodeSetMaterial",
    "SetPosition": "GeometryNodeSetPosition",
    "SplineParameter": "GeometryNodeSplineParameter",
    "StoreNamedAttribute": "GeometryNodeStoreNamedAttribute",
    "SubdivideCurve": "GeometryNodeSubdivideCurve",
    "Switch": "GeometryNodeSwitch",
    "Tangent": "GeometryNodeInputTangent",
    "TexNoise": "ShaderNodeTexNoise",
    "TexWhiteNoise": "ShaderNodeTexWhiteNoise",
    "Transform": "GeometryNodeTransform",
    "TransformGeometry": "GeometryNodeTransform",
    "Triangulate": "GeometryNodeTriangulate",
    "TrimCurve": "GeometryNodeTrimCurve",
    "VectorMath": "ShaderNodeVectorMath",
    "VectorRotate": "ShaderNodeVectorRotate",
    "WhiteNoise": "ShaderNodeTexWhiteNoise",
}

ZONE_BL_IDNAMES: dict[str, set[str]] = {
    "repeat": {"GeometryNodeRepeatInput", "GeometryNodeRepeatOutput"},
    "foreach": {"GeometryNodeForeachGeometryElementInput", "GeometryNodeForeachGeometryElementOutput"},
    "simulate": {"GeometryNodeSimulationInput", "GeometryNodeSimulationOutput"},
    "closure": {"GeometryNodeClosureInput", "GeometryNodeClosureOutput"},
}

PLUMBING_BL_IDNAMES: set[str] = {
    "NodeGroupInput",
    "NodeGroupOutput",
    "GeometryNodeGroup",
    "group_input",
    "group_output",
    "NodeFrame",
    "NodeReroute",
}

# Profils intégrés par défaut (fallback si fichiers non accessibles)
BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "core": {
        "name": "core",
        "version": 1,
        "description": "Profil mathématique et logique pur, universellement portable",
        "extends": None,
        "kinds": ["geometry", "vector", "pixel"],
        "types": [
            "Float", "Int", "Bool", "Vector", "Color", "Rotation", "Matrix", "String", "Menu"
        ],
        "implicit": ["Position", "Normal", "Index", "ID"],
        "aliases": {
            "WhiteNoise": "TexWhiteNoise",
            "TransformGeometry": "Transform",
            "CurveCircle": "CurvePrimitiveCircle",
            "CurveQuadrilateral": "CurvePrimitiveQuadrilateral",
            "CurveLine": "CurvePrimitiveLine",
            "BoundingBox": "BoundBox",
        },
        "zones": ["repeat"],
        "nodes": [
            "Math", "VectorMath", "Compare", "BooleanMath", "Switch", "Mix",
            "MapRange", "Clamp", "CombineXYZ", "SeparateXYZ", "TexNoise",
            "WhiteNoise", "RandomValue", "VectorRotate"
        ],
    },
    "sdf2d": {
        "name": "sdf2d",
        "version": 1,
        "description": "Profil 2D champs de distance signée (SDF)",
        "extends": "core",
        "implicit": ["Position", "Normal", "Index", "ID"],
        "nodes": ["Position", "Normal", "Index", "ID"],
    },
    "vector2d": {
        "name": "vector2d",
        "version": 1,
        "description": "Profil 2D vectoriel (courbes, maillages 2D, semis de points, attributs)",
        "extends": "sdf2d",
        "types": ["Geometry", "Material"],
        "zones": ["foreach"],
        "nodes": [
            "CurveCircle", "CurveQuadrilateral", "CurveStar", "CurveLine", "CurveSpiral",
            "ResampleCurve", "TrimCurve", "SubdivideCurve", "ReverseCurve", "FillCurve",
            "FilletCurve", "SetCurveRadius", "CurveToMesh", "SplineParameter", "Tangent",
            "Radius", "MeshGrid", "MeshCircle", "MeshLine", "Points", "Triangulate",
            "SetPosition", "TransformGeometry", "JoinGeometry", "InstanceOnPoints",
            "RealizeInstances", "MergeByDistance", "BoundingBox", "SampleIndex",
            "CaptureAttribute", "StoreNamedAttribute", "NamedAttribute",
            "IndexSwitch", "MenuSwitch", "SetMaterial"
        ],
    },
    "raster2d": {
        "name": "raster2d",
        "version": 1,
        "description": "Profil 2D matriciel / image",
        "extends": "sdf2d",
        "types": ["Image"],
        "nodes": [
            "Flatten", "Classifier", "ClassColors", "SeparateColor", "CombineColor",
            "SetPixel", "Blur", "Blend", "Vectorize", "Rasterize"
        ],
    },
    "blender-geometry": {
        "name": "blender-geometry",
        "version": 1,
        "description": "Profil hôte complet Blender Geometry Nodes (5.2+ / 5.3+)",
        "extends": "vector2d",
        "allow_all_blender_nodes": True,
        "zones": ["simulate", "closure"],
        "types": ["Bundle", "Closure", "Object", "Collection", "Texture"],
    },
}


def _find_profile_file(name: str) -> Path | None:
    """Cherche le fichier JSON correspondant au profil spécifié."""
    # Chemin direct
    p = Path(name)
    if p.is_file():
        return p
    if not name.endswith(".json"):
        p_json = Path(f"{name}.json")
        if p_json.is_file():
            return p_json

    # Recherche dans les dossiers de profils usuels
    candidates = [
        Path.cwd() / "profiles" / f"{name}.json",
        Path(__file__).resolve().parents[2] / "profiles" / f"{name}.json",
        Path(__file__).resolve().parent / "profiles" / f"{name}.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_profile(name: str) -> dict[str, Any]:
    """Charge un profil de compatibilité en résolvant la chaîne d'héritage `extends`."""
    base_name = name[:-5] if name.endswith(".json") else name

    profile_file = _find_profile_file(name)
    if profile_file is not None:
        data = json.loads(profile_file.read_text(encoding="utf-8"))
    elif base_name in BUILTIN_PROFILES:
        data = dict(BUILTIN_PROFILES[base_name])
    else:
        raise ValueError(f"Profil inconnu : '{name}'")

    parent_name = data.get("extends")
    if parent_name:
        parent = load_profile(parent_name)
        # Fusion récursive
        resolved: dict[str, Any] = {
            "name": data.get("name", base_name),
            "version": data.get("version", parent.get("version", 1)),
            "description": data.get("description", parent.get("description", "")),
            "extends": parent_name,
            "kinds": list(dict.fromkeys(parent.get("kinds", []) + data.get("kinds", []))),
            "types": list(dict.fromkeys(parent.get("types", []) + data.get("types", []))),
            "implicit": list(dict.fromkeys(parent.get("implicit", []) + data.get("implicit", []))),
            "aliases": {**parent.get("aliases", {}), **data.get("aliases", {})},
            "zones": list(dict.fromkeys(parent.get("zones", []) + data.get("zones", []))),
            "nodes": list(dict.fromkeys(parent.get("nodes", []) + data.get("nodes", []))),
            "allow_all_blender_nodes": data.get(
                "allow_all_blender_nodes", parent.get("allow_all_blender_nodes", False)
            ),
        }
    else:
        resolved = {
            "name": data.get("name", base_name),
            "version": data.get("version", 1),
            "description": data.get("description", ""),
            "extends": None,
            "kinds": list(data.get("kinds", ["geometry", "vector", "pixel"])),
            "types": list(data.get("types", [])),
            "implicit": list(data.get("implicit", [])),
            "aliases": dict(data.get("aliases", {})),
            "zones": list(data.get("zones", [])),
            "nodes": list(data.get("nodes", [])),
            "allow_all_blender_nodes": bool(data.get("allow_all_blender_nodes", False)),
        }

    # Calcul des bl_idnames autorisés
    allowed_bl_ids: set[str] = set(PLUMBING_BL_IDNAMES)
    for z in resolved.get("zones", []):
        if z in ZONE_BL_IDNAMES:
            allowed_bl_ids.update(ZONE_BL_IDNAMES[z])

    aliases = resolved.get("aliases", {})
    for node_name in resolved.get("nodes", []):
        if node_name in CANONICAL_TO_BL_IDNAME:
            allowed_bl_ids.add(CANONICAL_TO_BL_IDNAME[node_name])
        elif node_name in aliases and aliases[node_name] in CANONICAL_TO_BL_IDNAME:
            allowed_bl_ids.add(CANONICAL_TO_BL_IDNAME[aliases[node_name]])
        else:
            allowed_bl_ids.add(node_name)

    resolved["_allowed_bl_idnames"] = allowed_bl_ids

    # Calcul des identifiants implicites autorisés
    allowed_impls: set[str] = set()
    for imp in resolved.get("implicit", []):
        if imp in IMPLICIT_MAP:
            allowed_impls.update(IMPLICIT_MAP[imp])
        else:
            allowed_impls.add(imp)
    resolved["_allowed_implicits"] = allowed_impls

    return resolved


def check_profile(graphs: Any, profile: str | dict[str, Any] = "vector2d") -> list[str]:
    """Vérifie qu'une liste de graphes (IR ou AST) respecte les contraintes du profil.

    Retourne [] si tous les graphes sont conformes, sinon la liste des messages d'erreur.
    """
    if isinstance(profile, str):
        prof = load_profile(profile)
    else:
        prof = profile
        if "_allowed_bl_idnames" not in prof:
            prof = load_profile(prof.get("name", "core"))

    errors: list[str] = []
    if not isinstance(graphs, (list, tuple)):
        graphs = [graphs]

    allowed_kinds = set(prof.get("kinds", ["geometry", "vector", "pixel"]))
    allowed_types = set(prof.get("types", []))
    allowed_implicits = prof.get("_allowed_implicits", set())
    allowed_bl_idnames = prof.get("_allowed_bl_idnames", set())
    allow_all = prof.get("allow_all_blender_nodes", False)

    for g in graphs:
        # Vérification du type d'arbre
        if g.kind not in allowed_kinds:
            errors.append(
                f"Graphe '{g.name}' : type d'arbre '{g.kind}' non autorisé par le profil '{prof['name']}' (attendu {sorted(allowed_kinds)})"
            )

        # Vérification des entrées / sorties de l'interface
        # Compatible IR (g.inputs: list[tuple[name, type]]) et AST (g.params: list[Param])
        inputs = g.inputs if hasattr(g, "inputs") else [(p.name, p.type) for p in getattr(g, "params", [])]
        outputs = g.outputs if hasattr(g, "outputs") else [(r.name, r.type) for r in getattr(g, "outputs", [])]

        for name, typ in inputs:
            if typ not in allowed_types:
                errors.append(
                    f"Graphe '{g.name}' : entrée '{name}' de type '{typ}' non autorisé par le profil '{prof['name']}'"
                )
        for name, typ in outputs:
            if typ not in allowed_types:
                errors.append(
                    f"Graphe '{g.name}' : sortie '{name}' de type '{typ}' non autorisé par le profil '{prof['name']}'"
                )

        # Vérification des entrées implicites
        defaults = getattr(g, "defaults", {})
        for param, defs in defaults.items():
            if isinstance(defs, dict) and "implicit" in defs:
                impl = defs["implicit"]
                if impl not in allowed_implicits:
                    errors.append(
                        f"Graphe '{g.name}' : entrée implicite '{impl}' pour '{param}' non autorisée par le profil '{prof['name']}'"
                    )

        # Vérification des nœuds (IR)
        if hasattr(g, "nodes") and not allow_all:
            for node in g.nodes:
                bl_id = getattr(node, "bl_idname", "")
                node_name = getattr(node, "name", "") or bl_id
                if bl_id not in allowed_bl_idnames and node_name not in allowed_bl_idnames:
                    errors.append(
                        f"Graphe '{g.name}' : nœud '{node_name}' (bl_idname '{bl_id}') hors du profil '{prof['name']}'"
                    )

                # Vérification des types des items internes
                for item_name, item_type in getattr(node, "items", ()) or ():
                    if item_type not in allowed_types:
                        errors.append(
                            f"Graphe '{g.name}' : item '{item_name}' du nœud '{bl_id}' de type non autorisé '{item_type}'"
                        )
                for item_name, item_type in getattr(node, "out_items", ()) or ():
                    if item_type not in allowed_types:
                        errors.append(
                            f"Graphe '{g.name}' : sortie d'item '{item_name}' du nœud '{bl_id}' de type non autorisé '{item_type}'"
                        )

    return errors
